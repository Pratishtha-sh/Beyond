"""Accommodation search tool using SerpApi Google Hotels with TF-IDF preference reranking."""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hotel_search")

SERP_API_KEY = os.getenv("serp_hotel_api")
PEXELS_API_KEY = os.getenv("pexels_api")

SERP_API_URL = "https://serpapi.com/search?engine=google_hotels"
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

FALLBACK_IMAGE = "https://images.pexels.com/photos/271624/pexels-photo-271624.jpeg"

# 1. Hotel-type -> which Google Hotels sub-queries to run
# hotel_class: Google Hotels only supports 2/3/4/5 star (no 1-star tier) --
#   confirmed against SerpApi's documented parameter values. "hotel_class"
#   and "brands" are NOT available when vacation_rentals=true, per SerpApi
#   docs, so those params are only ever sent on the hotels pass, never the
#   vacation-rentals pass.
# sort_by: "3" = lowest price, "8" = highest rating, "13" = most reviewed.
#   Budget-tier search sorts by lowest price by default since that's the
#   more useful ordering for that hotel_type; other tiers sort by relevance.
# vacation_rentals: whether to also pull an Airbnb/Vrbo-style pass.
# This is the rule enforcing "no vacation rentals for Budget/Hostel" etc.
HOTEL_TYPE_CONFIG: Dict[str, Dict[str, Any]] = {
    "Budget/Hostel":  {"hotel_class": "2",     "vacation_rentals": False, "sort_by": "3", "label": "budget hotel/hostel"},
    "Mid-range":      {"hotel_class": "2,3",   "vacation_rentals": True,  "sort_by": None, "label": "mid-range hotel"},
    "Boutique":       {"hotel_class": "3,4",   "vacation_rentals": True,  "sort_by": None, "label": "boutique hotel"},
    "Luxury/Resort":  {"hotel_class": "4,5",   "vacation_rentals": True,  "sort_by": "8", "label": "luxury resort"},
}

REQUIRED_STATE_FIELDS = ["destination", "hotel_type", "budget_per_day", "num_people"]

# 2. Data model
@dataclass
class HotelResult:
    name: str
    category: str                      # hotel / vacation rental
    platform: str                      # e.g. Booking.com, MakeMyTrip, Google Hotels
    price_per_night: Optional[float]
    currency: str
    rating: Optional[float]
    description: str
    image_url: str = FALLBACK_IMAGE
    booking_link: str = ""
    source_url: str = ""
    relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def _validate_state(state: Dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_STATE_FIELDS if f not in state or state[f] in (None, "")]
    if missing:
        raise ValueError(f"hotel_search: missing required state fields: {missing}")
    if state["hotel_type"] not in HOTEL_TYPE_CONFIG:
        raise ValueError(
            f"hotel_search: unknown hotel_type '{state['hotel_type']}'. "
            f"Must be one of {list(HOTEL_TYPE_CONFIG.keys())}"
        )

def _default_dates(state: Dict[str, Any]) -> Tuple[str, str]:
    """Google Hotels requires check_in/check_out dates. Falls back to a
    generic near-future 1-night stay if the planner agent didn't supply them
    -- results will still be usable but you should prefer passing real dates."""
    check_in = state.get("check_in")
    check_out = state.get("check_out")
    if check_in and check_out:
        return check_in, check_out

    logger.warning("check_in/check_out not provided in state; defaulting to a placeholder date range.")
    fallback_in = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
    fallback_out = (datetime.utcnow() + timedelta(days=31)).strftime("%Y-%m-%d")
    return fallback_in, fallback_out

