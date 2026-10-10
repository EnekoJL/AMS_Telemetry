"""Tests for multi-channel telemetry ingestion and API endpoints."""

import csv
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from ams_telemetry_studio.app import app, service
from ams_telemetry_studio.services.telemetry_service import TelemetryStudioService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_adc_csv(tmp_path: Path) -> Path:
    f = tmp_path / "adc_sensors.csv"
    with open(f, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["timestamp_ms", "susp_front_mm", "susp_rear_mm", "susp_front_mv", "susp_rear_mv", "batt_12v_v", "batt_12v_mv", "mcu_temp_c"])
        w.writerow([1000, 35.0, 20.0, 850, 1400, 12.5, 12500, 42.0])
        w.writerow([1040, 45.0, 18.0, 950, 1300, 12.4, 12400, 42.1])
        w.writerow([1080, 55.0, 16.0, 1050, 1200, 12.3, 12300, 42.2])
    return f


@pytest.fixture
def sample_bms_csv(tmp_path: Path) -> Path:
    f = tmp_path / "bms_battery.csv"
    with open(f, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["timestamp_ms", "pack_voltage_v", "pack_current_a", "soc_percent", "cell_min_v", "cell_max_v", "cell_temp_max_c"])
        w.writerow([1000, 114.0, 25.0, 88.0, 4.05, 4.08, 34.0])
        w.writerow([1100, 108.0, 150.0, 87.9, 3.82, 3.86, 34.2])
    return f


@pytest.fixture
def sample_inverter_csv(tmp_path: Path) -> Path:
    f = tmp_path / "inverter_can.csv"
    with open(f, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["timestamp_ms", "motor_rpm", "motor_temp_c", "inverter_temp_c", "torque_nm"])
        w.writerow([1000, 3500, 48.0, 40.0, 50.0])
        w.writerow([1020, 3600, 48.1, 40.1, 80.0])
    return f


def test_decoupled_bms_upload(sample_bms_csv: Path):
    """Verifies that uploading only BMS battery data produces a valid session with has_bms=True and has_gps=False."""
    svc = TelemetryStudioService()
    session = svc.ingest_files([sample_bms_csv])
    assert session is not None
    assert session.channels.has_bms is True
    assert session.channels.has_gps is False
    assert len(session.channels.bms) == 2
    assert session.channels.bms[0].pack_voltage_v == 114.0
    assert "BMS" in session.summary.loaded_channels
    assert session.summary.duration_s == 0.1


def test_decoupled_adc_upload(sample_adc_csv: Path):
    """Verifies that uploading only ADC data produces a valid session with has_adc=True and has_gps=False."""
    svc = TelemetryStudioService()
    session = svc.ingest_files([sample_adc_csv])
    assert session is not None
    assert session.channels.has_adc is True
    assert session.channels.has_gps is False
    assert len(session.channels.adc) == 3
    assert session.channels.adc[0].susp_front_mm == 35.0
    assert "ADC" in session.summary.loaded_channels


def test_multi_channel_merge(sample_adc_csv: Path, sample_bms_csv: Path, sample_inverter_csv: Path):
    """Verifies temporal alignment across ADC, BMS, and Inverter streams."""
    svc = TelemetryStudioService()
    session = svc.ingest_files([sample_adc_csv, sample_bms_csv, sample_inverter_csv])
    assert session.channels.has_adc is True
    assert session.channels.has_bms is True
    assert session.channels.has_inverter is True
    assert session.channels.has_gps is False
    assert set(session.summary.loaded_channels) == {"ADC", "BMS", "Inversor"}
    # Global t0 is 1000 ms, so rel_time_s at 1000 ms is 0.0
    assert session.channels.adc[0].rel_time_s == 0.0
    assert session.channels.bms[0].rel_time_s == 0.0
    assert session.channels.inverter[0].rel_time_s == 0.0


def test_multi_upload_endpoint(client: TestClient, sample_bms_csv: Path, sample_inverter_csv: Path):
    """Verifies POST /api/telemetry/upload with multiple multipart files."""
    with open(sample_bms_csv, "rb") as f1, open(sample_inverter_csv, "rb") as f2:
        response = client.post(
            "/api/telemetry/upload",
            files=[
                ("files", ("bms_battery.csv", f1, "text/csv")),
                ("files", ("inverter_can.csv", f2, "text/csv")),
            ],
        )
    assert response.status_code == 200
    data = response.json()
    assert data["channels"]["has_bms"] is True
    assert data["channels"]["has_inverter"] is True
    assert data["channels"]["has_gps"] is False
    assert len(data["channels"]["bms"]) == 2
    assert len(data["channels"]["inverter"]) == 2


def test_companion_autodiscovery_with_sample(client: TestClient):
    """Verifies that load-sample automatically discovers companion CSV channels."""
    response = client.post("/api/sessions/load-sample")
    assert response.status_code == 200
    data = response.json()
    assert data["channels"]["has_gps"] is True
    assert data["channels"]["has_adc"] is True
    assert data["channels"]["has_bms"] is True
    assert data["channels"]["has_inverter"] is True
    assert len(data["channels"]["adc"]) > 1000
    assert len(data["channels"]["bms"]) > 500
    assert len(data["channels"]["inverter"]) > 2000
