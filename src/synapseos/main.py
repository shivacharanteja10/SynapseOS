"""FastAPI application factory for SynapseOS."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from synapseos import __version__
from synapseos.agents import AgentDependencies
from synapseos.api.routes import router as api_router
from synapseos.core.config import Settings, get_settings
from synapseos.core.exceptions import SynapseOSError
from synapseos.core.logging import configure_logging, get_logger
from synapseos.graph.workflow import WorkflowGraph
from synapseos.services import (
    ApprovalService,
    DatabaseService,
    EventBus,
    LLMService,
    MemoryService,
    VectorStoreService,
)
from synapseos.services.task_manager import TaskManager


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application and wire runtime dependencies."""

    settings = settings or get_settings()
    configure_logging(log_level=settings.log_level, json_logs=settings.log_json)
    _configure_langsmith(settings)
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("synapseos_starting", environment=settings.environment)
        memory = MemoryService(settings)
        vector_store = VectorStoreService(settings)
        database = DatabaseService(settings)
        approvals = ApprovalService(settings)
        event_bus = EventBus()
        llm = LLMService(settings)

        await memory.connect()
        await vector_store.connect()
        await database.init_schema()

        dependencies = AgentDependencies(llm=llm, memory=memory, vector_store=vector_store)
        workflow = WorkflowGraph(
            settings=settings,
            dependencies=dependencies,
            approvals=approvals,
            event_bus=event_bus,
        )
        task_manager = TaskManager(
            workflow=workflow,
            event_bus=event_bus,
            database=database,
            memory=memory,
            approvals=approvals,
            api_prefix=settings.api_prefix,
        )

        app.state.settings = settings
        app.state.memory = memory
        app.state.vector_store = vector_store
        app.state.database = database
        app.state.approvals = approvals
        app.state.event_bus = event_bus
        app.state.task_manager = task_manager
        try:
            yield
        finally:
            logger.info("synapseos_shutting_down")
            await memory.close()
            await database.close()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Autonomous multi-agent AI orchestration platform.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    app.add_exception_handler(SynapseOSError, _synapse_error_handler)
    app.add_exception_handler(ValidationError, _validation_error_handler)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {
            "service": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


async def _synapse_error_handler(_: Request, exc: SynapseOSError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "type": exc.__class__.__name__},
    )


async def _validation_error_handler(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "type": "ValidationError"},
    )


def _configure_langsmith(settings: Settings) -> None:
    if not settings.langsmith_tracing:
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = str(settings.langsmith_endpoint)


app = create_app()