# 3. SerpApi Google Hotels call
def _call_google_hotels(
    query: str,
    check_in: str,
    check_out: str,
    adults: int,
    currency: str,
    hotel_class: Optional[str] = None,
    vacation_rentals: bool = False,
    max_price: Optional[float] = None,
    sort_by: Optional[str] = None,
    rating: Optional[str] = None,
    children: int = 0,
    children_ages: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Calls SerpApi's Google Hotels engine (https://serpapi.com/search?engine=google_hotels).

    Per SerpApi's documented parameters:
      - check_in_date / check_out_date are REQUIRED (YYYY-MM-DD).
      - hotel_class accepts only 2/3/4/5 (no 1-star tier exists).
      - hotel_class and brands are NOT valid when vacation_rentals=true --
        so they are only ever attached on the hotels pass below.
      - sort_by: "3" lowest price, "8" highest rating, "13" most reviewed.
      - rating: "7" = 3.5+, "8" = 4.0+, "9" = 4.5+.
    """
    if not SERP_API_KEY:
        raise EnvironmentError("SERP_API_KEY (serp_api) is not set in the environment.")

    params = {
        "engine": "google_hotels",
        "q": query,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": str(adults),
        "currency": currency,
        "gl": "in",
        "hl": "en",
        "api_key": SERP_API_KEY,
    }
    if children:
        params["children"] = str(children)
        if children_ages:
            params["children_ages"] = children_ages
    if vacation_rentals:
        params["vacation_rentals"] = "true"
        # hotel_class / brands intentionally omitted here -- unsupported for vacation rentals
    elif hotel_class:
        params["hotel_class"] = hotel_class
    if max_price:
        # generous ceiling; the reranker/budget filter tightens this further
        params["max_price"] = str(int(max_price * 1.5))
    if sort_by:
        params["sort_by"] = sort_by
    if rating:
        params["rating"] = rating

    try:
        resp = requests.get(SERP_API_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"SerpApi Google Hotels call failed for '{query}' (vacation_rentals={vacation_rentals}): {e}")
        return []

    return data.get("properties", []) or []

# 4. Parse a raw SerpApi property into HotelResult
def _parse_property(prop: Dict[str, Any], is_vacation_rental: bool, currency: str) -> Optional[HotelResult]:
    name = prop.get("name")
    if not name:
        return None

    # Price: SerpApi gives rate_per_night.extracted_lowest as a clean number.
    rate_info = prop.get("rate_per_night", {}) or {}
    price = rate_info.get("extracted_lowest")

    # Booking link: prefer a real OTA offer link if present, else the
    # property's own link, else the general Google Hotels result link.
    booking_link = prop.get("link", "")
    offers = prop.get("prices", []) or []
    if offers:
        # offers look like: {"source": "Booking.com", "link": "...", "rate_per_night": {...}}
        booking_link = offers[0].get("link", booking_link)

    platform = "Google Hotels"
    if offers:
        platform = offers[0].get("source", platform)
    elif is_vacation_rental:
        platform = "Vacation Rental (Google)"

    images = prop.get("images", []) or []
    image_url = images[0].get("thumbnail") if images and images[0].get("thumbnail") else FALLBACK_IMAGE

    amenities = ", ".join(prop.get("amenities", [])[:6]) if prop.get("amenities") else ""
    description = prop.get("description", "") or amenities

    return HotelResult(
        name=name,
        category="vacation rental" if is_vacation_rental else prop.get("type", "hotel"),
        platform=platform,
        price_per_night=price,
        currency=currency,
        rating=prop.get("overall_rating"),
        description=description[:280],
        image_url=image_url,
        booking_link=booking_link,
        source_url=prop.get("link", booking_link),
    )

# 5. Gather candidates across hotel + (optionally) vacation-rental passes
def gather_candidates(state: Dict[str, Any], target_count: int = 15) -> List[HotelResult]:
    config = HOTEL_TYPE_CONFIG[state["hotel_type"]]
    check_in, check_out = _default_dates(state)
    currency = state.get("currency", "INR")
    adults = state.get("num_people", 1)

    query_parts = [state["destination"], config["label"]]
    if state.get("description"):
        query_parts.append(state["description"])
    if state.get("mood"):
        query_parts.append(state["mood"])
    query = " ".join(query_parts)

    candidates: List[HotelResult] = []
    seen_names = set()

    # Pass 1: hotels (always runs)
    hotel_props = _call_google_hotels(
        query=query, check_in=check_in, check_out=check_out, adults=adults,
        currency=currency, hotel_class=config["hotel_class"],
        vacation_rentals=False, max_price=state["budget_per_day"],
        sort_by=config.get("sort_by"),
    )
    for prop in hotel_props:
        h = _parse_property(prop, is_vacation_rental=False, currency=currency)
        if h and h.name.lower() not in seen_names:
            seen_names.add(h.name.lower())
            candidates.append(h)

    # Pass 2: vacation rentals (airbnb/vrbo-style) -- only for types that allow it
    if config["vacation_rentals"]:
        vr_props = _call_google_hotels(
            query=query, check_in=check_in, check_out=check_out, adults=adults,
            currency=currency, vacation_rentals=True, max_price=state["budget_per_day"],
            sort_by=config.get("sort_by"),
        )
        for prop in vr_props:
            h = _parse_property(prop, is_vacation_rental=True, currency=currency)
            if h and h.name.lower() not in seen_names:
                seen_names.add(h.name.lower())
                candidates.append(h)

    return candidates[:target_count]

# 6. Budget filter (now against real extracted prices, not regex guesses)
def filter_by_budget(candidates: List[HotelResult], budget_per_day: float, tolerance: float = 1.15) -> List[HotelResult]:
    filtered = [c for c in candidates if c.price_per_night is None or c.price_per_night <= budget_per_day * tolerance]
    return filtered

# 7. Rerank via TF-IDF (still valuable: matches "beach facing, quiet" style
#    preferences that Google Hotels' own filters don't expose)
def rerank_candidates(candidates: List[HotelResult], state: Dict[str, Any], top_k: int = 5) -> List[HotelResult]:
    if not candidates:
        return []

    query_text = " ".join(filter(None, [
        state["destination"], state["hotel_type"],
        state.get("mood", ""), state.get("description", ""),
        f"for {state['num_people']} people",
    ]))

    corpus = [query_text] + [f"{c.name} {c.category} {c.description}" for c in candidates]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)
    scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    for c, score in zip(candidates, scores):
        c.relevance_score = round(float(score), 4)

    # Blend relevance with price-fit: cheaper-and-closer-to-budget nudges up
    # equally relevant options, without letting price override a poor match.
    ranked = sorted(candidates, key=lambda c: c.relevance_score, reverse=True)
    return ranked[:top_k]

# 8. Image fallback (Pexels) -- only used if a listing has no real photo
def _fallback_image(hotel_name: str, destination: str) -> str:
    if not PEXELS_API_KEY:
        return FALLBACK_IMAGE
    try:
        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": f"{hotel_name} {destination}", "per_page": 1, "orientation": "landscape"},
            timeout=8,
        )
        if resp.status_code == 200:
            photos = resp.json().get("photos", [])
            if photos:
                return photos[0]["src"]["medium"]
    except requests.RequestException:
        pass
    return FALLBACK_IMAGE

def ensure_images(hotels: List[HotelResult], destination: str) -> None:
    for hotel in hotels:
        if hotel.image_url == FALLBACK_IMAGE:
            hotel.image_url = _fallback_image(hotel.name, destination)

# 9. Main entry point (called by planner_agent.py)
def hotel_search(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
        state: trip state dict. Must contain destination, hotel_type,
               budget_per_day, num_people. Strongly recommended: check_in,
               check_out (Google Hotels needs real dates for real prices).

    Returns:
        {
            "destination": str,
            "hotel_type": str,
            "results": [ {name, category, platform, price_per_night,
                          currency, rating, description, image_url,
                          booking_link, source_url, relevance_score}, ... ]
        }
    """
    _validate_state(state)

    logger.info(f"Searching accommodation in {state['destination']} "
                f"(type={state['hotel_type']}, budget/day={state['budget_per_day']})")

    candidates = gather_candidates(state, target_count=15)
    logger.info(f"Google Hotels returned {len(candidates)} structured candidates")

    budget_filtered = filter_by_budget(candidates, state["budget_per_day"])
    top_hotels = rerank_candidates(budget_filtered or candidates, state, top_k=5)
    ensure_images(top_hotels, state["destination"])

    return {
        "destination": state["destination"],
        "hotel_type": state["hotel_type"],
        "results": [h.to_dict() for h in top_hotels],
    }
