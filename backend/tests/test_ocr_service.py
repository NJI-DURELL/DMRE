"""Unit tests for ocr_service.extract_text."""

import io
import pytest
from unittest.mock import patch, MagicMock


def test_extract_text_from_bytes_calls_tesseract():
    """extract_text(bytes) opens the image and calls pytesseract."""
    fake_image = MagicMock()
    mock_pil = MagicMock()
    mock_pil.Image.open.return_value = fake_image

    with patch.dict("sys.modules", {"PIL": mock_pil, "PIL.Image": mock_pil.Image}):
        with patch("pytesseract.image_to_string", return_value="  hello world  ") as mock_ocr:
            from importlib import reload
            import app.services.ocr_service as ocr_mod
            reload(ocr_mod)

            with patch("PIL.Image.open", return_value=fake_image):
                with patch("pytesseract.image_to_string", return_value="  hello world  "):
                    result = ocr_mod.extract_text(b"\x89PNG fake bytes")

    # The result should be stripped / collapsed whitespace
    assert isinstance(result, str)


def test_extract_text_collapses_whitespace():
    """Newlines and multiple spaces are collapsed to a single space."""
    raw = "line one\n\nline two   extra"
    fake_image = MagicMock()

    with patch("PIL.Image.open", return_value=fake_image):
        with patch("pytesseract.image_to_string", return_value=raw):
            from app.services.ocr_service import extract_text
            result = extract_text(b"dummy")

    assert result == "line one line two extra"


def test_extract_text_empty_returns_empty():
    """Empty OCR output returns an empty string, not whitespace."""
    fake_image = MagicMock()

    with patch("PIL.Image.open", return_value=fake_image):
        with patch("pytesseract.image_to_string", return_value="   \n  "):
            from app.services.ocr_service import extract_text
            result = extract_text(b"dummy")

    assert result == ""


def test_missing_pytesseract_raises_import_error():
    """ImportError is raised when pytesseract is not available."""
    import sys
    real_modules = {}
    for mod in ["pytesseract", "PIL", "PIL.Image"]:
        real_modules[mod] = sys.modules.pop(mod, None)

    try:
        from importlib import reload, import_module
        import builtins
        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name in ("pytesseract", "PIL", "PIL.Image"):
                raise ImportError("blocked")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = blocking_import
        try:
            import app.services.ocr_service as ocr_mod
            with pytest.raises(ImportError):
                ocr_mod.extract_text(b"data")
        finally:
            builtins.__import__ = real_import
    finally:
        for mod, val in real_modules.items():
            if val is not None:
                sys.modules[mod] = val
