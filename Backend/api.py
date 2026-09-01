"""FastAPI server — exposes the LangGraph planner to the Beyond frontend."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adapters import TripPlanRequest, to_frontend_itinerary, trip_request_to_state
from planner_agent import PlannerState, _select_summary_places, build_graph
from general_planner import (
    enrich_swap_alternatives,
    find_destination,
    generate_general_itinerary,
    generate_swap_query,
    get_all_destination_names,
    is_known_destination,
)

GOOGLE_PLACES_API_KEY = os.getenv("Google_places_api") or os.getenv("GOOGLE_PLACES_API_KEY", "")

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
SUMMARY_PLACES_FILE = Path(__file__).with_name("summary_places_output.json")

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


def _save_summary_places(state: PlannerState) -> None:
    """Persist the summary places to summary_places_output.json for future use."""
    try:
        summary_places = _select_summary_places(
            state["places"], 
            state["travel_style"],
            max_total=40,
            max_per_city=10
        )
        payload = {
            "destination":      state["destination"],
            "travel_style":     state["travel_style"],
            "cities":           state["cities"],
            "summary_places_count": len(summary_places),
            "summary_places":   summary_places,
        }
        with SUMMARY_PLACES_FILE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"[SAVED] summary_places_output.json updated for '{state['destination']}' ({len(summary_places)} places)")
    except Exception as exc:
        print(f"[WARN] Could not save summary_places_output.json: {exc}")


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


# ── General planner helper ────────────────────────────────────────────────────

def _run_general_planner(req: TripPlanRequest) -> dict | None:
    """
    Attempt to generate an itinerary using the dataset-based general planner.
    Returns the formatted frontend response dict, or None if the destination
    is not found in the dataset or generation fails.
    """
    try:
        itinerary = generate_general_itinerary(
            destination=req.destination.strip(),
            days=req.days,
            travel_style=req.travel_style,
            number_of_people=req.number_of_people,
            party_type=req.party_type.replace("-", " "),
            start_date=req.trip_start_date,
        )

        if itinerary is None:
            return None

        if "raw" in itinerary:
            print("[GENERAL PLANNER] LLM returned unparseable JSON — skipping.")
            return None

        if not itinerary.get("days"):
            print("[GENERAL PLANNER] LLM returned empty days list — skipping.")
            return None

        # Build a minimal state-like dict for the adapter
        pseudo_state = {"itinerary": itinerary}
        result = to_frontend_itinerary(req, pseudo_state)

        if not result.get("days"):
            return None

        # Save to itinerary_output.json
        _save_general_itinerary(req, itinerary)

        return result

    except Exception as exc:
        print(f"[GENERAL PLANNER] Error: {exc}")
        return None


def _save_general_itinerary(req: TripPlanRequest, itinerary: dict) -> None:
    """Persist general planner output to itinerary_output.json."""
    try:
        dest_entry = find_destination(req.destination)
        cities = itinerary.get("cities_visited", [req.destination])
        payload = {
            "destination":      req.destination,
            "start_date":       req.trip_start_date,
            "cities":           cities,
            "days":             req.days,
            "travel_style":     req.travel_style,
            "number_of_people": req.number_of_people,
            "party_type":       req.party_type,
            "weather_skip":     True,
            "weather":          {},
            "places_count":     0,
            "places":           [],
            "itinerary":        itinerary,
            "source":           "general_planner",
            "dataset_id":       dest_entry.get("id") if dest_entry else None,
        }
        with ITINERARY_FILE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"[SAVED] itinerary_output.json updated via general planner for '{req.destination}'")
    except Exception as exc:
        print(f"[WARN] Could not save general planner output: {exc}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Swap Alternatives ─────────────────────────────────────────────────────────

class SwapRequest(BaseModel):
    place: str
    category: str
    city: str
    destination: str
    travel_style: str = "calm"


class SwapAlternative(BaseModel):
    name: str
    address: str
    rating: Optional[float] = None
    place_id: str
    description: Optional[str] = None
    tips: Optional[str] = None
    fun_fact: Optional[str] = None
    image: Optional[str] = None


@app.post("/api/swap-alternatives", response_model=List[SwapAlternative])
async def swap_alternatives(req: SwapRequest) -> list:
    """
    1. Use Groq LLM to generate an optimised Google Places Text Search query.
    2. Call Google Places API (New) — Text Search endpoint.
    3. Use Groq LLM to enrich the candidate places with vivid descriptions and tips.
    4. Return up to 4 alternative places of the same category.
    """
    if not GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=503, detail="Google Places API key not configured.")

    # Step 1 — LLM generates the Places query
    query = generate_swap_query(
        place=req.place,
        category=req.category,
        city=req.city,
        destination=req.destination,
        travel_style=req.travel_style,
    )
    print(f"[SWAP] LLM query for '{req.place}' in '{req.city}': {query!r}")

    # Step 2 — Call Google Places API (New): Text Search
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.id",
    }
    payload = {
        "textQuery": query,
        "languageCode": "en",
        "regionCode": "IN",
        "maxResultCount": 8,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers=headers,
                json=payload,
            )
        data = resp.json()
    except Exception as exc:
        print(f"[SWAP] Google Places call failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Google Places API error: {exc}")

    if resp.status_code != 200:
        err_msg = data.get("error", {}).get("message", str(data))
        print(f"[SWAP] Google Places API error {resp.status_code}: {err_msg}")
        raise HTTPException(
            status_code=502,
            detail=f"Google Places API error: {err_msg}",
        )

    results = data.get("places", [])

    # Filter out the original place (name overlap) and take max 4
    original_norm = req.place.lower().split(",")[0].strip()
    raw_candidates = []
    for r in results:
        name = r.get("displayName", {}).get("text", "")
        if not name:
            continue
        if original_norm and original_norm in name.lower():
            continue
        raw_candidates.append({
            "name": name,
            "address": r.get("formattedAddress", ""),
            "rating": r.get("rating"),
            "place_id": r.get("id", ""),
        })
        if len(raw_candidates) >= 4:
            break

    # Step 3 — Enrich with LLM-generated descriptions and insider tips
    enriched = enrich_swap_alternatives(
        raw_candidates,
        category=req.category,
        city=req.city,
        destination=req.destination,
        travel_style=req.travel_style,
    )

    alternatives = [
        SwapAlternative(
            name=p.get("name", ""),
            address=p.get("address", ""),
            rating=p.get("rating"),
            place_id=p.get("place_id", ""),
            description=p.get("description"),
            tips=p.get("tips"),
            fun_fact=p.get("fun_fact"),
            image=p.get("image"),
        )
        for p in enriched
    ]

    print(f"[SWAP] Returning {len(alternatives)} enriched alternatives for '{req.place}'")
    return alternatives


# ── Add Activity ──────────────────────────────────────────────────────────────

class AddActivityRequest(BaseModel):
    query: str                  # natural-language user request, e.g. "a nice rooftop restaurant"
    slot: str                   # 'morning' | 'afternoon' | 'evening'
    day_date: str               # YYYY-MM-DD
    destination: str
    city: str = ""
    travel_style: str = "calm"


class AddActivityResponse(BaseModel):
    place: str
    time: Optional[str] = None
    duration: str
    category: str
    description: str
    tips: str
    fun_fact: Optional[str] = None


@app.post("/api/add-activity", response_model=AddActivityResponse)
async def add_activity(req: AddActivityRequest) -> dict:
    """
    LLM generates a structured ActivityItem from a natural-language query.
    Uses Google Places API (New) to find a real matching place, then enriches
    it with a description and tips using the LLM.
    """
    if not GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=503, detail="Google Places API key not configured.")

    city_context = req.city or req.destination

    # Step 1 — LLM interprets the query into a Places search query
    system_prompt = (
        "You are a travel assistant. Given a user's request for an activity, "
        "generate ONE concise Google Places Text Search query to find a real matching venue. "
        "Rules:\n"
        "- Return ONLY the raw query string. No JSON, no quotes, no explanation.\n"
        "- Keep it under 12 words.\n"
        "- Always include the city name."
    )
    user_msg = (
        f"User wants to add to {req.slot} in {city_context}: '{req.query}'\n"
        f"Travel style: {req.travel_style}\n"
        "Google Places search query:"
    )
    try:
        llm_resp = groq_client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.2,
            max_tokens=48,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        search_query = llm_resp.choices[0].message.content.strip().strip('"\'')
    except Exception as exc:
        search_query = f"{req.query} {city_context}"

    print(f"[ADD-ACTIVITY] Searching Places for: {search_query!r}")

    # Step 2 — Google Places API (New): Text Search
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.id,places.primaryTypeDisplayName",
    }
    places_payload = {
        "textQuery": search_query,
        "languageCode": "en",
        "regionCode": "IN",
        "maxResultCount": 1,
    }
    place_name = req.query
    place_address = city_context
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            places_resp = await client.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers=headers,
                json=places_payload,
            )
        places_data = places_resp.json()
        if places_resp.status_code == 200 and places_data.get("places"):
            top = places_data["places"][0]
            place_name = top.get("displayName", {}).get("text", req.query)
            place_address = top.get("formattedAddress", city_context)
    except Exception as exc:
        print(f"[ADD-ACTIVITY] Places lookup failed: {exc}")

    # Step 3 — LLM generates a rich ActivityItem
    enrich_system = (
        "You are a travel storyteller for the Beyond app. "
        "Return a JSON object for a single travel activity. No extra text.\n"
        "Schema: {\"place\": str, \"duration\": \"Xh\", "
        "\"category\": str, \"description\": str (2-3 sentences, vivid), "
        "\"tips\": str (practical insider tip), \"fun_fact\": str or null}\n"
        "CRITICAL: No emojis, no em-dashes anywhere."
    )
    enrich_user = (
        f"Place found: {place_name}\n"
        f"Address: {place_address}\n"
        f"User request: {req.query}\n"
        f"Slot: {req.slot}\n"
        f"Destination: {req.destination} | Travel style: {req.travel_style}\n"
        "Generate the activity JSON now."
    )
    try:
        enrich_resp = groq_client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.4,
            max_tokens=256,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": enrich_system},
                {"role": "user", "content": enrich_user},
            ],
        )
        raw = enrich_resp.choices[0].message.content.strip()
        activity_data = json.loads(raw)
    except Exception as exc:
        print(f"[ADD-ACTIVITY] LLM enrichment failed: {exc}")
        activity_data = {
            "place": f"{place_name}, {city_context}",
            "duration": "2h",
            "category": "Explore",
            "description": f"A great stop in {city_context} based on your request.",
            "tips": "Check opening hours and book in advance if possible.",
            "fun_fact": None,
        }

    # Ensure required fields exist
    activity_data.setdefault("place", f"{place_name}, {city_context}")
    activity_data.setdefault("duration", "2h")
    activity_data.setdefault("category", "Explore")
    activity_data.setdefault("description", f"An activity in {city_context}.")
    activity_data.setdefault("tips", "Check opening hours before visiting.")

    print(f"[ADD-ACTIVITY] Returning activity: {activity_data.get('place')}")
    return activity_data


@app.get("/api/destinations")
def get_destinations() -> dict:
    """Return the list of known destination names from the dataset."""
    names = get_all_destination_names()
    return {"destinations": names, "count": len(names)}


@app.get("/api/saved-itinerary")
def get_saved_itinerary() -> dict:
    """Return the raw contents of the last saved planner run."""
    if not ITINERARY_FILE.exists():
        raise HTTPException(status_code=404, detail="itinerary_output.json not found")
    with ITINERARY_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@app.post("/api/plan-trip-general")
def plan_trip_general(req: TripPlanRequest) -> dict:
    """
    Dataset-based itinerary generation endpoint.
    Uses the india_tourism_dataset.json to generate itineraries via LLM.
    Returns 404 if the destination is not found in the dataset.
    """
    if not is_known_destination(req.destination):
        raise HTTPException(
            status_code=404,
            detail=f"'{req.destination}' not found in dataset. Use /api/plan-trip for the full planner.",
        )

    result = _run_general_planner(req)
    if result is None:
        raise HTTPException(
            status_code=500,
            detail="General planner failed to generate itinerary.",
        )
    return result


@app.post("/api/plan-trip")
def plan_trip(req: TripPlanRequest) -> dict:
    """
    1. Try the general (dataset-based) planner first for known destinations.
    2. Fall back to the live LangGraph planner.
    3. Last resort: fall back to saved itinerary_output.json.
    """
    # ── Step 0: Try general planner for dataset destinations ──────────────────
    if is_known_destination(req.destination):
        print(f"[PLANNER] '{req.destination}' found in dataset — trying general planner first...")
        general_result = _run_general_planner(req)
        if general_result is not None:
            return general_result
        print("[PLANNER] General planner failed — falling through to live planner.")

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
        _save_summary_places(final_state)

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
