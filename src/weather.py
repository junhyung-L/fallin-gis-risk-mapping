"""KMA short-term forecast (단기예보, getVilageFcst) client and value parsers.

Source: 기상청_단기예보 조회서비스 OpenAPI 활용가이드 (data.go.kr dataset 15084084,
guide revision 2610). Facts used here:

- ``getVilageFcst`` (단기예보조회) returns TMP, TMX, TMN, UUU, VVV, VEC, WSD,
  SKY, PTY, POP, PCP, SNO, REH, WAV. (``getUltraSrtFcst`` returns T1H/RN1/...
  instead, so TMP/PCP/SNO only exist in the short-term forecast.)
- Issue times (base_time): 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 KST;
  each is available from the API 10 minutes later (02:10, 05:10, ...).
- PTY (short-term): 0 none, 1 rain, 2 rain/snow, 3 snow, 4 shower.
- PCP is a category string: "강수없음" (also -, null, 0), "1mm 미만"
  (0.1-1.0 mm), "<x>mm" (1.0-29.9 mm), "30.0~50.0mm", "50.0mm 이상".
- SNO: "적설없음" (also -, null, 0), "0.5cm 미만" (0.1-0.5 cm), "<x>cm"
  (0.5-4.9 cm), "5.0cm 이상".
- One response holds many forecast hours (fcstDate/fcstTime); each category
  appears once per hour, so the client must pick one hour explicitly.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

try:
    from .config import WEATHER_API_KEY
except ImportError:
    from config import WEATHER_API_KEY

KMA_VILAGE_FCST_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
ISSUE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)
AVAILABILITY_DELAY = timedelta(minutes=10)
# Categories the risk rule reads (src/risk_calculator.py).
USED_CATEGORIES = ("TMP", "REH", "PTY", "PCP", "SNO", "WSD")

_NO_PRECIP = {"", "-", "0", "0.0", "null", "none", "강수없음"}
_NO_SNOW = {"", "-", "0", "0.0", "null", "none", "적설없음"}
_NUMBER = r"(\d+(?:\.\d+)?)"


def latest_base_datetime(now: datetime) -> tuple[str, str]:
    """Return (base_date, base_time) of the latest issue already served at ``now``.

    An issue at hour h is usable from h:10. Before 02:10 the latest usable issue
    is 2300 of the previous day.
    """
    for hour in reversed(ISSUE_HOURS):
        issued = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now >= issued + AVAILABILITY_DELAY:
            return issued.strftime("%Y%m%d"), issued.strftime("%H%M")
    previous = (now - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)
    return previous.strftime("%Y%m%d"), previous.strftime("%H%M")


def _parse_amount(value, unit: str, none_words: set[str]) -> float:
    """Parse a KMA PCP/SNO category string into a number in ``unit``.

    Ranges map to their lower bound ("1mm 미만" -> 0.1, "30.0~50.0mm" -> 30.0,
    "50.0mm 이상" -> 50.0) so any reported precipitation stays above zero.
    Raises ValueError for text that matches no documented form.
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if text.lower() in none_words:
        return 0.0
    if re.fullmatch(_NUMBER + re.escape(unit) + "미만", text):
        return 0.1  # "below x": the documented category starts at 0.1
    match = re.fullmatch(_NUMBER + "~" + _NUMBER + re.escape(unit), text)
    if match:
        return float(match.group(1))
    match = re.fullmatch(_NUMBER + re.escape(unit) + "이상", text)
    if match:
        return float(match.group(1))
    match = re.fullmatch(_NUMBER + "(?:" + re.escape(unit) + ")?", text)
    if match:
        return float(match.group(1))
    raise ValueError(f"unrecognised KMA amount {value!r} (unit {unit})")


def parse_precipitation(value) -> float:
    """PCP / RN1 category string -> millimetres."""
    return _parse_amount(value, "mm", _NO_PRECIP)


def parse_snowfall(value) -> float:
    """SNO category string -> centimetres."""
    return _parse_amount(value, "cm", _NO_SNOW)


def _parse_float(value) -> float:
    return float(str(value).strip())


def _parse_code(value) -> str:
    return str(int(float(str(value).strip())))


