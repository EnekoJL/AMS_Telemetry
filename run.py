#!/usr/bin/env python3
"""Launcher for AMS Telemetry Studio Web Dashboard."""

import argparse
from pathlib import Path
import sys

_ROOT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _ROOT_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start AMS Telemetry Studio Web Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Binding host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable automatic code reload")
    args = parser.parse_args()

    print("=" * 70)
    print(" AMS TELEMETRY STUDIO — MOTORSPORT ANALYTICS DASHBOARD")
    print("=" * 70)
    print(f" -> Local Dashboard URL:  http://localhost:{args.port}")
    print(f" -> Network Access:       http://{args.host}:{args.port}")
    print(f" -> API Documentation:    http://localhost:{args.port}/docs")
    print("=" * 70)

    uvicorn.run(
        "ams_telemetry_studio.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
