"""CLI Entrypoint for AMS Log Parser package."""

import argparse
from pathlib import Path
import sys
from typing import Optional, Sequence

from AMS_Parser.adapters.csv_exporter import CsvGpsExporterAdapter
from AMS_Parser.adapters.file_reader import ChunkedBinaryReaderAdapter
from AMS_Parser.application.dtos import ParseResultDTO
from AMS_Parser.application.registry import DecoderRegistry
from AMS_Parser.application.use_cases import ParseBinaryLogUseCase
from AMS_Parser.domain.enums import LogSourceId


def build_arg_parser() -> argparse.ArgumentParser:
    """Creates the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="ams-log-parser",
        description="Professional Hexagonal Parser for AMS Binary Telemetry Logs (*.bin)",
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        required=True,
        help="Path to the input binary log file (*.bin)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=Path("./output"),
        help="Destination directory for exported CSV files (default: ./output)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed diagnostic output",
    )
    return parser


def format_summary(result: ParseResultDTO) -> str:
    """Formats an ingestion summary report for CLI output."""
    audit = result.audit
    lines = []
    lines.append("=" * 80)
    lines.append(" AMS_PARSER — TELEMETRY INGESTION REPORT")
    lines.append("=" * 80)
    lines.append(f" File path:       {audit.source_file}")
    lines.append(f" File size:       {audit.file_size_bytes:,} bytes ({audit.file_size_bytes / 1024:.1f} KB)")
    lines.append(f" 4096-B blocks:   {audit.total_blocks} blocks")

    if result.file_header:
        hdr = result.file_header
        lines.append(f" Format version:  {hdr.format_version} (block size: {hdr.block_size_B} B, pool: {hdr.pool_blocks})")

    lines.append("-" * 80)
    lines.append(" RECORD BREAKDOWN:")
    for src_id, count in sorted(audit.record_counts.items()):
        name = LogSourceId.get_name(src_id)
        status = " (Decoded)" if src_id not in audit.unhandled_sources else " (Ignored/Unhandled)"
        lines.append(f"   [0x{src_id:02X}] {name:<16}: {count:,} records{status}")
    lines.append(f"   Total parsed:     {audit.total_records:,} records")

    # Sequence integrity
    lines.append("-" * 80)
    lines.append(" INTEGRITY AUDIT:")
    if not audit.sequence_gaps:
        lines.append("   Sequence check:   OK (100% monotonic, 0 gaps detected)")
    else:
        lines.append(f"   WARNING:          Detected {len(audit.sequence_gaps)} sequence counter gaps:")
        for last_seq, new_seq in audit.sequence_gaps[:5]:
            lines.append(f"     Gap: {last_seq} -> {new_seq}")
        if len(audit.sequence_gaps) > 5:
            lines.append(f"     ... and {len(audit.sequence_gaps) - 5} more gaps")

    # GPS metrics
    gps = result.gps_records
    lines.append("-" * 80)
    lines.append(f" GPS SUBSYSTEM ({len(gps):,} total records):")
    if gps:
        valid_fixes = result.valid_gps_fixes
        fix_pct = (valid_fixes / len(gps)) * 100.0 if gps else 0.0
        max_speed = max(r.speed_kmh for r in gps)
        avg_speed = sum(r.speed_kmh for r in gps) / len(gps)
        t_start = gps[0]
        t_end = gps[-1]
        dt_s = (t_end.timestamp_ms - t_start.timestamp_ms) / 1000.0 if t_end.timestamp_ms >= t_start.timestamp_ms else 0.0

        lines.append(f"   Valid fix ratio:  {valid_fixes:,} / {len(gps):,} ({fix_pct:.1f}%)")
        lines.append(f"   Max speed:        {max_speed:.2f} km/h")
        lines.append(f"   Average speed:    {avg_speed:.2f} km/h")
        lines.append(f"   Start UTC:        {t_start.utc_date_str} {t_start.utc_time_str} (tick: {t_start.timestamp_ms} ms)")
        lines.append(f"   End UTC:          {t_end.utc_date_str} {t_end.utc_time_str} (tick: {t_end.timestamp_ms} ms)")
        lines.append(f"   Session duration: {dt_s:.1f} s (~{dt_s / 60:.1f} min)")
    else:
        lines.append("   No GPS records found.")

    # Exported files
    lines.append("-" * 80)
    lines.append(" EXPORTED ARTIFACTS:")
    if result.exported_files:
        for f in result.exported_files:
            lines.append(f"   -> {f}")
    else:
        lines.append("   (None)")
    lines.append("=" * 80)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI execution flow."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Composition Root: Dependency Injection
    reader = ChunkedBinaryReaderAdapter()
    registry = DecoderRegistry.create_default()
    gps_exporter = CsvGpsExporterAdapter()

    use_case = ParseBinaryLogUseCase(
        reader=reader,
        registry=registry,
        gps_exporter=gps_exporter,
    )

    try:
        result = use_case.execute(
            input_file=args.input,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(format_summary(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
