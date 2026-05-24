"""Render the authored text sources into actual .txt / .docx / .pdf / .png files.

Run: `uv run python -m tests.fixtures.build`

Outputs land under tests/fixtures/rendered/ (gitignored — regenerate on demand).
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from docx import Document
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from tests.fixtures.sources import ALL_SOURCES

OUTPUT_DIR = Path(__file__).parent / "rendered"


@dataclass(frozen=True)
class Rendered:
    name: str
    path: Path


def to_txt(text: str, dst: Path) -> Rendered:
    dst.write_text(text, encoding="utf-8")
    return Rendered(name=dst.name, path=dst)


def to_docx(text: str, dst: Path) -> Rendered:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(dst)
    return Rendered(name=dst.name, path=dst)


def to_pdf(text: str, dst: Path) -> Rendered:
    """Text-layered PDF — pypdf will extract directly without needing OCR."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 10)
    width, height = letter
    x = 0.75 * inch
    y = height - 0.75 * inch
    for line in text.splitlines():
        if y < 0.75 * inch:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 0.75 * inch
        c.drawString(x, y, line)
        y -= 13
    c.save()
    dst.write_bytes(buf.getvalue())
    return Rendered(name=dst.name, path=dst)


def to_png(text: str, dst: Path) -> Rendered:
    """PIL-rendered 'scan-style' image to exercise the OCR path. Wider canvas
    + larger font so Tesseract has an easier time."""
    lines = text.splitlines()
    font_size = 18
    line_height = 24
    margin = 30
    width = 1000
    height = max(margin * 2 + line_height * len(lines), 200)
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    # Try a TrueType font; fall back to default if not available.
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size
        )
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((margin, margin + i * line_height), line, fill="black", font=font)
    img.save(dst, format="PNG")
    return Rendered(name=dst.name, path=dst)


_RENDERERS = {
    "txt": to_txt,
    "docx": to_docx,
    "pdf": to_pdf,
    "png": to_png,
}


def render_all() -> list[Rendered]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rendered: list[Rendered] = []
    for source in ALL_SOURCES:
        for fmt in ("txt", "docx", "pdf", "png"):
            dst = OUTPUT_DIR / f"{source.NAME}.{fmt}"
            renderer = _RENDERERS[fmt]
            rendered.append(renderer(source.TEXT, dst))
    return rendered


def render_one(source: ModuleType, fmt: str) -> Rendered:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = OUTPUT_DIR / f"{source.NAME}.{fmt}"
    return _RENDERERS[fmt](source.TEXT, dst)


if __name__ == "__main__":
    rendered = render_all()
    print(f"Wrote {len(rendered)} files to {OUTPUT_DIR}:")
    for r in rendered:
        size = r.path.stat().st_size
        print(f"  {r.name} ({size:,} bytes)")
