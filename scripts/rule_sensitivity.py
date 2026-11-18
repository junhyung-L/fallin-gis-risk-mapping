"""Show how the Fallin rule score and risk level respond to weather and segment conditions.

Runs the maintained RiskCalculator on a handful of synthetic segments, so it
needs only pandas (no GIS data, GeoPandas, or API key). It compares clear
weather with the deterministic fallback weather used when KMA_SERVICE_KEY is
unset.

    python scripts/rule_sensitivity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.risk_calculator import RiskCalculator  # noqa: E402

CLEAR_WEATHER = {"TMP": "15", "REH": "50", "PTY": "0", "PCP": "0", "SNO": "0", "WSD": "2"}
# Same values as WeatherFetcher._get_fallback_weather (src/weather.py).
FALLBACK_WEATHER = {"TMP": "0", "REH": "95", "PTY": "1", "PCP": "1.0", "SNO": "1.0", "WSD": "6.0"}

SEGMENTS = pd.DataFrame(
    [
        {"segment": "flat, no hazards, lit", "mean_slope_degree": 1.0, "risk_count": 0, "조도": "밝음"},
        {"segment": "slope 6 deg", "mean_slope_degree": 6.0, "risk_count": 0, "조도": "밝음"},
        {"segment": "slope 8 deg + 3 hazards", "mean_slope_degree": 8.0, "risk_count": 3, "조도": "밝음"},
        {"segment": "slope 8 deg + 3 hazards + dark", "mean_slope_degree": 8.0, "risk_count": 3, "조도": "어두움"},
        {"segment": "slope 8 deg + 3 hazards + numeric lux", "mean_slope_degree": 8.0, "risk_count": 3, "조도": 3903},
    ]
)


def main() -> None:
    rows = []
    for label, weather in (("clear", CLEAR_WEATHER), ("fallback", FALLBACK_WEATHER)):
        scored = RiskCalculator(weather).apply_risk_modeling(SEGMENTS.copy())
        for _, row in scored.iterrows():
            rows.append({"weather": label, "segment": row["segment"], "score": row["risk_score"], "level": row["risk_level"]})
    table = pd.DataFrame(rows).pivot(index="segment", columns="weather", values=["score", "level"])
    print(table.loc[SEGMENTS["segment"]].to_string())


if __name__ == "__main__":
    main()
