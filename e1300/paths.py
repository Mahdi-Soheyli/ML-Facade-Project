from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "building_code" / "e1300_data"


def data_path(name: str) -> Path:
    return DATA_DIR / name
