"""get_weather tool

Pure function(s) to fetch per-day weather summaries from Open-Meteo.

Functions
- get_weather(location, dates) -> dict
- geocode_place(place_name) -> tuple[float, float] | None

The `location` argument can be either:
- a place name string such as "Paris" or "California"
- a tuple of latitude and longitude values

The returned dictionary maps each original input date string to a result object.
If data is unavailable, the object contains a `status` field.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime,timedelta
from typing import List, Dict, Tuple, Union


WEATHERCODE_MAP = {
	0: "clear",
	1: "mainly_clear",
	2: "partly_cloudy",
	3: "overcast",
	45: "fog",
	48: "depositing_rime_fog",
	51: "drizzle_light",
	53: "drizzle_moderate",
	55: "drizzle_dense",
	56: "freezing_drizzle_light",
	57: "freezing_drizzle_dense",
	61: "rain_slight",
	63: "rain_moderate",
	65: "rain_heavy",
	66: "freezing_rain_light",
	67: "freezing_rain_heavy",
	71: "snow_fall_slight",
	73: "snow_fall_moderate",
	75: "snow_fall_heavy",
	77: "snow_grains",
	80: "rain_showers_slight",
	81: "rain_showers_moderate",
	82: "rain_showers_violent",
	85: "snow_showers_slight",
	86: "snow_showers_heavy",
	95: "thunderstorm",
	96: "thunderstorm_with_hail_light",
	99: "thunderstorm_with_hail_heavy",
}


def _parse_date_iso(date_str: str) -> str | None:
	"""Try to parse a date string into YYYY-MM-DD. Returns None on failure."""
	formats = [
		"%Y-%m-%d",
		"%d/%m/%Y",
		"%d/%m/%y",
		"%d-%m-%Y",
		"%d-%m-%y",
		"%Y/%m/%d",
	]
	for fmt in formats:
		try:
			dt = datetime.strptime(date_str, fmt)
			return dt.strftime("%Y-%m-%d")
		except ValueError:
			continue
	return None


def _geocode_place(place_name: str) -> Tuple[float, float] | None:
	"""Resolve a place name to latitude and longitude using Open-Meteo geocoding."""
	base = "https://geocoding-api.open-meteo.com/v1/search"
	params = {
		"name": place_name,
		"count": "1",
		"language": "en",
	}
	url = base + "?" + urllib.parse.urlencode(params)
	try:
		with urllib.request.urlopen(url, timeout=15) as resp:
			if resp.status != 200:
				return None
			data = resp.read().decode("utf-8")
			payload = json.loads(data)
			results = payload.get("results") or []
			if not results:
				return None
			first = results[0]
			latitude = float(first.get("latitude"))
			longitude = float(first.get("longitude"))
			return latitude, longitude
	except Exception:
		return None


def _call_open_meteo(latitude: float, longitude: float, start_date: str, end_date: str) -> dict | None:
	base = "https://api.open-meteo.com/v1/forecast"
	params = {
		"latitude": str(latitude),
		"longitude": str(longitude),
		"start_date": start_date,
		"end_date": end_date,
		"daily": ",".join([
			"weathercode",
			"precipitation_sum",
			"temperature_2m_max",
			"temperature_2m_min",
		]),
		"timezone": "UTC",
	}
	url = base + "?" + urllib.parse.urlencode(params)
	try:
		with urllib.request.urlopen(url, timeout=15) as resp:
			if resp.status != 200:
				return None
			data = resp.read().decode("utf-8")
			return json.loads(data)
	except Exception:
		return None


def _normalize_location(location: Union[str, Tuple[float, float]]) -> Tuple[float, float] | None:
	"""Accept either a place name or a latitude/longitude tuple."""
	if isinstance(location, str):
		return _geocode_place(location)
	if isinstance(location, tuple) and len(location) == 2:
		try:
			lat = float(location[0])
			lon = float(location[1])
			return lat, lon
		except Exception:
			return None
	return None


def _weather_entry(code: int, temp_min: float, temp_max: float, precipitation: float) -> Dict[str, Union[str, float, int]]:
	return {
		"weather": WEATHERCODE_MAP.get(code, f"unknown_{code}"),
		"temp_min_c": temp_min,
		"temp_max_c": temp_max,
		"rain_mm": precipitation,
	}


def get_weather(location: Union[str, Tuple[float, float]], dates: List[str]) -> Dict[str, dict]:
    """Return weather for every date between the earliest and latest input date.

    The `location` may be a place name string or a lat/lon tuple.
    If weather data is unavailable, the value will contain `status: "no info"`.
    """
    coords = _normalize_location(location)
    if coords is None:
        return {"status": "geocode_failed"}

    latitude, longitude = coords

    normalized = []
    for d in dates:
        iso = _parse_date_iso(d)
        if iso:
            normalized.append(iso)

    if not normalized:
        return {"status": "invalid date"}

    start_date = min(normalized)
    end_date = max(normalized)

    api = _call_open_meteo(latitude, longitude, start_date, end_date)

    if not api or "daily" not in api:
        return {"status": "no info"}

    daily = api.get("daily", {})
    times = daily.get("time", [])
    codes = daily.get("weathercode", [])
    temps_min = daily.get("temperature_2m_min", [])
    temps_max = daily.get("temperature_2m_max", [])
    precip = daily.get("precipitation_sum", [])

    weather_by_date: Dict[str, dict] = {}

    for d, c, tmin, tmax, p in zip(
        times,
        codes,
        temps_min,
        temps_max,
        precip,
    ):
        try:
            weather_by_date[d] = _weather_entry(
                int(c),
                float(tmin),
                float(tmax),
                float(p),
            )
        except Exception:
            continue

    result: Dict[str, dict] = {}

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end_dt:
        iso = current.strftime("%Y-%m-%d")
        result[iso] = weather_by_date.get(
            iso,
            {"status": "no info"},
        )
        current += timedelta(days=1)

    return result


if __name__ == "__main__":
	import sys

	if len(sys.argv) < 3:
		print("Usage: python get_weather.py <place|lat,lon> <date1> [date2 ...]")
		print("Example: python get_weather.py \"Paris, France\" 2026-06-15 16/06/2026")
		sys.exit(1)

	location_arg = sys.argv[1]
	dates_cli = sys.argv[2:]
	coords = None
	if "," in location_arg:
		parts = [part.strip() for part in location_arg.split(",")]
		if len(parts) == 2:
			try:
				coords = (float(parts[0]), float(parts[1]))
			except ValueError:
				coords = None

	location = coords if coords is not None else location_arg
	out = get_weather(location, dates_cli)
	print(json.dumps(out, indent=2))

