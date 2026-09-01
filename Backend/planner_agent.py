"""
planner_agent.py — Beyond Project  (v4 — Deterministic LangGraph)
======================================================================
Removed the LLM master-coordinator agent. The pipeline is fully deterministic:

  START
    │
    ▼
  resolve_cities          (LLM: region → list of cities)
    │
    ▼
  fetch_weather_loop ──── conditional: any city missing weather?
    │   ▲                   YES → fetch_weather → back here
    │   └─────────────────── NO  → proceed
    ▼
  build_places_query      (LLM: craft one Places query per city)
    │
    ▼
  search_places_loop ──── conditional: any city not yet searched?
    │   ▲                   YES → search_places → back here
    │   └─────────────────── NO  → proceed
    ▼
  generate_itinerary      (LLM: final day-by-day plan)
    │
    ▼
   END

Weather skip rule: if trip start date is > 16 days from today,
skip the weather fetch entirely (Open-Meteo only has 16-day forecasts).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, TypedDict

from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import END, START, StateGraph

# ── Local tool imports ───────────────────────────────────────────────────────
sys.path.append(os.path.dirname(__file__))
from Tools.get_weather import get_weather
from Tools.google_places import search_google_places

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

WEATHER_FORECAST_HORIZON_DAYS = 16  # Open-Meteo free tier limit


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class PlannerState(TypedDict):
    # ── User inputs ──────────────────────────────────────────────────────────
    destination: str            # raw user input e.g. "Rajasthan"
    days: int
    travel_style: str           # e.g. "calm", "adventure", "historical-cultural", "spiritual"
    number_of_people: int
    party_type: str             # e.g. "couple", "friends", "family", "solo"
    start_date: str             # ISO date string "YYYY-MM-DD" (first day of trip)

    # ── Pipeline data ────────────────────────────────────────────────────────
    cities: list[str]           # Resolved city list e.g. ["Jaipur", "Udaipur"]
    weather_skip: bool          # True when start_date is > 16 days away
    weather: dict               # city → weather dict
    places_queries: dict        # city → LLM-crafted Places query string
    places: list                # consolidated list of place dicts (with "city" key)
    searched_cities: list[str]  # cities already queried against Places API
    itinerary: dict             # final output


# ─────────────────────────────────────────────────────────────────────────────
# LLM helpers
# ─────────────────────────────────────────────────────────────────────────────

def _llm(system: str, user: str, temperature: float = 0.3) -> str:
    response = groq_client.chat.completions.create(
        model=LLM_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def _extract_json(text: str) -> dict | list:
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    start = min(
        (text.find("{") if "{" in text else len(text)),
        (text.find("[") if "[" in text else len(text)),
    )
    return json.loads(text[start:])


# ─────────────────────────────────────────────────────────────────────────────
# Input collection
# ─────────────────────────────────────────────────────────────────────────────

def create_initial_state(
    destination: str,
    days: int,
    travel_style: str,
    number_of_people: int,
    party_type: str,
    start_date: str,
) -> PlannerState:
    """Build planner state from structured inputs (API or tests)."""
    return PlannerState(
        destination=destination,
        days=days,
        travel_style=travel_style,
        number_of_people=number_of_people,
        party_type=party_type,
        start_date=start_date,
        cities=[],
        weather_skip=False,
        weather={},
        places_queries={},
        places=[],
        searched_cities=[],
        itinerary={},
    )


def collect_inputs() -> PlannerState:
    print("\n✈️  Welcome to Beyond — Your AI Travel Planner\n")
    print("=" * 50)

    destination = input("📍 Destination (e.g. 'New Delhi', 'Himachal Pradesh'): ").strip()
    while not destination:
        destination = input("   Please enter a destination: ").strip()

    # Start date
    while True:
        raw_date = input("📅 Trip start date (YYYY-MM-DD, or press Enter for today): ").strip()
        if not raw_date:
            start_date = date.today().strftime("%Y-%m-%d")
            break
        try:
            datetime.strptime(raw_date, "%Y-%m-%d")
            start_date = raw_date
            break
        except ValueError:
            print("   Please enter a valid date in YYYY-MM-DD format.")

    days_raw = input("📅 Number of days: ").strip()
    while not days_raw.isdigit() or int(days_raw) < 1:
        days_raw = input("   Please enter a valid number of days (e.g. 3): ").strip()
    days = int(days_raw)

    print("\n   Travel styles: calm | adventure | historical-cultural | spiritual")
    travel_style = input("🎒 Travel style: ").strip().lower() or "standard"

    people_raw = input("👥 Number of people: ").strip()
    while not people_raw.isdigit() or int(people_raw) < 1:
        people_raw = input("   Please enter a valid number (e.g. 2): ").strip()
    number_of_people = int(people_raw)

    print("\n   Party types: solo | couple | friends | family | adventure group")
    party_type = input("🎉 Party type: ").strip().lower() or "solo"

    print("\n" + "=" * 50)
    print("🔍 Activating Planner — building your itinerary...\n")

    return create_initial_state(
        destination=destination,
        days=days,
        travel_style=travel_style,
        number_of_people=number_of_people,
        party_type=party_type,
        start_date=start_date,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Node 1 — Resolve Cities
# ─────────────────────────────────────────────────────────────────────────────

def node_resolve_cities(state: PlannerState) -> PlannerState:
    """LLM maps destination → list of specific cities to visit."""
    print(f"🏙️  Resolving '{state['destination']}' to tourist cities...")

    system = (
        "You are a geography and travel expert. Given a destination name, determine whether it "
        "refers to a state/province/region or a specific city.\n"
        "Respond in JSON with two keys:\n"
        "  'is_state': boolean\n"
        "  'cities': list of strings — if is_state is true, the 3-4 most famous tourist cities "
        "in that state; if false, a list containing only the destination itself.\n\n"
        "Examples:\n"
        "  Input: 'Rajasthan'  → {\"is_state\": true,  \"cities\": [\"Jaipur\", \"Udaipur\", \"Jodhpur\", \"Jaisalmer\"]}\n"
        "  Input: 'New Delhi'  → {\"is_state\": false, \"cities\": [\"New Delhi\"]}\n"
        "Respond with JSON only, no other text."
    )

    try:
        raw = _llm(system, f"Input: '{state['destination']}'", temperature=0.0)
        res = _extract_json(raw)
        cities = res.get("cities") or [state["destination"]]
        is_state = res.get("is_state", False)
    except Exception as e:
        print(f"   ⚠️  City resolution failed ({e}), using destination as-is.")
        cities = [state["destination"]]
        is_state = False

    print(f"   ✅ Cities: {cities}  (is_state={is_state})")

    # Determine weather skip here — before we enter the weather loop
    trip_start = datetime.strptime(state["start_date"], "%Y-%m-%d").date()
    days_until_trip = (trip_start - date.today()).days
    weather_skip = days_until_trip > WEATHER_FORECAST_HORIZON_DAYS

    if weather_skip:
        print(
            f"   ⏭️  Weather skipped — trip starts in {days_until_trip} days "
            f"(forecast only covers {WEATHER_FORECAST_HORIZON_DAYS} days)."
        )

    state["cities"] = cities
    state["weather_skip"] = weather_skip
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 — Weather loop dispatcher (conditional routing only, no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def node_fetch_weather(state: PlannerState) -> PlannerState:
    """Fetch weather for the next city that hasn't been fetched yet."""
    unfetched = [c for c in state["cities"] if c not in state["weather"]]
    city = unfetched[0]  # router guarantees at least one exists

    print(f"🌤️  Fetching weather for '{city}'...")
    trip_start = datetime.strptime(state["start_date"], "%Y-%m-%d").date()
    trip_dates = [
        (trip_start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(state["days"])
    ]

    result = get_weather(location=city, dates=trip_dates)

    if result.get("status") == "geocode_failed":
        print(f"   ⚠️  Weather geocode failed for '{city}'.")
    else:
        print(f"   ✅ Weather data received for '{city}'.")

    state["weather"][city] = result
    return state


def route_weather(state: PlannerState) -> str:
    """
    Deterministic router — no LLM involved.
    Skip entirely if weather_skip is set.
    Loop back until every city has weather data.
    """
    if state["weather_skip"]:
        return "build_places_queries"
    unfetched = [c for c in state["cities"] if c not in state["weather"]]
    return "fetch_weather" if unfetched else "build_places_queries"


# ─────────────────────────────────────────────────────────────────────────────
# Node 3 — Build Places Queries (one LLM call, all cities at once)
# ─────────────────────────────────────────────────────────────────────────────

def node_build_places_queries(state: PlannerState) -> PlannerState:
    """
    Single LLM call that produces a tailored Google Places text query
    for every city, informed by all trip parameters and weather context.
    """
    print("🔎  Building Places search queries for all cities...")

    weather_context = ""
    style_query_intent = _style_intent(state["travel_style"])
    if state["weather"]:
        lines = []
        for city, city_w in state["weather"].items():
            if not isinstance(city_w, dict) or "status" in city_w:
                continue
            sample = next(iter(city_w.values()), {})
            if isinstance(sample, dict) and "weather" in sample:
                lines.append(
                    f"  {city}: {sample['weather']}, "
                    f"{sample.get('temp_min_c','?')}-{sample.get('temp_max_c','?')}°C, "
                    f"rain {sample.get('rain_mm','?')}mm"
                )
        weather_context = "\nWeather snapshot:\n" + "\n".join(lines) if lines else ""

    system = (
        "You are a travel search specialist. Given trip parameters and a list of cities, "
        "produce one descriptive Google Places text-search query per city.\n"
        "Each query must target real visitor attractions only: forts, palaces, tombs, temples, churches, mosques, museums, parks, beaches, viewpoints, wildlife, heritage sites, and cultural landmarks.\n"
        "Never search for tour agencies, travel companies, packages, hotels, taxis, guides, operators, travel agents, private tours, or booking services.\n"
        "Respond with JSON only — an object where keys are city names and values are query strings.\n"
        "Example: {\"Jaipur\": \"Jaipur famous forts palaces museums heritage monuments\", \"Puri\": \"Puri famous temples beaches pilgrimage places\"}"
    )

    user = (
        f"Destination: {state['destination']}\n"
        f"Cities: {state['cities']}\n"
        f"Travel style: {state['travel_style']} ({style_query_intent})\n"
        f"Party type: {state['party_type']}\n"
        f"Number of people: {state['number_of_people']}\n"
        f"Number of days: {state['days']}\n"
        f"Start date: {state['start_date']}"
        f"{weather_context}\n\n"
        "Generate one attraction-only search query per city. Avoid the words agency, package, operator, taxi, hotel, and private tour."
    )

    try:
        raw = _llm(system, user, temperature=0.2)
        queries: dict = _extract_json(raw)
        # Ensure every city has a query (fallback if LLM missed one)
        for city in state["cities"]:
            if city not in queries:
                queries[city] = (
                    f"{city} {_style_intent(state['travel_style'])} tourist attractions"
                )
            else:
                queries[city] = (
                    str(queries[city])
                    .replace("travel agency", "tourist attractions")
                    .replace("travel", "tourist")
                    .replace("tour packages", "landmarks")
                    .replace("private tours", "attractions")
                )
        print(f"   ✅ Queries built for: {list(queries.keys())}")
    except Exception as e:
        print(f"   ⚠️  Query building failed ({e}), using fallback queries.")
        queries = {
            city: (
                f"{city} {_style_intent(state['travel_style'])} tourist attractions"
            )
            for city in state["cities"]
        }

    state["places_queries"] = queries
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Node 4 — Places search loop (no LLM, query already prepared)
# ─────────────────────────────────────────────────────────────────────────────

def node_search_places(state: PlannerState) -> PlannerState:
    """Search Google Places for the next unsearched city using its pre-built query."""
    unsearched = [c for c in state["cities"] if c not in state["searched_cities"]]
    city = unsearched[0]
    query = state["places_queries"].get(
        city,
        f"{city} top tourist attractions landmarks"
    )

    print(f"🔍  Searching Places for '{city}' → query: \"{query}\"")
    results = search_google_places(query=query, max_results=25)

    if results:
        print(f"   ✅ Found {len(results)} places for '{city}'.")
        for p in results:
            p["city"] = city
        state["places"].extend(results)
    else:
        print(f"     No places found for '{city}'.")

    state["searched_cities"] = state["searched_cities"] + [city]
    return state


def route_places(state: PlannerState) -> str:
    """Loop back until every city has been searched, then generate itinerary."""
    unsearched = [c for c in state["cities"] if c not in state["searched_cities"]]
    return "search_places" if unsearched else "generate_itinerary"


# ─────────────────────────────────────────────────────────────────────────────
# Node 5 — Generate Itinerary  (unchanged logic, same LLM call as before)
# ─────────────────────────────────────────────────────────────────────────────

def _summarize_weather(weather: dict, days: int) -> str:
    lines: list[str] = []
    for city, city_weather in weather.items():
        if not isinstance(city_weather, dict):
            continue
        date_lines: list[str] = []
        for date_str, entry in list(city_weather.items())[:days]:
            if isinstance(entry, dict) and entry.get("status"):
                date_lines.append(f"{date_str}: {entry['status']}")
            elif isinstance(entry, dict):
                date_lines.append(
                    f"{date_str}: {entry.get('weather', 'unknown')} | "
                    f"{entry.get('temp_min_c', '?')}-{entry.get('temp_max_c', '?')}°C | "
                    f"rain {entry.get('rain_mm', '?')}mm"
                )
        if date_lines:
            lines.append(f"{city}: " + "; ".join(date_lines))
    return "\n".join(lines) if lines else "No weather data available."


STYLE_QUERY_INTENT = {
    "calm": "peaceful tourist attractions gardens lakes museums scenic places",
    "adventure": "adventure outdoor tourist attractions nature trails viewpoints wildlife",
    "adventure-nature": "adventure outdoor tourist attractions nature trails waterfalls viewpoints wildlife national parks",
    "historical-cultural": "famous forts palaces tombs museums heritage monuments cultural sites",
    "spiritual": "famous temples churches mosques gurudwaras pilgrimage sacred places",
    "party": "vibrant beach shacks clubs nightlife promenades markets music venues sunset spots",
    "party-nightlife": "vibrant beach shacks clubs nightlife promenades markets music venues sunset spots",
    "culinary-foodie": "famous food streets night markets authentic local cuisine traditional cafes culinary landmarks",
    "foodie": "famous food streets night markets authentic local cuisine traditional cafes culinary landmarks",
}

STYLE_PLACE_KEYWORDS = {
    "calm": {
        "garden", "park", "lake", "museum", "beach", "viewpoint", "promenade",
        "sanctuary", "zoo", "waterfall", "botanical", "palace",
    },
    "adventure": {
        "trek", "trail", "fort", "hill", "peak", "wildlife", "sanctuary",
        "reserve", "waterfall", "beach", "cave", "viewpoint", "rafting",
        "paragliding", "zipline", "camp",
    },
    "adventure-nature": {
        "trek", "trail", "fort", "hill", "peak", "wildlife", "sanctuary",
        "reserve", "waterfall", "beach", "cave", "viewpoint", "rafting",
        "paragliding", "zipline", "camp", "forest", "safari", "valley",
    },
    "historical-cultural": {
        "fort", "palace", "tomb", "mahal", "museum", "heritage", "monument",
        "temple", "stupa", "cave", "archaeological", "old", "chowk",
        "market", "haveli", "mosque", "church",
    },
    "spiritual": {
        "temple", "mandir", "dham", "math", "ashram", "mosque", "masjid",
        "dargah", "church", "cathedral", "gurudwara", "monastery", "stupa",
        "shrine", "ghat", "pilgrimage",
    },
    "party": {
        "club", "bar", "pub", "beach", "shack", "cafe", "lounge", "bistro",
        "promenade", "market", "night", "live", "sunset", "dj",
    },
    "party-nightlife": {
        "club", "bar", "pub", "beach", "shack", "cafe", "lounge", "bistro",
        "promenade", "market", "night", "live", "sunset", "dj",
    },
    "culinary-foodie": {
        "food", "restaurant", "cafe", "dhaba", "bazaar", "market", "chowk",
        "cuisine", "bakery", "sweet", "chaat", "rooftop", "street",
    },
    "foodie": {
        "food", "restaurant", "cafe", "dhaba", "bazaar", "market", "chowk",
        "cuisine", "bakery", "sweet", "chaat", "rooftop", "street",
    },
}

GENERAL_ATTRACTION_KEYWORDS = {
    "fort", "palace", "tomb", "temple", "mandir", "mosque", "masjid", "church",
    "cathedral", "gurudwara", "monastery", "museum", "park", "garden", "lake",
    "beach", "viewpoint", "point", "waterfall", "cave", "sanctuary", "reserve",
    "zoo", "heritage", "monument", "stupa", "market", "ghat", "dham",
}

NON_ATTRACTION_KEYWORDS = {
    "tour", "tours", "travels", "travel", "holidays", "holiday", "package",
    "packages", "agency", "operator", "pvt", "ltd", "private", "taxi", "cab",
    "rental", "booking", "hotel", "resort", "homestay", "guest house", "visa",
    "consultant", "flight", "ticket", "transport", "car hire",
}


def _style_intent(style: str) -> str:
    return STYLE_QUERY_INTENT.get(style, "top tourist attractions landmarks heritage places")


def _place_text(place: dict) -> str:
    return " ".join(
        str(place.get(field, ""))
        for field in ("name", "address", "types", "category", "description")
    ).lower()


def _is_non_attraction(place: dict) -> bool:
    text = _place_text(place)
    name = str(place.get("name", "")).lower()
    if any(keyword in name for keyword in NON_ATTRACTION_KEYWORDS):
        return True
    return not any(keyword in text for keyword in GENERAL_ATTRACTION_KEYWORDS)


def _place_score(place: dict, style: str, index: int) -> int:
    text = _place_text(place)
    score = max(0, 20 - index)
    if any(keyword in text for keyword in GENERAL_ATTRACTION_KEYWORDS):
        score += 10
    for keyword in STYLE_PLACE_KEYWORDS.get(style, set()):
        if keyword in text:
            score += 6
    if _is_non_attraction(place):
        score -= 100
    return score


def _select_summary_places(
    places: list[dict],
    travel_style: str,
    max_total: int = 15,
    max_per_city: int = 7,
) -> list[dict]:
    selected: list[dict] = []
    seen: set = set()
    city_groups: dict[str, list[dict]] = {}
    for index, place in enumerate(places):
        city = place.get("city", "Unknown")
        place["_source_index"] = index
        city_groups.setdefault(city, []).append(place)

    for city, city_places in city_groups.items():
        sorted_places = sorted(
            city_places,
            key=lambda p: _place_score(p, travel_style, p.get("_source_index", 999)),
            reverse=True,
        )
        city_selected = 0
        for place in sorted_places:
            if _is_non_attraction(place):
                continue
            key = (place.get("name"), place.get("address"), city)
            if key in seen:
                continue
            seen.add(key)
            selected.append({
                "name": place.get("name", "Unknown place"),
                "address": place.get("address", "Address not available"),
                "timings": place.get("timings", "Timings not available"),
                "city": city,
                "why_selected": (
                    f"Matches the {travel_style.replace('-', ' ')} style and looks like a real visitor attraction."
                ),
            })
            city_selected += 1
            if len(selected) >= max_total:
                return selected
            if city_selected >= max_per_city:
                break
    return selected


def node_generate_itinerary(state: PlannerState) -> PlannerState:
    print("📝  Synthesizing final day-by-day itinerary...")

    places_list = _select_summary_places(state["places"], state["travel_style"])
    places_available = len(places_list) > 0
    weather_summary = _summarize_weather(state["weather"], state["days"])

    if places_available:
        place_block = (
            "VERIFIED PLACES (from Google Places — use ONLY these, never invent others):\n"
            + json.dumps(places_list, indent=2)
            + "\n\nCRITICAL: If you run out of verified places for a time slot, leave that slot as []."
            + " Do NOT add any named attraction not in this list. Generic lunch, snack, and rest breaks are allowed."
        )
        data_warning_instruction = 'Set "data_warning": "" (empty string).'
    else:
        place_block = (
            "NO VERIFIED PLACE DATA AVAILABLE — Google Places returned no results.\n\n"
            "Rules:\n"
            "1. Use your general knowledge of the destination.\n"
            "2. Append ' [UNVERIFIED]' to every place name.\n"
            "3. Set timings to 'Verify before visiting'.\n"
            "4. Set tip to 'Please confirm this place exists and check current timings.'\n"
        )
        data_warning_instruction = (
            'Set "data_warning": "Place data could not be verified via Google Places. '
            'All suggestions are based on general knowledge — please verify before visiting."'
        )

    trip_start = datetime.strptime(state["start_date"], "%Y-%m-%d").date()
    date_list = [
        (trip_start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(state["days"])
    ]

    system_prompt = (
        "You are an expert travel planner for the Beyond app.\n"
        "Create a day-by-day itinerary as valid JSON only - no extra text.\n\n"
        "PLANNING RULES:Do not add any emoji or Em dash in the generated text anywhere\n\n"
        f"Party type ({state['party_type']}):\n"
        "- couple: romantic, private - viewpoints at dusk, quiet gardens, intimate cafes.\n"
        "- friends: group fun - adventure parks, street food, nightlife etc.\n"
        "- family: educational + fun, kid-friendly pacing, no late nights.\n"
        "- solo: flexible — museums, walking tours, monuments.\n"
        "- adventure group: outdoor/active first — trekking, nature reserves, sports.\n\n"
        f"Travel style ({state['travel_style']}):\n"
        "- historical-cultural: forts, tombs, palaces, monuments, museums, old markets, heritage walks, and culturally significant places.\n"
        "- spiritual: famous temples, dhams, churches, mosques, gurudwaras, monasteries, shrines, ghats, and places known for local lore.\n"
        "- calm: relaxed pace with 2-3 main attractions per day, gardens, lakes, museums, scenic places, and enough rest.\n"
        "- adventure: outdoor/active places first - trails, viewpoints, waterfalls, wildlife, caves, water activities, and nature reserves.\n\n"
        f"Group size ({state['number_of_people']} people):\n"
        "- 1: solo-friendly.  2–4: couples/small group.  5+: group discounts, large venues.\n\n"
        "Weather Rules:\n"
        "- If a city's weather has rain_mm > 5, schedule indoor venues for that day.\n"
        "- If a city's weather has temp_max_c > 38, schedule outdoor only before 11 AM and after 5 PM.\n\n"
        "- If forecast data is unavailable, infer from the month and destination climate. In summer or hot months, keep outdoor places early morning or evening and put museums/indoor heritage stops after lunch.\n"
        "- Add weather-aware tips in daily notes or general tips, such as rain gear, hydration, sun protection, breathable clothing, or safer indoor alternates.\n\n"
        "Timing and pacing:\n"
        "- Every activity must include a realistic estimated duration like '1.5h' or '2h'. Do NOT include start/end time ranges or timestamps.\n"
        "- Do not pack too many stops. Most days should have 3-5 attractions maximum, plus lunch/snack/rest breaks.\n"
        "- Include a lunch break around midday and an optional snack/tea/rest break in the afternoon when the day has enough activities.\n"
        "- Each attraction must include a short description telling the traveller what to expect.\n"
        "- Do not include address or rating fields in activities.\n\n"
        "Places mapping:\n"
        "- Group places in the same city together across consecutive days.\n"
        "- eg we DO NOT want a whole day dedicates to 1 kind of activity for eg nature day where all wildlife sanctures of that day are planned."
        "- Ensure routing between places in a day makes geographic sense.\n\n"
        + place_block
        + "\n\n"
        + data_warning_instruction
        + "\n\n"
        "OUTPUT — ONLY this JSON, no other text.\n"
        "Return a JSON object with keys: destination, cities_visited, total_days, party_type, travel_style, number_of_people, data_warning, days, general_tips. Each day must have date, theme, city, weather_summary, morning, afternoon, evening, daily_notes. Each activity must have place, duration, category, description, tip."
    )

    user_prompt = (
        f"Destination: {state['destination']} (cities: {state['cities']})\n"
        f"Days: {state['days']} | Dates: {', '.join(date_list)}\n"
        f"Style: {state['travel_style']} | People: {state['number_of_people']} | Party: {state['party_type']}\n\n"
        f"Weather summary:\n{weather_summary}\n\n"
        f"Verified places (top {len(places_list)}):\n{json.dumps(places_list, indent=2)}\n\n"
        f"Generate the full {state['days']}-day itinerary JSON now."
    )

    raw = _llm(system_prompt, user_prompt, temperature=0.3)

    try:
        itinerary = _extract_json(raw)
        if isinstance(itinerary, list):
            itinerary = {"days": itinerary}
    except (json.JSONDecodeError, ValueError) as e:
        print(f"   ⚠️  JSON parse error ({e}). Storing raw response.")
        itinerary = {"raw": raw}

    state["itinerary"] = itinerary
    if itinerary.get("data_warning"):
        print(f"   ⚠️  {itinerary['data_warning']}")
    print("   ✅ Itinerary generated.")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Build Graph
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(PlannerState)

    # Register nodes
    graph.add_node("resolve_cities",      node_resolve_cities)
    graph.add_node("fetch_weather",       node_fetch_weather)
    graph.add_node("build_places_queries", node_build_places_queries)
    graph.add_node("search_places",       node_search_places)
    graph.add_node("generate_itinerary",  node_generate_itinerary)

    # Linear start
    graph.add_edge(START, "resolve_cities")

    # After resolve_cities: deterministic weather-loop gate
    graph.add_conditional_edges(
        "resolve_cities",
        route_weather,
        {
            "fetch_weather":       "fetch_weather",
            "build_places_queries": "build_places_queries",   # skipped when weather_skip=True
        }
    )

    # Weather loop: keep fetching until all cities done, then move on
    graph.add_conditional_edges(
        "fetch_weather",
        route_weather,
        {
            "fetch_weather":       "fetch_weather",
            "build_places_queries": "build_places_queries",
        }
    )

    # After queries are built, enter the places search loop
    graph.add_edge("build_places_queries", "search_places")

    # Places loop: keep searching until all cities done
    graph.add_conditional_edges(
        "search_places",
        route_places,
        {
            "search_places":      "search_places",
            "generate_itinerary": "generate_itinerary",
        }
    )

    graph.add_edge("generate_itinerary", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Pretty-print itinerary
# ─────────────────────────────────────────────────────────────────────────────

def print_itinerary(itinerary: dict) -> None:
    if "raw" in itinerary:
        print("\n📋 Itinerary (raw):\n")
        print(itinerary["raw"])
        return

    warning = itinerary.get("data_warning", "")
    if warning:
        print(f"\n⚠️  DATA WARNING: {warning}\n")

    print(f"\n{'='*60}")
    print(f"  🗺️  {itinerary.get('destination', 'Your Trip')} Itinerary")
    cities = itinerary.get("cities_visited", [])
    if cities:
        print(f"       Cities: {', '.join(cities)}")
    print(
        f"  👥 {itinerary.get('number_of_people', '?')} people · "
        f"{itinerary.get('party_type', '')} · "
        f"{itinerary.get('travel_style', '')} style"
    )
    print(f"{'='*60}\n")

    for day_num, day in enumerate(itinerary.get("days", []), start=1):
        print(f"📅 Day {day.get('day', day_num)} — {day.get('date', '')}  |  {day.get('theme', '')}")
        print(f"   🏙  City: {day.get('city', 'N/A')}  |  🌤  Weather: {day.get('weather_summary', 'N/A')}")
        for slot in ["morning", "afternoon", "evening", "night"]:
            acts = day.get(slot, [])
            if not acts:
                continue
            print(f"\n   {slot.upper()}")
            for act in acts:
                print(f"     🕐 {act.get('time', '')}  {act.get('place', '')}  ({act.get('duration', '')})")
                print(f"        📍 {act.get('address', 'N/A')}  |  ⭐ {act.get('rating', 'N/A')}")
                print(f"        ⏰ {act.get('timings', 'N/A')}")
                if act.get("tip"):
                    print(f"        💡 {act['tip']}")
                if act.get("activities"):
                    print(f"        🎯 {', '.join(act['activities'][:3])}")
        if day.get("daily_notes"):
            print(f"\n   📌 {day['daily_notes']}")
        print()

    for tip in itinerary.get("general_tips", []):
        print(f"   • {tip}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    initial_state = collect_inputs()
    planner = build_graph()
    final_state = planner.invoke(initial_state)
    print_itinerary(final_state["itinerary"])

    output_path = os.path.join(os.path.dirname(__file__), "itinerary_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "destination":   final_state["destination"],
                "start_date":    final_state["start_date"],
                "cities":        final_state["cities"],
                "days":          final_state["days"],
                "travel_style":  final_state["travel_style"],
                "number_of_people": final_state["number_of_people"],
                "party_type":    final_state["party_type"],
                "weather_skip":  final_state["weather_skip"],
                "weather":       final_state["weather"],
                "places_count":  len(final_state["places"]),
                "places":        final_state["places"],
                "itinerary":     final_state["itinerary"],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"✅ Saved to: {output_path}\n")


if __name__ == "__main__":
    main()
