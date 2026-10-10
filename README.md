# AMS Telemetry
> Professional Motorsport Telemetry Studio & Hexagonal Binary Log Parser for AMS STM32 Black-Box.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## ⚡ Overview

**AMS Telemetry** is the dedicated motorsport data analysis suite for the electric motorcycle prototype. It ingests high-frequency binary black-box logs dumped to microSD by the STM32F469 microcontroller, validates packet integrity, and provides both:

1. **CLI Headless Parser**: High-performance streaming parser converting heterogeneous `.bin` logs to clean telemetry CSVs.
2. **Telemetry Studio Web Dashboard**: Interactive motorsport web application with dark theme, Leaflet track map (speed-colored continuous gradient), and high-frequency linked telemetry charts (uPlot at 60 FPS).

---

## 🏎️ Features

- **Hexagonal Architecture (Ports & Adapters)**:
  - Pure domain models (`GpsRecord`, `LogRecordHeader`, `LoggerStatsRecord`).
  - Open/Closed Principle: extensible to CAN Inverter (`0x10`), ADC Suspensions (`0x20`), and BMS SPI (`0x40`) without modifying the ingestion loop.
- **Microsecond Wire-Format Handling**:
  - Aligned to 4096-byte SD block boundaries.
  - Automatic `0x00` padding discard and monotonic sequence continuity audit (`ui16_seq`).
  - O(1) memory footprint: streams hundreds of megabytes in fixed block chunks.
- **Motorsport Web Dashboard**:
  - **Theme**: Neon Racing Green (`#00ff88`) with Hot Racing Pink (`#ff007f`) accents.
  - **Track Map**: Watermark-free dark motorsport tiles (Esri Dark Gray & High-Res Satellite imagery).
  - **Speed Gradient**: Continuous velocity gradient along the track (Green ➔ Lime ➔ Gold ➔ Hot Pink).
  - **uPlot Chart**: Hardware-accelerated canvas speed curve (0–400 km/h) with time/distance toggles.
  - **Linked Hovering (60 FPS)**: Moving the cursor on the graph tracks the vehicle marker on the map and updates live digital HUD metrics.
  - **100% Offline Capable**: Bundled vendor libraries (Leaflet, uPlot) for paddock use without cellular connection.

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/EnekoJL/AMS_Telemetry.git
cd AMS_Telemetry

# Install dependencies
pip install -r requirements.txt
```

### 1. Launch Web Dashboard

```bash
# Launch server on http://localhost:8000
python3 run.py

# Or specify custom port:
python3 run.py --port 8080
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**. Drag-and-drop any `.bin` file or analyze the included reference session from Motorland Aragón.

### 2. Run CLI Parser (Export to CSV)

```bash
# Parse binary log and export GPS CSV
python3 main.py -i data/sample/20261010_144951.bin -o ./output
```

---

## 🧪 Running Tests

```bash
python3 -m pytest tests -v
```

---

## 📁 Repository Structure

```text
AMS_Telemetry/
├── run.py                             # Web Dashboard launcher
├── main.py                            # CLI Binary Parser launcher
├── pyproject.toml                     # Package & pytest configuration
├── requirements.txt                   # Production & dev dependencies
├── src/
│   ├── ams_log_parser/                # Hexagonal binary parser engine
│   │   ├── domain/                    # Models, enums, decoders (GPS, Header, Stats)
│   │   ├── ports/                     # Abstract Reader, Decoder, Exporter interfaces
│   │   ├── application/               # ParseBinaryLogUseCase, DecoderRegistry
│   │   └── adapters/                  # ChunkedBinaryReader, CsvGpsExporter
│   └── ams_telemetry_studio/          # FastAPI web service
│       ├── app.py                     # REST endpoints, static SPA mounting
│       ├── models.py                  # Pydantic DTOs
│       └── services/                  # Haversine distance, acceleration G metrics
├── frontend/                          # Motorsport SPA (HTML5, JS, CSS)
│   ├── index.html
│   ├── css/studio.css
│   ├── js/ (app.js, map.js, chart.js, colormap.js, hud.js, api.js)
│   └── vendor/ (leaflet, uPlot)
├── data/
│   └── sample/
│       └── 20261010_144951.bin        # Reference session (Motorland Aragón)
└── tests/                             # Unit & integration test suite
```
