"""Offline tests for the KMA short-term forecast client (src/weather.py).

Fixtures in tests/fixtures/ are hand-written getVilageFcst JSON responses that
follow the format in the KMA OpenAPI guide; no network access is needed.

    python -m pytest tests        # with pytest installed
    python tests/test_weather.py  # plain asserts, no pytest needed
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.risk_calculator import RiskCalculator  # noqa: E402
from src.weather import (  # noqa: E402
    WeatherFetcher,
    extract_items,
    latest_base_datetime,
    normalize_weather,
    parse_precipitation,
    parse_snowfall,
    select_nearest_slot,
)

FIXTURES = ROOT / "tests" / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_precipitation():
    cases = {
        "강수없음": 0.0,
        "-": 0.0,
        "0": 0.0,
        None: 0.0,
        "1mm 미만": 0.1,
        "1.0mm 미만": 0.1,
        "1mm": 1.0,
        "6.2mm": 6.2,
        "1.0~29.0mm": 1.0,
        "30.0~50.0mm": 30.0,
        "50.0mm 이상": 50.0,
        "50.0mm이상": 50.0,
        "3.5": 3.5,
    }
    for raw, expected in cases.items():
        assert parse_precipitation(raw) == expected, raw


def test_parse_snowfall():
    cases = {"적설없음": 0.0, "-": 0.0, "0.5cm 미만": 0.1, "1.2cm": 1.2, "5.0cm 이상": 5.0}
    for raw, expected in cases.items():
        assert parse_snowfall(raw) == expected, raw


def test_parse_rejects_unknown_text():
    for bad in ("비 조금", "1.0cm"):  # wrong unit for precipitation is not silently accepted
        try:
            parse_precipitation(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad!r}")


def test_latest_base_datetime():
    assert latest_base_datetime(datetime(2026, 11, 19, 5, 9)) == ("20261119", "0200")
    assert latest_base_datetime(datetime(2026, 11, 19, 5, 10)) == ("20261119", "0500")
    assert latest_base_datetime(datetime(2026, 11, 19, 13, 59)) == ("20261119", "1100")
    assert latest_base_datetime(datetime(2026, 11, 19, 23, 30)) == ("20261119", "2300")
    assert latest_base_datetime(datetime(2026, 11, 19, 2, 5)) == ("20261118", "2300")
    assert latest_base_datetime(datetime(2026, 1, 1, 0, 30)) == ("20251231", "2300")


def test_select_nearest_slot():
    items = extract_items(load("vilage_fcst_sample.json"))
    # 06:20 is nearest to the 0600 slot; values from later hours must not leak in.
    slot = select_nearest_slot(items, datetime(2026, 11, 19, 6, 20))
    assert slot["TMP"] == "-1" and slot["PTY"] == "3" and slot["SNO"] == "0.5cm 미만"
    # 06:40 -> 0700 slot.
    slot = select_nearest_slot(items, datetime(2026, 11, 19, 6, 40))
    assert slot["TMP"] == "0" and slot["PCP"] == "1mm 미만" and slot["SNO"] == "1.2cm"
    # Exact tie (07:30 between 0700 and 0800) -> earlier hour.
    assert select_nearest_slot(items, datetime(2026, 11, 19, 7, 30))["TMP"] == "0"
    # Far in the future -> last available slot.
    assert select_nearest_slot(items, datetime(2026, 11, 20, 12, 0))["TMP"] == "4"


def test_normalize_weather_and_score():
    items = extract_items(load("vilage_fcst_sample.json"))
    weather = normalize_weather(select_nearest_slot(items, datetime(2026, 11, 19, 7, 0)))
    assert weather == {"TMP": 0.0, "REH": 95.0, "PTY": "2", "PCP": 0.1, "SNO": 1.2, "WSD": 4.1}
    # TMP<=0 (2) + REH>=90 (1) + PTY rain/snow (2) + PCP>0 (1) + SNO>0 (2); WSD<5.
    assert RiskCalculator(weather).weather_points == 8


def test_one_bad_field_does_not_drop_others():
    raw = {"TMP": "-3", "REH": "N/A", "PTY": "1", "PCP": "비 많이", "SNO": "적설없음", "WSD": "7.5"}
    weather = normalize_weather(raw)
    assert weather == {"TMP": -3.0, "PTY": "1", "SNO": 0.0, "WSD": 7.5}
    # Raw strings scored directly: REH and PCP skipped, the rest still count.
    assert RiskCalculator(raw).weather_points == 2 + 2 + 1


def test_api_error_raises():
    try:
        extract_items(load("vilage_fcst_no_data.json"))
    except RuntimeError as exc:
        assert "03" in str(exc)
    else:
        raise AssertionError("NODATA_ERROR not raised")


def test_fetch_uses_computed_base_time_and_nearest_slot():
    """Replays the recorded response through fetch_current_weather with a stub requests module."""
    import types

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return load("vilage_fcst_sample.json")

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return FakeResponse()

    real = sys.modules.get("requests")
    sys.modules["requests"] = types.SimpleNamespace(get=fake_get)
    try:
        weather = WeatherFetcher(api_key="test-key").fetch_current_weather(now=datetime(2026, 11, 19, 6, 10))
    finally:
        if real is None:
            del sys.modules["requests"]
        else:
            sys.modules["requests"] = real
    url, params = calls[0]
    assert url.endswith("/getVilageFcst")
    assert (params["base_date"], params["base_time"]) == ("20261119", "0500")
    assert weather == {"TMP": -1.0, "REH": 92.0, "PTY": "3", "PCP": 0.0, "SNO": 0.1, "WSD": 5.4}


def test_fallback_without_key():
    fetcher = WeatherFetcher(api_key=None)
    fetcher.api_key = None  # ignore any KMA_SERVICE_KEY in the environment
    weather = fetcher.fetch_current_weather()
    assert RiskCalculator(weather).weather_points == 9


if __name__ == "__main__":
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} tests passed")
