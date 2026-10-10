"""Unit tests for GpsPayloadDecoder and GpsRecord model."""

import pytest

from ams_log_parser.domain.decoders.gps import GpsPayloadDecoder
from ams_log_parser.domain.enums import LogSourceId
from ams_log_parser.domain.models import LogRecordHeader
from tests.conftest import make_gps_payload


def test_gps_decoder_successful():
    decoder = GpsPayloadDecoder()
    assert decoder.source_id == LogSourceId.GPS_RMC

    header = LogRecordHeader(timestamp_ms=15636, seq=1, source_id=LogSourceId.GPS_RMC, payload_len=23)
    payload = make_gps_payload(
        lat_udeg=41079492,
        lon_udeg=-200745,
        vel_kmh_x1000=126250,
        utc_ms=53391390,  # 14:49:51.390
        course_cdeg=22206,
        year=2026,
        month=10,
        day=10,
        fix_valid=1,
    )

    record = decoder.decode(header, payload)
    assert record.timestamp_ms == 15636
    assert record.seq == 1
    assert pytest.approx(record.latitude_deg, rel=1e-6) == 41.079492
    assert pytest.approx(record.longitude_deg, rel=1e-6) == -0.200745
    assert pytest.approx(record.speed_kmh, rel=1e-5) == 126.250
    assert pytest.approx(record.speed_ms, rel=1e-5) == 126.250 / 3.6
    assert pytest.approx(record.course_deg, rel=1e-4) == 222.06
    assert record.fix_valid is True
    assert record.year == 2026
    assert record.month == 10
    assert record.day == 10
    assert record.utc_date_str == "2026-10-10"
    assert record.utc_time_str == "14:49:51.390"
    assert record.utc_iso == "2026-10-10T14:49:51.390Z"


def test_gps_decoder_invalid_fix():
    decoder = GpsPayloadDecoder()
    header = LogRecordHeader(timestamp_ms=1000, seq=5, source_id=LogSourceId.GPS_RMC, payload_len=23)
    payload = make_gps_payload(fix_valid=0)

    record = decoder.decode(header, payload)
    assert record.fix_valid is False


def test_gps_decoder_payload_too_short():
    decoder = GpsPayloadDecoder()
    header = LogRecordHeader(timestamp_ms=1000, seq=5, source_id=LogSourceId.GPS_RMC, payload_len=10)
    truncated_payload = b"\x00" * 10

    with pytest.raises(ValueError, match="GPS payload too short"):
        decoder.decode(header, truncated_payload)
