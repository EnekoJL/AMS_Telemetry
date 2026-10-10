"""Adapter for exporting telemetry data to structured CSV files."""

import csv
from pathlib import Path
from typing import Iterable

from ams_log_parser.domain.models import GpsRecord


class CsvGpsExporterAdapter:
    """Serializes GPS domain records into standard CSV format."""

    CSV_HEADERS = [
        "seq",
        "timestamp_ms",
        "utc_iso",
        "utc_date",
        "utc_time",
        "fix_valid",
        "latitude",
        "longitude",
        "speed_kmh",
        "speed_ms",
        "course_deg",
    ]

    def export(self, records: Iterable[GpsRecord], destination_file: Path) -> Path:
        """Writes GpsRecord instances to destination_file in CSV format."""
        destination_file.parent.mkdir(parents=True, exist_ok=True)

        with open(destination_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.CSV_HEADERS)

            for r in records:
                writer.writerow([
                    r.seq,
                    r.timestamp_ms,
                    r.utc_iso,
                    r.utc_date_str,
                    r.utc_time_str,
                    1 if r.fix_valid else 0,
                    f"{r.latitude_deg:.6f}",
                    f"{r.longitude_deg:.6f}",
                    f"{r.speed_kmh:.3f}",
                    f"{r.speed_ms:.3f}",
                    f"{r.course_deg:.2f}",
                ])

        return destination_file
