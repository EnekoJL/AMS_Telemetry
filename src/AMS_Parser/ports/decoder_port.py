"""Payload decoder port definition."""

from typing import Any, Protocol

from AMS_Parser.domain.models import LogRecordHeader


class PayloadDecoderPort(Protocol):
    """Port interface for domain payload decoders."""

    @property
    def source_id(self) -> int:
        """The LogSourceId this decoder is responsible for."""
        ...

    def decode(self, header: LogRecordHeader, payload_bytes: bytes) -> Any:
        """Decodes the raw payload bytes into a structured domain entity."""
        ...
