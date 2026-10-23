# AMS Telemetry Studio — specification

**Version:** 2.0.0 (2026-10-10) · **Code:** this repo (git submodule
`tools/AMS_Telemetry/` of `AMS_GitHub`) · **Launch:** `./runTelemetry.sh` or
`windows/telemetry/`.

Decodes the SD black-box files (`.bin`) and shows a session on a web
dashboard: track map, stacked synchronised charts, HUD. Offline: every
JS/CSS library is bundled.

## 1. Goals

1. **Robust streaming decode** of `.bin` files in 4096 B blocks: skip
   padding (`0x00`) and unknown records without losing the file offset,
   O(1) RAM.
2. **Hexagonal architecture** (ports and adapters): binary decoder,
   multi-channel aggregator and presentation (CLI, web) are independent.
3. **Local web app**: async FastAPI, typed REST endpoints (Pydantic).
4. **Racing visualisation**: satellite map with an SVG track coloured by
   speed (neon green `#00ff88` → lime `#76ff03` → gold `#ffea00` → racing
   pink `#ff007f`); 4 stacked uPlot charts at 60 FPS; bidirectional
   crosshair (chart ↔ map marker ↔ HUD); synchronised drag-to-zoom.
5. **Multi-source**: correlate a raw `.bin` with separate CSVs
   (`adc_sensors.csv`, `bms_battery.csv`, `inverter_can.csv`), aligned on
   `timestamp_ms`.

## 2. Architecture

```
FRONTEND  (web dashboard)
  Unified cockpit: collapsible satellite map (SVG) + digital HUD
  Stacked uPlot charts: [1 Dynamics] [2 Suspension] [3 Battery] [4 Temperatures]
        │ HTTP / REST JSON
BACKEND  (FastAPI)
  Endpoints (§5) · MultiChannelService (timebase interpolation, alignment)
  Kinematics: Haversine distance, accel in g, speeds
        │ hexagonal use cases
LOG PARSER  (src/AMS_Parser)
  Application: ParseBinaryLogUseCase, DecoderRegistry
  Domain: GpsRecord, LogRecordHeader, LoggerStatsRecord
  Ports: BlockReaderPort, PayloadDecoderPort, TelemetryExporterPort
  Adapters: ChunkedBinaryReader, CsvGpsExporter
        │
  microSD .bin / CSV files
```

## 3. Binary input

The file format is defined by the firmware, not here:
[`docs/architecture/Log_Format.md`](https://github.com/EnekoJL/AMS_GitHub/blob/main/docs/architecture/Log_Format.md)
in the firmware repo (source of truth: `Core/Inc/Algorithms/AMS_log_format.h`).

| Record | ID | Decoder in the studio |
|---|---|---|
| File header | `0x01` | Yes |
| GPS RMC | `0x30` | Yes |
| Logger stats | `0xF0` | Yes |
| BMS v2 (28 cells + 12 NTC, 80 B) | `0x40` | **No** — Backlog S10 |
| CAN inverter / ADC | `0x10` / `0x20` | No — the firmware doesn't log them yet (Backlog S6/S7) |

Until those exist, ADC, BMS and inverter channels come from the mock CSVs
(§6), whose columns are a **dashboard model**, not the firmware records
(e.g. the mock BMS has current and SoC, which the firmware doesn't produce).

## 4. Data model (Pydantic DTOs)

```python
class TelemetryPointDTO(BaseModel):      # GPS kinematics
    timestamp_ms: int; rel_time_s: float; utc_iso: Optional[str]
    lat: float; lon: float; speed_kmh: float; course_deg: float
    fix_valid: bool; distance_m: float; accel_g: float

class AdcPointDTO(BaseModel):            # suspension and analog
    timestamp_ms: int; rel_time_s: float
    suspension_front_raw: float          # mV or mm
    suspension_rear_raw: float
    v12_aux_v: float                     # 12 V line
    mcu_temp_c: float

class BmsPointDTO(BaseModel):            # battery
    timestamp_ms: int; rel_time_s: float
    pack_voltage_v: float; pack_current_a: float   # + discharge, − regen
    soc_percent: float; cell_min_v: float; cell_max_v: float
    cell_temp_max_c: float

class InverterPointDTO(BaseModel):       # powertrain (CAN)
    timestamp_ms: int; rel_time_s: float
    motor_rpm: float; motor_temp_c: float; inverter_temp_c: float; torque_nm: float
```

`MultiTelemetrySessionDTO` groups the four streams on the session timebase,
plus duration, total distance and min / max / average speed.

## 5. REST API

| Method | Endpoint | Input | Returns |
|---|---|---|---|
| `GET` | `/api/sessions/current` | — | `TelemetrySessionDTO` (GPS + kinematics) |
| `POST` | `/api/sessions/upload` | form `file` (`.bin`) | `TelemetrySessionDTO` |
| `POST` | `/api/sessions/load-sample` | — | Motorland sample session |
| `POST` | `/api/telemetry/upload` | form `files` (several `.csv`) | `MultiTelemetrySessionDTO` |
| `GET` | `/api/telemetry/current` | — | `MultiTelemetrySessionDTO` |

## 6. Frontend

- **Map toggle** (`Hide map` / `Show map`): collapsed, the charts take the
  whole screen.
- **SVG track** (Leaflet `preferCanvas: false`): no line clipping at deep
  zoom. Google satellite tiles with `keepBuffer: 6`,
  `updateWhenZooming: false` (no black tiles).
- **Charts** (common time axis):
  1. Dynamics — GPS speed km/h (left, green) and motor RPM (right, pink).
  2. Suspension — front and rear travel, mm.
  3. Battery — pack voltage V (left, floating origin) and current A (right,
     signed).
  4. Temperatures — motor, inverter, max battery, STM32 °C.
- **Auto-scale `calcScaleRange`**: ~10 % margin, round steps (5 / 10 / 500),
  zero kept for speed / RPM / suspension, floating origin for voltage and
  temperature; every tick formatted with its unit (no `NaN`).
- **Maximise** per chart (`position: fixed`, full viewport); `Escape`
  restores. Crosshair, map and HUD keep working.
- **Zoom**: drag on any chart (`.u-select`) → applied to all 4;
  double-click resets.
- **Crosshair**: moves the map marker and updates the HUD (speed, RPM, g,
  distance).

## 7. Mock data (`tools/AMS_Telemetry/scripts/generate_mock_telemetry.py`)

Uses the time window of the real GPS log `20261010_144951.bin` (Motorland,
t = 15.636 … 113.653 s) and writes into `tools/AMS_Telemetry/telemetry/`:

| File | Rate | Model |
|---|---|---|
| `adc_sensors.csv` | 25 Hz | Front fork compresses to 3100 mV under braking (< −0.3 g), rear under acceleration (> 0.2 g); 12 V at 12.35 V with ripple and dips; STM32 34.2 → 38.5 °C |
| `bms_battery.csv` | 10 Hz | Pack 114.5 V nominal, up to +115 A on straights, −35 A regen under braking |
| `inverter_can.csv` | 50 Hz | RPM ≈ speed × 46.5; inverter and motor temperatures with thermal inertia |
