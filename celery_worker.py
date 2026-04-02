"""
Celery worker and task definitions for async audio processing pipeline.
"""
import os
import sys
import logging
from datetime import datetime, timezone

from celery import Celery

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings

logger = logging.getLogger(__name__)

# ── Celery App ──────────────────────────────────────────
celery_app = Celery(
    "callcenter",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_call(self, job_id: str, file_path: str, language: str = None):
    """
    Full processing pipeline for an uploaded audio file.
    Steps:
      1. Update status → processing
      2. Transcribe via Sarvam AI (fallback: Whisper)
      3. Analyse transcript via Groq (summary, SOP, payment, rejection)
      4. Save results to DB
      5. Update status → completed
    Idempotent — safe to retry.
    """
    from database import SessionLocal
    from models import Call
    from stt import transcribe
    from ai_pipeline import analyse_transcript

    db = SessionLocal()
    try:
        # ── Step 1: Mark as processing ──────────────────
        call = db.query(Call).filter(Call.id == job_id).first()
        if not call:
            logger.error(f"Job {job_id} not found in database")
            return {"error": "Job not found"}

        call.status = "processing"
        db.commit()
        logger.info(f"[{job_id}] Processing started — file: {call.filename}")

        # ── Step 2: Transcribe ──────────────────────────
        try:
            transcript, detected_lang = transcribe(file_path, language)
        except Exception as e:
            logger.error(f"[{job_id}] Transcription failed: {e}")
            raise self.retry(exc=e)

        call.transcript = transcript
        call.language = detected_lang
        db.commit()
        logger.info(f"[{job_id}] Transcription complete — {len(transcript)} chars, lang: {detected_lang}")

        # ── Step 3: AI Analysis ─────────────────────────
        try:
            analysis = analyse_transcript(transcript)
        except Exception as e:
            logger.error(f"[{job_id}] AI analysis failed: {e}")
            raise self.retry(exc=e)

        # ── Step 4: Save results ────────────────────────
        call.summary = analysis["summary"]
        call.sop_score = analysis["sop_total"]
        call.sop_breakdown = analysis["sop_scores"]
        call.payment_type = analysis["payment_type"]
        call.rejection_reason = analysis["rejection_reason"]
        call.status = "completed"
        call.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"[{job_id}] Processing completed successfully — SOP: {call.sop_score}")

        return {
            "job_id": job_id,
            "status": "completed",
            "sop_score": call.sop_score,
            "payment_type": call.payment_type,
        }

    except self.MaxRetriesExceededError:
        logger.error(f"[{job_id}] Max retries exceeded — marking as failed")
        call = db.query(Call).filter(Call.id == job_id).first()
        if call:
            call.status = "failed"
            call.error_message = "Max retries exceeded — all STT/AI attempts failed"
            db.commit()
        return {"error": "Max retries exceeded"}

    except Exception as e:
        logger.error(f"[{job_id}] Unexpected error: {e}")
        call = db.query(Call).filter(Call.id == job_id).first()
        if call:
            call.status = "failed"
            call.error_message = str(e)[:500]
            db.commit()
        return {"error": str(e)}

    finally:
        db.close()
