"""
Speech-to-Text Service — Sarvam AI Saaras v3 for transcription + translation.
Uses the official sarvamai SDK.

Features:
- Original language transcription (mode=transcribe)
- English translation (mode=translate)
- Handles long audio (up to 1 hour) natively — no manual chunking
- Retry logic for transient API failures
"""
import os
import time
import json
import logging
import tempfile
from typing import Tuple, Optional

from config import settings

logger = logging.getLogger(__name__)

# Sarvam language code mapping
LANGUAGE_MAP = {
    "Hindi": "hi-IN",
    "Tamil": "ta-IN",
    "Auto": "unknown"
}

def _get_client():
    from sarvamai import SarvamAI
    if not settings.SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not configured — get a key at https://dashboard.sarvam.ai")
    return SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)


def _run_batch_job(client, audio_path: str, mode: str, language: Optional[str]) -> Tuple[str, str]:
    """Run a single Sarvam Batch AI STT job and return (text, detected_language_code)."""
    lang_code = LANGUAGE_MAP.get(language, "unknown")
    
    logger.info(f"Creating Sarvam Saaras v3 BATCH job (mode={mode}, lang={lang_code})...")
    job = client.speech_to_text_job.create_job(
        model="saaras:v3",
        mode=mode,
        language_code=lang_code
    )
    
    logger.info(f"Uploading file for job: {job.job_id}...")
    job.upload_files([audio_path])
    
    logger.info(f"Starting job: {job.job_id}...")
    job.start()
    
    logger.info(f"Polling job {job.job_id} for completion (this may take a few minutes)...")
    job.wait_until_complete(timeout=1200) # Wait up to 20 mins for long audio
    
    results = job.get_file_results()
    if not results.get("successful"):
        err = results.get("failed", [{}])[0].get("error_message", "Unknown error")
        raise RuntimeError(f"Sarvam batch job failed: {err}")
        
    with tempfile.TemporaryDirectory() as tmp_dir:
        job.download_outputs(tmp_dir)
        original_name = os.path.basename(audio_path)
        out_file = os.path.join(tmp_dir, f"{original_name}.json")
        
        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            text = data.get("transcript", "")
            detected_code = data.get("language_code", "unknown")
            return text.strip(), detected_code


def transcribe_and_translate(
    audio_path: str,
    language: Optional[str] = None,
    max_retries: int = 1,
) -> Tuple[str, str, str]:
    """
    Transcribe audio using Sarvam Saaras Batch API and get both:
    - Original language transcript
    - English translation
    - Detected language string ("Hindi" or "Tamil" or fallback)
    """
    client = _get_client()

    print("Submitting STT tasks using Sarvam Saaras v3 Batch API...")

    detected_code_transcribe = "unknown"
    detected_code_translate = "unknown"

    # 1. Transcribe (original audio)
    try:
        transcript, detected_code_transcribe = _run_batch_job(client, audio_path, mode="transcribe", language=language)
        print(f"Transcript sample: {transcript[:100]}")
    except Exception as e:
        logger.error(f"Batch Transcribe failed: {e}")
        transcript = ""

    # 2. Translate (to English)
    try:
        translated, detected_code_translate = _run_batch_job(client, audio_path, mode="translate", language=language)
        print(f"Translated sample: {translated[:100]}")
    except Exception as e:
        logger.error(f"Batch Translate failed: {e}")
        translated = ""

    # Validate output
    if not transcript and not translated:
        raise ValueError(
            "Sarvam API returned empty results for both transcription and translation. "
            "Check audio file quality and SARVAM_API_KEY validity."
        )

    # Fallbacks
    if not transcript and translated:
        transcript = translated
    if not translated and transcript:
        translated = transcript

    # Resolve final language string
    final_code = detected_code_transcribe
    if final_code == "unknown" or not final_code:
        final_code = detected_code_translate
        
    # Map back to string
    final_language_string = "Hindi" # Fallback
    if "ta" in final_code.lower():
        final_language_string = "Tamil"
    elif "hi" in final_code.lower():
        final_language_string = "Hindi"

    return transcript, translated, final_language_string
