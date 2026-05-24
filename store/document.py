"""Encrypted document storage — per-user filesystem layout."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import aiofiles
from cryptography.fernet import Fernet

from store.extractors import extract_text_from_bytes
from store.keys import UserKeyStore


class DocumentStore(Protocol):
    async def put(self, user_id: str, *, content: bytes, filename: str) -> str: ...
    async def get_text(self, user_id: str, doc_id: str) -> str: ...


class FilesystemDocumentStore:
    """Layout: <base>/<user_id>/<doc_id>.enc

    Where doc_id is a uuid hex prefix + original extension (e.g.
    'a1b2c3d4.pdf'). The extension is preserved so the extractor knows what
    format the decrypted bytes are.
    """

    def __init__(self, base: Path | str, keystore: UserKeyStore) -> None:
        self._base = Path(base)
        self._base.mkdir(parents=True, exist_ok=True)
        self._keystore = keystore

    def _user_dir(self, user_id: str) -> Path:
        if (
            not user_id
            or user_id in {".", ".."}
            or "/" in user_id
            or "\\" in user_id
        ):
            raise ValueError(f"Unsafe user_id: {user_id!r}")
        d = self._base / user_id
        if not d.resolve().is_relative_to(self._base.resolve()):
            raise ValueError(f"Unsafe user_id: {user_id!r}")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _doc_path(self, user_id: str, doc_id: str) -> Path:
        return self._user_dir(user_id) / f"{doc_id}.enc"

    async def put(self, user_id: str, *, content: bytes, filename: str) -> str:
        # Preserve the original extension so the extractor can dispatch later.
        ext = Path(filename).suffix.lower()
        doc_id = f"{uuid4().hex[:12]}{ext}"
        key = self._keystore.get_or_create(user_id)
        ciphertext = Fernet(key).encrypt(content)
        path = self._doc_path(user_id, doc_id)
        async with aiofiles.open(path, "wb") as f:
            await f.write(ciphertext)
        return doc_id

    async def get_raw(self, user_id: str, doc_id: str) -> bytes:
        path = self._doc_path(user_id, doc_id)
        if not path.exists():
            raise FileNotFoundError(f"No document {doc_id!r} for user {user_id!r}")
        async with aiofiles.open(path, "rb") as f:
            ciphertext = await f.read()
        key = self._keystore.get_or_create(user_id)
        return Fernet(key).decrypt(ciphertext)

    async def get_text(self, user_id: str, doc_id: str) -> str:
        raw = await self.get_raw(user_id, doc_id)
        # Sync extraction → run in a thread.
        return await asyncio.to_thread(
            extract_text_from_bytes, raw, filename=doc_id
        )
