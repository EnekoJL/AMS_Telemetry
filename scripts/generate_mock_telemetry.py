#!/usr/bin/env python3
"""Generates realistic synthetic multi-channel telemetry correlated with real GPS data.

Models physical sensors conforming to STM32 firmware architecture:
- LOG_SRC_SENSORS_ADC (0x20): 25 Hz (40 ms) - Front fork & rear shock travel/voltages, 12V bus, MCU temp.
- LOG_SRC_BMS_SPI (0x40): 10 Hz (100 ms) - Pack voltage, pack current, SoC, min/max cell V, max cell temp.
- LOG_SRC_CAN_INVERTER (0x10): 50 Hz (20 ms) - Motor RPM, motor temp, inverter temp, motor torque.

Correlated against reference log: 20261010_144951.bin (t0 = 15636 ms, t_end = 113653 ms).
"""

import argparse
import csv
import math
from pathlib import Path
import sys
from typing import Dict, List, Tuple

# Ensure we can import AMS_Parser from src
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent  # tools/AMS_Telemetry
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from AMS_Parser.adapters.file_reader import ChunkedBinaryReaderAdapter
    from AMS_Parser.application.registry import DecoderRegistry
    from AMS_Parser.application.use_cases import ParseBinaryLogUseCase
except ImportError:
    from ams_log_parser.adapters.file_reader import ChunkedBinaryReaderAdapter
    from ams_log_parser.application.registry import DecoderRegistry
    from ams_log_parser.application.use_cases import ParseBinaryLogUseCase


def load_gps_reference_profile(bin_path: Path) -> Tuple[List[int], List[float], List[float]]:
    """Loads GPS timestamps, speeds (km/h) and computes longitudinal acceleration (G)."""
    reader = ChunkedBinaryReaderAdapter()
    registry = DecoderRegistry.create_default()
    use_case = ParseBinaryLogUseCase(reader, registry)
    result = use_case.execute(bin_path)

    if not result.gps_records:
        raise ValueError(f"No GPS records found in {bin_path}")

    times_ms = [r.timestamp_ms for r in result.gps_records]
    speeds_kmh = [r.speed_kmh for r in result.gps_records]

    # Compute longitudinal acceleration G
    accels_g: List[float] = [0.0]
    for i in range(1, len(times_ms)):
        dt_s = (times_ms[i] - times_ms[i - 1]) / 1000.0
        dv_ms = (speeds_kmh[i] - speeds_kmh[i - 1]) / 3.6
        if dt_s > 0.001:
            g = (dv_ms / dt_s) / 9.80665
            # Clamp realistic motorcycle acceleration (-1.5 G braking to +1.2 G acceleration)
            g = max(-1.5, min(1.2, g))
        else:
            g = 0.0
        accels_g.append(g)

    return times_ms, speeds_kmh, accels_g


def interpolate_signal(t: float, x_series: List[int], y_series: List[float]) -> float:
    """Linear interpolation of a signal at time t."""
    if t <= x_series[0]:
        return y_series[0]
    if t >= x_series[-1]:
        return y_series[-1]

    # Binary search
    low = 0
    high = len(x_series) - 1
    while low <= high:
        mid = (low + high) // 2
        if x_series[mid] <= t:
            low = mid + 1
        else:
            high = mid - 1

    idx0 = max(0, high)
    idx1 = min(len(x_series) - 1, idx0 + 1)
    if idx0 == idx1 or x_series[idx1] == x_series[idx0]:
        return y_series[idx0]

    frac = (t - x_series[idx0]) / (x_series[idx1] - x_series[idx0])
    return y_series[idx0] + frac * (y_series[idx1] - y_series[idx0])


