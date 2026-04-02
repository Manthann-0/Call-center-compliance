"""
Celery tasks — async processing pipeline for legacy upload endpoint.
Uses the new service modules for STT and LLM analysis.
"""
import os
import sys
import logging
from datetime import datetime, timezone

from celery import Celery

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    Full processing pipeline for an uploaded audio file (legacy upload flow).
    Steps:
      1. Update status → processing
      2. Preprocess audio via FFmpeg
      3. Split into chunks
      4. Transcribe via faster-whisper
      5. Analyse transcript via Cerebras LLM
      6. Normalize results
      7. Save results to DB
      8. Update status → completed
    """
    from database import SessionLocal
    from models import Call
    from services.audio.processor import preprocess_audio, split_audio_chunks
    from services.stt.transcriber import transcribe_chunks
    from services.llm.analyzer import analyse_transcript
    from services.sop.validator import normalize_response
    from utils.helpers import clean_transcript, cleanup_temp_files, cleanup_temp_dir

    db = SessionLocal()
    temp_files = []
    temp_dirs = []

    try:
        # ── Step 1: Mark as processing ──────────────────
        call = db.query(Call).filter(Call.id == job_id).first()
        if not call:
            logger.error(f"Job {job_id} not found in database")
            return {"error": "Job not found"}

        call.status = "processing"
        db.commit()
        logger.info(f"[{job_id}] Processing started — file: {call.filename}")

        # ── Step 2: Preprocess audio ────────────────────
        try:
            clean_wav_path = preprocess_audio(file_path)
            temp_files.append(clean_wav_path)
        except Exception as e:
            logger.warning(f"[{job_id}] FFmpeg preprocessing failed: {e}, using original file")
            clean_wav_path = file_path

        # ── Step 3: Split into chunks ───────────────────
        chunk_paths = split_audio_chunks(clean_wav_path)
        if chunk_paths and chunk_paths[0] != clean_wav_path:
            temp_dirs.append(os.path.dirname(chunk_paths[0]))

        # ── Step 4: Transcribe ──────────────────────────
        try:
            transcript, detected_lang = transcribe_chunks(chunk_paths, language)
            transcript = clean_transcript(transcript)
        except Exception as e:
            logger.error(f"[{job_id}] Transcription failed: {e}")
            raise self.retry(exc=e)

        if not transcript:
            raise ValueError("Empty transcript after processing")

        call.transcript = transcript
        call.language = detected_lang
        db.commit()
        logger.info(f"[{job_id}] Transcription complete — {len(transcript)} chars, lang: {detected_lang}")

        # ── Step 5: AI Analysis ─────────────────────────
        try:
            llm_result = analyse_transcript(transcript)
        except Exception as e:
            logger.error(f"[{job_id}] AI analysis failed: {e}")
            raise self.retry(exc=e)

        # ── Step 6: Normalize ───────────────────────────
        normalized = normalize_response(llm_result, detected_lang, transcript)

        # ── Step 7: Save results ────────────────────────
        call.summary = normalized["summary"]

        # Compute SOP score from sop_validation
        sop = normalized["sop_validation"]
        call.sop_score = sop["complianceScore"]
        call.sop_breakdown = sop

        call.payment_type = normalized["analytics"]["paymentPreference"]
        call.rejection_reason = normalized["analytics"]["rejectionReason"]
        call.sentiment = normalized["analytics"]["sentiment"]
        call.keywords = normalized["keywords"]
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
        cleanup_temp_files(*temp_files)
        for d in temp_dirs:
            cleanup_temp_dir(d)
        db.close()
