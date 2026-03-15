"""MessageQueue abstract base class — event bus abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable


class MessageQueue(ABC):
    """Abstract interface for message queue / event bus operations."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the message broker."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the message broker."""
        ...

    @abstractmethod
    async def publish(self, topic: str, msg: bytes) -> None:
        """Publish a message to a topic/queue."""
        ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable[[bytes], Awaitable[None]]) -> None:
        """Subscribe to a topic and process messages with the given handler."""
        ...