def generate_adc_telemetry(
    times_ms: List[int],
    speeds_kmh: List[float],
    accels_g: List[float],
    out_file: Path,
) -> None:
    """Generates telemetry/adc_sensors.csv at 25 Hz (40 ms step).

    Hardware formulas from Core/Src/Algorithms/AMS_sensors.c:
      RANGO_POT_SUSP_1_MM = 150 mm
      RANGO_POT_SUSP_2_MM = 50 mm
      VOLTAJE_ALIMENTACION_POT_MV = 5000 mV
      travel_dmm = (pot_mV * range_mm * 10) / 5000
      pot_mV = (pin_mV * 139) / 100
    """
    t0 = times_ms[0]
    tend = times_ms[-1]
    step_ms = 40  # 25 Hz

    rows = []
    t = t0
    sample_idx = 0
    while t <= tend:
        progress = (t - t0) / (tend - t0) if tend > t0 else 0.0
        speed = interpolate_signal(t, times_ms, speeds_kmh)
        accel = interpolate_signal(t, times_ms, accels_g)

        # High-frequency road chatter / vibration
        chatter = 1.2 * math.sin(sample_idx * 0.45) + 0.6 * math.cos(sample_idx * 1.1)

        # Front fork: static sag ~35mm. Under braking (accel < 0), fork compresses heavily (up to 135mm).
        # Under acceleration (accel > 0), fork extends (down to ~15mm).
        if accel < 0:
            fork_compression = (-accel) * 65.0
        else:
            fork_compression = -accel * 18.0
        fork_mm = max(10.0, min(145.0, 35.0 + fork_compression + chatter))

        # Rear shock: static sag ~20mm. Under acceleration (squat), compresses up to ~40mm.
        # Under braking (unweights), extends down to ~8mm.
        if accel > 0:
            shock_compression = accel * 18.0
        else:
            shock_compression = accel * 10.0
        shock_mm = max(5.0, min(48.0, 20.0 + shock_compression - chatter * 0.4))

        # Invert to pin millivolts using firmware ratios:
        # pot_mV = (mm * 5000) / range_mm
        # pin_mV = (pot_mV * 100) / 139
        fork_pot_mv = (fork_mm * 5000.0) / 150.0
        shock_pot_mv = (shock_mm * 5000.0) / 50.0
        susp_front_mv = int((fork_pot_mv * 100.0) / 139.0)
        susp_rear_mv = int((shock_pot_mv * 100.0) / 139.0)

        # 12V battery: nominal 12.55 V with small dynamic ripple from solenoids and current draw
        batt_12v_v = 12.52 - (0.15 * max(0.0, accel)) + 0.04 * math.sin(sample_idx * 0.15)
        batt_12v_mv = int(batt_12v_v * 1000.0)

        # STM32 MCU junction temp: starts at 41.2°C, warms up to 47.8°C across the run
        mcu_temp_c = round(41.2 + (6.6 * progress) + 0.3 * math.sin(sample_idx * 0.05), 2)

        rows.append({
            "timestamp_ms": t,
            "susp_front_mm": round(fork_mm, 2),
            "susp_rear_mm": round(shock_mm, 2),
            "susp_front_mv": susp_front_mv,
            "susp_rear_mv": susp_rear_mv,
            "batt_12v_v": round(batt_12v_v, 2),
            "batt_12v_mv": batt_12v_mv,
            "mcu_temp_c": mcu_temp_c,
        })
        t += step_ms
        sample_idx += 1

    out_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp_ms",
        "susp_front_mm",
        "susp_rear_mm",
        "susp_front_mv",
        "susp_rear_mv",
        "batt_12v_v",
        "batt_12v_mv",
        "mcu_temp_c",
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[Synthetic Telemetry] Wrote {len(rows)} ADC records to {out_file}")


def generate_bms_telemetry(
    times_ms: List[int],
    speeds_kmh: List[float],
    accels_g: List[float],
    out_file: Path,
) -> None:
    """Generates telemetry/bms_battery.csv at 10 Hz (100 ms step).

    Pack: 28S lithium pack (~100-116 V).
    Columns: timestamp_ms, pack_voltage_v, pack_current_a, soc_percent, cell_min_v, cell_max_v, cell_temp_max_c
    """
    t0 = times_ms[0]
    tend = times_ms[-1]
    step_ms = 100  # 10 Hz

    rows = []
    t = t0
    sample_idx = 0
    soc = 88.0

    while t <= tend:
        progress = (t - t0) / (tend - t0) if tend > t0 else 0.0
        accel = interpolate_signal(t, times_ms, accels_g)
        speed = interpolate_signal(t, times_ms, speeds_kmh)

        # Current calculation:
        # High acceleration -> large positive current (up to 210 A)
        # Cruising -> overcoming drag ~ 25-45 A
        # Braking -> regenerative charging current (negative, down to -45 A)
        if accel > 0.05:
            current_a = 40.0 + (accel * 145.0) + (speed / 340.0) * 35.0
        elif accel < -0.1:
            current_a = max(-45.0, accel * 32.0)
        else:
            current_a = 15.0 + (speed / 340.0) * 20.0

        current_a += 1.5 * math.sin(sample_idx * 0.3)

        # Pack internal resistance sag: R_pack ~ 0.048 Ohm (28 cells * 1.7 mOhm)
        # OCV starts at 114.2V and decreases slowly with SoC
        ocv_pack = 114.5 - (1.5 * progress)
        pack_voltage = ocv_pack - (current_a * 0.048)
        pack_voltage = max(100.5, min(116.5, pack_voltage))

        # SoC drains with cumulative Amp-hours
        soc -= (current_a * (step_ms / 1000.0) / 3600.0) / 45.0 * 100.0  # 45 Ah pack

        # 28 Series cells: min and max cell voltages
        avg_cell_v = pack_voltage / 28.0
        cell_min_v = avg_cell_v - 0.018 - (0.005 if current_a > 100 else 0.0)
        cell_max_v = avg_cell_v + 0.015 + (0.004 if current_a > 100 else 0.0)

        # Max cell temperature: heats up with I^2 * R from 33.8°C to 38.6°C
        cell_temp = 33.8 + (4.6 * progress) + (0.4 * (current_a / 200.0))

        rows.append({
            "timestamp_ms": t,
            "pack_voltage_v": round(pack_voltage, 2),
            "pack_current_a": round(current_a, 1),
            "soc_percent": round(soc, 2),
            "cell_min_v": round(cell_min_v, 3),
            "cell_max_v": round(cell_max_v, 3),
            "cell_temp_max_c": round(cell_temp, 1),
        })
        t += step_ms
        sample_idx += 1

    out_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp_ms",
        "pack_voltage_v",
        "pack_current_a",
        "soc_percent",
        "cell_min_v",
        "cell_max_v",
        "cell_temp_max_c",
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[Synthetic Telemetry] Wrote {len(rows)} BMS records to {out_file}")


