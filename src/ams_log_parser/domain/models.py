"""Domain entities and value objects."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class LogRecordHeader:
    """Wire header (8 bytes, little-endian) preceding each record."""
    timestamp_ms: int
    seq: int
    source_id: int
    payload_len: int


@dataclass(frozen=True)
class RawRecord:
    """Envelope holding a decoded header and its associated raw payload bytes."""
    header: LogRecordHeader
    payload: bytes


@dataclass(frozen=True)
class FileHeaderRecord:
    """Metadata recorded in the first block of the log (LOG_SRC_FILE_HEADER = 0x01)."""
    timestamp_ms: int
    format_version: int
    pool_blocks: int
    block_size_B: int


@dataclass(frozen=True)
class GpsRecord:
    """Domain representation of a parsed GPS RMC frame (LOG_SRC_GPS_RMC = 0x30)."""
    timestamp_ms: int
    seq: int
    latitude_deg: float
    longitude_deg: float
    speed_kmh: float
    course_deg: float
    utc_time_of_day_ms: int
    year: int
    month: int
    day: int
    fix_valid: bool

    @property
    def speed_ms(self) -> float:
        return self.speed_kmh / 3.6

    @property
    def utc_time_str(self) -> str:
        hours = (self.utc_time_of_day_ms // 3_600_000) % 24
        rem = self.utc_time_of_day_ms % 3_600_000
        minutes = rem // 60_000
        rem %= 60_000
        seconds = rem // 1_000
        millis = rem % 1_000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

    @property
    def utc_date_str(self) -> str:
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"

    @property
    def utc_iso(self) -> str:
        return f"{self.utc_date_str}T{self.utc_time_str}Z"


@dataclass(frozen=True)
class LoggerStatsRecord:
    """Firmware self-diagnostic record (LOG_SRC_LOGGER_STATS = 0xF0)."""
    timestamp_ms: int
    dropped_records: int
    max_write_ms: int
    max_sync_ms: int
    broker_faults: int
    pool_full_max: int
    write_errors: int


@dataclass
class ParsingAudit:
    """Audit log and diagnostic metrics collected during binary stream ingestion."""
    source_file: str
    file_size_bytes: int
    total_blocks: int
    record_counts: Dict[int, int] = field(default_factory=dict)
    sequence_gaps: List[Tuple[int, int]] = field(default_factory=list)
    unhandled_sources: Set[int] = field(default_factory=set)

    @property
    def total_records(self) -> int:
        return sum(self.record_counts.values())

    @property
    def total_gaps(self) -> int:
        return len(self.sequence_gaps)
