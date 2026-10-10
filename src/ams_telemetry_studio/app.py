"""FastAPI Application for AMS Telemetry Studio."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
import shutil
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ams_telemetry_studio.models import SessionResponseDTO
from ams_telemetry_studio.services.telemetry_service import TelemetryStudioService

_ROOT_DIR = Path(__file__).resolve().parents[2]
_FRONTEND_DIR = _ROOT_DIR / "frontend"
_SESSIONS_DIR = _ROOT_DIR / "data" / "sessions"
_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Candidate paths for the default sample session
_SAMPLE_CANDIDATES = [
    _ROOT_DIR / "data" / "sample" / "20261010_144951.bin",
    _ROOT_DIR.parent / "telemetry_studio" / "data" / "sessions" / "20261010_144951.bin",
    _ROOT_DIR.parent / "log_parser" / "20261010_144951.bin",
]

service = TelemetryStudioService()


def find_sample_bin() -> Optional[Path]:
    for p in _SAMPLE_CANDIDATES:
        if p.is_file():
            return p
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload sample log session if available
    sample_file = find_sample_bin()
    if sample_file:
        try:
            service.process_file(sample_file)
            print(f"[Telemetry Studio] Preloaded default session: {sample_file.name}")
        except Exception as exc:
            print(f"[Telemetry Studio] Failed to preload sample session: {exc}")
    yield


app = FastAPI(
    title="AMS Telemetry Studio API",
    version="1.1.0",
    description="Multi-Channel Motorsport Telemetry API for STM32 black-box binary logs and sensors",
    lifespan=lifespan,
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def get_health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "has_active_session": service.current_session is not None,
        "active_session_name": service.current_session.summary.session_name if service.current_session else None,
        "loaded_channels": service.current_session.summary.loaded_channels if service.current_session else [],
    }


@app.get("/api/sessions/current", response_model=SessionResponseDTO)
def get_current_session():
    """Returns the currently active telemetry session."""
    session = service.current_session
    if session is None:
        sample_file = find_sample_bin()
        if sample_file:
            session = service.process_file(sample_file)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No telemetry session loaded. Upload telemetry files first.",
            )
    return session


@app.post("/api/sessions/upload", response_model=SessionResponseDTO)
async def upload_session_file(file: UploadFile = File(...)):
    """Uploads, parses and sets an AMS binary log or CSV telemetry file."""
    fname = file.filename.lower()
    if not (fname.endswith(".bin") or fname.endswith(".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format: must be an AMS binary log (*.bin) or telemetry CSV (*.csv)",
        )

    dest_file = _SESSIONS_DIR / file.filename
    try:
        with open(dest_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if fname.endswith(".bin"):
            session = service.process_file(dest_file)
        else:
            session = service.ingest_files([dest_file])
        return session
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing uploaded file: {str(exc)}",
        )
    finally:
        await file.close()


@app.post("/api/telemetry/upload", response_model=SessionResponseDTO)
async def upload_multi_telemetry_files(files: List[UploadFile] = File(...)):
    """Uploads multiple telemetry files (.bin and/or .csv) and merges them into a synchronized session."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided.",
        )

    saved_paths: List[Path] = []
    try:
        for f in files:
            dest_file = _SESSIONS_DIR / f.filename
            with open(dest_file, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            saved_paths.append(dest_file)

        session = service.ingest_files(saved_paths)
        return session
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing uploaded telemetry batch: {str(exc)}",
        )
    finally:
        for f in files:
            await f.close()


@app.post("/api/sessions/load-sample", response_model=SessionResponseDTO)
def load_sample_session():
    """Explicitly loads the Aragon Motorland sample session with all companion channels."""
    sample_file = find_sample_bin()
    if not sample_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample binary file not found on disk.",
        )
    return service.process_file(sample_file)


# Serve frontend static assets
if _FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(_FRONTEND_DIR / "index.html")
