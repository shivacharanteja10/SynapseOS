"""PostgreSQL persistence for conversation history and audit logs."""

from __future__ import annotations

from typing import Any

from synapseos.core.config import Settings
from synapseos.core.logging import get_logger
from synapseos.models.conversation import AuditLogRecord, ConversationRecord

logger = get_logger(__name__)

try:  # pragma: no cover - import availability is environment-specific
    from sqlalchemy import DateTime, String, Text
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SQLALCHEMY_AVAILABLE = False

    class DeclarativeBase:  # type: ignore[no-redef]
        pass


if SQLALCHEMY_AVAILABLE:

    class Base(DeclarativeBase):
        pass

    class ConversationORM(Base):
        __tablename__ = "conversations"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
        goal: Mapped[str] = mapped_column(Text, nullable=False)
        final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
        messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
        metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
        created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
        updated_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)

    class AuditLogORM(Base):
        __tablename__ = "audit_logs"

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
        actor: Mapped[str] = mapped_column(String(128), nullable=False)
        action: Mapped[str] = mapped_column(String(128), nullable=False)
        details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
        created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)

else:
    Base = None  # type: ignore[assignment]
    ConversationORM = None  # type: ignore[assignment]
    AuditLogORM = None  # type: ignore[assignment]


class DatabaseService:
    """Async database service with in-memory fallback for demos and tests."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engine: Any | None = None
        self._sessionmaker: Any | None = None
        self._conversations: dict[str, ConversationRecord] = {}
        self._audit_logs: list[AuditLogRecord] = []
        if SQLALCHEMY_AVAILABLE:
            self._engine = create_async_engine(settings.database_url, pool_pre_ping=True)
            self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init_schema(self) -> None:
        """Create database tables if PostgreSQL is reachable."""

        if self._engine is None or Base is None:
            logger.warning("sqlalchemy_unavailable_using_memory_fallback")
            return
        try:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            logger.info("database_schema_ready")
        except Exception as exc:  # pragma: no cover - depends on local Postgres
            logger.warning("database_unavailable_using_memory_fallback", error=str(exc))
            self._engine = None
            self._sessionmaker = None

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()

    async def save_conversation(self, record: ConversationRecord) -> None:
        """Persist a conversation record."""

        self._conversations[record.task_id] = record
        if self._sessionmaker is None or ConversationORM is None:
            return
        payload = record.model_dump(mode="json")
        orm = ConversationORM(
            id=payload["id"],
            task_id=payload["task_id"],
            goal=payload["goal"],
            final_response=payload["final_response"],
            messages=payload["messages"],
            metadata_json=payload["metadata"],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        try:
            async with self._sessionmaker() as session:
                await session.merge(orm)
                await session.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("conversation_persist_failed", task_id=record.task_id, error=str(exc))

    async def get_conversation(self, task_id: str) -> ConversationRecord | None:
        """Return a conversation by task id."""

        return self._conversations.get(task_id)

    async def append_audit_log(self, record: AuditLogRecord) -> None:
        """Persist an audit log entry."""

        self._audit_logs.append(record)
        if self._sessionmaker is None or AuditLogORM is None:
            return
        try:
            async with self._sessionmaker() as session:
                session.add(
                    AuditLogORM(
                        id=record.id,
                        task_id=record.task_id,
                        actor=record.actor,
                        action=record.action,
                        details=record.model_dump(mode="json")["details"],
                        created_at=record.created_at,
                    )
                )
                await session.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("audit_log_persist_failed", task_id=record.task_id, error=str(exc))

    async def list_audit_logs(self, task_id: str) -> list[AuditLogRecord]:
        """Return in-memory audit log snapshots for API reads."""

        return [item for item in self._audit_logs if item.task_id == task_id]
