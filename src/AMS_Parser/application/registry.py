"""Registry for payload decoders, fulfilling the Open/Closed Principle."""

from typing import Dict, Optional

from AMS_Parser.domain.decoders.file_header import FileHeaderPayloadDecoder
from AMS_Parser.domain.decoders.gps import GpsPayloadDecoder
from AMS_Parser.domain.decoders.stats import StatsPayloadDecoder
from AMS_Parser.ports.decoder_port import PayloadDecoderPort


class DecoderRegistry:
    """Registry maintaining a lookup table of PayloadDecoderPort instances.
    
    Adheres to the Open/Closed Principle (OCP): new subsytem decoders (e.g. CAN,
    BMS, ADC) can be dynamically registered without altering the parsing engine.
    """

    def __init__(self) -> None:
        self._decoders: Dict[int, PayloadDecoderPort] = {}

    def register(self, decoder: PayloadDecoderPort) -> "DecoderRegistry":
        """Registers a decoder for its declared source_id."""
        self._decoders[decoder.source_id] = decoder
        return self

    def get(self, source_id: int) -> Optional[PayloadDecoderPort]:
        """Returns the registered decoder for the given source_id, or None if unhandled."""
        return self._decoders.get(source_id)

    def is_registered(self, source_id: int) -> bool:
        """Checks if a decoder is registered for the given source_id."""
        return source_id in self._decoders

    @property
    def registered_sources(self) -> set[int]:
        """Returns set of all registered source IDs."""
        return set(self._decoders.keys())

    @classmethod
    def create_default(cls) -> "DecoderRegistry":
        """Factory creating a registry seeded with standard known decoders."""
        registry = cls()
        registry.register(FileHeaderPayloadDecoder())
        registry.register(GpsPayloadDecoder())
        registry.register(StatsPayloadDecoder())
        return registry
