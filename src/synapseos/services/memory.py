"""Redis-backed memory and task queue service."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from synapseos.core.config import Settings
from synapseos.core.logging import get_logger

logger = get_logger(__name__)


class MemoryService:
    """Agent memory service backed by Redis with an in-memory fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._redis: Any | None = None
        self._memory: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def connect(self) -> None:
        """Connect to Redis if available."""

        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(self.settings.redis_url, decode_responses=True)
            await self._redis.ping()
            logger.info("redis_connected", redis_url=self.settings.redis_url)
        except Exception as exc:  # pragma: no cover - depends on local services
            self._redis = None
            logger.warning("redis_unavailable_using_memory_fallback", error=str(exc))

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

    async def remember(self, task_id: str, namespace: str, value: str) -> None:
        """Persist an agent memory entry."""

        if self._redis is not None:
            await self._redis.rpush(self._memory_key(task_id, namespace), value)
            return
        self._memory[task_id][namespace].append(value)

    async def recall(self, task_id: str, namespace: str, limit: int = 20) -> list[str]:
        """Return recent memory items for a task and namespace."""

        if self._redis is not None:
            values = await self._redis.lrange(self._memory_key(task_id, namespace), -limit, -1)
            return [str(item) for item in values]
        return self._memory[task_id][namespace][-limit:]

    async def enqueue_task(self, payload: dict[str, Any]) -> None:
        """Queue a task payload for worker-style processing."""

        if self._redis is not None:
            await self._redis.lpush(self.settings.task_queue_name, json.dumps(payload))
            return
        await self._queue.put(payload)

    async def dequeue_task(self, timeout_seconds: int = 5) -> dict[str, Any] | None:
        """Pop the next task payload from the queue."""

        if self._redis is not None:
            item = await self._redis.brpop(self.settings.task_queue_name, timeout=timeout_seconds)
            if item is None:
                return None
            _, raw = item
            return json.loads(raw)
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout_seconds)
        except TimeoutError:
            return None

    @staticmethod
    def _memory_key(task_id: str, namespace: str) -> str:
        return f"synapseos:memory:{task_id}:{namespace}"
