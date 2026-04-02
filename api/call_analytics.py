"""
POST /api/call-analytics — Core evaluation endpoint.
Accepts Base64-encoded MP3, performs full pipeline, returns strict JSON.
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.auth import verify_api_key
from services.audio.processor import preprocess_audio, split_audio_chunks
from services.stt.transcriber import transcribe_chunks
from services.llm.analyzer import analyse_transcript
from services.sop.validator import normalize_response
from utils.helpers import decode_base64_to_file, clean_transcript, cleanup_temp_files, cleanup_temp_dir

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/call-analytics")
async def call_analytics(
    request: dict,
    api_key: str = Depends(verify_api_key),
):
    """
    Full call analytics pipeline:
    Base64 audio → decode → FFmpeg preprocess → chunk → faster-whisper STT → LLM analysis → strict JSON

    Protected by API key authentication (x-api-key header).
    """
    start_time = time.time()
    temp_files = []
    temp_dirs = []

    try:
        # ── Validate request fields ──────────────────────
        if not isinstance(request, dict):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Invalid JSON body"},
            )

        language = request.get("language")
        audio_format = request.get("audioFormat")
        audio_base64 = request.get("audioBase64")

        # Check all required fields
        missing_fields = []
        if not language:
            missing_fields.append("language")
        if not audio_format:
            missing_fields.append("audioFormat")
        if not audio_base64:
            missing_fields.append("audioBase64")

        if missing_fields:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}",
                },
            )

        # Validate language
        if language not in ("Tamil", "Hindi"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Language must be 'Tamil' or 'Hindi'",
                },
            )

        # Validate audio format
        if audio_format.lower() != "mp3":
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "audioFormat must be 'mp3'",
                },
            )

        logger.info(f"[call-analytics] Starting pipeline — language={language}, base64 length={len(audio_base64)}")

        # ── Step 1: Decode Base64 → temp MP3 ─────────────
        try:
            mp3_path = decode_base64_to_file(audio_base64, suffix=".mp3")
            temp_files.append(mp3_path)
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": str(e)},
            )

        logger.info(f"[call-analytics] Step 1 complete: decoded audio to {mp3_path}")

        # ── Step 2: FFmpeg preprocess ────────────────────
        try:
            clean_wav_path = preprocess_audio(mp3_path)
            temp_files.append(clean_wav_path)
        except RuntimeError as e:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"Audio preprocessing failed: {e}"},
            )

        logger.info(f"[call-analytics] Step 2 complete: FFmpeg preprocessing done")

        # ── Step 3: Split into chunks ────────────────────
        chunk_paths = split_audio_chunks(clean_wav_path)

        # Track chunk temp dir for cleanup
        if chunk_paths and chunk_paths[0] != clean_wav_path:
            import os
            chunk_dir = os.path.dirname(chunk_paths[0])
            temp_dirs.append(chunk_dir)

        logger.info(f"[call-analytics] Step 3 complete: {len(chunk_paths)} chunks")

        # ── Step 4: Transcribe via faster-whisper ────────
        try:
            transcript, detected_lang = transcribe_chunks(chunk_paths, language)
        except ValueError as e:
            return JSONResponse(
                status_code=422,
                content={"status": "error", "message": f"Transcription failed: {e}"},
            )
        except RuntimeError as e:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"STT engine error: {e}"},
            )

        # Clean transcript
        transcript = clean_transcript(transcript)

        if not transcript:
            return JSONResponse(
                status_code=422,
                content={"status": "error", "message": "Transcript is empty after processing"},
            )

        logger.info(f"[call-analytics] Step 4 complete: transcript={len(transcript)} chars")

        # ── Step 5: LLM Analysis via Cerebras ────────────
        try:
            llm_result = analyse_transcript(transcript)
        except (ValueError, RuntimeError) as e:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"LLM analysis failed: {e}"},
            )

        logger.info(f"[call-analytics] Step 5 complete: LLM analysis done")

        # ── Step 6: Normalize to strict format ───────────
        response = normalize_response(llm_result, language, transcript)

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"[call-analytics] Pipeline complete in {elapsed}s")

        return JSONResponse(status_code=200, content=response)

    except Exception as e:
        logger.exception(f"[call-analytics] Unexpected error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error: {str(e)}"},
        )

    finally:
        # ── Cleanup temp files ───────────────────────────
        cleanup_temp_files(*temp_files)
        for d in temp_dirs:
            cleanup_temp_dir(d)
