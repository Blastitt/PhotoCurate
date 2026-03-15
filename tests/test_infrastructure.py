"""Tests for infrastructure factory functions."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from photocurate.core.storage import BlobStore
from photocurate.core.queue import MessageQueue


def test_blob_store_abc_cannot_instantiate():
    """BlobStore is abstract and should not be directly instantiable."""
    import pytest
    with pytest.raises(TypeError):
        BlobStore()  # type: ignore[abstract]


def test_message_queue_abc_cannot_instantiate():
    """MessageQueue is abstract and should not be directly instantiable."""
    import pytest
    with pytest.raises(TypeError):
        MessageQueue()  # type: ignore[abstract]


def test_factory_selects_configured_blob_store(monkeypatch):
    from photocurate.infrastructure import factory

    class FakeAzureBlobStore:
        pass

    class FakeMinioBlobStore:
        pass

    monkeypatch.setitem(sys.modules, "photocurate.infrastructure.azure_blob", SimpleNamespace(AzureBlobStore=FakeAzureBlobStore))
    monkeypatch.setitem(sys.modules, "photocurate.infrastructure.minio_blob", SimpleNamespace(MinioBlobStore=FakeMinioBlobStore))

    monkeypatch.setattr(factory.settings, "storage_provider", "azure")
    assert isinstance(factory.create_blob_store(), FakeAzureBlobStore)

    monkeypatch.setattr(factory.settings, "storage_provider", "minio")
    assert isinstance(factory.create_blob_store(), FakeMinioBlobStore)


def test_factory_selects_configured_message_queue(monkeypatch):
    from photocurate.infrastructure import factory

    class FakeAzureQueue:
        pass

    class FakeNatsQueue:
        pass

    monkeypatch.setitem(sys.modules, "photocurate.infrastructure.azure_queue", SimpleNamespace(AzureServiceBusQueue=FakeAzureQueue))
    monkeypatch.setitem(sys.modules, "photocurate.infrastructure.nats_queue", SimpleNamespace(NatsMessageQueue=FakeNatsQueue))

    monkeypatch.setattr(factory.settings, "queue_provider", "azure_servicebus")
    assert isinstance(factory.create_message_queue(), FakeAzureQueue)

    monkeypatch.setattr(factory.settings, "queue_provider", "nats")
    assert isinstance(factory.create_message_queue(), FakeNatsQueue)


def test_factory_selects_image_analyzer_based_on_azure_credentials(monkeypatch):
    from photocurate.infrastructure import factory

    class FakeAzureAnalyzer:
        pass

    class FakeLocalAnalyzer:
        pass

    monkeypatch.setitem(sys.modules, "photocurate.infrastructure.azure_ai_vision", SimpleNamespace(AzureAIVisionAnalyzer=FakeAzureAnalyzer))
    monkeypatch.setitem(sys.modules, "photocurate.infrastructure.local_analyzer", SimpleNamespace(LocalImageAnalyzer=FakeLocalAnalyzer))

    monkeypatch.setattr(factory.settings, "azure_ai_vision_endpoint", "https://azure.test")
    monkeypatch.setattr(factory.settings, "azure_ai_vision_key", "secret")
    assert isinstance(factory.create_image_analyzer(), FakeAzureAnalyzer)

    monkeypatch.setattr(factory.settings, "azure_ai_vision_endpoint", None)
    monkeypatch.setattr(factory.settings, "azure_ai_vision_key", None)
    assert isinstance(factory.create_image_analyzer(), FakeLocalAnalyzer)


def test_dependency_singletons_reuse_and_reset(monkeypatch):
    from photocurate.api import deps

    blob_instances: list[object] = []
    queue_instances: list[object] = []

    def make_blob_store() -> object:
        instance = object()
        blob_instances.append(instance)
        return instance

    def make_queue() -> object:
        instance = object()
        queue_instances.append(instance)
        return instance

    deps.reset_dependency_singletons()
    monkeypatch.setattr(deps, "create_blob_store", make_blob_store)
    monkeypatch.setattr(deps, "create_message_queue", make_queue)

    first_blob = deps.get_blob_store()
    second_blob = deps.get_blob_store()
    first_queue = deps.get_message_queue()
    second_queue = deps.get_message_queue()

    assert first_blob is second_blob
    assert first_queue is second_queue
    assert len(blob_instances) == 1
    assert len(queue_instances) == 1

    deps.reset_dependency_singletons()

    assert deps.get_blob_store() is not first_blob
    assert deps.get_message_queue() is not first_queue
    assert len(blob_instances) == 2
    assert len(queue_instances) == 2
