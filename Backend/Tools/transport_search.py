"""Multi-modal transport search tool (flights, trains, buses) via SerpApi and RapidAPI."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transport_search")

SERP_API_KEY = os.getenv("serp_api")
RAPIDAPI_KEY = os.getenv("rapid_api")

SERP_API_URL = "https://serpapi.com/search"
IRCTC_TRAIN_URL = "https://irctc1.p.rapidapi.com/api/v3/trainBetweenStations"
IRCTC_HOST = "irctc1.p.rapidapi.com"

# preferred_time -> (start_hour, end_hour), used both to build SerpApi's
# outbound_times filter and to filter train/bus results client-side.
TIME_WINDOWS: Dict[str, Tuple[int, int]] = {
    "morning": (6, 12),
    "afternoon": (12, 17),
    "evening": (17, 21),
    "night": (21, 6),  # wraps past midnight
}

RESULT_LIMIT = 5

# Data model
@dataclass
class TransportResult:
    mode: str                      # flight / train / bus
    provider: str                  # airline / train name / bus operator
    identifier: str                # flight number / train number / bus id
    origin: str
    destination: str
    departure_time: Optional[str]
    arrival_time: Optional[str]
    duration: Optional[str]
    price: Optional[float]
    currency: str
    booking_link: str
    raw_note: str = ""             # anything extra worth surfacing

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

REQUIRED_STATE_FIELDS = ["transport_type", "origin_code", "destination_code", "travel_date", "budget"]

def _validate_state(state: Dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_STATE_FIELDS if f not in state or state[f] in (None, "")]
    if missing:
        raise ValueError(f"transport_search: missing required state fields: {missing}")
    if state["transport_type"] not in ("flight", "train", "bus"):
        raise ValueError("transport_search: transport_type must be 'flight', 'train', or 'bus'")

def _time_in_window(time_str: Optional[str], preferred_time: Optional[str]) -> bool:
    """Loose filter: keeps a result if we can't parse its time (avoid over-filtering)."""
    if not preferred_time or not time_str:
        return True
    window = TIME_WINDOWS.get(preferred_time.lower())
    if not window:
        return True
    try:
        hour = int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return True

    start, end = window
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # overnight window (e.g. "night")

# FLIGHT — SerpApi Google Flights engine
def search_flights(state: Dict[str, Any]) -> List[TransportResult]:
    if not SERP_API_KEY:
        raise EnvironmentError("SERP_API_KEY (serp_api) is not set in the environment.")

    params = {
        "engine": "google_flights",
        "departure_id": state["origin_code"],
        "arrival_id": state["destination_code"],
        "outbound_date": state["travel_date"],
        "type": "2",           # one-way
        "currency": state.get("currency", "INR"),
        "hl": "en",
        "adults": str(state.get("num_people", 1)),
        "api_key": SERP_API_KEY,
    }

    if state.get("preferred_time") and state["preferred_time"].lower() in TIME_WINDOWS:
        start, end = TIME_WINDOWS[state["preferred_time"].lower()]
        params["outbound_times"] = f"{start},{end}"

    try:
        resp = requests.get(SERP_API_URL, params=params, timeout=20, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"SerpApi flight search failed: {e}")
        return []

    flights_raw = (data.get("best_flights", []) or []) + (data.get("other_flights", []) or [])
    results: List[TransportResult] = []

    for entry in flights_raw:
        price = entry.get("price")
        legs = entry.get("flights", [])
        if not legs:
            continue

        first_leg = legs[0]
        last_leg = legs[-1]
        airline = first_leg.get("airline", "Unknown airline")
        flight_number = first_leg.get("flight_number", "")

        results.append(TransportResult(
            mode="flight",
            provider=airline,
            identifier=flight_number,
            origin=first_leg.get("departure_airport", {}).get("name", state["origin_code"]),
            destination=last_leg.get("arrival_airport", {}).get("name", state["destination_code"]),
            departure_time=first_leg.get("departure_airport", {}).get("time"),
            arrival_time=last_leg.get("arrival_airport", {}).get("time"),
            duration=str(entry.get("total_duration", "")),
            price=price,
            currency=state.get("currency", "INR"),
            booking_link=data.get("search_metadata", {}).get("google_flights_url", "https://www.google.com/travel/flights"),
        ))

    return results

