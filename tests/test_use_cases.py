"""Unit tests for ParseBinaryLogUseCase: padding skipping, gap auditing, heterogeneous sources."""

from pathlib import Path
from typing import Iterator
import pytest

from ams_log_parser.application.registry import DecoderRegistry
from ams_log_parser.application.use_cases import ParseBinaryLogUseCase
from ams_log_parser.domain.enums import (
    LOG_BLOCK_SIZE_B,
    LOG_HEADER_SIZE_B,
    LogSourceId,
)
from ams_log_parser.domain.models import GpsRecord
from ams_log_parser.ports.reader_port import BinaryReaderPort
from tests.conftest import (
    make_file_header_payload,
    make_gps_payload,
    make_record,
    pad_block,
)


class MockBinaryReader(BinaryReaderPort):
    """In-memory mock for BinaryReaderPort."""

    def __init__(self, blocks: list[bytes]) -> None:
        self._blocks = blocks

    def stream_blocks(self, file_path: Path) -> Iterator[bytes]:
        yield from self._blocks

    def get_file_size(self, file_path: Path) -> int:
        return sum(len(b) for b in self._blocks)


def test_use_case_skips_padding_and_advances_block(tmp_path: Path):
    """Verifies that upon reaching source_id == 0x00, the parser discards the rest of the block."""
    registry = DecoderRegistry.create_default()
    fake_file = tmp_path / "stream.bin"
    fake_file.touch()

    # Block 1: 1 GPS record, then 0x00 padding to end of 4096-B block
    gps_payload_1 = make_gps_payload(lat_udeg=40000000, lon_udeg=1000000)
    rec1 = make_record(timestamp_ms=100, seq=1, source_id=LogSourceId.GPS_RMC, payload=gps_payload_1)
    block_1 = pad_block(rec1)

    # Block 2: 1 GPS record, then 0x00 padding
    gps_payload_2 = make_gps_payload(lat_udeg=40001000, lon_udeg=1000500)
    rec2 = make_record(timestamp_ms=200, seq=2, source_id=LogSourceId.GPS_RMC, payload=gps_payload_2)
    block_2 = pad_block(rec2)

    reader = MockBinaryReader([block_1, block_2])
    use_case = ParseBinaryLogUseCase(reader=reader, registry=registry)

    result = use_case.execute(fake_file)

    assert result.audit.total_blocks == 2
    assert result.audit.total_records == 2
    assert len(result.gps_records) == 2
    assert result.gps_records[0].seq == 1
    assert result.gps_records[1].seq == 2
    assert len(result.audit.sequence_gaps) == 0


def test_use_case_heterogeneous_mixed_sources(tmp_path: Path):
    """Verifies that unknown or unhandled sources (CAN, BMS, ADC) are tolerated and counted without error."""
    registry = DecoderRegistry.create_default()
    fake_file = tmp_path / "mixed.bin"
    fake_file.touch()

    # CAN Inverter record (0x10) - unhandled in default registry
    rec_can = make_record(timestamp_ms=50, seq=1, source_id=0x10, payload=b"\x01\x02\x03\x04\x05\x06\x07\x08")
    # GPS record (0x30)
    rec_gps = make_record(timestamp_ms=60, seq=2, source_id=LogSourceId.GPS_RMC, payload=make_gps_payload())
    # BMS SPI record (0x40) - unhandled in default registry
    rec_bms = make_record(timestamp_ms=70, seq=3, source_id=0x40, payload=b"\xAA\xBB\xCC\xDD")

    block = pad_block(rec_can + rec_gps + rec_bms)
    reader = MockBinaryReader([block])
    use_case = ParseBinaryLogUseCase(reader=reader, registry=registry)

    result = use_case.execute(fake_file)

    assert result.audit.total_records == 3
    assert result.audit.record_counts[0x10] == 1
    assert result.audit.record_counts[0x30] == 1
    assert result.audit.record_counts[0x40] == 1
    assert 0x10 in result.audit.unhandled_sources
    assert 0x40 in result.audit.unhandled_sources
    assert len(result.gps_records) == 1
    assert len(result.audit.sequence_gaps) == 0


def test_use_case_sequence_gap_detection(tmp_path: Path):
    """Verifies that gaps in the monotonic sequence counter are audited."""
    registry = DecoderRegistry.create_default()
    fake_file = tmp_path / "gaps.bin"
    fake_file.touch()

    rec1 = make_record(timestamp_ms=100, seq=10, source_id=LogSourceId.GPS_RMC, payload=make_gps_payload())
    # Missing seq 11, 12, 13
    rec2 = make_record(timestamp_ms=140, seq=14, source_id=LogSourceId.GPS_RMC, payload=make_gps_payload())

    block = pad_block(rec1 + rec2)
    reader = MockBinaryReader([block])
    use_case = ParseBinaryLogUseCase(reader=reader, registry=registry)

    result = use_case.execute(fake_file)

    assert len(result.audit.sequence_gaps) == 1
    assert result.audit.sequence_gaps[0] == (10, 14)


def test_use_case_truncated_record_at_block_end(tmp_path: Path):
    """Verifies that a record with payload length overrunning the block is safely discarded."""
    import struct
    registry = DecoderRegistry.create_default()
    fake_file = tmp_path / "truncated.bin"
    fake_file.touch()

    # Valid GPS record (31 bytes)
    rec1 = make_record(timestamp_ms=100, seq=1, source_id=LogSourceId.GPS_RMC, payload=make_gps_payload())
    # Corrupted header claiming 50 bytes payload when only 10 bytes exist before block ends
    truncated_hdr = struct.pack("<IHBB", 105, 2, LogSourceId.GPS_RMC, 50) + (b"X" * 10)

    # Total block size: 31 + 8 + 10 = 49 bytes. Record 2 requires 58 bytes, so it overruns block
    reader = MockBinaryReader([rec1 + truncated_hdr])
    use_case = ParseBinaryLogUseCase(reader=reader, registry=registry)

    result = use_case.execute(fake_file)
    assert len(result.gps_records) == 1
