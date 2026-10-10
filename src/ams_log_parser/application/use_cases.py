"""Application use case for binary log parsing and telemetry dispatch."""

import struct
from pathlib import Path
from typing import List, Optional

from ams_log_parser.application.dtos import ParseResultDTO
from ams_log_parser.application.registry import DecoderRegistry
from ams_log_parser.domain.enums import (
    LOG_BLOCK_SIZE_B,
    LOG_HEADER_SIZE_B,
    LogSourceId,
)
from ams_log_parser.domain.models import (
    FileHeaderRecord,
    GpsRecord,
    LogRecordHeader,
    LoggerStatsRecord,
    ParsingAudit,
)
from ams_log_parser.ports.exporter_port import TelemetryExporterPort
from ams_log_parser.ports.reader_port import BinaryReaderPort


class ParseBinaryLogUseCase:
    """Orchestrates streaming ingestion, validation, decoding and export.
    
    Adheres to the Dependency Inversion Principle (DIP): depends only on
    injected ports and registry abstractions, completely decoupled from
    GUI, storage mechanisms or file formats.
    """

    HEADER_STRUCT_FORMAT = "<IHBB"

    def __init__(
        self,
        reader: BinaryReaderPort,
        registry: DecoderRegistry,
        gps_exporter: Optional[TelemetryExporterPort[GpsRecord]] = None,
    ) -> None:
        self._reader = reader
        self._registry = registry
        self._gps_exporter = gps_exporter

    def execute(self, input_file: Path, output_dir: Optional[Path] = None) -> ParseResultDTO:
        """Executes streaming parse of the given binary log file."""
        if not input_file.is_file():
            raise FileNotFoundError(f"Binary log file not found: {input_file}")

        file_size = self._reader.get_file_size(input_file)
        total_blocks = file_size // LOG_BLOCK_SIZE_B

        audit = ParsingAudit(
            source_file=str(input_file),
            file_size_bytes=file_size,
            total_blocks=total_blocks,
        )

        file_header: Optional[FileHeaderRecord] = None
        gps_records: List[GpsRecord] = []
        stats_records: List[LoggerStatsRecord] = []
        last_seq: Optional[int] = None

        # Process file block-by-block using streaming generator
        for block in self._reader.stream_blocks(input_file):
            block_len = len(block)
            offset = 0

            while offset + LOG_HEADER_SIZE_B <= block_len:
                hdr_bytes = block[offset : offset + LOG_HEADER_SIZE_B]
                timestamp_ms, seq, source_id, payload_len = struct.unpack(
                    self.HEADER_STRUCT_FORMAT, hdr_bytes
                )

                # Spec Rule: if source_id is 0x00 (PAD), jump to the next 4096-B block
                if source_id == LogSourceId.PAD:
                    break

                offset += LOG_HEADER_SIZE_B

                # Discard corrupted/truncated record at block tail
                if offset + payload_len > block_len:
                    break

                payload_bytes = block[offset : offset + payload_len]
                offset += payload_len

                # Audit sequence continuity (gap check)
                if last_seq is not None:
                    expected_seq = (last_seq + 1) & 0xFFFF
                    if seq != expected_seq and seq != last_seq:
                        audit.sequence_gaps.append((last_seq, seq))
                last_seq = seq

                # Record source count audit
                audit.record_counts[source_id] = audit.record_counts.get(source_id, 0) + 1

                # Polymorphic decoding via registry (OCP)
                header = LogRecordHeader(
                    timestamp_ms=timestamp_ms,
                    seq=seq,
                    source_id=source_id,
                    payload_len=payload_len,
                )

                decoder = self._registry.get(source_id)
                if decoder is not None:
                    try:
                        decoded_record = decoder.decode(header, payload_bytes)
                        if isinstance(decoded_record, GpsRecord):
                            gps_records.append(decoded_record)
                        elif isinstance(decoded_record, FileHeaderRecord):
                            file_header = decoded_record
                        elif isinstance(decoded_record, LoggerStatsRecord):
                            stats_records.append(decoded_record)
                    except Exception:
                        # Resilient parsing: unparseable single records never break stream
                        continue
                else:
                    # Heterogeneous sources (CAN, BMS, etc.): gracefully ignored
                    audit.unhandled_sources.add(source_id)

        exported_files: List[Path] = []
        if output_dir is not None and self._gps_exporter is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            gps_target = output_dir / "gps_telemetry.csv"
            exported_path = self._gps_exporter.export(gps_records, gps_target)
            exported_files.append(exported_path)

        return ParseResultDTO(
            audit=audit,
            file_header=file_header,
            gps_records=gps_records,
            stats_records=stats_records,
            exported_files=exported_files,
        )