PARSERS = {
    "TMP": _parse_float,
    "REH": _parse_float,
    "WSD": _parse_float,
    "PTY": _parse_code,
    "PCP": parse_precipitation,
    "SNO": parse_snowfall,
}


def select_nearest_slot(items: list[dict], target: datetime) -> dict[str, str]:
    """Return {category: fcstValue} for the forecast hour nearest to ``target``.

    Items carry fcstDate (YYYYMMDD) and fcstTime (HHMM); ties go to the earlier
    hour. Items with a malformed date/time are skipped with a warning.
    """
    slots: dict[datetime, dict[str, str]] = {}
    for item in items:
        try:
            when = datetime.strptime(f"{item['fcstDate']}{item['fcstTime']}", "%Y%m%d%H%M")
            slots.setdefault(when, {})[item["category"]] = item["fcstValue"]
        except (KeyError, TypeError, ValueError) as exc:
            logging.warning("Skipping malformed forecast item %r: %s", item, exc)
    if not slots:
        return {}
    nearest = min(slots, key=lambda when: (abs((when - target).total_seconds()), when))
    logging.info("Using forecast slot %s (target %s).", nearest.strftime("%Y-%m-%d %H:%M"), target.strftime("%Y-%m-%d %H:%M"))
    return slots[nearest]


def normalize_weather(raw: dict) -> dict:
    """Convert raw category strings to numbers, one category at a time.

    A category that fails to parse is logged and left out, so the risk rule
    falls back to its neutral default for that factor only.
    """
    weather = {}
    for category in USED_CATEGORIES:
        if category not in raw:
            continue
        try:
            weather[category] = PARSERS[category](raw[category])
        except (TypeError, ValueError) as exc:
            logging.warning("Could not parse %s=%r: %s; factor skipped.", category, raw[category], exc)
    return weather


def extract_items(payload: dict) -> list[dict]:
    """Return the item list of a getVilageFcst JSON payload; raise on API errors."""
    response = payload["response"]
    code = str(response["header"]["resultCode"])
    if code not in ("00", "0"):
        raise RuntimeError(f"KMA error {code}: {response['header'].get('resultMsg')}")
    items = response["body"]["items"]["item"]
    return items if isinstance(items, list) else [items]


class WeatherFetcher:
    """Fetches the KMA short-term forecast (getVilageFcst), or a fixed fallback."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or WEATHER_API_KEY

    def fetch_current_weather(self, nx: int = 55, ny: int = 124, now: datetime | None = None) -> dict:
        """Return numeric TMP/REH/PTY/PCP/SNO/WSD for the forecast hour nearest ``now``."""
        if not self.api_key:
            logging.info("KMA_SERVICE_KEY is not set; using deterministic fallback weather.")
            return self._get_fallback_weather()
        import requests

        now = now or datetime.now()
        base_date, base_time = latest_base_datetime(now)
        params = {
            "serviceKey": self.api_key,
            "pageNo": "1",
            "numOfRows": "1000",
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": str(nx),
            "ny": str(ny),
        }
        logging.info("Fetching KMA getVilageFcst base %s %s for grid (%s, %s).", base_date, base_time, nx, ny)
        try:
            response = requests.get(KMA_VILAGE_FCST_URL, params=params, timeout=10)
            response.raise_for_status()
            items = extract_items(response.json())
        except Exception as exc:
            logging.error("Error fetching weather data: %s. Using fallback.", exc)
            return self._get_fallback_weather()

        weather = normalize_weather(select_nearest_slot(items, now))
        if not weather:
            logging.warning("No usable forecast categories in the response. Using fallback.")
            return self._get_fallback_weather()
        logging.info("Weather data fetched: %s", weather)
        return weather

    def _get_fallback_weather(self) -> dict:
        """Provides default winter conditions for simulation (same keys as the API path)."""
        logging.info("Using fallback standard winter weather conditions.")
        return {
            "TMP": 0.0,   # 0 degrees Celsius
            "REH": 95.0,  # high humidity
            "PTY": "1",   # rain
            "PCP": 1.0,   # 1 mm precipitation
            "SNO": 1.0,   # 1 cm snow
            "WSD": 6.0,   # high wind speed (m/s)
        }
