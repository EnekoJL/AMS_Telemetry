"""Decoder for LOG_SRC_LOGGER_STATS (0xF0) records."""

import struct
from AMS_Parser.domain.enums import LogSourceId
from AMS_Parser.domain.models import LogRecordHeader, LoggerStatsRecord


class StatsPayloadDecoder:
    """Decodes packed logger statistics payloads into LoggerStatsRecord entities."""

    STRUCT_FORMAT = "<IHHHBB"
    MIN_PAYLOAD_LEN = struct.calcsize(STRUCT_FORMAT)  # 12 bytes

    @property
    def source_id(self) -> int:
        return LogSourceId.LOGGER_STATS

    def decode(self, header: LogRecordHeader, payload_bytes: bytes) -> LoggerStatsRecord:
        if len(payload_bytes) < self.MIN_PAYLOAD_LEN:
            raise ValueError(
                f"Stats payload too short: expected {self.MIN_PAYLOAD_LEN} bytes, got {len(payload_bytes)}"
            )

        dropped, max_wr_ms, max_sync_ms, faults, full_cnt, wr_err = struct.unpack(
            self.STRUCT_FORMAT, payload_bytes[:self.MIN_PAYLOAD_LEN]
        )
        return LoggerStatsRecord(
            timestamp_ms=header.timestamp_ms,
            dropped_records=dropped,
            max_write_ms=max_wr_ms,
            max_sync_ms=max_sync_ms,
            broker_faults=faults,
            pool_full_max=full_cnt,
            write_errors=wr_err,
        )
