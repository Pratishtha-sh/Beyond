"""
general_planner.py — Beyond Project (Dataset-Powered General Itinerary Planner)
=================================================================================
Generates itineraries using pre-existing data from india_tourism_dataset.json
instead of live API calls (weather, Google Places). When a destination or state is found
in the dataset, the rich local data (attractions, activities, cuisine, culture,
budget, fun facts, hidden gems, etc.) is fed to the Groq LLM to produce an enriched
day-by-day itinerary with fun info and text.

Flow:
  1. Load destination_names.txt (with bracketed states) → index state-to-places mapping
  2. Load india_tourism_dataset.json → index by id / name / state
  3. find_destinations_for_query(user_input) → match state or specific place → list of dataset entries
  4. generate_general_itinerary(…) → extract rich context → Groq LLM → enriched itinerary JSON
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import concurrent.futures

import httpx
from dotenv import load_dotenv
from groq import Groq

# ── Env ──────────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

GROQ_API_KEY = os.getenv("Groq_api_key") or os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise EnvironmentError("Groq_api_key not found in .env file.")

groq_client = Groq(api_key=GROQ_API_KEY)
LLM_MODEL = "openai/gpt-oss-120b"

PEXELS_API_KEY = (
    os.getenv("pexels_api")
    or os.getenv("PEXELS_API_KEY")
    or os.getenv("PEXELS_API")
    or ""
)


def fetch_pexels_image(query: str, fallback_query: Optional[str] = None) -> Optional[str]:
    """
    Search Pexels API for a photo of the given place.
    Endpoint: https://api.pexels.com/v1/search?query={place}&per_page=1
    """
    if not PEXELS_API_KEY or not query:
        return None

    # Clean query (remove parentheticals, clean commas)
    clean_q = re.sub(r"\s*\(.*?\)", "", query)
    clean_q = clean_q.replace(",", " ").strip()
    clean_q = re.sub(r"\s+", " ", clean_q)

    headers = {"Authorization": PEXELS_API_KEY}

    def _query_api(term: str) -> Optional[str]:
        try:
            with httpx.Client(timeout=6.0) as client:
                resp = client.get(
                    f"https://api.pexels.com/v1/search?query={term}&per_page=1",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    photos = data.get("photos", [])
                    if photos and len(photos) > 0:
                        src = photos[0].get("src", {})
                        return src.get("medium") or src.get("landscape") or src.get("small")
        except Exception as exc:
            print(f"[PEXELS] Error querying '{term}': {exc}")
        return None

    # 1. Full clean query
    url = _query_api(clean_q)
    if url:
        return url

    # 2. Main place title (first 2-3 words)
    words = clean_q.split()
    if len(words) > 2:
        url = _query_api(" ".join(words[:2]))
        if url:
            return url

    # 3. Fallback query if provided
    if fallback_query and fallback_query.strip():
        fb_clean = fallback_query.replace(",", " ").strip()
        if fb_clean != clean_q:
            url = _query_api(fb_clean)
            if url:
                return url

    return None


def attach_activity_images(itinerary: dict, destination: str) -> dict:
    """Concurrently fetch and attach Pexels photo URLs to all activities in the itinerary."""
    if not isinstance(itinerary, dict) or "days" not in itinerary:
        return itinerary

    activities_to_fetch = []
    for day in itinerary.get("days", []):
        for slot in ("morning", "afternoon", "evening"):
            for act in day.get(slot, []):
                if isinstance(act, dict) and not act.get("image"):
                    activities_to_fetch.append(act)

    if not activities_to_fetch:
        return itinerary

    def _fetch_for_act(act: dict):
        place_str = act.get("place") or act.get("name") or ""
        img_url = fetch_pexels_image(place_str, fallback_query=f"{place_str} {destination}")
        if img_url:
            act["image"] = img_url

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_fetch_for_act, activities_to_fetch))

    return itinerary

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "Data"
DATASET_PATH = DATA_DIR / "india_tourism_dataset.json"
DESTINATION_NAMES_PATH = DATA_DIR / "destination_names.txt"

# ── Load dataset on module import ────────────────────────────────────────────
_dataset: list[dict] = []
_destination_names: list[str] = []
_state_to_dest_names: dict[str, list[str]] = {}
_dest_name_to_state: dict[str, str] = {}


def _normalize(name: str) -> str:
    """Lowercase, strip parenthetical qualifiers, collapse whitespace."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove parenthetical qualifiers e.g. "(Leh)", "(Kashi)", "(Rajasthan)"
    name = re.sub(r"\s*\(.*?\)", "", name)
    name = re.sub(r"[^a-z0-9\s\-]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def _load_data() -> None:
    """Load the tourism dataset and destination names list."""
    global _dataset, _destination_names, _state_to_dest_names, _dest_name_to_state

    # Load dataset
    if DATASET_PATH.exists():
        with DATASET_PATH.open("r", encoding="utf-8") as f:
            _dataset = json.load(f)
        print(f"[GENERAL PLANNER] Loaded {len(_dataset)} destinations from dataset.")
    else:
        print(f"[GENERAL PLANNER] WARNING: Dataset not found at {DATASET_PATH}")

    # Load destination names with bracket states
    if DESTINATION_NAMES_PATH.exists():
        with DESTINATION_NAMES_PATH.open("r", encoding="utf-8") as f:
            raw_lines = f.readlines()
        _destination_names = []
        _state_to_dest_names = {}
        _dest_name_to_state = {}

        for line in raw_lines:
            cleaned = re.sub(r"^\d+\.\s*", "", line.strip())
            if not cleaned:
                continue

            _destination_names.append(cleaned)

            state_match = re.search(r"\(([^()]+)\)$", cleaned)
            if state_match:
                state_name = state_match.group(1).strip()
                dest_base = cleaned[: state_match.start()].strip()
                norm_state = _normalize(state_name)

                _dest_name_to_state[_normalize(dest_base)] = state_name
                if norm_state not in _state_to_dest_names:
                    _state_to_dest_names[norm_state] = []
                _state_to_dest_names[norm_state].append(dest_base)

        print(
            f"[GENERAL PLANNER] Loaded {len(_destination_names)} destination lines "
            f"covering {len(_state_to_dest_names)} states from destination_names.txt."
        )
    else:
        print(f"[GENERAL PLANNER] WARNING: Destination names not found at {DESTINATION_NAMES_PATH}")


# Auto-load on import
_load_data()


# ─────────────────────────────────────────────────────────────────────────────
# LLM helpers
# ─────────────────────────────────────────────────────────────────────────────

def _llm(system: str, user: str, temperature: float = 0.3) -> str:
    response = groq_client.chat.completions.create(
        model=LLM_MODEL,
        temperature=temperature,
        max_tokens=4096,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def _extract_json(text: str) -> dict | list:
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    start_obj = text.find("{")
    start_arr = text.find("[")

    if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
        end_obj = text.rfind("}")
        if end_obj != -1:
            text = text[start_obj : end_obj + 1]
    elif start_arr != -1:
        end_arr = text.rfind("]")
        if end_arr != -1:
            text = text[start_arr : end_arr + 1]

    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass

    try:
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass

    try:
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        cleaned = re.sub(r"[\x00-\x1F\x7F]", " ", cleaned)
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Destination & State lookup
# ─────────────────────────────────────────────────────────────────────────────

def is_known_destination(name: str) -> bool:
    """Quick check if a destination or state is in the dataset or destination_names.txt."""
    return len(find_destinations_for_query(name)) > 0


def find_destinations_for_query(name: str) -> list[dict]:
    """
    Match user input against dataset entries.
    Supports state input (returns all destinations in that state) as well as specific place input.
    """
    if not _dataset or not name:
        return []

    query = _normalize(name)

    # 1. Check if query matches a State name
    state_matches: list[dict] = []
    for entry in _dataset:
        entry_state = _normalize(entry.get("state", ""))
        if entry_state and (query == entry_state or query in entry_state or entry_state in query):
            state_matches.append(entry)

    if state_matches:
        seen_ids = set()
        unique_matches = []
        for em in state_matches:
            if em.get("id") not in seen_ids:
                seen_ids.add(em.get("id"))
                unique_matches.append(em)
        return unique_matches

    # 2. Check exact / substring match on destination_name
    for entry in _dataset:
        entry_name = _normalize(entry.get("destination_name", ""))
        if entry_name == query:
            return [entry]

    for entry in _dataset:
        entry_name = _normalize(entry.get("destination_name", ""))
        if query in entry_name or entry_name in query:
            return [entry]

    # 3. Token overlap match
    query_tokens = set(query.split())
    best_match = None
    best_score = 0
    for entry in _dataset:
        entry_name = _normalize(entry.get("destination_name", ""))
        entry_tokens = set(entry_name.split())
        overlap = len(query_tokens & entry_tokens)
        if overlap > best_score:
            best_score = overlap
            best_match = entry

    if best_score >= 1 and best_match:
        return [best_match]

    return []


def find_destination(name: str) -> Optional[dict]:
    """Backward compatibility helper returning single dataset entry or None."""
    matches = find_destinations_for_query(name)
    return matches[0] if matches else None


def get_all_destination_names() -> list[str]:
    """Return all known destination names from destination_names.txt / dataset."""
    if _destination_names:
        return _destination_names
    return [entry.get("destination_name", "") for entry in _dataset if entry.get("destination_name")]


# ─────────────────────────────────────────────────────────────────────────────
# Dataset context extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_dataset_context(entries: list[dict]) -> str:
    """
    Extract and format rich fields from one or multiple dataset entries
    into a comprehensive context block for the LLM.
    """
    sections = []

    if len(entries) > 1:
        state_name = entries[0].get("state", "State")
        place_names = [e.get("destination_name", "Unknown") for e in entries]
        sections.append(f"REGION / STATE: {state_name}")
        sections.append(f"PLACES INCLUDED IN THIS STATE: {', '.join(place_names)}\n")

    for idx, entry in enumerate(entries, 1):
        dest_name = entry.get("destination_name", "Unknown")
        sections.append(f"--- PLACE {idx}: {dest_name} ---")
        sections.append(f"State: {entry.get('state', 'N/A')} | Region: {entry.get('region', 'N/A')} | District: {entry.get('district', 'N/A')}")

        attractions = entry.get("primary_attractions", [])
        if attractions:
            sections.append(f"PRIMARY ATTRACTIONS: {', '.join(attractions)}")

        activities = entry.get("activities_available", [])
        if activities:
            sections.append(f"ACTIVITIES AVAILABLE: {', '.join(activities)}")

        hidden = entry.get("hidden_gems", [])
        if hidden:
            sections.append(f"HIDDEN GEMS: {', '.join(hidden)}")

        unique = entry.get("unique_experiences", "")
        if unique:
            sections.append(f"UNIQUE EXPERIENCES: {unique}")

        best = entry.get("best_seasons", [])
        if best:
            sections.append(f"BEST SEASONS: {', '.join(best)}")

        temps = entry.get("average_temperature", {})
        if temps:
            temp_lines = [f"{s}: {t}" for s, t in temps.items()]
            sections.append(f"AVERAGE TEMPERATURES: {', '.join(temp_lines)}")

        food = entry.get("food_scene", "")
        if food:
            sections.append(f"FOOD SCENE: {food}")

        cuisine = entry.get("local_cuisine_must_try", [])
        if cuisine:
            sections.append(f"MUST-TRY CUISINE: {', '.join(cuisine)}")

        culture = entry.get("local_culture", "")
        if culture:
            sections.append(f"LOCAL CULTURE & CUSTOMS: {culture}")

        festivals = entry.get("festivals_events", "")
        if festivals:
            sections.append(f"FESTIVALS & EVENTS: {festivals}")

        shopping = entry.get("shopping_highlights", [])
        if shopping:
            sections.append(f"SHOPPING HIGHLIGHTS: {', '.join(shopping)}")

        safety = entry.get("safety_notes", "")
        if safety:
            sections.append(f"SAFETY & TIPS: {safety}")

        sections.append("")

    return "\n".join(sections)


# ─────────────────────────────────────────────────────────────────────────────
# Enriched Itinerary generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_general_itinerary(
    destination: str,
    days: int,
    travel_style: str,
    number_of_people: int,
    party_type: str,
    start_date: str,
) -> Optional[dict]:
    """
    Generate an enriched itinerary with fun info & text using dataset context + Groq LLM.
    Supports both state-level inputs (covering all places in state) and specific places.
    """
    print(f"[GENERAL PLANNER] Looking up '{destination}' in dataset / destination_names...")

    entries = find_destinations_for_query(destination)
    if not entries:
        print(f"[GENERAL PLANNER] '{destination}' not found in dataset. Returning None.")
        return None

    places_covered = [e.get("destination_name", destination) for e in entries]
    is_state_trip = len(entries) > 1 or any(
        _normalize(e.get("state", "")) == _normalize(destination) for e in entries
    )
    dest_display_name = entries[0].get("state") if is_state_trip else places_covered[0]

    print(
        f"[GENERAL PLANNER] Found {len(entries)} place(s) for '{dest_display_name}': "
        f"{', '.join(places_covered)}. Generating enriched itinerary..."
    )

    dataset_context = _extract_dataset_context(entries)

    # Build date list
    trip_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    date_list = [
        (trip_start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days)
    ]

    month = trip_start.month
    if month in (11, 12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5, 6):
        season = "summer"
    else:
        season = "monsoon"

    system_prompt = (
        "You are an expert travel storyteller and itinerary planner for the Beyond app.\n"
        "Generate a rich, vibrant, and fun day-by-day travel itinerary as valid JSON only — no extra text.\n\n"
        "CRITICAL TEXT RULE: No emojis or emoji-like symbols and em dashes are allowed anywhere in any generated text field\n\n"
        "IMPORTANT DATA RULE:\n"
        "You are given REAL CURATED DATA about the destination/state from the Indian Tourism Dataset.\n"
        "Make full use of all the rich information in the dataset (attractions, hidden gems, local foods, culture, "
        "travel hacks, fun facts) to craft an engaging, fun-to-read itinerary.\n"
        "Do NOT invent places that are not in the provided dataset.\n\n"
        "OUTPUT JSON SCHEMA:\n"
        "{\n"
        '  "destination": "<destination or state name>",\n'
        '  "places_covered": ["place 1", "place 2"],\n'
        '  "overview": "<2-3 sentence engaging storytelling summary of the vibe and magic of this trip>",\n'
        '  "fun_facts": ["Cool trivia 1", "Fun fact 2", "Did you know... 3"],\n'
        '  "must_try_food": ["Dishes & drinks with short appetizing descriptions"],\n'
        '  "hidden_gems": ["Offbeat secret spots & experiences to look out for"],\n'
        '  "local_culture": "<Short paragraph on local etiquette, traditions, art, or festivals>",\n'
        '  "travel_hacks": ["Insider tip 1", "Photo/timing hack 2"],\n'
        '  "budget_info": "<Daily budget advice and category recommendation>",\n'
        '  "days": [\n'
        "    {\n"
        '      "date": "YYYY-MM-DD",\n'
        '      "day": 1,\n'
        '      "theme": "<Theme of the day>",\n'
        '      "city": "<City or location>",\n'
        '      "weather_summary": "<Weather note>",\n'
        '      "morning": [\n'
        "        {\n"
        '          "place": "<Attraction Name>,<City>",\n'
        '          "duration": "2.5h",\n'
        '          "category": "<Category>",\n'
        '          "description": "<Vibrant description of what to experience>",\n'
        '          "tips": "<Useful insider tip>",\n'
        '          "fun_fact": "<Cool trivia about this specific place>" \n'
        "        }\n"
        "      ],\n"
        '      "afternoon": [...],\n'
        '      "evening": [...],\n'
        '      "daily_notes": "<Evening rest note or food recommendation>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Trip Style: {travel_style} | Party Type: {party_type} ({number_of_people} people) | Season: {season}\n"
        "Ensure all days maintain a realistic pacing (3-5 attractions max per day + lunch/rest breaks)."
    )

    user_prompt = (
        f"CURATED TOURISM DATASET CONTEXT:\n"
        f"{'='*60}\n"
        f"{dataset_context}\n"
        f"{'='*60}\n\n"
        f"TRIP PARAMETERS:\n"
        f"Destination / State requested: {dest_display_name}\n"
        f"Places in dataset: {', '.join(places_covered)}\n"
        f"Days: {days} | Dates: {', '.join(date_list)}\n"
        f"Travel Style: {travel_style} | Party: {party_type} ({number_of_people} people)\n"
        f"Season: {season}\n\n"
        f"Generate the full enriched {days}-day itinerary JSON with fun facts and text now."
    )

    print(f"[GENERAL PLANNER] Calling LLM for {days}-day {travel_style} itinerary...")
    raw = _llm(system_prompt, user_prompt, temperature=0.5)

    try:
        itinerary = _extract_json(raw)
        if isinstance(itinerary, list):
            itinerary = {"days": itinerary}
        
        # Attach real place photos from Pexels
        itinerary = attach_activity_images(itinerary, dest_display_name)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[GENERAL PLANNER] JSON parse error ({e}). Storing raw response.")
        itinerary = {"raw": raw}

    print(f"[GENERAL PLANNER] [OK] Enriched itinerary generated for '{dest_display_name}'.")
    return itinerary


# ─────────────────────────────────────────────────────────────────────────────
# Swap alternatives — query generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_swap_query(
    place: str,
    category: str,
    city: str,
    destination: str,
    travel_style: str,
) -> str:
    """
    Ask the LLM to produce one optimised Google Places Text Search query
    for finding alternatives to a given activity.

    Returns a plain string query (e.g. "historical temples near Jaipur Rajasthan").
    Falls back to a simple heuristic string if the LLM call fails.
    """
    system_prompt = (
        "You are a travel search expert. "
        "Given an activity/place that a traveller wants to swap, generate ONE concise Google Places Text Search query "
        "that will surface 3-4 similar alternatives in the same city. "
        "Rules:\n"
        "- Return ONLY the raw search query string. No JSON, no explanation, no quotes.\n"
        "- Keep it under 12 words.\n"
        "- Include the city name and category context.\n"
        "- Do NOT include the original place name.\n"
        "- Aim for results that match the travel style."
    )
    user_prompt = (
        f"Original place: {place}\n"
        f"Category: {category}\n"
        f"City: {city}\n"
        f"Destination/Region: {destination}\n"
        f"Travel style: {travel_style}\n\n"
        "Generate the Google Places search query:"
    )

    try:
        response = groq_client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.2,
            max_tokens=64,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        # Strip any accidental quotes
        raw = raw.strip('"\'')
        if raw:
            return raw
    except Exception as exc:
        print(f"[GENERAL PLANNER] generate_swap_query LLM error: {exc}")

    # Heuristic fallback
    return f"{category} attractions near {city} India"


