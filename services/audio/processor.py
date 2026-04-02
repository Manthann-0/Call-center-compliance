"""
Audio Processing Service — FFmpeg preprocessing, chunking, and format conversion.
"""
import os
import subprocess
import tempfile
import logging
from typing import List
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# Chunk target duration in seconds (15-25s range, target 20s)
CHUNK_DURATION_SEC = 20
MIN_CHUNK_SEC = 15
MAX_CHUNK_SEC = 25


def preprocess_audio(input_path: str) -> str:
    """
    Preprocess audio using FFmpeg:
    - Convert to mono channel
    - Resample to 16kHz
    - Apply volume boost (2.5x) and noise reduction (afftdn)

    Returns path to the cleaned WAV file.
    Raises RuntimeError if FFmpeg fails.
    """
    fd, output_path = tempfile.mkstemp(suffix="_clean.wav")
    os.close(fd)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-af", "volume=2.5,afftdn",
        output_path,
    ]

    logger.info(f"FFmpeg preprocessing: {os.path.basename(input_path)} → {os.path.basename(output_path)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout for long files
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg stderr: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg failed (exit {result.returncode}): {result.stderr[-200:]}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            raise RuntimeError("FFmpeg produced empty or invalid output")

        logger.info(f"FFmpeg preprocessing complete: {os.path.getsize(output_path)} bytes")
        return output_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg timed out after 5 minutes")
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Install from https://ffmpeg.org/download.html "
            "and ensure it's in your system PATH."
        )


def split_audio_chunks(wav_path: str) -> List[str]:
    """
    Split a WAV file into chunks of 15-25 seconds.
    Returns a list of chunk file paths.
    If the audio is shorter than MAX_CHUNK_SEC, returns the original path.
    """
    try:
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
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"Could not determine audio duration: {e}")
        return 0.0
