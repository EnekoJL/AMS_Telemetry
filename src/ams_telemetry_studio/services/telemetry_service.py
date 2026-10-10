"""Service bridging Hexagonal parser and multi-channel telemetry streams with Telemetry Studio API."""

import csv
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from AMS_Parser.adapters.file_reader import ChunkedBinaryReaderAdapter
from AMS_Parser.application.registry import DecoderRegistry
from AMS_Parser.application.use_cases import ParseBinaryLogUseCase
from AMS_Parser.domain.models import GpsRecord
from ams_telemetry_studio.models import (
    AdcPointDTO,
    BmsPointDTO,
    GpsPointDTO,
    InverterPointDTO,
    SessionResponseDTO,
    SessionSummary,
    TelemetryChannelsDTO,
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
    """Processes, enriches, temporal-aligns and caches multi-channel motorsport telemetry sessions."""

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

    def process_file(self, file_path: Path, companion_dir: Optional[Path] = None) -> SessionResponseDTO:
        """Parses a binary log and automatically loads companion CSV telemetry if available."""
        result = self._use_case.execute(input_file=file_path)
        gps_raw = result.gps_records

        gps_points: List[GpsPointDTO] = []
        t0_ms = gps_raw[0].timestamp_ms if gps_raw else 0
        cum_dist = 0.0

        for i, rec in enumerate(gps_raw):
            rel_time_s = round((rec.timestamp_ms - t0_ms) / 1000.0, 3)

            if i > 0:
                prev_rec = gps_raw[i - 1]
                seg_m = _haversine_distance_m(
                    prev_rec.latitude_deg,
                    prev_rec.longitude_deg,
                    rec.latitude_deg,
                    rec.longitude_deg,
                )
                cum_dist += seg_m
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
            gps_points.append(point)

        channels = TelemetryChannelsDTO(
            has_gps=bool(gps_points),
            gps=gps_points,
        )

        loaded_names = ["GPS"] if gps_points else []

        # Check for companions (e.g. in telemetry/ or next to file)
        candidate_dirs = []
        if companion_dir and companion_dir.is_dir():
            candidate_dirs.append(companion_dir)
        candidate_dirs.append(file_path.parent)
        # Also check standard telemetry/ locations
        project_root = Path(__file__).resolve().parents[3]
        candidate_dirs.append(project_root / "telemetry")
        candidate_dirs.append(Path(__file__).resolve().parents[2] / "telemetry")

        self._check_and_load_companions(channels, candidate_dirs, loaded_names)

        # Align relative time base across all loaded channels
        self._align_timebases(channels)

        duration_s = (
            round((gps_points[-1].time_ms - gps_points[0].time_ms) / 1000.0, 2)
            if gps_points
            else self._calculate_channels_duration(channels)
        )
        max_speed = round(max((p.speed_kmh for p in gps_points), default=0.0), 2)
        avg_speed = round(sum(p.speed_kmh for p in gps_points) / len(gps_points), 2) if gps_points else 0.0

        summary = SessionSummary(
            session_name=file_path.name,
            file_size_bytes=result.audit.file_size_bytes,
            total_blocks=result.audit.total_blocks,
            total_records=result.audit.total_records,
            gps_records=len(gps_points),
            valid_gps_fixes=result.valid_gps_fixes,
            duration_s=duration_s,
            total_distance_m=round(cum_dist, 1),
            max_speed_kmh=max_speed,
            avg_speed_kmh=avg_speed,
            start_utc=gps_raw[0].utc_iso if gps_raw else "",
            end_utc=gps_raw[-1].utc_iso if gps_raw else "",
            sequence_gaps_count=len(result.audit.sequence_gaps),
            loaded_channels=loaded_names,
        )

        response = SessionResponseDTO(summary=summary, points=gps_points, channels=channels)
        self._current_session = response
        return response

    def ingest_files(self, file_paths: List[Path], session_name: Optional[str] = None) -> SessionResponseDTO:
        """Ingests a collection of files (.bin and/or .csv) modularly into a unified session."""
        channels = TelemetryChannelsDTO()
        loaded_names: List[str] = []
        total_size = 0
        bin_result = None
        cum_dist = 0.0

        for path in file_paths:
            total_size += path.stat().st_size if path.is_file() else 0
            ext = path.suffix.lower()

            if ext == ".bin":
                bin_result = self._use_case.execute(input_file=path)
                gps_raw = bin_result.gps_records
                t0_ms = gps_raw[0].timestamp_ms if gps_raw else 0
                cum_dist = 0.0
                gps_points: List[GpsPointDTO] = []
                for i, rec in enumerate(gps_raw):
                    rel_time_s = round((rec.timestamp_ms - t0_ms) / 1000.0, 3)
                    if i > 0:
                        prev = gps_raw[i - 1]
                        cum_dist += _haversine_distance_m(prev.latitude_deg, prev.longitude_deg, rec.latitude_deg, rec.longitude_deg)
                        dt = (rec.timestamp_ms - prev.timestamp_ms) / 1000.0
                        dv = rec.speed_ms - prev.speed_ms
                        acc = round((dv / dt) / 9.80665, 2) if dt > 0.001 else 0.0
                    else:
                        acc = 0.0

                    gps_points.append(GpsPointDTO(
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
                        accel_g=acc,
                    ))
                channels.has_gps = bool(gps_points)
                channels.gps = gps_points
                if "GPS" not in loaded_names:
                    loaded_names.append("GPS")

            elif ext == ".csv":
                ch_type = self._detect_csv_type(path)
                if ch_type == "adc":
                    channels.adc = self.parse_adc_csv(path)
                    channels.has_adc = bool(channels.adc)
                    if "ADC" not in loaded_names:
                        loaded_names.append("ADC")
                elif ch_type == "bms":
                    channels.bms = self.parse_bms_csv(path)
                    channels.has_bms = bool(channels.bms)
                    if "BMS" not in loaded_names:
                        loaded_names.append("BMS")
                elif ch_type == "inverter":
                    channels.inverter = self.parse_inverter_csv(path)
                    channels.has_inverter = bool(channels.inverter)
                    if "Inversor" not in loaded_names:
                        loaded_names.append("Inversor")
                elif ch_type == "gps":
                    channels.gps = self.parse_gps_csv(path)
                    channels.has_gps = bool(channels.gps)
                    if "GPS" not in loaded_names:
                        loaded_names.append("GPS")

        self._align_timebases(channels)

        duration_s = self._calculate_channels_duration(channels)
        max_speed = round(max((p.speed_kmh for p in channels.gps), default=0.0), 2)
        avg_speed = round(sum(p.speed_kmh for p in channels.gps) / len(channels.gps), 2) if channels.gps else 0.0

        resolved_name = session_name or (file_paths[0].name if len(file_paths) == 1 else f"Multi-sesión ({len(file_paths)} archivos)")

        summary = SessionSummary(
            session_name=resolved_name,
            file_size_bytes=total_size,
            total_blocks=bin_result.audit.total_blocks if bin_result else 0,
            total_records=bin_result.audit.total_records if bin_result else sum([
                len(channels.gps), len(channels.adc), len(channels.bms), len(channels.inverter)
            ]),
            gps_records=len(channels.gps),
            valid_gps_fixes=bin_result.valid_gps_fixes if bin_result else len(channels.gps),
            duration_s=duration_s,
            total_distance_m=round(cum_dist, 1),
            max_speed_kmh=max_speed,
            avg_speed_kmh=avg_speed,
            start_utc=channels.gps[0].utc_time if channels.gps else "",
            end_utc=channels.gps[-1].utc_time if channels.gps else "",
            sequence_gaps_count=len(bin_result.audit.sequence_gaps) if bin_result else 0,
            loaded_channels=loaded_names,
        )

        response = SessionResponseDTO(summary=summary, points=channels.gps, channels=channels)
        self._current_session = response
        return response

    def _check_and_load_companions(
        self,
        channels: TelemetryChannelsDTO,
        candidate_dirs: List[Path],
        loaded_names: List[str],
    ) -> None:
        """Looks for companion CSV files across candidate directories."""
        for d in candidate_dirs:
            if not d.is_dir():
                continue

            adc_candidate = d / "adc_sensors.csv"
            if not channels.has_adc and adc_candidate.is_file():
                channels.adc = self.parse_adc_csv(adc_candidate)
                channels.has_adc = bool(channels.adc)
                if channels.has_adc and "ADC" not in loaded_names:
                    loaded_names.append("ADC")

            bms_candidate = d / "bms_battery.csv"
            if not channels.has_bms and bms_candidate.is_file():
                channels.bms = self.parse_bms_csv(bms_candidate)
                channels.has_bms = bool(channels.bms)
                if channels.has_bms and "BMS" not in loaded_names:
                    loaded_names.append("BMS")

            inv_candidate = d / "inverter_can.csv"
            if not channels.has_inverter and inv_candidate.is_file():
                channels.inverter = self.parse_inverter_csv(inv_candidate)
                channels.has_inverter = bool(channels.inverter)
                if channels.has_inverter and "Inversor" not in loaded_names:
                    loaded_names.append("Inversor")

    def _detect_csv_type(self, path: Path) -> str:
        """Inspects CSV headers to identify telemetry domain."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                header_line = f.readline().lower()
            if "susp_" in header_line or "fork" in header_line or "shock" in header_line or "batt_12v" in header_line:
                return "adc"
            if "pack_voltage" in header_line or "cell_min" in header_line or "cell_temp" in header_line:
                return "bms"
            if "motor_rpm" in header_line or "torque" in header_line or "inverter_temp" in header_line:
                return "inverter"
            if "lat" in header_line and "lon" in header_line:
                return "gps"
        except Exception:
            pass

        # Fallback to file name heuristic
        fname = path.name.lower()
        if "adc" in fname or "sensor" in fname:
            return "adc"
        if "bms" in fname or "batt" in fname:
            return "bms"
        if "inverter" in fname or "can" in fname or "sevcon" in fname:
            return "inverter"
        if "gps" in fname:
            return "gps"
        return "unknown"

    def parse_adc_csv(self, path: Path) -> List[AdcPointDTO]:
        """Parses an ADC sensors CSV file into strongly typed DTOs."""
        points: List[AdcPointDTO] = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    t_ms = int(row.get("timestamp_ms", 0))
                    susp_front_mm = float(row.get("susp_front_mm", row.get("fork_mm", 0.0)))
                    susp_rear_mm = float(row.get("susp_rear_mm", row.get("shock_mm", 0.0)))
                    susp_front_mv = int(float(row.get("susp_front_mv", 0)))
                    susp_rear_mv = int(float(row.get("susp_rear_mv", 0)))
                    batt_12v_v = float(row.get("batt_12v_v", float(row.get("batt_12v_mv", 0)) / 1000.0))
                    mcu_temp_c = float(row.get("mcu_temp_c", 0.0))
                    points.append(AdcPointDTO(
                        time_ms=t_ms,
                        rel_time_s=0.0,
                        susp_front_mm=susp_front_mm,
                        susp_rear_mm=susp_rear_mm,
                        susp_front_mv=susp_front_mv,
                        susp_rear_mv=susp_rear_mv,
                        batt_12v_v=batt_12v_v,
                        mcu_temp_c=mcu_temp_c,
                    ))
                except (ValueError, TypeError):
                    continue
        return points

    def parse_bms_csv(self, path: Path) -> List[BmsPointDTO]:
        """Parses a BMS battery CSV file into strongly typed DTOs."""
        points: List[BmsPointDTO] = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    t_ms = int(row.get("timestamp_ms", 0))
                    pack_voltage_v = float(row.get("pack_voltage_v", 0.0))
                    pack_current_a = float(row.get("pack_current_a", 0.0))
                    soc_percent = float(row.get("soc_percent", 0.0))
                    cell_min_v = float(row.get("cell_min_v", 0.0))
                    cell_max_v = float(row.get("cell_max_v", 0.0))
                    cell_temp_max_c = float(row.get("cell_temp_max_c", 0.0))
                    points.append(BmsPointDTO(
                        time_ms=t_ms,
                        rel_time_s=0.0,
                        pack_voltage_v=pack_voltage_v,
                        pack_current_a=pack_current_a,
                        soc_percent=soc_percent,
                        cell_min_v=cell_min_v,
                        cell_max_v=cell_max_v,
                        cell_temp_max_c=cell_temp_max_c,
                    ))
                except (ValueError, TypeError):
                    continue
        return points

    def parse_inverter_csv(self, path: Path) -> List[InverterPointDTO]:
        """Parses an Inverter CAN CSV file into strongly typed DTOs."""
        points: List[InverterPointDTO] = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    t_ms = int(row.get("timestamp_ms", 0))
                    motor_rpm = int(float(row.get("motor_rpm", 0)))
                    motor_temp_c = float(row.get("motor_temp_c", 0.0))
                    inverter_temp_c = float(row.get("inverter_temp_c", 0.0))
                    torque_nm = float(row.get("torque_nm", 0.0))
                    points.append(InverterPointDTO(
                        time_ms=t_ms,
                        rel_time_s=0.0,
                        motor_rpm=motor_rpm,
                        motor_temp_c=motor_temp_c,
                        inverter_temp_c=inverter_temp_c,
                        torque_nm=torque_nm,
                    ))
                except (ValueError, TypeError):
                    continue
        return points

    def parse_gps_csv(self, path: Path) -> List[GpsPointDTO]:
        """Parses a standalone GPS CSV file."""
        points: List[GpsPointDTO] = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cum_dist = 0.0
            prev_lat, prev_lon = None, None
            for idx, row in enumerate(reader):
                try:
                    t_ms = int(row.get("timestamp_ms", row.get("time_ms", 0)))
                    lat = float(row.get("lat", row.get("latitude", 0.0)))
                    lon = float(row.get("lon", row.get("longitude", 0.0)))
                    speed_kmh = float(row.get("speed_kmh", 0.0))
                    course = float(row.get("course_deg", 0.0))
                    utc_time = row.get("utc_time", "")

                    if prev_lat is not None:
                        cum_dist += _haversine_distance_m(prev_lat, prev_lon, lat, lon)
                    prev_lat, prev_lon = lat, lon

                    points.append(GpsPointDTO(
                        seq=idx,
                        time_ms=t_ms,
                        rel_time_s=0.0,
                        lat=lat,
                        lon=lon,
                        speed_kmh=speed_kmh,
                        speed_ms=round(speed_kmh / 3.6, 2),
                        course_deg=course,
                        cum_dist_m=round(cum_dist, 1),
                        utc_time=utc_time,
                        accel_g=0.0,
                    ))
                except (ValueError, TypeError):
                    continue
        return points

    def _align_timebases(self, channels: TelemetryChannelsDTO) -> None:
        """Finds global t0 and computes synchronized rel_time_s across all active channels."""
        t0_candidates: List[int] = []
        if channels.gps:
            t0_candidates.append(channels.gps[0].time_ms)
        if channels.adc:
            t0_candidates.append(channels.adc[0].time_ms)
        if channels.bms:
            t0_candidates.append(channels.bms[0].time_ms)
        if channels.inverter:
            t0_candidates.append(channels.inverter[0].time_ms)

        if not t0_candidates:
            return

        t0_global = min(t0_candidates)

        for p in channels.gps:
            p.rel_time_s = round((p.time_ms - t0_global) / 1000.0, 3)
        for p in channels.adc:
            p.rel_time_s = round((p.time_ms - t0_global) / 1000.0, 3)
        for p in channels.bms:
            p.rel_time_s = round((p.time_ms - t0_global) / 1000.0, 3)
        for p in channels.inverter:
            p.rel_time_s = round((p.time_ms - t0_global) / 1000.0, 3)

    def _calculate_channels_duration(self, channels: TelemetryChannelsDTO) -> float:
        """Computes the overall time span covered by any active channel in seconds."""
        t_starts: List[int] = []
        t_ends: List[int] = []
        for ch in [channels.gps, channels.adc, channels.bms, channels.inverter]:
            if ch:
                t_starts.append(ch[0].time_ms)
                t_ends.append(ch[-1].time_ms)
        if not t_starts or not t_ends:
            return 0.0
        return round((max(t_ends) - min(t_starts)) / 1000.0, 2)
