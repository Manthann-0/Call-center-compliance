"""
Utility helpers — Base64 decoding, text cleaning, temp file management.
"""
import os
import re
import base64
import tempfile
import logging
from typing import List

logger = logging.getLogger(__name__)


def decode_base64_to_file(b64_str: str, suffix: str = ".mp3") -> str:
    """
    Decode a Base64-encoded string and write it to a temporary file.
    Returns the absolute path to the temp file.
    Raises ValueError if the Base64 string is invalid.
    """
    try:
        audio_bytes = base64.b64decode(b64_str, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid Base64 audio data: {e}")

    if len(audio_bytes) < 100:
        raise ValueError("Decoded audio data is too small — likely invalid")

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)
    except Exception:
        os.close(fd)
        raise

    logger.info(f"Decoded Base64 audio → {tmp_path} ({len(audio_bytes)} bytes)")
    return tmp_path


def clean_transcript(text: str) -> str:
    """
    Clean a raw transcript:
    - Remove noise markers like [noise], [music], (inaudible), etc.
    - Collapse multiple spaces/newlines
    - Strip leading/trailing whitespace
    """
    if not text:
        return ""

    # Remove common noise markers
    noise_patterns = [
        r"\[.*?\]",       # [noise], [music], [silence]
        r"\(.*?\)",       # (inaudible), (unclear)
        r"<.*?>",         # <unk>, <noise>
        r"\*+",           # *** or similar
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def cleanup_temp_files(*paths: str) -> None:
    """
    Safely remove temporary files. Never raises.
    """
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Cleaned up temp file: {path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {path}: {e}")


def cleanup_temp_dir(dir_path: str) -> None:
    """
    Safely remove a temporary directory and all contents.
    """
    if dir_path and os.path.isdir(dir_path):
        try:
            import shutil
            shutil.rmtree(dir_path, ignore_errors=True)
            logger.debug(f"Cleaned up temp dir: {dir_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up dir {dir_path}: {e}")
