"""
Speech-to-Text module.
Primary: Sarvam AI SDK (saaras:v3) for Indian language accuracy.
Fallback: OpenAI Whisper (local model).
"""
import os
import logging
from typing import Optional, Tuple

from config import settings

logger = logging.getLogger(__name__)

# Language code mapping
LANGUAGE_MAP = {
    "Hindi": "hi-IN",
    "Tamil": "ta-IN",
}


def transcribe_sarvam(file_path: str, language: Optional[str] = None) -> Tuple[str, str]:
    """
    Transcribe audio using Sarvam AI SDK.
    Returns (transcript, detected_language).
    Raises Exception on failure.
    """
    if not settings.SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not configured")

    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)

    lang_code = LANGUAGE_MAP.get(language) if language else None

    with open(file_path, "rb") as audio_file:
        kwargs = {
            "file": audio_file,
            "model": "saaras:v3",
            "mode": "codemix",  # Best for Hinglish/Tanglish mixed-language speech
        }
        if lang_code:
            kwargs["language_code"] = lang_code

        response = client.speech_to_text.transcribe(**kwargs)

    # Extract transcript from response
    transcript = ""
    detected_lang = language or "Hindi"

    if hasattr(response, "transcript"):
        transcript = response.transcript
    elif isinstance(response, dict):
        transcript = response.get("transcript", "")
    else:
        transcript = str(response)

    # Try to detect language from response metadata
    if hasattr(response, "language_code"):
        lc = response.language_code
        if lc and "ta" in lc.lower():
            detected_lang = "Tamil"
        else:
            detected_lang = "Hindi"
    elif isinstance(response, dict) and "language_code" in response:
        lc = response["language_code"]
        if lc and "ta" in lc.lower():
            detected_lang = "Tamil"
        else:
            detected_lang = "Hindi"

    if not transcript or not transcript.strip():
        raise ValueError("Sarvam returned empty transcript")

    return transcript.strip(), detected_lang


def transcribe_whisper(file_path: str, language: Optional[str] = None) -> Tuple[str, str]:
    """
    Fallback transcription using OpenAI Whisper (local model).
    Returns (transcript, detected_language).
    """
    import whisper

    model = whisper.load_model("base")

    whisper_lang = None
    if language == "Hindi":
        whisper_lang = "hi"
    elif language == "Tamil":
        whisper_lang = "ta"

    options = {}
    if whisper_lang:
        options["language"] = whisper_lang

    result = model.transcribe(file_path, **options)

    transcript = result.get("text", "").strip()
    detected = result.get("language", "hi")

    if detected and "ta" in detected:
        detected_lang = "Tamil"
    else:
        detected_lang = "Hindi"

    if not transcript:
        raise ValueError("Whisper returned empty transcript")

    return transcript, detected_lang


def transcribe(file_path: str, language: Optional[str] = None) -> Tuple[str, str]:
    """
    Main transcription entry point.
    Tries Sarvam AI first, falls back to Whisper on failure.
    Returns (transcript, detected_language).
    """
    # Try Sarvam AI first
    try:
        logger.info(f"Attempting Sarvam AI transcription for {os.path.basename(file_path)}")
        transcript, lang = transcribe_sarvam(file_path, language)
        logger.info(f"Sarvam AI transcription successful — {len(transcript)} chars, language: {lang}")
        return transcript, lang
    except Exception as e:
        logger.warning(f"Sarvam AI failed: {e}. Falling back to Whisper.")

    # Fallback to Whisper
    try:
        logger.info(f"Attempting Whisper transcription for {os.path.basename(file_path)}")
        transcript, lang = transcribe_whisper(file_path, language)
        logger.info(f"Whisper transcription successful — {len(transcript)} chars, language: {lang}")
        return transcript, lang
    except Exception as e:
        logger.error(f"Whisper also failed: {e}")
        raise RuntimeError(f"All STT engines failed. Sarvam error, Whisper error: {e}")
