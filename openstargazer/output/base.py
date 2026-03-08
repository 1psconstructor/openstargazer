"""Abstract base class for all output plugins."""
from __future__ import annotations

from abc import ABC, abstractmethod

from openstargazer.engine.api import TrackingFrame


class OutputPlugin(ABC):
    """
    Base class for head-tracking output backends.

    Each plugin receives a TrackingFrame and is responsible for
    encoding and transmitting it in its own protocol format.
    """

    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """Initialise resources (open socket, shared memory, etc.)."""

    @abstractmethod
    async def stop(self) -> None:
        """Release resources."""

    @abstractmethod
    async def send(self, frame: TrackingFrame) -> None:
        """Encode and transmit a single tracking frame."""

    @property
    def is_running(self) -> bool:
        return False