def enrich_swap_alternatives(
    places: list[dict],
    category: str,
    city: str,
    destination: str,
    travel_style: str = "calm",
) -> list[dict]:
    """
    Given a list of candidate Google Places alternative dicts, use Groq LLM
    to generate engaging 1-2 sentence descriptions and tips for each place.
    """
    if not places:
        return []

    system_prompt = (
        "You are an expert travel storyteller for the Beyond app.\n"
        "Given a list of place names in a city/destination, generate a short, engaging description (1-2 sentences) "
        "and a practical insider tip for each place.\n"
        "CRITICAL: No emojis, no em-dashes. Return valid JSON only.\n\n"
        "Output Schema:\n"
        "{\n"
        '  "places": [\n'
        "    {\n"
        '      "name": "<Place Name>",\n'
        '      "description": "<1-2 sentence vivid description of the vibe and highlights of this place>",\n'
        '      "tips": "<Useful insider tip, e.g. best time, photography, what to order/see>",\n'
        '      "fun_fact": "<Interesting short trivia or null>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
    names_str = "\n".join(f"- {p.get('name')} (Address: {p.get('address', '')})" for p in places)
    user_prompt = (
        f"City: {city} | Region: {destination} | Category: {category} | Travel style: {travel_style}\n\n"
        f"Places to describe:\n{names_str}\n\n"
        "Generate JSON with vivid descriptions and tips for all places."
    )

    try:
        response = groq_client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.3,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        data = _extract_json(raw)
        described_list = data.get("places", []) if isinstance(data, dict) else []
        desc_map = {
            item.get("name", "").lower().strip(): item
            for item in described_list
            if isinstance(item, dict) and item.get("name")
        }

        for p in places:
            p_name = p.get("name", "").lower().strip()
            matched = desc_map.get(p_name)
            if not matched:
                for k, v in desc_map.items():
                    if k in p_name or p_name in k:
                        matched = v
                        break
            if matched:
                p["description"] = matched.get("description")
                p["tips"] = matched.get("tips")
                p["fun_fact"] = matched.get("fun_fact")
            else:
                p["description"] = f"A popular {category.lower()} highlight in {city} offering authentic local experiences."
                p["tips"] = "Check current opening hours and plan your visit ahead."
    except Exception as exc:
        print(f"[GENERAL PLANNER] enrich_swap_alternatives LLM error: {exc}")
        for p in places:
            p.setdefault("description", f"A wonderful {category.lower()} stop in {city} with vibrant local charm.")
            p.setdefault("tips", "Check current opening hours before visiting.")

    # Attach Pexels image for each alternative
    for p in places:
        p_name = p.get("name", "")
        p_img = fetch_pexels_image(p_name, fallback_query=f"{p_name} {city}")
        if p_img:
            p["image"] = p_img

    return places
