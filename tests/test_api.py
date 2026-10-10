"""API integration tests for AMS Telemetry Studio backend."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from ams_telemetry_studio.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_get_current_session(client: TestClient):
    response = client.get("/api/sessions/current")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "points" in data
    assert data["summary"]["gps_records"] > 0
    assert len(data["points"]) == data["summary"]["gps_records"]

    # Verify point structure
    first_pt = data["points"][0]
    assert "seq" in first_pt
    assert "time_ms" in first_pt
    assert "rel_time_s" in first_pt
    assert "lat" in first_pt
    assert "lon" in first_pt
    assert "speed_kmh" in first_pt
    assert "cum_dist_m" in first_pt


def test_upload_invalid_extension(client: TestClient):
    files = {"file": ("test.txt", b"invalid contents", "text/plain")}
    response = client.post("/api/sessions/upload", files=files)
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]


def test_upload_valid_bin_file(client: TestClient):
    sample_path = Path(__file__).resolve().parents[1] / "data" / "sample" / "20261010_144951.bin"
    if not sample_path.is_file():
        pytest.skip("Sample binary log file not found")

    with open(sample_path, "rb") as f:
        files = {"file": ("uploaded_test.bin", f.read(), "application/octet-stream")}

    response = client.post("/api/sessions/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["session_name"] == "uploaded_test.bin"
    assert len(data["points"]) == 2303
