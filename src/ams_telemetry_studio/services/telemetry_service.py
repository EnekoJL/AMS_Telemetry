"""Service bridging Hexagonal parser with Telemetry Studio API."""

import math
from pathlib import Path
from typing import List, Optional

from ams_log_parser.adapters.file_reader import ChunkedBinaryReaderAdapter
from ams_log_parser.application.registry import DecoderRegistry
from ams_log_parser.application.use_cases import ParseBinaryLogUseCase
from ams_log_parser.domain.models import GpsRecord
from ams_telemetry_studio.models import (
    GpsPointDTO,
    SessionResponseDTO,
    SessionSummary,
)


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class TelemetryStudioService:
    """Processes, enriches and caches motorsport telemetry sessions."""

    def __init__(self) -> None:
        self._reader = ChunkedBinaryReaderAdapter()
        self._registry = DecoderRegistry.create_default()
        self._use_case = ParseBinaryLogUseCase(
            reader=self._reader,
            registry=self._registry,
        )
        self._current_session: Optional[SessionResponseDTO] = None

    @property
    def current_session(self) -> Optional[SessionResponseDTO]:
        return self._current_session

    def process_file(self, file_path: Path) -> SessionResponseDTO:
        """Parses a binary log and enriches GPS records with distance and acceleration metrics."""
        result = self._use_case.execute(input_file=file_path)
        gps_raw = result.gps_records

        if not gps_raw:
            summary = SessionSummary(
                session_name=file_path.name,
                file_size_bytes=result.audit.file_size_bytes,
                total_blocks=result.audit.total_blocks,
                total_records=result.audit.total_records,
                gps_records=0,
                valid_gps_fixes=0,
                duration_s=0.0,
                total_distance_m=0.0,
                max_speed_kmh=0.0,
                avg_speed_kmh=0.0,
                start_utc="",
                end_utc="",
                sequence_gaps_count=len(result.audit.sequence_gaps),
            )
            response = SessionResponseDTO(summary=summary, points=[])
            self._current_session = response
            return response

        t0_ms = gps_raw[0].timestamp_ms
        cum_dist = 0.0
        enriched_points: List[GpsPointDTO] = []

        for i, rec in enumerate(gps_raw):
            rel_time_s = round((rec.timestamp_ms - t0_ms) / 1000.0, 3)

            # Compute segment distance
            if i > 0:
                prev_rec = gps_raw[i - 1]
                seg_m = _haversine_distance_m(
                    prev_rec.latitude_deg,
                    prev_rec.longitude_deg,
                    rec.latitude_deg,
                    rec.longitude_deg,
                )
                cum_dist += seg_m

                # Estimate longitudinal acceleration in G: a = (dv / dt) / 9.80665
                dt = (rec.timestamp_ms - prev_rec.timestamp_ms) / 1000.0
                dv_ms = rec.speed_ms - prev_rec.speed_ms
                accel_g = round((dv_ms / dt) / 9.80665, 2) if dt > 0.001 else 0.0
            else:
                accel_g = 0.0

            point = GpsPointDTO(
                seq=rec.seq,
                time_ms=rec.timestamp_ms,
                rel_time_s=rel_time_s,
                lat=round(rec.latitude_deg, 6),
                lon=round(rec.longitude_deg, 6),
                speed_kmh=round(rec.speed_kmh, 2),
                speed_ms=round(rec.speed_ms, 2),
                course_deg=round(rec.course_deg, 2),
                cum_dist_m=round(cum_dist, 1),
                utc_time=rec.utc_time_str,
                accel_g=accel_g,
            )
            enriched_points.append(point)

        duration_s = round((gps_raw[-1].timestamp_ms - t0_ms) / 1000.0, 2)
        max_speed = round(max(p.speed_kmh for p in enriched_points), 2)
        avg_speed = round(sum(p.speed_kmh for p in enriched_points) / len(enriched_points), 2)

        summary = SessionSummary(
            session_name=file_path.name,
            file_size_bytes=result.audit.file_size_bytes,
            total_blocks=result.audit.total_blocks,
            total_records=result.audit.total_records,
            gps_records=len(enriched_points),
            valid_gps_fixes=result.valid_gps_fixes,
            duration_s=duration_s,
            total_distance_m=round(cum_dist, 1),
            max_speed_kmh=max_speed,
            avg_speed_kmh=avg_speed,
            start_utc=gps_raw[0].utc_iso,
            end_utc=gps_raw[-1].utc_iso,
            sequence_gaps_count=len(result.audit.sequence_gaps),
        )

        response = SessionResponseDTO(summary=summary, points=enriched_points)
        self._current_session = response
        return response