def generate_inverter_telemetry(
    times_ms: List[int],
    speeds_kmh: List[float],
    accels_g: List[float],
    out_file: Path,
) -> None:
    """Generates telemetry/inverter_can.csv at 50 Hz (20 ms step).

    Columns: timestamp_ms, motor_rpm, motor_temp_c, inverter_temp_c, torque_nm
    """
    t0 = times_ms[0]
    tend = times_ms[-1]
    step_ms = 20  # 50 Hz

    rows = []
    t = t0
    sample_idx = 0

    while t <= tend:
        progress = (t - t0) / (tend - t0) if tend > t0 else 0.0
        speed = interpolate_signal(t, times_ms, speeds_kmh)
        accel = interpolate_signal(t, times_ms, accels_g)

        # Correlation between GPS speed and motor RPM:
        # At 340 km/h -> ~10,200 RPM (~30.0 RPM per km/h with 3.6:1 reduction and 2.0m wheel)
        # Small tire slip during high acceleration (+1.5%) / braking (-1%)
        slip = 1.0 + (0.02 * accel)
        motor_rpm = max(0, int(speed * 30.0 * slip + 5 * math.sin(sample_idx * 0.2)))

        # Torque: directly tied to acceleration demand
        if accel > 0.05:
            torque_nm = 25.0 + (accel * 140.0) + (speed / 340.0) * 20.0
        elif accel < -0.1:
            torque_nm = max(-45.0, accel * 35.0)
        else:
            torque_nm = 12.0 + (speed / 340.0) * 15.0

        # Inverter and motor temperatures
        motor_temp = 47.0 + (14.5 * progress) + (1.2 * max(0.0, accel))
        inverter_temp = 38.5 + (9.8 * progress) + (1.8 * max(0.0, accel))

        rows.append({
            "timestamp_ms": t,
            "motor_rpm": motor_rpm,
            "motor_temp_c": round(motor_temp, 1),
            "inverter_temp_c": round(inverter_temp, 1),
            "torque_nm": round(torque_nm, 1),
        })
        t += step_ms
        sample_idx += 1

    out_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp_ms",
        "motor_rpm",
        "motor_temp_c",
        "inverter_temp_c",
        "torque_nm",
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[Synthetic Telemetry] Wrote {len(rows)} Inverter CAN records to {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate realistic multi-channel telemetry CSVs from reference GPS log")
    parser.add_argument(
        "--bin",
        type=Path,
        default=_PROJECT_ROOT / "data" / "sample" / "20261010_144951.bin",
        help="Path to reference binary log file",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_PROJECT_ROOT / "telemetry",
        help="Output directory to save generated CSV files (default: telemetry/)",
    )
    args = parser.parse_args()

    if not args.bin.is_file():
        print(f"Error: reference binary file not found at {args.bin}", file=sys.stderr)
        sys.exit(1)

    print(f"[Synthetic Telemetry] Reading reference GPS log: {args.bin}")
    times_ms, speeds_kmh, accels_g = load_gps_reference_profile(args.bin)
    print(f"[Synthetic Telemetry] GPS window: {times_ms[0]} ms to {times_ms[-1]} ms ({len(times_ms)} fixes)")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[Synthetic Telemetry] Generating datasets into: {out_dir}")
    generate_adc_telemetry(times_ms, speeds_kmh, accels_g, out_dir / "adc_sensors.csv")
    generate_bms_telemetry(times_ms, speeds_kmh, accels_g, out_dir / "bms_battery.csv")
    generate_inverter_telemetry(times_ms, speeds_kmh, accels_g, out_dir / "inverter_can.csv")

    print("\n[Synthetic Telemetry] Generation completed successfully!")


if __name__ == "__main__":
    main()
