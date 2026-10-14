from __future__ import annotations

import os
import sys
from pathlib import Path

DB_NAME = "ecg_app.db"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Portable data dir next to the app; override with ECG_APP_DATA."""
    d = Path(os.environ.get("ECG_APP_DATA") or app_dir() / "ecg_data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path(base: Path | None = None) -> Path:
    return (base or data_dir()) / DB_NAME
