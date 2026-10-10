"""Data Transfer Objects and Schemas for AMS Telemetry Studio."""

from typing import List
from pydantic import BaseModel, Field


class SessionSummary(BaseModel):
    """Aggregate high-level session metrics."""
    session_name: str = Field(..., description="File name of the ingested binary log")
    file_size_bytes: int
    total_blocks: int
    total_records: int
    gps_records: int
    valid_gps_fixes: int
    duration_s: float
    total_distance_m: float
    max_speed_kmh: float
    avg_speed_kmh: float
    start_utc: str
    end_utc: str
    sequence_gaps_count: int


class GpsPointDTO(BaseModel):
    """Individual high-frequency GPS telemetry point."""
    seq: int
    time_ms: int
    rel_time_s: float
    lat: float
    lon: float
    speed_kmh: float
    speed_ms: float
    course_deg: float
    cum_dist_m: float
    utc_time: str
    accel_g: float = 0.0


class SessionResponseDTO(BaseModel):
    """Complete session payload for the dashboard."""
    summary: SessionSummary
    points: List[GpsPointDTO]
