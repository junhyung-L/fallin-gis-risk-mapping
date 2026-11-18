"""Portable paths and runtime settings for the Fallin prototype."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("FALLIN_DATA_DIR", PROJECT_ROOT / "data"))
RESULTS_DIR = Path(os.getenv("FALLIN_RESULTS_DIR", PROJECT_ROOT / "results"))
WEATHER_API_KEY = os.getenv("KMA_SERVICE_KEY")
DEFAULT_SHAPEFILE = os.getenv("FALLIN_SHAPEFILE", "인도_조도_경사도.shp")


def result_path(filename: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR / filename

# Source: EN 13201-2:2015 Road lighting - Part 2, P-class table; CIE 115:2010.
# Lighting rule: a segment earns the lighting point when its measured
# illuminance is below this value (lux). 2.0 lx is the lowest maintained average
# horizontal illuminance in the pedestrian (P) lighting classes of
# EN 13201-2:2015 (class P6; P1-P6 = 15, 10, 7.5, 5, 3, 2 lx), which
# follows CIE 115:2010. A reading below it falls short of every pedestrian class.
DARK_LUX_THRESHOLD = float(os.getenv("FALLIN_DARK_LUX", "2.0"))
DARK_LIGHTING_LABELS = ("낮음", "어두움")
