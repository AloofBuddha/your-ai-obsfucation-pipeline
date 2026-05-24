"""Session lifecycle + document upload routes."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from api.schemas import (
    PutDocumentResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from obfuscation.strategies import available_strategies
from pipeline import SessionNotFoundError

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _manager(request: Request):
    return request.app.state.app_state.manager


def _docstore(request: Request):
    return request.app.state.app_state.docstore


@router.post("", response_model=StartSessionResponse, status_code=201)
async def start_session(
    body: StartSessionRequest, request: Request
) -> StartSessionResponse:
    strategy = (
        body.strategy
        or request.app.state.app_state.settings.obfuscation_strategy_default
    )
    if strategy not in available_strategies():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_strategy",
                "available": available_strategies(),
            },
        )
    pipeline = await _manager(request).start_session(body.user_id, strategy)
    return StartSessionResponse(
        session_id=pipeline.session_id,
        user_id=body.user_id,
        strategy=pipeline.strategy_name,
    )


@router.delete("/{session_id}", status_code=204)
async def end_session(session_id: str, request: Request) -> None:
    try:
        await _manager(request).end_session(session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"}) from e


@router.post(
    "/{session_id}/documents",
    response_model=PutDocumentResponse,
    status_code=201,
)
async def upload_document(
    session_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> PutDocumentResponse:
    try:
        pipeline = _manager(request).get(session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"}) from e

    if not file.filename:
        raise HTTPException(status_code=400, detail={"error": "missing_filename"})

    content = await file.read()
    docstore = _docstore(request)
    doc_id = await docstore.put(
        pipeline.user_id, content=content, filename=file.filename
    )
    return PutDocumentResponse(doc_id=doc_id, filename=file.filename)
