"""FastAPI app factory + lifecycle."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import Settings
from api.routes import audit as audit_routes
from api.routes import pipeline as pipeline_routes
from api.routes import sessions as session_routes
from api.state import build_state


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.app_state = await build_state(cfg)
        try:
            yield
        finally:
            await app.state.app_state.vault_db.close()

    app = FastAPI(
        title="Secure Context Pipeline",
        description="PII/PHI obfuscation pipeline for external LLM providers",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(session_routes.router)
    app.include_router(pipeline_routes.router)
    app.include_router(audit_routes.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# Module-level app so `uvicorn api.main:app` works.
app = create_app()
