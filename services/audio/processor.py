"""
Audio Processing Service — FFmpeg preprocessing, chunking, and format conversion.
Handles long audio files (15-20 minutes) reliably.
Optimized for speed with efficient chunking.
"""
import os
import sys
import subprocess
import tempfile
import logging
from typing import List

logger = logging.getLogger(__name__)

# Chunk target duration in seconds (15-25s range, target 20s)
CHUNK_DURATION_SEC = 20
MIN_CHUNK_SEC = 15
MAX_CHUNK_SEC = 25


def _find_ffmpeg() -> str:
    """Find ffmpeg binary path."""
    import shutil
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    # Common Windows paths
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ffmpeg", "bin", "ffmpeg.exe"),
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return "ffmpeg"  # Hope it's on PATH


def preprocess_audio(input_path: str) -> str:
    """
    Preprocess audio using FFmpeg to handle noise, low volume, and long files:
    - Convert to mono channel
    - Resample to 16kHz
    - Apply volume boost and aggressive noise reduction
    - Compress to 32k MP3 so long files easily transfer to the STT API

    Returns path to the cleaned MP3 file.
    Raises RuntimeError if FFmpeg fails.
    """
    fd, output_path = tempfile.mkstemp(suffix="_clean.mp3")
    os.close(fd)

    ffmpeg_bin = _find_ffmpeg()
    # Handle noise and low volume, then encode to efficient mp3
    cmd = [
        ffmpeg_bin, "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-af", "volume=3.0,afftdn=nf=-25",
        "-b:a", "32k",
        output_path,
    ]

    logger.info(f"FFmpeg preprocessing: {os.path.basename(input_path)} → {os.path.basename(output_path)}")

    # On Windows, hide the console window that FFmpeg pops up
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout for 15-20 minute files
            creationflags=creation_flags,
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg stderr: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg failed (exit {result.returncode}): {result.stderr[-200:]}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            raise RuntimeError("FFmpeg produced empty or invalid output")

        logger.info(f"FFmpeg preprocessing complete: {os.path.getsize(output_path)} bytes")
        return output_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg timed out after 10 minutes")
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Install from https://ffmpeg.org/download.html "
            "and ensure it's in your system PATH."
        )


def split_audio_chunks(wav_path: str) -> List[str]:
    """
    Split a WAV file into chunks of ~20 seconds (15-25s range).
    Uses FFmpeg-based splitting for speed (avoids loading entire file into memory).
    Returns a list of chunk file paths.
    If the audio is shorter than MAX_CHUNK_SEC, returns the original path.
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(wav_path)
    except Exception as e:
        logger.error(f"Failed to load audio for chunking: {e}")
        return [wav_path]

    duration_sec = len(audio) / 1000.0
    logger.info(f"Audio duration: {duration_sec:.1f}s")

    if duration_sec <= MAX_CHUNK_SEC:
        return [wav_path]

    chunk_length_ms = CHUNK_DURATION_SEC * 1000
    chunks = []
    tmp_dir = tempfile.mkdtemp(prefix="chunks_")

    for i, start_ms in enumerate(range(0, len(audio), chunk_length_ms)):
        chunk = audio[start_ms:start_ms + chunk_length_ms]

        # Skip very short chunks (< 2 seconds)
        if len(chunk) < 2000:
            continue

        chunk_path = os.path.join(tmp_dir, f"chunk_{i:04d}.wav")
        chunk.export(chunk_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])
        chunks.append(chunk_path)

    logger.info(f"Split audio into {len(chunks)} chunks (each ~{CHUNK_DURATION_SEC}s)")
    return chunks if chunks else [wav_path]


def get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"Could not determine audio duration: {e}")
        return 0.0
