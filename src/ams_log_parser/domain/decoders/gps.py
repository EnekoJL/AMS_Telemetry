"""Decoder for LOG_SRC_GPS_RMC (0x30) records."""

import struct
from ams_log_parser.domain.enums import LogSourceId
from ams_log_parser.domain.models import GpsRecord, LogRecordHeader


class GpsPayloadDecoder:
    """Decodes packed GPS RMC payloads into GpsRecord domain entities."""

    # struct LogPayloadGps_t: int32 lat, int32 lon, int32 vel, uint32 utc_ms, uint16 course, uint16 year, uint8 mon, uint8 day, uint8 fix
    STRUCT_FORMAT = "<iiiIHHBBB"
    MIN_PAYLOAD_LEN = struct.calcsize(STRUCT_FORMAT)  # 23 bytes

    @property
    def source_id(self) -> int:
        return LogSourceId.GPS_RMC

    def decode(self, header: LogRecordHeader, payload_bytes: bytes) -> GpsRecord:
        if len(payload_bytes) < self.MIN_PAYLOAD_LEN:
            raise ValueError(
                f"GPS payload too short: expected at least {self.MIN_PAYLOAD_LEN} bytes, got {len(payload_bytes)}"
            )

        (
            lat_udeg,
            lon_udeg,
            vel_kmh_x1000,
            utc_ms,
            course_cdeg,
            year,
            month,
            day,
            fix_valid,
        ) = struct.unpack(self.STRUCT_FORMAT, payload_bytes[:self.MIN_PAYLOAD_LEN])

        return GpsRecord(
            timestamp_ms=header.timestamp_ms,
            seq=header.seq,
            latitude_deg=lat_udeg / 1_000_000.0,
            longitude_deg=lon_udeg / 1_000_000.0,
            speed_kmh=vel_kmh_x1000 / 1_000.0,
            course_deg=course_cdeg / 100.0,
            utc_time_of_day_ms=utc_ms,
            year=year,
            month=month,
            day=day,
            fix_valid=bool(fix_valid),
        )
