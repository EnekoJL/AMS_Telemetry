"""Data Transfer Objects and Schemas for AMS Telemetry Studio."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SessionSummary(BaseModel):
    """Aggregate high-level session metrics."""
    session_name: str = Field(..., description="File name of the ingested binary log or dataset")
    file_size_bytes: int = 0
    total_blocks: int = 0
    total_records: int = 0
    gps_records: int = 0
    valid_gps_fixes: int = 0
    duration_s: float = 0.0
    total_distance_m: float = 0.0
    max_speed_kmh: float = 0.0
    avg_speed_kmh: float = 0.0
    start_utc: str = ""
    end_utc: str = ""
    sequence_gaps_count: int = 0
    loaded_channels: List[str] = Field(default_factory=list)


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


class AdcPointDTO(BaseModel):
    """Analog sensor point (suspensions, 12V bus, MCU temperature)."""
    time_ms: int
    rel_time_s: float
    susp_front_mm: float
    susp_rear_mm: float
    susp_front_mv: int
    susp_rear_mv: int
    batt_12v_v: float
    mcu_temp_c: float


class BmsPointDTO(BaseModel):
    """Battery Management System measurement point (LTC6813)."""
    time_ms: int
    rel_time_s: float
    pack_voltage_v: float
    pack_current_a: float
    soc_percent: float
    cell_min_v: float
    cell_max_v: float
    cell_temp_max_c: float


class InverterPointDTO(BaseModel):
    """Powertrain inverter CAN point (Sevcon)."""
    time_ms: int
    rel_time_s: float
    motor_rpm: int
    motor_temp_c: float
    inverter_temp_c: float
    torque_nm: float


class TelemetryChannelsDTO(BaseModel):
    """Multi-channel synchronized telemetry streams."""
    has_gps: bool = False
    has_adc: bool = False
    has_bms: bool = False
    has_inverter: bool = False
    gps: List[GpsPointDTO] = Field(default_factory=list)
    adc: List[AdcPointDTO] = Field(default_factory=list)
    bms: List[BmsPointDTO] = Field(default_factory=list)
    inverter: List[InverterPointDTO] = Field(default_factory=list)


class SessionResponseDTO(BaseModel):
    """Complete session payload for the motorsport telemetry studio."""
    summary: SessionSummary
    points: List[GpsPointDTO] = Field(default_factory=list)
    channels: TelemetryChannelsDTO = Field(default_factory=TelemetryChannelsDTO)
