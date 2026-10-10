"""Data Transfer Objects for application results."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from AMS_Parser.domain.models import (
    FileHeaderRecord,
    GpsRecord,
    LoggerStatsRecord,
    ParsingAudit,
)


@dataclass
class ParseResultDTO:
    """Consolidated outcome of parsing a binary log session."""
    audit: ParsingAudit
    file_header: Optional[FileHeaderRecord] = None
    gps_records: List[GpsRecord] = field(default_factory=list)
    stats_records: List[LoggerStatsRecord] = field(default_factory=list)
    exported_files: List[Path] = field(default_factory=list)

    @property
    def has_gps_data(self) -> bool:
        return len(self.gps_records) > 0

    @property
    def valid_gps_fixes(self) -> int:
        return sum(1 for r in self.gps_records if r.fix_valid)
