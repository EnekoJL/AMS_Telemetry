"""End-to-End integration test using real STM32 black-box binary log."""

import csv
from pathlib import Path
import pytest

from ams_log_parser.adapters.csv_exporter import CsvGpsExporterAdapter
from ams_log_parser.adapters.file_reader import ChunkedBinaryReaderAdapter
from ams_log_parser.application.registry import DecoderRegistry
from ams_log_parser.application.use_cases import ParseBinaryLogUseCase


def test_real_log_file_ingestion(tmp_path: Path):
    candidates = [
        Path(__file__).resolve().parents[1] / "data" / "sample" / "20261010_144951.bin",
        Path(__file__).resolve().parents[1] / "20261010_144951.bin",
        Path(__file__).resolve().parents[2] / "tests" / "20261010_144951.bin",
    ]
    real_bin_file = next((p for p in candidates if p.is_file()), None)
    if real_bin_file is None:
        pytest.skip("Real hardware test fixture not found")

    reader = ChunkedBinaryReaderAdapter()
    registry = DecoderRegistry.create_default()
    exporter = CsvGpsExporterAdapter()

    use_case = ParseBinaryLogUseCase(
        reader=reader,
        registry=registry,
        gps_exporter=exporter,
    )

    output_dir = tmp_path / "csv_out"
    result = use_case.execute(input_file=real_bin_file, output_dir=output_dir)

    # 1. Audit assertions
    assert result.audit.total_blocks == 49
    assert result.audit.file_size_bytes == 200_704
    assert result.audit.total_records == 2353
    assert len(result.audit.sequence_gaps) == 0

    # 2. Source distribution assertions
    assert result.audit.record_counts[0x01] == 1     # FILE_HEADER
    assert result.audit.record_counts[0x30] == 2303  # GPS_RMC
    assert result.audit.record_counts[0xF0] == 49    # LOGGER_STATS

    # 3. GPS data integrity assertions
    assert len(result.gps_records) == 2303
    assert result.valid_gps_fixes == 2303
    first_gps = result.gps_records[0]
    last_gps = result.gps_records[-1]

    # Motorland Aragon coordinates
    assert pytest.approx(first_gps.latitude_deg, abs=0.01) == 41.079
    assert pytest.approx(first_gps.longitude_deg, abs=0.01) == -0.200
    assert first_gps.speed_kmh > 0
    assert first_gps.utc_date_str == "2026-10-10"
    assert first_gps.utc_time_str == "14:49:51.390"

    # 4. CSV file verification
    csv_path = output_dir / "gps_telemetry.csv"
    assert csv_path.is_file()
    assert csv_path in result.exported_files

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == [
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
        rows = list(reader)
        assert len(rows) == 2303
        assert rows[0][0] == "1"
        assert rows[0][1] == "15636"
        assert rows[0][2] == "2026-10-10T14:49:51.390Z"
        assert rows[0][5] == "1"
        assert rows[0][6] == "41.079492"
        assert rows[0][7] == "-0.200745"
