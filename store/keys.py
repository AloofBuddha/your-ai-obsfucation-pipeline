"""Per-user encryption keys.

Resolution order:
  1. Env var USER_KEY_<user_id> — set explicitly by the operator.
  2. Persisted store at data/user_keys.json (gitignored).
  3. Auto-generate and persist.

The persisted file holds keys in plaintext — gitignored, OK for local dev.
Production would replace this layer with KMS-resident keys (documented in
README known gaps).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet


class UserKeyStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._keys: dict[str, str] = {}
        if self._path.exists():
            self._keys = json.loads(self._path.read_text())

    def get_or_create(self, user_id: str) -> bytes:
        env_var = f"USER_KEY_{user_id}"
        if env_value := os.getenv(env_var):
            return env_value.encode("ascii")
        if user_id in self._keys:
            return self._keys[user_id].encode("ascii")
        # Generate, persist, return.
        new_key = Fernet.generate_key()
        self._keys[user_id] = new_key.decode("ascii")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._keys, indent=2))
        self._path.chmod(0o600)
        return new_key

    def has_key(self, user_id: str) -> bool:
        return bool(os.getenv(f"USER_KEY_{user_id}")) or user_id in self._keys
