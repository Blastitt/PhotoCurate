"""NATS implementation of MessageQueue."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import nats
from nats.aio.client import Client as NatsClient

from photocurate.config import settings
from photocurate.core.queue import MessageQueue

logger = logging.getLogger(__name__)


class NatsMessageQueue(MessageQueue):
    """NATS-based message queue implementation."""

    def __init__(self) -> None:
        self._nc: NatsClient | None = None
        self._url = settings.nats_url

    async def connect(self) -> None:
        self._nc = await nats.connect(self._url)
        logger.info("Connected to NATS at %s", self._url)

    async def disconnect(self) -> None:
        if self._nc:
            await self._nc.drain()
            logger.info("Disconnected from NATS")

    async def publish(self, topic: str, msg: bytes) -> None:
        if not self._nc:
            raise RuntimeError("Not connected to NATS. Call connect() first.")
        await self._nc.publish(topic, msg)

    async def subscribe(self, topic: str, handler: Callable[[bytes], Awaitable[None]]) -> None:
        if not self._nc:
            raise RuntimeError("Not connected to NATS. Call connect() first.")

        async def _msg_handler(msg: nats.aio.client.Msg) -> None:
            try:
                await handler(msg.data)
            except Exception:
                logger.exception("Error processing message on topic %s", topic)

        await self._nc.subscribe(topic, cb=_msg_handler)
        logger.info("Subscribed to NATS topic: %s", topic)
