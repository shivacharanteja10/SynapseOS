"""In-process realtime event fan-out for HTTP and WebSocket clients."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from synapseos.models.agent import AgentEvent


class EventBus:
    """Simple async pub/sub bus scoped by task id."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[AgentEvent]]] = defaultdict(set)

    async def publish(self, event: AgentEvent) -> None:
        """Publish an event to all subscribers for a task."""

        for queue in list(self._subscribers[event.task_id]):
            await queue.put(event)

    async def subscribe(self, task_id: str) -> AsyncIterator[AgentEvent]:
        """Subscribe to task events until the caller disconnects."""

        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=200)
        self._subscribers[task_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[task_id].discard(queue)
            if not self._subscribers[task_id]:
                self._subscribers.pop(task_id, None)
