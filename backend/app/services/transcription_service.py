# =============================================================================
# backend/app/services/transcription_service.py
# Speech-to-text service for the DMRE voice search endpoint.
# Wraps faster-whisper (a CTranslate2-based reimplementation of OpenAI Whisper)
# which is used instead of openai-whisper for Python 3.13 compatibility.
# The "base" model runs on CPU with int8 quantisation — no GPU required.
# =============================================================================

from __future__ import annotations

import tempfile
from pathlib import Path

_model = None  # lazy singleton


def _get_model():
    """Load the Whisper 'base' model on first call; cached thereafter."""
    global _model
    if _model is not None:
        return _model
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "faster-whisper is not installed. "
            "Run: pip install faster-whisper==1.0.3"
        ) from exc

    # int8 quantisation halves memory use with negligible accuracy loss on CPU.
    _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def transcribe(audio_source: str | bytes | Path) -> str:
    """
    Transcribe an audio file to text using Whisper 'base'.

    Args:
        audio_source: File path (str or Path) or raw audio bytes (WAV/MP3/etc.).
                      If bytes are provided, they are written to a temp file first.

    Returns:
        Transcribed text as a single stripped string.
    """
    model = _get_model()

    if isinstance(audio_source, bytes):
        # Write bytes to a temporary file; faster-whisper requires a file path.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_source)
            tmp_path = tmp.name
        audio_path = tmp_path
    else:
        audio_path = str(audio_source)

    segments, _info = model.transcribe(audio_path, beam_size=5)
    transcript = " ".join(segment.text for segment in segments).strip()
    return transcript
