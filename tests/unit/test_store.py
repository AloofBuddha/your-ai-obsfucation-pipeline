"""Document store tests — encrypted at rest, per-user isolation, all formats."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken
from docx import Document
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from store import FilesystemDocumentStore, UserKeyStore, extract_text_from_bytes


@pytest.fixture
def keystore(tmp_path: Path) -> UserKeyStore:
    return UserKeyStore(tmp_path / "user_keys.json")


@pytest.fixture
def docstore(tmp_path: Path, keystore: UserKeyStore) -> FilesystemDocumentStore:
    return FilesystemDocumentStore(tmp_path / "data", keystore)


# ---------------------------------------------------------------- format helpers

def _make_docx_bytes(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pdf_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in text.splitlines():
        c.drawString(50, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def _make_image_bytes(text: str) -> bytes:
    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)
    # Use default font for portability.
    draw.text((10, 50), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- user keys

def test_user_keystore_generates_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "ks.json"
    ks1 = UserKeyStore(path)
    key1 = ks1.get_or_create("alice")
    # Persisted to disk.
    assert path.exists()
    # New instance loads same key.
    ks2 = UserKeyStore(path)
    key2 = ks2.get_or_create("alice")
    assert key1 == key2


def test_user_keystore_env_overrides_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ks = UserKeyStore(tmp_path / "ks.json")
    env_key = Fernet.generate_key()
    monkeypatch.setenv("USER_KEY_bob", env_key.decode())
    assert ks.get_or_create("bob") == env_key


# ---------------------------------------------------------------- encryption at rest

async def test_doc_encrypted_at_rest(
    docstore: FilesystemDocumentStore, tmp_path: Path
) -> None:
    """Raw bytes on disk must not contain any plaintext from input. PRD must-have."""
    secret = "Patient: John Smith. SSN: 529-99-0001."
    doc_id = await docstore.put(
        "alice", content=secret.encode(), filename="record.txt"
    )

    # Walk the data dir and assert no plaintext token appears.
    data_dir = tmp_path / "data"
    for f in data_dir.rglob("*"):
        if f.is_file():
            blob = f.read_bytes()
            for phrase in ["John Smith", "Patient", "529-99-0001"]:
                assert phrase.encode() not in blob, f"Plaintext {phrase!r} found in {f}"

    # And we can still round-trip.
    text = await docstore.get_text("alice", doc_id)
    assert text == secret


async def test_cross_user_decrypt_fails(
    docstore: FilesystemDocumentStore, keystore: UserKeyStore
) -> None:
    """PRD: 'retrievable only with correct user key'."""
    doc_id = await docstore.put("alice", content=b"alice's secret", filename="a.txt")

    # Bob attempts to read alice's doc. Implementation enforces this via path
    # scoping AND by using Bob's (different) key — Fernet will raise on the
    # cross-user attempt because the key won't match the ciphertext.
    alice_path = docstore._doc_path("alice", doc_id)
    bob_key = keystore.get_or_create("bob")
    with pytest.raises(InvalidToken):
        Fernet(bob_key).decrypt(alice_path.read_bytes())


async def test_get_missing_doc_raises(
    docstore: FilesystemDocumentStore,
) -> None:
    with pytest.raises(FileNotFoundError):
        await docstore.get_text("alice", "nonexistent.txt")


async def test_user_id_cannot_escape_data_dir(
    docstore: FilesystemDocumentStore,
) -> None:
    with pytest.raises(ValueError, match="Unsafe user_id"):
        await docstore.put("../outside", content=b"secret", filename="a.txt")


# ---------------------------------------------------------------- extractors

async def test_extract_txt(docstore: FilesystemDocumentStore) -> None:
    text = "Hello, John Smith.\nSecond line."
    doc_id = await docstore.put("alice", content=text.encode(), filename="note.txt")
    assert await docstore.get_text("alice", doc_id) == text


async def test_extract_docx(docstore: FilesystemDocumentStore) -> None:
    content = _make_docx_bytes("Patient name: Jane Doe\nDOB: 1985-03-14")
    doc_id = await docstore.put("alice", content=content, filename="patient.docx")
    extracted = await docstore.get_text("alice", doc_id)
    assert "Patient name: Jane Doe" in extracted
    assert "1985-03-14" in extracted


async def test_extract_pdf(docstore: FilesystemDocumentStore) -> None:
    content = _make_pdf_bytes("Confidential medical record\nMRN: 1234567")
    doc_id = await docstore.put("alice", content=content, filename="record.pdf")
    extracted = await docstore.get_text("alice", doc_id)
    assert "MRN: 1234567" in extracted


async def test_extract_image_via_ocr(docstore: FilesystemDocumentStore) -> None:
    """Tesseract OCR on a PIL-rendered image. The test verifies the OCR path
    runs end-to-end; we don't assert exact text because rendered glyph fidelity
    depends on system fonts."""
    content = _make_image_bytes("HELLO MRN 1234567")
    doc_id = await docstore.put("alice", content=content, filename="scan.png")
    extracted = await docstore.get_text("alice", doc_id)
    # Tesseract typically gets MRN-style strings right with default font.
    # Accept either upper or lower case.
    assert "1234567" in extracted or "HELLO" in extracted.upper()


def test_unsupported_format_raises() -> None:
    from store import UnsupportedFormatError

    with pytest.raises(UnsupportedFormatError):
        extract_text_from_bytes(b"unused", filename="evil.exe")
