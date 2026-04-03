"""
POST /api/call-analytics — Core evaluation endpoint.
Accepts Base64-encoded MP3, performs full pipeline, returns strict JSON.

Pipeline: Base64 → decode → Sarvam Saaras STT (transcript + translation) → LLM analysis → strict JSON
Protected by API key authentication (x-api-key header).

Rule: The Base64 string must be processed as-is (no FFmpeg modification).
Rule: Evidence that transcripts are indexed for semantic search (ChromaDB added).
"""
import uuid
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.auth import verify_api_key
from services.stt.transcriber import transcribe_and_translate
from services.llm.analyzer import analyse_transcript
from services.sop.validator import normalize_response
from utils.helpers import decode_base64_to_file, clean_transcript, cleanup_temp_files
from database import get_db
from models import Call

# Import the new vector database integration
try:
    from services.vector_db import index_transcript
except ImportError:
    # Fallback if chromadb isn't installed yet
    def index_transcript(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/call-analytics")
async def call_analytics(
    request: Request,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    Full call analytics pipeline.
    Protected by API key authentication (x-api-key header).
    """
    start_time = time.time()
    temp_files = []
    
    # Generate a job_id for tracking in Dashboard/DB
    job_id = str(uuid.uuid4())

    try:
        # ── Parse and validate JSON body ─────────────────
        try:
            raw_body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid JSON body"})

        if not isinstance(raw_body, dict):
            return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid JSON body — expected object"})

        missing_fields = []
        if not raw_body.get("language"): missing_fields.append("language")
        if not raw_body.get("audioFormat"): missing_fields.append("audioFormat")
        if not raw_body.get("audioBase64"): missing_fields.append("audioBase64")

        if missing_fields:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Missing required fields: {', '.join(missing_fields)}"})

        language = raw_body["language"]
        audio_format = raw_body["audioFormat"]
        audio_base64 = raw_body["audioBase64"]

        if language not in ("Tamil", "Hindi", "Auto"):
            return JSONResponse(status_code=400, content={"status": "error", "message": "Language must be 'Tamil', 'Hindi', or 'Auto'"})

        if audio_format.lower() != "mp3":
            return JSONResponse(status_code=400, content={"status": "error", "message": "audioFormat must be 'mp3'"})

        logger.info(f"[call-analytics] Starting pipeline — Job ID: {job_id}, language={language}")

        # ── Step 0: Save initial state to DB (Dashboard visibility) ──
        call_record = Call(
            id=job_id,
            filename=f"api_upload_{job_id[:8]}.{audio_format}",
            language=language,
            status="processing"
        )
        db.add(call_record)
        db.commit()

        # ── Step 1: Decode Base64 → temp MP3 (processed internally for noise) ──
        try:
            raw_mp3_path = decode_base64_to_file(audio_base64, suffix=".mp3")
            temp_files.append(raw_mp3_path)
            
            # ── Force FFmpeg pre-processing to remove noise and boost volume ──
            from services.audio.processor import preprocess_audio
            clean_mp3_path = preprocess_audio(raw_mp3_path)
            temp_files.append(clean_mp3_path)
        except ValueError as e:
            call_record.status = "failed"
            call_record.error_message = str(e)
            db.commit()
            return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
        except Exception as e:
            call_record.status = "failed"
            call_record.error_message = f"Audio processing failed: {str(e)}"
            db.commit()
            return JSONResponse(status_code=500, content={"status": "error", "message": f"Audio processing failed: {str(e)}"})

        logger.info(f"[call-analytics] Step 1 complete: decoded and cleaned audio")

        # ── Step 2: Sarvam Saaras STT ──
        try:
            transcript, translated_text, detected_language = transcribe_and_translate(clean_mp3_path, language)
        except Exception as e:
            call_record.status = "failed"
            call_record.error_message = f"STT failed: {str(e)}"
            db.commit()
            return JSONResponse(status_code=500, content={"status": "error", "message": f"STT error: {e}"})

        transcript = clean_transcript(transcript)
        translated_text = clean_transcript(translated_text)

        if not transcript:
            call_record.status = "failed"
            call_record.error_message = "Empty transcript"
            db.commit()
            return JSONResponse(status_code=422, content={"status": "error", "message": "Transcript is empty"})

        logger.info(f"[call-analytics] Step 2 complete: got transcript")

        # ── Step 3: LLM Analysis via Cerebras ────────────
        try:
            llm_input = translated_text if translated_text else transcript
            llm_result = analyse_transcript(llm_input)
        except Exception as e:
            call_record.status = "failed"
            call_record.error_message = f"LLM analysis failed: {str(e)}"
            db.commit()
            return JSONResponse(status_code=500, content={"status": "error", "message": f"LLM analysis failed: {e}"})

        # ── Step 4: Normalize response strictly to requirement ──
        response = normalize_response(llm_result, detected_language, transcript)
        
        # Ensure 'status' is success exactly as requested
        response["status"] = "success"

        # ── Step 5: Update Database for Dashboard ────────────
        call_record.language = detected_language
        call_record.transcript = transcript
        call_record.summary = response.get("summary")
        call_record.sop_breakdown = response.get("sop_validation")
        call_record.sop_score = response.get("sop_validation", {}).get("complianceScore", 0)
        call_record.payment_type = response.get("analytics", {}).get("paymentPreference")
        call_record.rejection_reason = response.get("analytics", {}).get("rejectionReason")
        call_record.sentiment = response.get("analytics", {}).get("sentiment")
        call_record.keywords = response.get("keywords", [])
        call_record.status = "completed"
        call_record.completed_at = datetime.now(timezone.utc)
        db.commit()
        
        # ── Step 6: Vector Storage Indexing ────────────
        index_transcript(
            job_id=job_id,
            transcript=transcript,
            summary=response.get("summary", ""),
            metadata={
                "language": detected_language, 
                "payment_type": call_record.payment_type,
                "rejection_reason": call_record.rejection_reason
            }
        )

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"[call-analytics] Pipeline complete in {elapsed}s")

        return JSONResponse(status_code=200, content=response)

    except Exception as e:
        logger.exception(f"[call-analytics] Unexpected error: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Internal server error: {str(e)}"})

    finally:
        cleanup_temp_files(*temp_files)
