"""Unit tests for FileHeader and Stats decoders, and DecoderRegistry."""

import pytest

from AMS_Parser.application.registry import DecoderRegistry
from AMS_Parser.domain.decoders.file_header import FileHeaderPayloadDecoder
from AMS_Parser.domain.decoders.gps import GpsPayloadDecoder
from AMS_Parser.domain.decoders.stats import StatsPayloadDecoder
from AMS_Parser.domain.enums import LogSourceId
from AMS_Parser.domain.models import LogRecordHeader
from tests.conftest import make_file_header_payload, make_stats_payload


def test_file_header_decoder():
    decoder = FileHeaderPayloadDecoder()
    assert decoder.source_id == LogSourceId.FILE_HEADER

    header = LogRecordHeader(timestamp_ms=10, seq=0, source_id=LogSourceId.FILE_HEADER, payload_len=4)
    payload = make_file_header_payload(format_version=1, pool_blocks=4, block_size_B=4096)

    record = decoder.decode(header, payload)
    assert record.timestamp_ms == 10
    assert record.format_version == 1
    assert record.pool_blocks == 4
    assert record.block_size_B == 4096


def test_stats_decoder():
    decoder = StatsPayloadDecoder()
    assert decoder.source_id == LogSourceId.LOGGER_STATS

    header = LogRecordHeader(timestamp_ms=2000, seq=10, source_id=LogSourceId.LOGGER_STATS, payload_len=12)
    payload = make_stats_payload(
        dropped=3,
        max_write_ms=45,
        max_sync_ms=52,
        broker_faults=0,
        full_count_max=2,
        write_errors=0,
    )

    record = decoder.decode(header, payload)
    assert record.dropped_records == 3
    assert record.max_write_ms == 45
    assert record.max_sync_ms == 52
    assert record.broker_faults == 0
    assert record.pool_full_max == 2
    assert record.write_errors == 0


def test_decoder_registry():
    registry = DecoderRegistry()
    assert registry.get(LogSourceId.GPS_RMC) is None

    gps_dec = GpsPayloadDecoder()
    registry.register(gps_dec)
    assert registry.get(LogSourceId.GPS_RMC) is gps_dec
    assert LogSourceId.GPS_RMC in registry.registered_sources

    # Test create_default
    default_reg = DecoderRegistry.create_default()
    assert default_reg.get(LogSourceId.FILE_HEADER) is not None
    assert default_reg.get(LogSourceId.GPS_RMC) is not None
    assert default_reg.get(LogSourceId.LOGGER_STATS) is not None
    assert default_reg.get(LogSourceId.CAN_INVERTER) is None
