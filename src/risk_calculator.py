import logging
import math

import pandas as pd

from src.config import DARK_LIGHTING_LABELS, DARK_LUX_THRESHOLD
from src.weather import parse_precipitation, parse_snowfall

# KMA short-term PTY codes: 1 rain, 2 rain/snow, 3 snow, 4 shower (0 = none).
PRECIPITATION_TYPES = {'1', '2', '3', '4'}


def _weather_value(weather: dict, key: str, parse):
    """Parse one weather field; return None (factor not scored) when missing or invalid."""
    value = weather.get(key)
    if value is None:
        return None
    try:
        return parse(value)
    except (TypeError, ValueError) as exc:
        logging.warning("Weather field %s=%r not usable: %s", key, value, exc)
        return None


def is_dark(value, threshold: float = DARK_LUX_THRESHOLD) -> bool:
    """Return True when a lighting value counts as dark.

    Accepts a text label ("낮음" / "어두움") or a numeric illuminance in lux.
    Numeric values below ``threshold`` (default 2.0 lx, the EN 13201-2 / CIE 115
    P6 class average; see src/config.py) count as dark. Missing values do not.
    """
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip()
        if text in DARK_LIGHTING_LABELS:
            return True
        try:
            value = float(text)
        except ValueError:
            return False
    try:
        lux = float(value)
    except (TypeError, ValueError):
        return False
    if math.isnan(lux):
        return False
    return lux < threshold


class RiskCalculator:
    """Implements the heuristic risk scoring logic for elderly falls."""
    def __init__(self, weather_data: dict):
        self.weather_data = weather_data
        # Weather is one forecast per run, so its points are computed once.
        self.weather_points = self.score_weather(weather_data)

    @staticmethod
    def score_weather(w: dict) -> int:
        """Weather points (0-9). Each factor is parsed on its own, so one bad
        value cannot drop the others; see src/weather.py for the KMA formats."""
        tmp = _weather_value(w, 'TMP', float)
        reh = _weather_value(w, 'REH', float)
        pty = _weather_value(w, 'PTY', lambda v: str(int(float(v))))
        pcp = _weather_value(w, 'PCP', parse_precipitation)
        sno = _weather_value(w, 'SNO', parse_snowfall)
        wsd = _weather_value(w, 'WSD', float)
        score = 0
        if tmp is not None and tmp <= 0: score += 2
        if reh is not None and reh >= 90: score += 1
        if pty in PRECIPITATION_TYPES: score += 2
        if pcp is not None and pcp > 0: score += 1
        if sno is not None and sno > 0: score += 2
        if wsd is not None and wsd >= 5: score += 1
        return score

    def calculate_score(self, row) -> int:
        """Calculates risk score for a single row/segment."""
        # 1. Weather Factors
        score = self.weather_points

        # 2. Terrain & Environment Factors
        try:
            slope = float(row.get('mean_slope_degree', 0))
            if slope > 7: score += 5
            elif slope > 5: score += 3
            
            if is_dark(row.get('조도')): score += 1
            
            risk_count = float(row.get('risk_count', 0))
            if risk_count >= 3: score += 5
            elif risk_count >= 1: score += 3
        except Exception as e:
            logging.debug(f"GIS scoring error: {e}")

        return score

    def apply_risk_modeling(self, gdf) -> pd.DataFrame:
        """Applies risk scoring to the entire GeoDataFrame and categorizes levels."""
        logging.info("Calculating risk scores for all segments...")
        gdf['risk_score'] = gdf.apply(self.calculate_score, axis=1)
        
        gdf['risk_level'] = pd.cut(
            gdf['risk_score'],
            bins=[-1, 5, 10, 20],
            labels=['Low', 'Medium', 'High']
        )
        return gdf
