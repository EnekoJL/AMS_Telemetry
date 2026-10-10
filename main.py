#!/usr/bin/env python3
"""CLI Entrypoint wrapper for AMS_Parser."""

from pathlib import Path
import sys

_ROOT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _ROOT_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from AMS_Parser.main import main

if __name__ == "__main__":
    sys.exit(main())
