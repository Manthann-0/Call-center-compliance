"""
Speech-to-Text module.
Primary: OpenAI Whisper (local model).
Fallback: Sarvam AI SDK (saaras:v3) for Indian language accuracy.
"""
import os
import logging
from typing import Optional, Tuple
from pydub import AudioSegment
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

# Language code mapping
LANGUAGE_MAP = {
    "Hindi": "hi-IN",
    "Tamil": "ta-IN",
}

# Sarvam API limits: max 5 minutes (300 seconds)
MAX_AUDIO_DURATION_SECONDS = 280  # Keep buffer


def get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds."""
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0  # Convert ms to seconds
    except Exception as e:
        logger.warning(f"Could not determine audio duration: {e}")
        return 0


def split_audio_if_needed(file_path: str) -> list:
    """
    Split audio file into chunks if it exceeds Sarvam's limit.
    Returns list of file paths (original if no split needed).
    """
    duration = get_audio_duration(file_path)
    
    if duration == 0 or duration <= MAX_AUDIO_DURATION_SECONDS:
        return [file_path]
    
    logger.info(f"Audio duration {duration}s exceeds limit. Splitting into chunks...")
    
    try:
        audio = AudioSegment.from_file(file_path)
        chunk_length_ms = MAX_AUDIO_DURATION_SECONDS * 1000
        chunks = []
        
        base_path = Path(file_path)
        base_name = base_path.stem
        base_dir = base_path.parent
        
        for i, start_ms in enumerate(range(0, len(audio), chunk_length_ms)):
            chunk = audio[start_ms:start_ms + chunk_length_ms]
            chunk_path = base_dir / f"{base_name}_chunk_{i}.wav"
            chunk.export(str(chunk_path), format="wav")
            chunks.append(str(chunk_path))
            logger.info(f"Created chunk {i+1}: {chunk_path}")
        
        return chunks
    except Exception as e:
        logger.error(f"Failed to split audio: {e}")
        return [file_path]


def transcribe_sarvam(file_path: str, language: Optional[str] = None) -> Tuple[str, str]:
    """
    Transcribe audio using Sarvam AI SDK.
    Handles long audio by splitting into chunks.
    Returns (transcript, detected_language).
    Raises Exception on failure.
    """
    if not settings.SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not configured")

    try:
        from sarvamai import SarvamAI
    except ImportError:
        raise RuntimeError("sarvamai package not installed. Run: pip install sarvamai")

    try:
        client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
    except Exception as e:
        raise RuntimeError(f"Failed to create Sarvam client: {e}")

    # Split audio if needed
    chunk_paths = split_audio_if_needed(file_path)
    
    lang_code = LANGUAGE_MAP.get(language) if language else None
    all_transcripts = []
    detected_lang = language or "Hindi"

    try:
        for i, chunk_path in enumerate(chunk_paths):
            logger.info(f"Transcribing chunk {i+1}/{len(chunk_paths)}: {os.path.basename(chunk_path)}")
            
            with open(chunk_path, "rb") as audio_file:
                kwargs = {
                    "file": audio_file,
                    "model": "saaras:v3",
                    "mode": "codemix",
                }
                if lang_code:
                    kwargs["language_code"] = lang_code

                response = client.speech_to_text.transcribe(**kwargs)
            
            # Extract transcript
            transcript = ""
            if hasattr(response, "transcript"):
                transcript = response.transcript
            elif isinstance(response, dict):
                transcript = response.get("transcript", "")
            else:
                transcript = str(response)
            
            if transcript and transcript.strip():
                all_transcripts.append(transcript.strip())
            
            # Detect language from first chunk
            if i == 0:
                if hasattr(response, "language_code"):
                    lc = response.language_code
                    detected_lang = "Tamil" if lc and "ta" in lc.lower() else "Hindi"
                elif isinstance(response, dict) and "language_code" in response:
                    lc = response["language_code"]
                    detected_lang = "Tamil" if lc and "ta" in lc.lower() else "Hindi"
            
            # Clean up chunk files (except original)
            if chunk_path != file_path:
                try:
                    os.remove(chunk_path)
                except:
                    pass
    
    except FileNotFoundError:
        raise RuntimeError(f"Audio file not found: {file_path}")
    except Exception as e:
        # Clean up any remaining chunks
        for chunk_path in chunk_paths:
            if chunk_path != file_path:
                try:
                    os.remove(chunk_path)
                except:
                    pass
        raise RuntimeError(f"Sarvam API call failed: {e}")

    if not all_transcripts:
        raise ValueError("Sarvam returned empty transcript")

    # Combine all transcripts
    final_transcript = " ".join(all_transcripts)
    return final_transcript, detected_lang


def transcribe_whisper(file_path: str, language: Optional[str] = None) -> Tuple[str, str]:
    """
    Fallback transcription using OpenAI Whisper (local model).
    Returns (transcript, detected_language).
    Requires ffmpeg installed on system.
    """
    try:
        import whisper
    except ImportError:
        raise RuntimeError("Whisper not available. Install: pip install openai-whisper")

    try:
        model = whisper.load_model("base")
    except Exception as e:
        raise RuntimeError(f"Failed to load Whisper model: {e}")

    whisper_lang = None
    if language == "Hindi":
        whisper_lang = "hi"
    elif language == "Tamil":
        whisper_lang = "ta"

    options = {}
    if whisper_lang:
        options["language"] = whisper_lang

    try:
        result = model.transcribe(file_path, **options)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Install from: https://ffmpeg.org/download.html")
    except Exception as e:
        raise RuntimeError(f"Whisper transcription failed: {e}")

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
    Uses Whisper as primary, Sarvam AI as fallback.
    Returns (transcript, detected_language).
    """
    whisper_error = None
    sarvam_error = None

    # Try Whisper first
    try:
        logger.info(f"Attempting Whisper transcription for {os.path.basename(file_path)}")
        transcript, lang = transcribe_whisper(file_path, language)
        logger.info(f"Whisper transcription successful — {len(transcript)} chars, language: {lang}")
        return transcript, lang
    except Exception as e:
        whisper_error = str(e)
        logger.warning(f"Whisper failed: {e}. Falling back to Sarvam AI.")

    # Fallback to Sarvam AI
    try:
        logger.info(f"Attempting Sarvam AI transcription for {os.path.basename(file_path)}")
        transcript, lang = transcribe_sarvam(file_path, language)
        logger.info(f"Sarvam AI transcription successful — {len(transcript)} chars, language: {lang}")
        return transcript, lang
    except Exception as e:
        sarvam_error = str(e)
        logger.error(f"Sarvam AI also failed: {e}")

    # Both failed
    error_msg = f"All STT engines failed.\n"
    error_msg += f"Whisper: {whisper_error}\n"
    error_msg += f"Sarvam: {sarvam_error}\n\n"
    error_msg += "Fix: Install ffmpeg from https://ffmpeg.org/download.html"
    raise RuntimeError(error_msg)
