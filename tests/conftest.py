"""Shared fixtures and byte builders for testing."""

import struct
from ams_log_parser.domain.enums import (
    LOG_BLOCK_SIZE_B,
    LOG_HEADER_SIZE_B,
    LogSourceId,
)


def make_record(timestamp_ms: int, seq: int, source_id: int, payload: bytes) -> bytes:
    """Packs an 8-byte LogRecordHeader_t followed by payload bytes."""
    header = struct.pack("<IHBB", timestamp_ms, seq, source_id, len(payload))
    return header + payload


def make_file_header_payload(format_version: int = 1, pool_blocks: int = 4, block_size_B: int = 4096) -> bytes:
    """Packs a LogPayloadFileHeader_t."""
    return struct.pack("<BBH", format_version, pool_blocks, block_size_B)


def make_gps_payload(
    lat_udeg: int = 41079492,
    lon_udeg: int = -200745,
    vel_kmh_x1000: int = 126250,
    utc_ms: int = 53391390,
    course_cdeg: int = 22206,
    year: int = 2026,
    month: int = 10,
    day: int = 10,
    fix_valid: int = 1,
) -> bytes:
    """Packs a LogPayloadGps_t (23 bytes)."""
    return struct.pack(
        "<iiiIHHBBB",
        lat_udeg,
        lon_udeg,
        vel_kmh_x1000,
        utc_ms,
        course_cdeg,
        year,
        month,
        day,
        fix_valid,
    )


def make_stats_payload(
    dropped: int = 0,
    max_write_ms: int = 48,
    max_sync_ms: int = 54,
    broker_faults: int = 0,
    full_count_max: int = 1,
    write_errors: int = 0,
) -> bytes:
    """Packs a LogPayloadStats_t (12 bytes)."""
    return struct.pack("<IHHHBB", dropped, max_write_ms, max_sync_ms, broker_faults, full_count_max, write_errors)


def pad_block(data: bytes, block_size: int = LOG_BLOCK_SIZE_B) -> bytes:
    """Pads data with 0x00 to complete a block."""
    if len(data) > block_size:
        raise ValueError(f"Data exceeds block size: {len(data)} > {block_size}")
    return data + bytes(block_size - len(data))
