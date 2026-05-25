"""Format-specific text extractors. All sync; the caller wraps in to_thread."""
from __future__ import annotations

import io
from pathlib import Path

import pypdf
import pytesseract
from docx import Document
from pdf2image import convert_from_bytes
from PIL import Image


class UnsupportedFormatError(ValueError):
    pass


def _ext_from(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")


def extract_text_from_bytes(raw: bytes, *, filename: str) -> str:
    """Dispatch by file extension. Filename's extension is the only hint —
    we never sniff content (the encrypted-at-rest path means the bytes are
    decrypted just-in-time and we trust the filename metadata)."""
    ext = _ext_from(filename)
    if ext == "txt":
        return raw.decode("utf-8", errors="replace")
    if ext == "docx":
        return _extract_docx(raw)
    if ext == "pdf":
        return _extract_pdf(raw)
    if ext in {"png", "jpg", "jpeg"}:
        return _extract_image(raw)
    raise UnsupportedFormatError(f"Unsupported format: .{ext}")


def _extract_docx(raw: bytes) -> str:
    doc = Document(io.BytesIO(raw))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_pdf(raw: bytes) -> str:
    """Try pypdf first; fall back to OCR if no text was extracted (likely an
    image-only PDF)."""
    reader = pypdf.PdfReader(io.BytesIO(raw))
    pages_text: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)
    combined = "\n".join(pages_text).strip()
    if combined:
        return combined
    # Empty -> rasterize and OCR each page.
    images = convert_from_bytes(raw, dpi=200)
    ocr_pages = [pytesseract.image_to_string(img) for img in images]
    return "\n".join(ocr_pages)


def _extract_image(raw: bytes) -> str:
    img = Image.open(io.BytesIO(raw))
    text: str = pytesseract.image_to_string(img)
    return text
