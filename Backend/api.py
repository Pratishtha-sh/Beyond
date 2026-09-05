"""FastAPI server — exposes the LangGraph planner to the Beyond frontend."""

from __future__ import annotations

import json
import os
import re
import traceback
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from groq import Groq
from adapters import TripPlanRequest, to_frontend_itinerary, trip_request_to_state
from agents.planner_agent import PlannerState, _select_summary_places, build_graph, create_initial_state
from general_planner import (
    _extract_json,
    enrich_swap_alternatives,
    fetch_pexels_image,
    find_destination,
    generate_general_itinerary,
    generate_swap_query,
    get_all_destination_names,
    is_known_destination,
)

GROQ_API_KEY = os.getenv("Groq_api_key") or os.getenv("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
LLM_MODEL = "openai/gpt-oss-120b"
GOOGLE_PLACES_API_KEY = (
    os.getenv("Google_places_api")
    or os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_PLACES_API")
    or ""
)
TAVILY_API_KEY = (
    os.getenv("Tavily_api")
    or os.getenv("TAVILY_API_KEY")
    or os.getenv("TAVILY_API")
    or ""
)

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

# Lazy planner singleton
_planner = None

def _get_planner():
    global _planner
    if _planner is None:
        _planner = build_graph()
    return _planner

# Save helper

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

# Saved-file fallback

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

    # Primary path: rich 'itinerary' object
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

    # Secondary path: rebuild from raw places list
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

# General planner helper

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
        pseudo_state = {"itinerary": itinerary, "source": "general_planner"}
        result = to_frontend_itinerary(req, pseudo_state)
        result["source"] = "general_planner"
        result["planner_type"] = "general_planner"

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

# Endpoints

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

# Swap Alternatives

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

# Add Activity

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
    image: Optional[str] = None

@app.post("/api/add-activity", response_model=AddActivityResponse)
async def add_activity(req: AddActivityRequest) -> dict:
    """
    Interprets user's natural-language activity request.
    Searches via Google Places API (New), falling back to Tavily Search API if needed.
    Enriches with engaging description, practical tips, fun fact, and authentic photos.
    """
    city_context = (req.city or req.destination or "").strip()

    # Step 1 — Clean search query via LLM or heuristic
    search_query = f"{req.query} in {city_context}".strip()
    if groq_client:
        system_prompt = (
            "You are a travel assistant. Given a user's request for an activity, "
            "generate ONE concise search query to find a real matching venue or place. "
            "Rules:\n"
            "- Return ONLY the raw query string. No JSON, no quotes, no explanation.\n"
            "- Keep it under 10 words.\n"
            "- Always include the city name."
        )
        user_msg = (
            f"User wants to add to {req.slot} in {city_context}: '{req.query}'\n"
            f"Travel style: {req.travel_style}\n"
            "Search query:"
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
            candidate_q = llm_resp.choices[0].message.content.strip().strip('"\'')
            if candidate_q and len(candidate_q) > 2:
                search_query = candidate_q
        except Exception as exc:
            print(f"[ADD-ACTIVITY] Query formulation error: {exc}")

    if not search_query.strip():
        search_query = f"{req.query} in {city_context}".strip()

    print(f"[ADD-ACTIVITY] Searching for venue with query: {search_query!r}")

    place_name: Optional[str] = None
    place_address: Optional[str] = None
    search_snippet: str = ""
    candidate_image: Optional[str] = None

    # Step 2a — Try Google Places API (New): Text Search
    if GOOGLE_PLACES_API_KEY:
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.id,places.primaryTypeDisplayName",
            }
            places_payload = {
                "textQuery": search_query,
                "languageCode": "en",
                "maxResultCount": 3,
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                places_resp = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers=headers,
                    json=places_payload,
                )
            if places_resp.status_code == 200:
                places_data = places_resp.json()
                places_list = places_data.get("places", [])
                if places_list:
                    top = places_list[0]
                    place_name = top.get("displayName", {}).get("text")
                    place_address = top.get("formattedAddress")
                    print(f"[ADD-ACTIVITY] Google Places matched: '{place_name}' ({place_address})")
            else:
                print(f"[ADD-ACTIVITY] Google Places status {places_resp.status_code}: {places_resp.text[:150]}")
        except Exception as exc:
            print(f"[ADD-ACTIVITY] Google Places search failed: {exc}")

    # Step 2b — Fallback to Tavily Search API if Google Places yielded nothing
    if not place_name and TAVILY_API_KEY:
        try:
            print(f"[ADD-ACTIVITY] Falling back to Tavily search for: {search_query!r}")
            tavily_payload = {
                "api_key": TAVILY_API_KEY,
                "query": f"{search_query} attractions places in {city_context}",
                "max_results": 3,
                "search_depth": "basic",
                "include_images": True,
            }
            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                tavily_resp = await client.post(
                    "https://api.tavily.com/search",
                    json=tavily_payload,
                )
            if tavily_resp.status_code == 200:
                t_data = tavily_resp.json()
                t_results = t_data.get("results", [])
                if t_results:
                    top_t = t_results[0]
                    raw_title = top_t.get("title", "")
                    cand_name = re.split(r"\s*[-|–—:]\s*", raw_title)[0].strip()
                    place_name = cand_name or raw_title
                    search_snippet = top_t.get("content", "")
                    place_address = city_context
                    print(f"[ADD-ACTIVITY] Tavily matched: '{place_name}'")
                images = t_data.get("images", [])
                if images and isinstance(images, list) and isinstance(images[0], str) and images[0].startswith("http"):
                    candidate_image = images[0]
            else:
                print(f"[ADD-ACTIVITY] Tavily status {tavily_resp.status_code}: {tavily_resp.text[:150]}")
        except Exception as exc:
            print(f"[ADD-ACTIVITY] Tavily search failed: {exc}")

    # Fallback if both searches return no match
    if not place_name:
        place_name = req.query.strip().title()
        place_address = city_context

    # Step 3 — LLM generates a rich, storytelling ActivityItem
    enrich_system = (
        "You are an expert travel storyteller for the Beyond app. "
        "Return a JSON object for a single travel activity. No extra text, no markdown codeblocks, no reasoning.\n"
        "Output JSON schema:\n"
        "{\n"
        '  "place": "Name of the venue, City",\n'
        '  "duration": "1.5h or 2h",\n'
        '  "category": "Sightseeing / Dining / Culture / Nature / Adventure",\n'
        '  "description": "2-3 engaging, vivid sentences about the experience and ambiance.",\n'
        '  "tips": "One practical insider tip (best timing, dress code, ticketing, what to try).",\n'
        '  "fun_fact": "A fascinating historical or local trivia fact (or null)."\n'
        "}\n"
        "CRITICAL: No emojis, no em-dashes anywhere."
    )
    enrich_user = (
        f"Place found: {place_name}\n"
        f"Address: {place_address}\n"
        f"Snippet info: {search_snippet[:250] if search_snippet else 'N/A'}\n"
        f"User request: {req.query}\n"
        f"Slot: {req.slot}\n"
        f"Destination: {req.destination} | Travel style: {req.travel_style}\n"
        "Generate the single activity JSON object now."
    )
    activity_data: dict = {}
    if groq_client:
        try:
            enrich_resp = groq_client.chat.completions.create(
                model=LLM_MODEL,
                temperature=0.3,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": enrich_system},
                    {"role": "user", "content": enrich_user},
                ],
            )
            raw = enrich_resp.choices[0].message.content.strip()
            parsed = _extract_json(raw)
            if isinstance(parsed, dict):
                activity_data = parsed
        except Exception as exc:
            print(f"[ADD-ACTIVITY] LLM enrichment failed: {exc}")

    def _sanitize_val(val: Optional[str], default: str = "") -> str:
        s = str(val or default).strip()
        s = s.replace("—", " - ").replace("–", " - ")
        return re.sub(r"[\U00010000-\U0010ffff]", "", s).strip()

    raw_place = activity_data.get("place") or f"{place_name}, {city_context}"
    activity_data["place"] = _sanitize_val(raw_place, f"{place_name}, {city_context}")
    activity_data["duration"] = _sanitize_val(activity_data.get("duration"), "2h")
    activity_data["category"] = _sanitize_val(activity_data.get("category"), "Explore")
    activity_data["description"] = _sanitize_val(
        activity_data.get("description"),
        f"A wonderful {req.slot} stop in {city_context} tailored to your request.",
    )
    activity_data["tips"] = _sanitize_val(
        activity_data.get("tips"),
        "Check operating hours and book in advance when possible.",
    )
    if activity_data.get("fun_fact"):
        activity_data["fun_fact"] = _sanitize_val(activity_data.get("fun_fact"))
    else:
        activity_data["fun_fact"] = None

    # Step 4 — Image Lookup
    image_url = candidate_image
    if not image_url:
        try:
            image_url = fetch_pexels_image(
                place_name,
                fallback_query=f"{place_name} {city_context}",
                category=activity_data.get("category"),
            )
        except Exception as exc:
            print(f"[ADD-ACTIVITY] Image search failed: {exc}")

    activity_data["image"] = image_url

    print(f"[ADD-ACTIVITY] Successfully created activity: {activity_data.get('place')}")
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
    # Step 0: Try general planner for dataset destinations
    if is_known_destination(req.destination):
        print(f"[PLANNER] '{req.destination}' found in dataset — trying general planner first...")
        general_result = _run_general_planner(req)
        if general_result is not None:
            return general_result
        print("[PLANNER] General planner failed — falling through to live planner.")

    # Step 1: Live planner
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

        # Step 2: Save to disk
        _save_state(final_state)
        _save_summary_places(final_state)

        # Step 3: Format & return
        final_state["source"] = "planner_agent"
        result = to_frontend_itinerary(req, final_state)
        result["source"] = "planner_agent"
        result["planner_type"] = "planner_agent"
        if result.get("days"):
            return result
        raise ValueError("to_frontend_itinerary returned empty days")

    except Exception as exc:
        live_error = exc
        print(f"[WARN] Live planner failed: {exc}")

    # Fallback: last saved itinerary
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