# TRAIN — IRCTC1 RapidAPI
def search_trains(state: Dict[str, Any]) -> List[TransportResult]:
    if not RAPIDAPI_KEY:
        raise EnvironmentError("RAPIDAPI_KEY is not set in the environment.")

    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": IRCTC_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    params = {
        "fromStationCode": state["origin_code"],
        "toStationCode": state["destination_code"],
        "dateOfJourney": state["travel_date"],
    }

    try:
        resp = requests.get(IRCTC_TRAIN_URL, headers=headers, params=params, timeout=20, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"IRCTC train search failed: {e}")
        return []

    trains_raw = data.get("data", []) or []
    results: List[TransportResult] = []

    for train in trains_raw:
        departure_time = train.get("train_start_time") or train.get("from_std")
        arrival_time = train.get("train_end_time") or train.get("to_sta")

        if not _time_in_window(departure_time, state.get("preferred_time")):
            continue

        results.append(TransportResult(
            mode="train",
            provider="Indian Railways",
            identifier=str(train.get("train_number", "")),
            origin=train.get("from_station_name", state["origin_code"]),
            destination=train.get("to_station_name", state["destination_code"]),
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration=train.get("duration"),
            price=None,  # this endpoint doesn't return fares; needs a separate fare-check call if required
            currency=state.get("currency", "INR"),
            booking_link="https://www.irctc.co.in/nget/train-search",
            raw_note=train.get("train_name", ""),
        ))

    return results

# BUS — no-auth bus booking API
def search_buses(state: Dict[str, Any]) -> List[TransportResult]:

    search_params = {
        "source": state["origin_code"],
        "destination": state["destination_code"],
        "date": state["travel_date"],
    }

    try:
        resp = requests.get(f"https:/freeprojectapi.com/api/BusBooking/searchBus", params=search_params, timeout=20, verify=False)
        resp.raise_for_status()
        buses_raw = resp.json()
        if isinstance(buses_raw, dict):
            buses_raw = buses_raw.get("data", []) or buses_raw.get("results", []) or []
    except requests.RequestException as e:
        logger.warning(f"searchBus failed, trying searchBus2 fallback: {e}")
        try:
            resp = requests.get(f"https:/freeprojectapi.com/api/BusBooking/searchBus2", params=search_params, timeout=20, verify=False)
            resp.raise_for_status()
            buses_raw = resp.json()
            if isinstance(buses_raw, dict):
                buses_raw = buses_raw.get("data", []) or buses_raw.get("results", []) or []
        except requests.RequestException as e2:
            logger.warning(f"searchBus2 also failed: {e2}")
            return []

    results: List[TransportResult] = []
    for bus in buses_raw:
        price = bus.get("fare") or bus.get("price")
        departure_time = bus.get("departureTime") or bus.get("departure_time")

        if price is not None and price > state["budget"] * 1.15:
            continue
        if not _time_in_window(departure_time, state.get("preferred_time")):
            continue

        results.append(TransportResult(
            mode="bus",
            provider=bus.get("operatorName", bus.get("operator", "Unknown operator")),
            identifier=str(bus.get("busId", bus.get("scheduleId", ""))),
            origin=bus.get("source", state["origin_code"]),
            destination=bus.get("destination", state["destination_code"]),
            departure_time=departure_time,
            arrival_time=bus.get("arrivalTime") or bus.get("arrival_time"),
            duration=bus.get("duration"),
            price=price,
            currency=state.get("currency", "INR"),
        ))

    return results

# Budget filter + sort (shared)
def _filter_and_sort(results: List[TransportResult], budget: float) -> List[TransportResult]:
    within_budget = [r for r in results if r.price is None or r.price <= budget * 1.1]
    # Priced-and-cheapest first; unpriced entries (e.g. trains w/o fare data) trail behind.
    within_budget.sort(key=lambda r: (r.price is None, r.price or 0))
    return within_budget[:RESULT_LIMIT]

# Main entry point (called by planner_agent.py)
def transport_search(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
        state: dict with transport_type, origin_code, destination_code,
               travel_date, budget, and optional preferred_time, num_people,
               currency. See module docstring for the full schema.

    Returns:
        {
            "transport_type": str,
            "results": [ {mode, provider, identifier, origin, destination,
                          departure_time, arrival_time, duration, price,
                          currency, booking_link, raw_note}, ... ]  # up to 5
        }
    """
    _validate_state(state)

    logger.info(
        f"Searching {state['transport_type']} from {state['origin_code']} to "
        f"{state['destination_code']} on {state['travel_date']} (budget={state['budget']})"
    )

    if state["transport_type"] == "flight":
        raw_results = search_flights(state)
    elif state["transport_type"] == "train":
        raw_results = search_trains(state)
    else:
        raw_results = search_buses(state)

    top_results = _filter_and_sort(raw_results, state["budget"])

    return {
        "transport_type": state["transport_type"],
        "results": [r.to_dict() for r in top_results],
    }

