"""Pipeline run endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.schemas import RunPipelineRequest
from pipeline import PipelineResult, SessionNotFoundError
from vault import SessionExpiredError

router = APIRouter(prefix="/sessions", tags=["pipeline"])


@router.post("/{session_id}/pipeline", response_model=PipelineResult)
async def run_pipeline(
    session_id: str,
    body: RunPipelineRequest,
    request: Request,
) -> PipelineResult:
    try:
        pipeline = request.app.state.app_state.manager.get(session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"}) from e

    try:
        return await pipeline.run(doc_id=body.doc_id, query=body.user_query)
    except SessionExpiredError as e:
        raise HTTPException(status_code=409, detail={"error": "session_expired"}) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "document_not_found"}) from e
