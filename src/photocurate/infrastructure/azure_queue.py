"""Azure Service Bus implementation of MessageQueue."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient

from photocurate.config import settings
from photocurate.core.queue import MessageQueue

logger = logging.getLogger(__name__)


class AzureServiceBusQueue(MessageQueue):
    """Azure Service Bus message queue implementation."""

    def __init__(self) -> None:
        if not settings.azure_servicebus_connection_string:
            raise ValueError("AZURE_SERVICEBUS_CONNECTION_STRING is required")
        self._conn_str = settings.azure_servicebus_connection_string
        self._client: AsyncServiceBusClient | None = None

    async def connect(self) -> None:
        self._client = AsyncServiceBusClient.from_connection_string(self._conn_str)
        logger.info("Connected to Azure Service Bus")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            logger.info("Disconnected from Azure Service Bus")

    async def publish(self, topic: str, msg: bytes) -> None:
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")
        async with self._client.get_topic_sender(topic_name=topic) as sender:
            await sender.send_messages(ServiceBusMessage(body=msg))

    async def subscribe(self, topic: str, handler: Callable[[bytes], Awaitable[None]]) -> None:
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")
        # Note: In production, this would run in a background task
        async with self._client.get_subscription_receiver(
            topic_name=topic, subscription_name="photocurate-worker"
        ) as receiver:
            async for msg in receiver:
                try:
                    await handler(bytes(msg))
                    await receiver.complete_message(msg)
                except Exception:
                    logger.exception("Error processing message on topic %s", topic)
                    await receiver.abandon_message(msg)
