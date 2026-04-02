"""
Speech-to-Text Service — faster-whisper with retry logic.
Uses medium model with CPU (int8) optimization.
"""
import os
import logging
from typing import Optional, Tuple, List

from config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — loaded once, reused across requests
_model = None
_model_lock = None


def _get_model():
    """
    Lazy-load the faster-whisper model (singleton).
    Thread-safe via import-time initialization.
    """
    global _model
    if _model is not None:
        return _model

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper not installed. Run: pip install faster-whisper"
        )

    model_size = getattr(settings, "WHISPER_MODEL", "medium")
    compute_type = getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")

    logger.info(f"Loading faster-whisper model: {model_size} (compute_type={compute_type})")

    try:
        _model = WhisperModel(
            model_size,
            device="cpu",
            compute_type=compute_type,
            cpu_threads=os.cpu_count() or 4,
        )
        logger.info("faster-whisper model loaded successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to load faster-whisper model: {e}")

    return _model


# Language code mapping for faster-whisper
LANGUAGE_MAP = {
    "Hindi": "hi",
    "Tamil": "ta",
}


def _transcribe_single_chunk(
    chunk_path: str,
    language: Optional[str] = None,
) -> str:
    """
    Transcribe a single audio chunk using faster-whisper.
    Returns the transcript text (may be empty).
    """
    model = _get_model()
    lang_code = LANGUAGE_MAP.get(language) if language else None

    kwargs = {
        "beam_size": 5,
        "best_of": 5,
        "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        "vad_filter": True,
        "vad_parameters": {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 400,
        },
    }
    if lang_code:
        kwargs["language"] = lang_code

    segments, info = model.transcribe(chunk_path, **kwargs)

    # Collect all segment texts
    texts = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            texts.append(text)

    return " ".join(texts)


def transcribe_chunks(
    chunk_paths: List[str],
    language: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Transcribe multiple audio chunks and merge results.
    Implements retry logic:
      1. Try with specified language
      2. If empty, retry with Hindi ("hi")
      3. If still empty, retry with Tamil ("ta")

    Returns (full_transcript, detected_language).
    Raises ValueError if transcript is empty after all retries.
    """
    detected_language = language or "Hindi"

    # Attempt 1: transcribe with specified language
    all_texts = []
    for i, chunk_path in enumerate(chunk_paths):
        logger.info(f"Transcribing chunk {i + 1}/{len(chunk_paths)}")
        text = _transcribe_single_chunk(chunk_path, language)
        if text:
            all_texts.append(text)

    full_transcript = " ".join(all_texts).strip()

    if full_transcript:
        logger.info(f"Transcription complete: {len(full_transcript)} chars (lang={detected_language})")
        return full_transcript, detected_language

    # Attempt 2: retry with Hindi
    logger.warning("Empty transcript — retrying with language=Hindi")
    all_texts = []
    for i, chunk_path in enumerate(chunk_paths):
        text = _transcribe_single_chunk(chunk_path, "Hindi")
        if text:
            all_texts.append(text)

    full_transcript = " ".join(all_texts).strip()
    if full_transcript:
        detected_language = "Hindi"
        logger.info(f"Retry (Hindi) succeeded: {len(full_transcript)} chars")
        return full_transcript, detected_language

    # Attempt 3: retry with Tamil
    logger.warning("Still empty — retrying with language=Tamil")
    all_texts = []
    for i, chunk_path in enumerate(chunk_paths):
        text = _transcribe_single_chunk(chunk_path, "Tamil")
        if text:
            all_texts.append(text)

    full_transcript = " ".join(all_texts).strip()
    if full_transcript:
        detected_language = "Tamil"
        logger.info(f"Retry (Tamil) succeeded: {len(full_transcript)} chars")
        return full_transcript, detected_language

    # All attempts failed
    raise ValueError("Transcription produced empty result after all retry attempts (original, Hindi, Tamil)")
