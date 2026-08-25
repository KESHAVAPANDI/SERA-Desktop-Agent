import logging
from typing import Type

from .base import WakeWordProvider, WakeWordStatus
from .local_custom import LocalCustomWakeWordProvider

logger = logging.getLogger(__name__)


class WakeWordRegistry:
    """Registry and factory for pluggable Wake-Word Providers."""

    _providers: dict[str, Type[WakeWordProvider]] = {
        "local_custom": LocalCustomWakeWordProvider,
    }

    @classmethod
    def register(cls, name: str, provider_cls: Type[WakeWordProvider]) -> None:
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def create(cls, name: str = "local_custom", **kwargs) -> WakeWordProvider:
        provider_cls = cls._providers.get(name.lower(), LocalCustomWakeWordProvider)
        instance = provider_cls(**kwargs)
        instance.initialize()
        return instance
