"""Audit query — list events for a given session."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from api.schemas import AuditEntry

router = APIRouter(prefix="/sessions", tags=["audit"])


@router.get("/{session_id}/audit", response_model=list[AuditEntry])
async def list_audit_events(session_id: str, request: Request) -> list[AuditEntry]:
    audit_path = Path(request.app.state.app_state.settings.audit_path)
    if not audit_path.exists():
        return []
    entries: list[AuditEntry] = []
    for line in audit_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("session_id") != session_id:
            continue
        try:
            entries.append(
                AuditEntry(
                    timestamp=event["timestamp"],
                    session_id=event["session_id"],
                    action=event["action"],
                    entity_type=event.get("entity_type"),
                    token_id=event.get("token_id"),
                    metadata=event.get("metadata", {}),
                )
            )
        except KeyError as e:
            raise HTTPException(
                status_code=500, detail={"error": "audit_corruption", "missing": str(e)}
            ) from e
    return entries