class ChatPlanRequest(BaseModel):
    query: str
    itinerary: Optional[dict] = None
    destination: Optional[str] = None
    days: Optional[int] = None
    travel_style: Optional[str] = None
    hotel_type: Optional[str] = None
    budget_tier: Optional[str] = None
    transport_type: Optional[str] = None
    number_of_people: Optional[int] = None
    party_type: Optional[str] = None
    start_date: Optional[str] = None

@app.post("/api/chat-plan")
def chat_plan(req: ChatPlanRequest) -> dict:
    """
    Direct endpoint for chat-based trip generation and modification.
    Processes user query using the Planner Agent (LangGraph + Groq LLM + Tools).
    Returns updated itinerary matching the App.tsx format along with hotel and transport options.
    """
    try:
        initial_state = create_initial_state(
            destination=req.destination or "Goa",
            days=req.days or 3,
            travel_style=req.travel_style or "calm",
            number_of_people=req.number_of_people or 2,
            party_type=req.party_type or "friends",
            start_date=req.start_date or (date.today() + timedelta(days=7)).strftime("%Y-%m-%d"),
            user_query=req.query,
            hotel_type=req.hotel_type or "Mid-range",
            budget_tier=req.budget_tier or "₹5K – ₹15K",
            transport_type=req.transport_type or "Flight",
        )
        if req.itinerary:
            initial_state["itinerary"] = req.itinerary

        planner = _get_planner()
        final_state = planner.invoke(initial_state)

        intent = final_state.get("intent", "generate_itinerary")
        user_message = final_state.get("user_message", "Your itinerary has been generated!")

        # Fast return for unsupported / off-topic / prompt injection queries
        if intent == "unsupported_query":
            return {
                "intent": intent,
                "user_message": user_message,
                "itinerary": req.itinerary,
                "hotel_options": final_state.get("hotel_options") or [],
                "selected_hotel": final_state.get("selected_hotel"),
                "transport_options": final_state.get("transport_options") or [],
                "selected_transport": final_state.get("selected_transport"),
                "budget_analysis": final_state.get("budget_analysis"),
                "optimization_confirmation": None,
                "api_errors": final_state.get("api_errors") or [],
            }

        itinerary = final_state.get("itinerary") or {}

        # If itinerary exists, format days properly
        if itinerary and "days" in itinerary and itinerary["days"]:
            itinerary["source"] = "planner_agent"
            itinerary["planner_type"] = "planner_agent"
            itinerary.setdefault("request", {
                "destination": final_state.get("destination", "Your Trip"),
                "trip_start_date": final_state.get("start_date", ""),
                "days": final_state.get("days", len(itinerary.get("days", []))),
                "travel_style": final_state.get("travel_style", "calm"),
                "number_of_people": final_state.get("number_of_people", 2),
                "party_type": final_state.get("party_type", "friends"),
            })
            itinerary.setdefault("summary", f"A {final_state.get('days', 3)}-day journey through {final_state.get('destination', 'your destination')}.")

            if final_state.get("selected_transport") and not itinerary.get("best_flight"):
                itinerary["best_flight"] = final_state["selected_transport"]
                itinerary["transport"] = final_state["selected_transport"]
            if final_state.get("hotel_options") and not itinerary.get("hotel_options"):
                itinerary["hotel_options"] = final_state["hotel_options"]
                itinerary["selected_hotel"] = final_state.get("selected_hotel")
            budget_analysis = final_state.get("budget_analysis") or {}
            if isinstance(budget_analysis, dict) and budget_analysis.get("breakdown") and not itinerary.get("budget_breakdown"):
                itinerary["budget_breakdown"] = budget_analysis["breakdown"]

        # Build optimization_confirmation for frontend confirmation card
        optimization_confirmation = None
        intent = final_state.get("intent", "generate_itinerary")
        budget_analysis = final_state.get("budget_analysis") or {}
        if intent == "budget_optimization" and isinstance(budget_analysis, dict):
            alternatives_found = budget_analysis.get("alternatives_found", [])
            conf: dict = {"requires_confirmation": bool(alternatives_found), "total_savings": 0.0}
            for alt in alternatives_found:
                cat = alt.get("category", "")
                if cat == "transport":
                    all_alts = (alt.get("details") or {}).get("all_alternatives", [])
                    conf["transport"] = {
                        "original_mode": alt.get("original_item", ""),
                        "original_cost": alt.get("original_cost", 0),
                        "alternatives": all_alts,
                    }
                elif cat == "accommodation":
                    conf["hotel"] = {
                        "original_name": alt.get("original_item", ""),
                        "original_cost": alt.get("original_cost", 0),
                        "suggested_name": alt.get("suggested_alternative", ""),
                        "new_cost": alt.get("new_cost", 0),
                        "savings": alt.get("savings", 0),
                        "booking_link": alt.get("booking_link", ""),
                        "details": alt.get("details", {}),
                    }
                conf["total_savings"] = round(conf["total_savings"] + float(alt.get("savings", 0)), 2)
            optimization_confirmation = conf

        # Collect API errors / warnings for frontend display
        api_errors = list(final_state.get("api_errors") or [])
        if isinstance(budget_analysis, dict) and budget_analysis.get("api_errors"):
            for err in budget_analysis.get("api_errors", []):
                if err not in api_errors:
                    api_errors.append(err)

        if optimization_confirmation is not None:
            optimization_confirmation["api_errors"] = api_errors

        return {
            "intent": intent,
            "user_message": final_state.get("user_message", "Your itinerary has been generated!"),
            "itinerary": itinerary,
            "hotel_options": final_state.get("hotel_options") or [],
            "selected_hotel": final_state.get("selected_hotel"),
            "transport_options": final_state.get("transport_options") or [],
            "selected_transport": final_state.get("selected_transport"),
            "budget_analysis": budget_analysis,
            "optimization_confirmation": optimization_confirmation,
            "api_errors": api_errors,
        }
    except Exception as exc:
        print(f"[CHAT-PLAN] Error running planner agent: {exc}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))

# Apply Optimization — patches itinerary when user confirms a switch

class ApplyOptimizationRequest(BaseModel):
    itinerary: dict
    category: str                   # "transport" | "hotel"
    selected_alternative: dict      # { mode, provider, new_cost, booking_link, ... }
    num_people: int = 2
    days: int = 3

@app.post("/api/apply-optimization")
def apply_optimization(req: ApplyOptimizationRequest) -> dict:
    """
    Applies a user-confirmed budget optimization to the itinerary.
    Patches transport or hotel data in-place and recalculates budget totals.
    Returns the updated itinerary so the frontend can replace its state.
    """
    itinerary = req.itinerary
    alt = req.selected_alternative
    category = req.category.lower()

    if category == "transport":
        new_mode = alt.get("mode", "Train")
        new_cost = float(alt.get("new_cost", 0))
        provider = alt.get("provider", "")
        booking_link = alt.get("booking_link", "")
        price_per_person = round(new_cost / max(req.num_people * 2, 1), 2)  # roundtrip per person

        transport_patch = {
            "mode": new_mode,
            "provider": provider,
            "price": price_per_person,
            "price_per_person": price_per_person,
            "total_price": new_cost,
            "booking_link": booking_link,
        }
        itinerary["best_flight"] = transport_patch
        itinerary["transport"] = transport_patch

        # Recalculate budget breakdown
        bd = itinerary.get("budget_breakdown") or {}
        old_transport = float(bd.get("transport_total", 0))
        bd["transport_total"] = new_cost
        if old_transport and bd.get("grand_total"):
            bd["grand_total"] = round(bd["grand_total"] - old_transport + new_cost, 2)
            bd["per_person_total"] = round(bd["grand_total"] / max(req.num_people, 1), 2)
        itinerary["budget_breakdown"] = bd

    elif category == "hotel":
        new_name = alt.get("name") or alt.get("suggested_alternative", "Budget Hotel")
        new_cost = float(alt.get("new_cost", 0))
        price_per_night = round(new_cost / max(req.days, 1), 2)
        provider = alt.get("platform", alt.get("provider", "Booking.com"))
        booking_link = alt.get("booking_link", "")

        hotel_patch = {
            "name": new_name,
            "price_per_night": price_per_night,
            "total_cost": new_cost,
            "platform": provider,
            "booking_link": booking_link,
            "rating": alt.get("rating"),
            "image_url": alt.get("image_url", ""),
        }
        itinerary["selected_hotel"] = hotel_patch

        # Update per-day selected_hotel and top-level hotel_options
        for day in itinerary.get("days", []):
            if isinstance(day, dict):
                day["selected_hotel"] = hotel_patch

        # Recalculate budget breakdown
        bd = itinerary.get("budget_breakdown") or {}
        old_hotel = float(bd.get("hotel_total", 0))
        bd["hotel_total"] = new_cost
        bd["hotel_per_night"] = price_per_night
        if old_hotel and bd.get("grand_total"):
            bd["grand_total"] = round(bd["grand_total"] - old_hotel + new_cost, 2)
            bd["per_person_total"] = round(bd["grand_total"] / max(req.num_people, 1), 2)
        itinerary["budget_breakdown"] = bd

    return {
        "success": True,
        "category": category,
        "itinerary": itinerary,
        "message": f"Switched to {alt.get('mode', alt.get('name', 'new option'))}. Budget recalculated.",
    }
