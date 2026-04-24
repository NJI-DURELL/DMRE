# =============================================================================
# backend/app/services/ocr_service.py
# OCR service for the DMRE image search endpoint.
# Wraps PyTesseract (a Python binding for Tesseract OCR) to extract plain text
# from uploaded images; the result is fed into the same embedding pipeline as
# text and voice queries, enabling multimodal semantic search.
# =============================================================================

from __future__ import annotations

import io
import os
import re
from pathlib import Path


def _configure_tesseract():
    """Point pytesseract at the system Tesseract binary if TESSERACT_CMD is set."""
    cmd = os.environ.get("TESSERACT_CMD", "")
    if cmd:
        try:
            import pytesseract  # noqa: PLC0415
            pytesseract.pytesseract.tesseract_cmd = cmd
        except ImportError:
            pass


_configure_tesseract()


def extract_text(image_source: str | bytes | Path) -> str:
    """
    Extract visible text from an image using Tesseract OCR.

    Args:
        image_source: File path (str or Path) or raw image bytes (PNG/JPEG/etc.).

    Returns:
        Cleaned plain-text string.  Empty string if no text is detected.
    """
    try:
        import pytesseract  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "pytesseract or Pillow is not installed. "
            "Run: pip install pytesseract==0.3.10 Pillow==11.0.0"
        ) from exc

    if isinstance(image_source, bytes):
        image = Image.open(io.BytesIO(image_source))
    else:
        image = Image.open(Path(image_source))

    # page_seg_mode=3 (auto): Tesseract segments the page automatically.
    raw_text: str = pytesseract.image_to_string(image, config="--psm 3")

    # Collapse runs of whitespace (newlines, tabs, multiple spaces) to single space.
    cleaned = re.sub(r"\s+", " ", raw_text).strip()
    return cleaned
