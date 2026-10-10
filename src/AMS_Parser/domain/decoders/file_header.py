"""Decoder for LOG_SRC_FILE_HEADER (0x01) records."""

import struct
from AMS_Parser.domain.enums import LogSourceId
from AMS_Parser.domain.models import FileHeaderRecord, LogRecordHeader


class FileHeaderPayloadDecoder:
    """Decodes packed file header payloads into FileHeaderRecord entities."""

    STRUCT_FORMAT = "<BBH"
    MIN_PAYLOAD_LEN = struct.calcsize(STRUCT_FORMAT)  # 4 bytes

    @property
    def source_id(self) -> int:
        return LogSourceId.FILE_HEADER

    def decode(self, header: LogRecordHeader, payload_bytes: bytes) -> FileHeaderRecord:
        if len(payload_bytes) < self.MIN_PAYLOAD_LEN:
            raise ValueError(
                f"File header payload too short: expected {self.MIN_PAYLOAD_LEN} bytes, got {len(payload_bytes)}"
            )

        fmt_ver, num_blocks, blk_sz = struct.unpack(self.STRUCT_FORMAT, payload_bytes[:self.MIN_PAYLOAD_LEN])
        return FileHeaderRecord(
            timestamp_ms=header.timestamp_ms,
            format_version=fmt_ver,
            pool_blocks=num_blocks,
            block_size_B=blk_sz,
        )
