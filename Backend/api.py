"""FastAPI server — exposes the LangGraph planner to the Beyond frontend."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from adapters import TripPlanRequest, to_frontend_itinerary, trip_request_to_state
from planner_agent import PlannerState, _select_summary_places, build_graph

app = FastAPI(title="Beyond Planner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ITINERARY_FILE = Path(__file__).with_name("itinerary_output.json")

# ── Lazy planner singleton ────────────────────────────────────────────────────
_planner = None


def _get_planner():
    global _planner
    if _planner is None:
        _planner = build_graph()
    return _planner


# ── Save helper ───────────────────────────────────────────────────────────────

def _save_state(state: PlannerState) -> None:
    """Persist the full planner state to itinerary_output.json for future use."""
    try:
        payload = {
            "destination":      state["destination"],
            "start_date":       state["start_date"],
            "cities":           state["cities"],
            "days":             state["days"],
            "travel_style":     state["travel_style"],
            "number_of_people": state["number_of_people"],
            "party_type":       state["party_type"],
            "weather_skip":     state["weather_skip"],
            "weather":          state["weather"],
            "places_count":     len(state["places"]),
            "places":           state["places"],
            "itinerary":        state["itinerary"],
        }
        with ITINERARY_FILE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"[SAVED] itinerary_output.json updated for '{state['destination']}'")
    except Exception as exc:
        print(f"[WARN] Could not save itinerary_output.json: {exc}")


# ── Saved-file fallback ───────────────────────────────────────────────────────

def _load_saved_fallback(req: TripPlanRequest) -> dict:
    """
    Load the most-recently saved planner output and adapt it to the current
    request's start_date / number of days.  Used only when the live planner fails.
    """
    if not ITINERARY_FILE.exists():
        raise FileNotFoundError("itinerary_output.json not found — no fallback available.")

    with ITINERARY_FILE.open("r", encoding="utf-8") as fh:
        raw_data = json.load(fh)

    saved_itin = None
    start_date = date.fromisoformat(req.trip_start_date)

    # ── Primary path: rich 'itinerary' object ─────────────────────────────────
    if saved_itin and isinstance(saved_itin, dict) and saved_itin.get("days"):
        saved_days = saved_itin["days"]
        adapted_days = []
        for i in range(req.days):
            day = saved_days[i % len(saved_days)].copy()
            day["date"] = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            day["day"] = i + 1
            adapted_days.append(day)

        general_tips = saved_itin.get("general_tips") or []
        if isinstance(general_tips, str):
            general_tips = [general_tips] if general_tips.strip() else []

        adapted_itin = {
            "destination":     saved_itin.get("destination") or req.destination,
            "cities_visited":  saved_itin.get("cities_visited") or [req.destination],
            "total_days":      req.days,
            "party_type":      req.party_type,
            "travel_style":    req.travel_style,
            "number_of_people": req.number_of_people,
            "data_warning":    saved_itin.get("data_warning") or "",
            "days":            adapted_days,
            "general_tips":    general_tips,
        }
        return to_frontend_itinerary(req, {"itinerary": adapted_itin})

    # ── Secondary path: rebuild from raw places list ───────────────────────────
    cities = raw_data.get("cities") or [req.destination]
    places = _select_summary_places(raw_data.get("places") or [], req.travel_style, max_total=40, max_per_city=10)
    days = []

    for i in range(req.days):
        current_date = start_date + timedelta(days=i)
        city = cities[i % len(cities)]
        city_places = [p for p in places if p.get("city") == city][:3]
        morning, afternoon, evening = [], [], []

        if city_places:
            morning.append({
                "place": city_places[0].get("name", city),
                "time": "08:30", "duration": "2h", "category": "Explore",
                "description": "A traveller-facing highlight selected from the saved place data.",
                "tips": "Check current opening hours before visiting.",
            })
            if len(city_places) > 1:
                afternoon.append({
                    "place": city_places[1].get("name", city),
                    "time": "13:00", "duration": "2h", "category": "Culture",
                    "description": "A good mid-day stop with enough time for lunch nearby.",
                    "tips": "Keep this flexible if weather or traffic slows the day.",
                })
            if len(city_places) > 2:
                evening.append({
                    "place": city_places[2].get("name", city),
                    "time": "18:30", "duration": "2h", "category": "Scenic",
                    "description": "An easy evening stop to close the day without rushing.",
                    "tips": "Plan sunset or evening travel time with a buffer.",
                })
        else:
            morning.append({
                "place": f"{city} highlights", "time": "08:30",
                "duration": "2h", "category": "Explore",
                "description": "A gentle local highlight to start the day.",
                "tips": "A local-first stop to keep the day relaxed.",
            })

        days.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "theme": f"{city} highlights",
            "weather": "A comfortable day for sightseeing and slow travel",
            "morning": morning, "afternoon": afternoon, "evening": evening,
            "notes": (
                f"⚠️ Live planner unavailable — showing last saved output "
                f"({raw_data.get('destination', 'unknown destination')}). "
                "Dates have been adjusted to your requested start date."
            ),
        })

    return {
        "request": req.model_dump(),
        "summary": (
            f"A {req.days}-day {req.travel_style.replace('-', ' ')} escape through {req.destination} "
            f"for {req.number_of_people} travellers in a {req.party_type} group. "
            f"⚠️ Showing last saved output — live planner was unavailable."
        ),
        "days": days,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/saved-itinerary")
def get_saved_itinerary() -> dict:
    """Return the raw contents of the last saved planner run."""
    if not ITINERARY_FILE.exists():
        raise HTTPException(status_code=404, detail="itinerary_output.json not found")
    with ITINERARY_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@app.post("/api/plan-trip")
def plan_trip(req: TripPlanRequest) -> dict:
    """
    1. Run the live LangGraph planner for the requested destination.
    2. Save the output to itinerary_output.json.
    3. Return the formatted itinerary to the frontend.

    If the live planner fails for any reason, fall back to the most recently
    saved itinerary_output.json (dates adapted to the current request).
    """
    # ── Step 1: Live planner ──────────────────────────────────────────────────
    live_error: Exception | None = None
    try:
        print(f"[PLANNER] Running live planner for '{req.destination}' ({req.days} days)...")
        initial_state = trip_request_to_state(req)
        final_state = _get_planner().invoke(initial_state)

        # Validate: planner must return a non-empty itinerary
        itin = final_state.get("itinerary") or {}
        if "raw" in itin:
            raise ValueError("Planner returned unparseable JSON — itinerary stored as raw string")
        if not itin.get("days"):
            raise ValueError("Planner returned an empty days list")

        # ── Step 2: Save to disk ──────────────────────────────────────────────
        _save_state(final_state)

        # ── Step 3: Format & return ───────────────────────────────────────────
        result = to_frontend_itinerary(req, final_state)
        if result.get("days"):
            return result
        raise ValueError("to_frontend_itinerary returned empty days")

    except Exception as exc:
        live_error = exc
        print(f"[WARN] Live planner failed: {exc}")

    # ── Fallback: last saved itinerary ────────────────────────────────────────
    try:
        print("[FALLBACK] Falling back to saved itinerary_output.json...")
        return _load_saved_fallback(req)
    except Exception as fallback_exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Live planner failed ({live_error}) and no saved itinerary "
                f"is available ({fallback_exc})."
            ),
        )
