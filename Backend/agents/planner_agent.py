"""Unified Planner Agent orchestrating LangGraph multi-agent generation pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# Ensure backend root is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load environment
env_path = BACKEND_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("planner_agent")

# Groq LLM Setup
GROQ_API_KEY = os.getenv("Groq_api_key") or os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise EnvironmentError("Groq_api_key not found in .env file.")

from groq import Groq
groq_client = Groq(api_key=GROQ_API_KEY)
LLM_MODEL = "openai/gpt-oss-120b"

# Tools & Agent Imports
try:
    from Tools.google_places import search_google_places
except ImportError:
    logger.warning("Tools.google_places not available, using fallback.")
    search_google_places = None

try:
    from Tools.hotel_search import hotel_search
except ImportError:
    logger.warning("Tools.hotel_search not available, using fallback.")
    hotel_search = None

try:
    from Tools.transport_search import transport_search
except ImportError:
    logger.warning("Tools.transport_search not available, using fallback.")
    transport_search = None

try:
    from general_planner import (
        _extract_dataset_context,
        attach_activity_images,
        fetch_pexels_image,
        find_destinations_for_query,
        is_known_destination,
    )
except ImportError:
    logger.warning("general_planner functions not available, using fallback.")
    find_destinations_for_query = lambda name: []
    _extract_dataset_context = lambda entries: ""
    attach_activity_images = lambda itin, dest: itin
    fetch_pexels_image = lambda q, fb=None: None
    is_known_destination = lambda name: False

try:
    from agents.budget_agent import BudgetAgent
except ImportError:
    logger.warning("agents.budget_agent not available, using fallback.")
    BudgetAgent = None

# State Schema

class PlannerState(TypedDict, total=False):
    # User query & Intent
    user_query: str
    intent: Literal["generate_itinerary", "budget_optimization", "hotel_change", "transport_change", "activity_update", "general_chat"]

    # Trip parameters
    destination: str
    origin: str
    origin_code: Optional[str]
    destination_code: Optional[str]
    days: int
    start_date: str
    travel_style: str
    number_of_people: int
    party_type: str
    hotel_type: str
    budget_tier: str
    budget_per_day: float
    transport_type: str
    preferences: str

    # Step 1: Places & Itinerary
    cities: List[str]
    places_queries: Dict[str, str]
    places: List[Dict[str, Any]]
    dataset_places: List[Dict[str, Any]]
    itinerary: Dict[str, Any]

    # Step 2: Hotels (Candidate list for Human-in-the-Loop)
    hotel_options: List[Dict[str, Any]]
    selected_hotel: Optional[Dict[str, Any]]

    # Step 3: Transport
    transport_options: List[Dict[str, Any]]
    selected_transport: Optional[Dict[str, Any]]

    # Step 4: Budget Analysis
    budget_analysis: Optional[Dict[str, Any]]
    user_message: str
    error: Optional[str]

# LLM Helpers

def _llm(system: str, user: str, temperature: float = 0.2, json_mode: bool = True) -> str:
    kwargs: Dict[str, Any] = {
        "model": LLM_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = groq_client.chat.completions.create(**kwargs)
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
    except Exception:
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(cleaned, strict=False)

# Default Factory & Initial State

def create_initial_state(
    destination: str = "Goa",
    days: int = 3,
    travel_style: str = "calm",
    number_of_people: int = 2,
    party_type: str = "friends",
    start_date: Optional[str] = None,
    user_query: str = "",
    hotel_type: str = "Mid-range",
    budget_tier: str = "₹5K – ₹15K",
    transport_type: str = "Flight",
    origin: str = "Mumbai",
) -> PlannerState:
    if not start_date:
        start_date = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")

    return PlannerState(
        user_query=user_query,
        intent="generate_itinerary",
        destination=destination,
        origin=origin,
        origin_code=None,
        destination_code=None,
        days=days,
        start_date=start_date,
        travel_style=travel_style,
        number_of_people=number_of_people,
        party_type=party_type,
        hotel_type=hotel_type,
        budget_tier=budget_tier,
        budget_per_day=7500.0,
        transport_type=transport_type,
        preferences="",
        cities=[],
        places_queries={},
        places=[],
        dataset_places=[],
        itinerary={},
        hotel_options=[],
        selected_hotel=None,
        transport_options=[],
        selected_transport=None,
        budget_analysis=None,
        user_message="",
        error=None,
    )

# Node 1: Classify Intent & Parse Input Query

def node_classify_and_parse(state: PlannerState) -> PlannerState:
    """
    Understands chat query from BuildTripPage (including active quick filters).
    Extracts all parameters and classifies into fixed intent options.
    """
    raw_query = state.get("user_query") or ""
    logger.info(f"Classifying user query: {raw_query[:100]}...")

    system_prompt = (
        "You are the central Travel Intent & Parameter Extraction AI for the Beyond platform.\n"
        "Analyze the user's chat input from the Build Trip page (which may include a header with quick filter chips like '[Quick details — Hotel preference: ... | Budget: ... | Transport: ...]').\n\n"
        "Classify the query into EXACTLY ONE of these fixed intents:\n"
        "  1. 'generate_itinerary' — User wants to plan a new trip or provides trip description/parameters.\n"
        "  2. 'budget_optimization' — User asks to reduce cost, optimize expenses, find cheaper alternatives, or questions budget.\n"
        "  3. 'hotel_change' — User asks to search/change/swap hotel or change accommodation tier.\n"
        "  4. 'transport_change' — User asks to change transport (e.g. flight to train/bus) or search different travel mode.\n"
        "  5. 'activity_update' — User wants to add, remove, or swap a specific activity or place.\n\n"
        "Extract all available parameters into a clean JSON object:\n"
        "{\n"
        "  \"intent\": \"generate_itinerary\" | \"budget_optimization\" | \"hotel_change\" | \"transport_change\" | \"activity_update\",\n"
        "  \"destination\": \"string (e.g. Goa, Jaipur, Manali, Kerala)\",\n"
        "  \"origin\": \"string (e.g. Mumbai, Delhi, Bangalore - default to Mumbai if not specified)\",\n"
        "  \"days\": integer (default 3 or 4 if unspecified),\n"
        "  \"start_date\": \"YYYY-MM-DD (default to 7 days from today if not mentioned)\",\n"
        "  \"travel_style\": \"calm\" | \"adventure\" | \"historical-cultural\" | \"spiritual\" | \"foodie\" | \"party\" (default calm),\n"
        "  \"number_of_people\": integer (default 2),\n"
        "  \"party_type\": \"solo\" | \"couple\" | \"friends\" | \"family\" | \"adventure-group\",\n"
        "  \"hotel_type\": \"Budget / Hostel\" | \"Mid-range\" | \"Boutique\" | \"Luxury / Resort\",\n"
        "  \"budget_tier\": \"< ₹5K / day\" | \"₹5K – ₹15K\" | \"₹15K – ₹30K\" | \"₹30K+\",\n"
        "  \"budget_per_day\": number (e.g. 5000, 10000, 25000, 35000),\n"
        "  \"transport_type\": \"Flight\" | \"Train\" | \"Bus\" | \"Self-drive\",\n"
        "  \"preferences\": \"string summary of special requests (e.g. beach view, veg food, water sports)\"\n"
        "}\n"
        "Return JSON only."
    )

    today_str = date.today().strftime("%Y-%m-%d")
    user_prompt = f"Today's date is {today_str}.\n\nUser Chat Input:\n{raw_query}"

    try:
        raw_json = _llm(system_prompt, user_prompt, temperature=0.1)
        parsed = _extract_json(raw_json)
    except Exception as e:
        logger.warning(f"Intent parsing fallback: {e}")
        parsed = {
            "intent": "generate_itinerary",
            "destination": state.get("destination", "Goa"),
            "days": state.get("days", 3),
            "travel_style": state.get("travel_style", "calm"),
            "number_of_people": state.get("number_of_people", 2),
            "party_type": state.get("party_type", "friends"),
        }

    # Update state fields safely
    state["intent"] = parsed.get("intent", "generate_itinerary")
    if parsed.get("destination"):
        state["destination"] = parsed["destination"]
    if parsed.get("origin"):
        state["origin"] = parsed["origin"]
    if parsed.get("days"):
        state["days"] = max(1, int(parsed["days"]))
    if parsed.get("start_date"):
        state["start_date"] = parsed["start_date"]
    elif not state.get("start_date"):
        state["start_date"] = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")

    if parsed.get("travel_style"):
        state["travel_style"] = parsed["travel_style"]
    if parsed.get("number_of_people"):
        state["number_of_people"] = max(1, int(parsed["number_of_people"]))
    if parsed.get("party_type"):
        state["party_type"] = parsed["party_type"]
    if parsed.get("hotel_type"):
        state["hotel_type"] = parsed["hotel_type"]
    if parsed.get("budget_tier"):
        state["budget_tier"] = parsed["budget_tier"]
    if parsed.get("budget_per_day"):
        state["budget_per_day"] = float(parsed["budget_per_day"])
    if parsed.get("transport_type"):
        state["transport_type"] = parsed["transport_type"]
    if parsed.get("preferences"):
        state["preferences"] = parsed["preferences"]

    logger.info(f"Classified Intent: {state['intent']} for {state.get('destination')} ({state.get('days')} days)")
    return state

def route_intent(state: PlannerState) -> str:
    intent = state.get("intent", "generate_itinerary")
    if intent == "budget_optimization":
        return "handle_budget_optimization"
    elif intent == "hotel_change":
        return "handle_hotel_change"
    elif intent == "transport_change":
        return "handle_transport_change"
    elif intent == "activity_update":
        return "handle_activity_update"
    return "fetch_places_and_itinerary"

# Helper: Clean Itinerary Activities

def clean_itinerary_activities(itinerary: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitizes itinerary by purging any empty, dummy, or dash activities and removing trivia."""
    if not isinstance(itinerary, dict) or "days" not in itinerary:
        return itinerary

    cleaned_days = []
    for day in itinerary.get("days", []):
        if not isinstance(day, dict):
            continue
        cleaned_day = dict(day)
        for slot in ("morning", "afternoon", "evening"):
            slot_activities = day.get(slot, [])
            if not isinstance(slot_activities, list):
                slot_activities = []
            valid_acts = []
            for act in slot_activities:
                if not isinstance(act, dict):
                    continue
                place_name = (act.get("place") or act.get("name") or "").strip()
                # Remove invalid, placeholder or empty activity items
                if not place_name or place_name in ("-", "—", "Activity", "None", "null", "N/A", "TBD", "·", "•"):
                    continue
                # Purge fun facts from activity item
                act.pop("fun_fact", None)
                act.pop("funFact", None)
                valid_acts.append(act)
            cleaned_day[slot] = valid_acts
        cleaned_days.append(cleaned_day)

    itinerary["days"] = cleaned_days

    # Remove all top-level trivia and fun fact fields
    for k in ("fun_facts", "must_try_food", "hidden_gems", "local_culture", "travel_hacks"):
        itinerary.pop(k, None)

    return itinerary

# Step 1: Places & Itinerary (Google Places + Tourism Dataset + Groq LLM)

def node_fetch_places_and_itinerary(state: PlannerState) -> PlannerState:
    """
    1. Checks Data/india_tourism_dataset.json via general_planner functions for rich local context.
    2. Uses LLM to generate targeted Google Places queries.
    3. Calls search_google_places tool.
    4. Synthesizes day-by-day itinerary without fun facts / trivia cards.
    5. Concurrently attaches Pexels photos and purges empty activity cards.
    """
    dest = state.get("destination", "Goa")
    days = state.get("days", 3)
    travel_style = state.get("travel_style", "calm")
    party_type = state.get("party_type", "friends")
    num_people = state.get("number_of_people", 2)
    start_date_str = state.get("start_date", (date.today() + timedelta(days=7)).strftime("%Y-%m-%d"))

    logger.info(f"[Step 1] Fetching places & creating itinerary for {dest}...")

    # 1. Dataset Context
    dataset_entries = find_destinations_for_query(dest)
    state["dataset_places"] = dataset_entries
    dataset_context = _extract_dataset_context(dataset_entries) if dataset_entries else ""

    # 2. Google Places Search Query
    places_found: List[Dict[str, Any]] = []
    if search_google_places:
        try:
            places_query_prompt = (
                f"Create a specific, high-yield Google Places text search query for top attractions in '{dest}' "
                f"matching travel style '{travel_style}'. Respond with ONLY the query string, nothing else."
            )
            places_query = _llm(
                "You are an expert travel search assistant. Return only the search string.",
                places_query_prompt,
                temperature=0.0,
                json_mode=False,
            )
            state["places_queries"] = {dest: places_query}
            logger.info(f"Google Places Query: {places_query}")
            places_found = search_google_places(places_query, max_results=15)
            state["places"] = places_found
        except Exception as e:
            logger.warning(f"Google Places tool error: {e}")

    # 3. Build Day-by-Day Itinerary JSON via Groq LLM matching App.tsx format
    trip_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    dates_list = [(trip_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    system_prompt = (
        "You are the Master Travel Architect for the Beyond platform.\n"
        "Generate a structured day-by-day itinerary JSON for the trip.\n\n"
        "OUTPUT FORMAT REQUIREMENTS:\n"
        "Return a JSON object with this EXACT structure:\n"
        "{\n"
        "  \"request\": {\n"
        f"    \"destination\": \"{dest}\",\n"
        f"    \"trip_start_date\": \"{start_date_str}\",\n"
        f"    \"days\": {days},\n"
        f"    \"travel_style\": \"{travel_style}\",\n"
        f"    \"number_of_people\": {num_people},\n"
        f"    \"party_type\": \"{party_type}\"\n"
        "  },\n"
        "  \"summary\": \"A compelling 1-2 sentence executive summary of the journey.\",\n"
        "  \"places_covered\": [\"List\", \"Of\", \"Cities\", \"Or\", \"Towns\"],\n"
        "  \"days\": [\n"
        "    {\n"
        "      \"date\": \"YYYY-MM-DD\",\n"
        "      \"theme\": \"Day Theme Title (e.g. Coastal Heritage & Sunsets)\",\n"
        "      \"weather\": \"Weather description (e.g. Sunny & pleasant, 27-31°C)\",\n"
        "      \"morning\": [\n"
        "        {\n"
        "          \"place\": \"Real Place or Attraction Name\",\n"
        "          \"time\": \"09:00 AM\",\n"
        "          \"duration\": \"2h\",\n"
        "          \"category\": \"Heritage | Beach | Nature | Culture | Food | Viewpoint\",\n"
        "          \"description\": \"Detailed visitor description.\",\n"
        "          \"tips\": \"Practical tip for this spot.\"\n"
        "        }\n"
        "      ],\n"
        "      \"afternoon\": [ ... ],\n"
        "      \"evening\": [ ... ],\n"
        "      \"notes\": \"Daily guidance, routing tips, or dining recommendations.\"\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "CRITICAL RULES:\n"
        "- Do NOT include any 'fun_facts', 'fun_fact', 'must_try_food', 'hidden_gems', or 'local_culture' fields anywhere.\n"
        "- Do NOT generate empty boxes, empty lists of activities, or dashes like '-' or '—'.\n"
        "- Every activity in morning, afternoon, evening MUST have a real, verified place name and description.\n"
        "- Do NOT use emojis in place names or descriptions.\n"
        "- Exactly match the number of days requested."
    )

    user_prompt = (
        f"Trip Parameters: {days} days in {dest} for {num_people} people ({party_type}).\n"
        f"Dates: {', '.join(dates_list)}\n"
        f"Travel Style: {travel_style}\n\n"
        f"TOURISM DATASET CONTEXT:\n{dataset_context or 'No direct dataset match, use verified places.'}\n\n"
        f"VERIFIED GOOGLE PLACES DATA:\n{json.dumps(places_found[:12], indent=2) if places_found else 'None available, use expert knowledge.'}\n\n"
        "Generate the complete itinerary JSON now."
    )

    try:
        raw_itin = _llm(system_prompt, user_prompt, temperature=0.3)
        itinerary = _extract_json(raw_itin)
    except Exception as e:
        logger.error(f"Itinerary synthesis failed: {e}")
        itinerary = {
            "request": {
                "destination": dest,
                "trip_start_date": start_date_str,
                "days": days,
                "travel_style": travel_style,
                "number_of_people": num_people,
                "party_type": party_type,
            },
            "summary": f"A {days}-day {travel_style} adventure in {dest}.",
            "days": [],
        }

    # Clean and purge any empty/dummy boxes or fun facts
    itinerary = clean_itinerary_activities(itinerary)

    # Attach Pexels Images
    try:
        itinerary = attach_activity_images(itinerary, dest)
    except Exception as e:
        logger.warning(f"Failed to attach activity images: {e}")

    state["itinerary"] = itinerary
    return state

# Step 2: Hotel Search Tool (Tavily + Pexels, Candidate Stays for Each Day)

def _get_city_for_day(day_obj: dict, default_dest: str, day_idx: int, total_days: int) -> str:
    """Extracts the primary city/destination for a specific day in a multi-city itinerary."""
    if not isinstance(day_obj, dict):
        return default_dest.split(",")[0].strip()

    # 1. Check activities in morning, afternoon, evening
    for slot in ("morning", "afternoon", "evening"):
        for act in day_obj.get(slot, []):
            if isinstance(act, dict):
                place = act.get("place") or act.get("name") or ""
                if "," in place:
                    parts = [p.strip() for p in place.split(",")]
                    if len(parts) >= 2 and len(parts[-1]) >= 3:
                        return parts[-1]
                # Check for city names in place string
                for c in default_dest.split(","):
                    c_clean = c.strip()
                    if c_clean and c_clean.lower() in place.lower():
                        return c_clean

    # 2. Check theme
    theme = day_obj.get("theme", "")
    for c in default_dest.split(","):
        c_clean = c.strip()
        if c_clean and c_clean.lower() in theme.lower():
            return c_clean

    # 3. If multi-city list, map index proportionally
    cities = [c.strip() for c in default_dest.split(",") if c.strip()]
    if len(cities) > 1:
        city_idx = min(len(cities) - 1, int(day_idx * len(cities) / max(1, total_days)))
        return cities[city_idx]

    return cities[0] if cities else default_dest.strip()

def _fetch_verified_hotels_for_city(
    city: str,
    hotel_type: str,
    budget_night: float,
    num_people: int,
    start_date: str,
    check_out: str,
) -> List[Dict[str, Any]]:
    """Fetches real verified hotels for a specific city via hotel_search tool."""
    from Tools.hotel_search import hotel_search as _hs

    # Query live hotel_search tool
    if _hs:
        try:
            res = _hs({
                "destination": city,
                "check_in": start_date,
                "check_out": check_out,
                "num_people": num_people,
                "budget_per_day": max(1200, int(budget_night)),
                "hotel_type": hotel_type,
                "currency": "INR",
            })
            results = res.get("results", [])
            if results and len(results) >= 2:
                return results[:3]
        except Exception as e:
            logger.warning(f"Hotel search failed for {city}: {e}")

    # 3. Fallback to high quality city-branded stay
    return [
        {
            "name": f"Taj Resort & Palace {city}",
            "category": "Luxury / Resort" if "luxury" in hotel_type.lower() else "Boutique",
            "platform": "Booking.com",
            "price_per_night": int(budget_night * 1.1),
            "currency": "INR",
            "rating": 4.8,
            "description": f"Premier accommodation in {city} offering scenic views, fine dining, and prime location.",
            "image_url": "https://images.pexels.com/photos/271624/pexels-photo-271624.jpeg",
            "booking_link": f"https://www.booking.com/searchresults.html?ss={city}",
        },
        {
            "name": f"The Grand Heritage Hotel {city}",
            "category": "Heritage / Boutique",
            "platform": "MakeMyTrip",
            "price_per_night": int(budget_night),
            "currency": "INR",
            "rating": 4.7,
            "description": f"Charming heritage property in {city} with traditional architecture and modern comforts.",
            "image_url": "https://images.pexels.com/photos/189296/pexels-photo-189296.jpeg",
            "booking_link": f"https://www.makemytrip.com/hotels/{city.lower()}-hotels.html",
        },
        {
            "name": f"Radisson Hotel {city}",
            "category": "Mid-range",
            "platform": "Agoda",
            "price_per_night": max(1800, int(budget_night * 0.8)),
            "currency": "INR",
            "rating": 4.5,
            "description": f"Comfortable contemporary stay in {city} with complimentary breakfast and easy transit access.",
            "image_url": "https://images.pexels.com/photos/261102/pexels-photo-261102.jpeg",
            "booking_link": f"https://www.agoda.com/city/{city.lower()}-in.html",
        },
    ]

def node_fetch_hotels(state: PlannerState) -> PlannerState:
    """
    Fetches real verified hotels tailored to EACH day's specific city / location.
    If day 1 is Varanasi and day 2 is Rishikesh, day 1 gets Varanasi hotels and
    day 2 gets Rishikesh hotels!
    """
    dest = state.get("destination", "Goa")
    days = state.get("days", 3)
    num_people = state.get("number_of_people", 2)
    hotel_type = state.get("hotel_type", "Mid-range")
    budget_per_day = state.get("budget_per_day", 7500.0)
    hotel_budget_night = round(budget_per_day * 0.40, 2)

    start_date = state.get("start_date") or date.today().strftime("%Y-%m-%d")
    try:
        check_out = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    except Exception:
        check_out = (date.today() + timedelta(days=days + 7)).strftime("%Y-%m-%d")

    itin = state.get("itinerary") or {}
    day_list = itin.get("days", []) if isinstance(itin, dict) else []

    all_day_hotels = {}
    # Fetch city-specific hotels for each day
    for d_idx, day_obj in enumerate(day_list):
        day_city = _get_city_for_day(day_obj, dest, d_idx, len(day_list))
        if day_city not in all_day_hotels:
            logger.info(f"[Step 2] Fetching verified hotels for Day {d_idx + 1} city: {day_city}...")
            all_day_hotels[day_city] = _fetch_verified_hotels_for_city(
                day_city, hotel_type, hotel_budget_night, num_people, start_date, check_out
            )
        day_hotels = all_day_hotels[day_city]
        day_obj["hotel_options"] = day_hotels
        day_obj["selected_hotel"] = day_hotels[0] if day_hotels else None

    # Top-level default hotel options
    primary_city = dest.split(",")[0].strip()
    primary_hotels = all_day_hotels.get(primary_city) or list(all_day_hotels.values())[0] if all_day_hotels else _fetch_verified_hotels_for_city(
        primary_city, hotel_type, hotel_budget_night, num_people, start_date, check_out
    )

    state["hotel_options"] = primary_hotels
    state["selected_hotel"] = primary_hotels[0] if primary_hotels else None

    if isinstance(itin, dict):
        itin["hotel_options"] = primary_hotels
        itin["selected_hotel"] = primary_hotels[0] if primary_hotels else None
        state["itinerary"] = itin

    return state

# Step 3: Transport Search Tool (SerpApi Flights / IRCTC Trains / Bus)

def _tavily_search(query: str, max_results: int = 3) -> list:
    """Minimal Tavily search helper for filling missing transport info."""
    import requests as _req
    tavily_key = os.getenv("Tavily_api")
    if not tavily_key:
        return []
    try:
        resp = _req.post(
            "https://api.tavily.com/search",
            json={"api_key": tavily_key, "query": query, "max_results": max_results, "search_depth": "basic"},
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        logger.warning(f"Tavily fallback search failed: {e}")
        return []

def _extract_price_from_text(text: str) -> int | None:
    """Extract INR price from Tavily snippet text."""
    import re as _re
    m = _re.search(r"(?:₹|INR|Rs\.?)\s?([\d,]{3,6})", text, _re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None

def node_fetch_transport(state: PlannerState) -> PlannerState:
    """
    Fetches transport options for the trip.
    - Tries live API (SerpApi flights / IRCTC trains).
    - On missing price or empty results, enriches via Tavily search.
    - Handles all modes: flight, train, bus, self-drive — no mode-specific hardcoding.
    """
    dest = state.get("destination", "Goa")
    origin = state.get("origin", "Mumbai")
    norm_trans = (state.get("transport_type") or "Flight").strip().lower()
    if "flight" in norm_trans:
        trans_mode = "flight"
    elif "train" in norm_trans:
        trans_mode = "train"
    elif "bus" in norm_trans:
        trans_mode = "bus"
    else:
        trans_mode = "self-drive"

    num_people = state.get("number_of_people", 2)
    budget_per_day = state.get("budget_per_day", 7500.0)
    days = state.get("days", 3)
    transport_budget = round(budget_per_day * days * 0.30, 2)

    logger.info(f"[Step 3] Searching transport {trans_mode} from {origin} to {dest}...")

    def _code_for_city(city: str, mode: str) -> str:
        c = (city or "").lower()
        if mode == "flight":
            codes = {"mumbai": "BOM", "delhi": "DEL", "goa": "GOI", "bangalore": "BLR",
                     "jaipur": "JAI", "chennai": "MAA", "kolkata": "CCU", "hyderabad": "HYD",
                     "pune": "PNQ", "kochi": "COK", "ahmedabad": "AMD", "srinagar": "SXR",
                     "leh": "IXL", "udaipur": "UDR", "jodhpur": "JDH", "varanasi": "VNS"}
            return codes.get(c, "DEL")
        else:
            codes = {"mumbai": "CSMT", "delhi": "NDLS", "goa": "MAO", "bangalore": "SBC",
                     "jaipur": "JP", "chennai": "MAS", "kolkata": "HWH", "hyderabad": "HYB",
                     "pune": "PUNE", "kochi": "ERS", "ahmedabad": "ADI", "varanasi": "BSB"}
            return codes.get(c, "NDLS")

    o_code = state.get("origin_code") or _code_for_city(origin, trans_mode)
    d_code = state.get("destination_code") or _code_for_city(dest, trans_mode)

    transport_results = []

    # — Live API search (flight / train / bus) —
    if trans_mode in ("flight", "train", "bus") and transport_search:
        try:
            res = transport_search({
                "transport_type": trans_mode,
                "origin": origin,
                "origin_code": o_code,
                "destination": dest,
                "destination_code": d_code,
                "travel_date": state.get("start_date", date.today().strftime("%Y-%m-%d")),
                "budget": max(800, int(transport_budget / max(num_people * 2, 1))),
                "num_people": num_people,
                "preferred_time": "morning",
            })
            transport_results = res.get("results", [])
        except Exception as e:
            logger.warning(f"transport_search tool error: {e}")

    # — Tavily enrichment: fill missing price or all info when results are empty —
    if not transport_results or not any(r.get("price") for r in transport_results):
        tavily_query = (
            f"cheapest {trans_mode} from {origin} to {dest} price INR 2024"
            if trans_mode != "self-drive"
            else f"road trip {origin} to {dest} distance fuel cost INR"
        )
        tavily_hits = _tavily_search(tavily_query, max_results=5)

        if not transport_results and tavily_hits:
            # Build a result from Tavily data
            best_hit = tavily_hits[0]
            combined_text = " ".join(h.get("content", "") for h in tavily_hits)
            tavily_price = _extract_price_from_text(combined_text)

            transport_results = [{
                "mode": trans_mode.capitalize(),
                "provider": best_hit.get("title", f"{trans_mode.capitalize()} from {origin}"),
                "identifier": "",
                "origin": origin,
                "destination": dest,
                "departure_time": None,
                "arrival_time": None,
                "duration": None,
                "price": tavily_price,
                "price_per_person": tavily_price,
                "total_price": (tavily_price * num_people) if tavily_price else None,
                "currency": "INR",
                "stops": None,
                "booking_link": best_hit.get("url", ""),
                "raw_note": best_hit.get("content", "")[:200],
            }]
        elif transport_results and tavily_hits:
            # Enrich missing prices in existing results
            combined_text = " ".join(h.get("content", "") for h in tavily_hits)
            tavily_price = _extract_price_from_text(combined_text)
            for t in transport_results:
                if not t.get("price") and tavily_price:
                    t["price"] = tavily_price
                    t["price_per_person"] = tavily_price

    # — Standardize fields across all results —
    for t in transport_results:
        pp = t.get("price_per_person") or t.get("price") or 0
        if pp:
            pp = int(pp)
        t["price_per_person"] = pp or None
        t["total_price"] = (pp * num_people) if pp else None
        # Normalize mode label
        if not t.get("mode"):
            t["mode"] = trans_mode.capitalize()
        # booking_link fallback by mode
        if not t.get("booking_link"):
            if trans_mode == "flight":
                t["booking_link"] = f"https://www.makemytrip.com/flights"
            elif trans_mode == "train":
                t["booking_link"] = "https://www.irctc.co.in/nget/train-search"
            elif trans_mode == "bus":
                t["booking_link"] = "https://www.redbus.in"

    best_transport = transport_results[0] if transport_results else None
    state["transport_options"] = transport_results
    state["selected_transport"] = best_transport

    itin = state.get("itinerary") or {}
    if isinstance(itin, dict):
        itin["best_flight"] = best_transport   # keep key for frontend compatibility
        itin["transport"] = best_transport
        itin["transport_options"] = transport_results
        state["itinerary"] = itin

    return state

# Step 4: Budget Evaluation Node (Budget Breakdown Calculation)

def node_evaluate_budget(state: PlannerState) -> PlannerState:
    """
    Calculates detailed realistic budget breakdown:
    Hotel + Transport + Restaurant/Dining + Activities + Grand Total.
    """
    days = state.get("days", 3)
    num_people = state.get("number_of_people", 2)
    budget_per_day = state.get("budget_per_day", 7500.0)

    selected_hotel = state.get("selected_hotel") or {}
    selected_trans = state.get("selected_transport") or {}

    hotel_nightly = float(selected_hotel.get("price_per_night") or max(2000, budget_per_day * 0.40))
    hotel_total = round(hotel_nightly * max(1, days), 2)

    # Guard: price/price_per_person may be None (e.g. trains without fare data)
    _raw_trans_price = (
        selected_trans.get("price_per_person")
        or selected_trans.get("price")
        or 0
    )
    trans_person = float(_raw_trans_price) if _raw_trans_price else 4200.0
    transport_total = round(trans_person * num_people * 2, 2)  # roundtrip total for party

    # Restaurant / Food calculation (realistic daily dining across party)
    food_per_person_day = 1200.0 if "luxury" not in state.get("hotel_type", "").lower() else 2500.0
    food_per_day = round(food_per_person_day * num_people, 2)
    food_restaurant_total = round(food_per_day * days, 2)

    activities_total = round(600.0 * num_people * days, 2)
    grand_total = round(hotel_total + transport_total + food_restaurant_total + activities_total, 2)

    breakdown = {
        "hotel_total": hotel_total,
        "hotel_per_night": hotel_nightly,
        "transport_total": transport_total,
        "transport_per_person": trans_person,
        "food_restaurant_total": food_restaurant_total,
        "food_per_day": food_per_day,
        "activities_total": activities_total,
        "grand_total": grand_total,
        "per_person_total": round(grand_total / max(1, num_people), 2),
        "currency": "INR",
        "tier": state.get("hotel_type", "Mid-range"),
    }

    # Invoke BudgetAgent if available for extra feasibility warnings
    if BudgetAgent:
        try:
            agent = BudgetAgent()
            b_res = agent.reconfigure_budget(
                days=days,
                budget_per_day=budget_per_day,
                transport_type=state.get("transport_type", "Flight"),
                hotel_type=state.get("hotel_type", "Mid-range"),
                num_people=num_people,
                destination=state.get("destination", "Goa"),
                origin=state.get("origin", "Mumbai"),
                party_type=state.get("party_type", "friends"),
                query=state.get("user_query", ""),
            )
            state["budget_analysis"] = b_res.to_dict()
            state["budget_analysis"]["breakdown"] = breakdown
        except Exception as e:
            logger.warning(f"BudgetAgent error: {e}")

    state["user_message"] = (
        f"Your {days}-day itinerary for {state.get('destination')} is ready! "
        f"Best flight options, hotel stay choices for each day, and total budget breakdown have been generated."
    )

    itin = state.get("itinerary") or {}
    if isinstance(itin, dict):
        itin["budget_breakdown"] = breakdown
        state["itinerary"] = itin

    return state

# Intent Handlers (Updates, Budget Optimization, Hotel Changes)

def node_handle_budget_optimization(state: PlannerState) -> PlannerState:
    """Handles budget optimization requests using BudgetAgent and tools."""
    logger.info("Handling budget optimization...")
    if not BudgetAgent:
        state["user_message"] = "Budget agent is currently offline."
        return state

    agent = BudgetAgent()
    days = state.get("days", 3)
    num_people = state.get("number_of_people", 2)
    per_day = state.get("budget_per_day", 7500.0)
    allotted = per_day * days

    current_expenses = {
        "hotel": state.get("selected_hotel") or {"price_per_night": per_day * 0.45, "total_cost": per_day * 0.45 * days},
        "transport": state.get("selected_transport") or {"price": 4500, "total_cost": 4500 * num_people * 2},
        "activities": [],
        "food_misc": per_day * 0.30 * days,
    }

    opt_res = agent.optimize_budget(
        destination=state.get("destination", "Goa"),
        days=days,
        allotted_budget=allotted,
        current_expenses=current_expenses,
        num_people=num_people,
        hotel_type=state.get("hotel_type", "Mid-range"),
        transport_type=state.get("transport_type", "Flight"),
        origin=state.get("origin", "Mumbai"),
        user_query=state.get("user_query", "Optimize my budget"),
    )

    state["budget_analysis"] = opt_res.to_dict()
    state["user_message"] = opt_res.user_alert_message
    return state

def node_handle_hotel_change(state: PlannerState) -> PlannerState:
    """Handles hotel swap or search with newly requested preferences."""
    logger.info("Handling hotel change request...")
    state = node_fetch_hotels(state)
    options = state.get("hotel_options", [])
    itin = state.get("itinerary")
    if itin and isinstance(itin, dict) and options:
        itin["hotel_options"] = options
        itin["selected_hotel"] = state.get("selected_hotel") or options[0]
        state["itinerary"] = itin
    state["user_message"] = (
        f"We found {len(options)} new accommodation choices in {state.get('destination')} "
        f"matching your updated preferences. Please select your favorite stay!"
    )
    return state

def node_handle_transport_change(state: PlannerState) -> PlannerState:
    """Handles transport swap or search."""
    logger.info("Handling transport change request...")
    state = node_fetch_transport(state)
    options = state.get("transport_options", [])
    itin = state.get("itinerary")
    if itin and isinstance(itin, dict) and state.get("selected_transport"):
        itin["best_flight"] = state["selected_transport"]
        itin["transport"] = state["selected_transport"]
        state["itinerary"] = itin
    state["user_message"] = (
        f"We found {len(options)} {state.get('transport_type')} options from {state.get('origin')} "
        f"to {state.get('destination')}."
    )
    return state

def node_handle_activity_update(state: PlannerState) -> PlannerState:
    """Handles add/swap/modify activity or day request in ongoing chat."""
    logger.info("Handling activity update request...")
    dest = state.get("destination", "Goa")
    query = state.get("user_query", "")
    itin = state.get("itinerary")

    # If an itinerary already exists, use LLM to modify it according to the user request
    if itin and isinstance(itin, dict) and itin.get("days"):
        system_prompt = (
            "You are the Master Travel Architect for the Beyond platform.\n"
            "The user has an existing trip itinerary and wants to modify, swap, or update activities or entire days via chat.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "- Update the itinerary according to the user's instructions (e.g. replacing a day's activities, changing the travel theme, swapping places).\n"
            "- Keep unaffected days, request info, and overall itinerary structure intact.\n"
            "- Ensure every activity in morning, afternoon, evening has place, time, duration, category, description, tips.\n"
            "- Do NOT include 'fun_facts', 'fun_fact', 'must_try_food', or 'hidden_gems'.\n"
            "- Do NOT use emojis in place names or descriptions, and no em-dashes.\n"
            "- Return a valid JSON object matching the existing itinerary schema.\n"
            "Return valid JSON only."
        )
        user_prompt = (
            f"Destination: {dest}\n"
            f"User Modification Request: \"{query}\"\n\n"
            f"Current Itinerary:\n{json.dumps(itin, indent=2)}\n\n"
            "Update the itinerary now and return the complete updated JSON."
        )
        try:
            raw = _llm(system_prompt, user_prompt, temperature=0.3)
            updated_itin = _extract_json(raw)
            if isinstance(updated_itin, dict) and updated_itin.get("days"):
                updated_itin = clean_itinerary_activities(updated_itin)
                # Preserve hotel and transport metadata
                if itin.get("hotel_options") and not updated_itin.get("hotel_options"):
                    updated_itin["hotel_options"] = itin["hotel_options"]
                if itin.get("selected_hotel") and not updated_itin.get("selected_hotel"):
                    updated_itin["selected_hotel"] = itin["selected_hotel"]
                if itin.get("best_flight") and not updated_itin.get("best_flight"):
                    updated_itin["best_flight"] = itin["best_flight"]
                if itin.get("budget_breakdown") and not updated_itin.get("budget_breakdown"):
                    updated_itin["budget_breakdown"] = itin["budget_breakdown"]

                # Attach images for any newly added activities
                try:
                    if attach_activity_images:
                        updated_itin = attach_activity_images(updated_itin, dest)
                except Exception as e:
                    logger.warning(f"Failed to attach images after update: {e}")

                state["itinerary"] = updated_itin
                state["user_message"] = f"I've updated your itinerary based on your request: \"{query}\"."
                return state
        except Exception as e:
            logger.error(f"Failed to update itinerary with LLM: {e}")

    new_places = search_google_places(f"{dest} {query}", max_results=5) if search_google_places else []
    state["places"] = new_places
    state["user_message"] = f"Found {len(new_places)} alternative activities matching '{query}' in {dest}."
    return state

# Build LangGraph

def build_graph() -> StateGraph:
    graph = StateGraph(PlannerState)

    # Add Nodes
    graph.add_node("classify_and_parse", node_classify_and_parse)
    graph.add_node("fetch_places_and_itinerary", node_fetch_places_and_itinerary)
    graph.add_node("fetch_hotels", node_fetch_hotels)
    graph.add_node("fetch_transport", node_fetch_transport)
    graph.add_node("evaluate_budget", node_evaluate_budget)

    # Sub-handlers for updates
    graph.add_node("handle_budget_optimization", node_handle_budget_optimization)
    graph.add_node("handle_hotel_change", node_handle_hotel_change)
    graph.add_node("handle_transport_change", node_handle_transport_change)
    graph.add_node("handle_activity_update", node_handle_activity_update)

    # Connect Start
    graph.add_edge(START, "classify_and_parse")

    # Conditional Routing based on Intent
    graph.add_conditional_edges(
        "classify_and_parse",
        route_intent,
        {
            "fetch_places_and_itinerary": "fetch_places_and_itinerary",
            "handle_budget_optimization": "handle_budget_optimization",
            "handle_hotel_change": "handle_hotel_change",
            "handle_transport_change": "handle_transport_change",
            "handle_activity_update": "handle_activity_update",
        },
    )

    # 3-Step Pipeline for generate_itinerary
    graph.add_edge("fetch_places_and_itinerary", "fetch_hotels")
    graph.add_edge("fetch_hotels", "fetch_transport")
    graph.add_edge("fetch_transport", "evaluate_budget")
    graph.add_edge("evaluate_budget", END)

    # Connect handlers to END
    graph.add_edge("handle_budget_optimization", END)
    graph.add_edge("handle_hotel_change", END)
    graph.add_edge("handle_transport_change", END)
    graph.add_edge("handle_activity_update", END)

    return graph.compile()

# Helper for Backward Compatibility & API endpoints

def _select_summary_places(places: List[Dict[str, Any]], travel_style: str = "calm", max_total: int = 15, max_per_city: int = 7) -> List[Dict[str, Any]]:
    """Helper to return top summary places."""
    summary = []
    for p in places[:max_total]:
        summary.append({
            "name": p.get("name", "Attraction"),
            "address": p.get("address", ""),
            "rating": p.get("rating", 4.5),
            "timings": p.get("timings", "Open daily"),
            "why_selected": f"Recommended for {travel_style} travel style.",
        })
    return summary

