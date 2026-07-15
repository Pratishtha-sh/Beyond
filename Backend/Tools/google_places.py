"""Google Places API helper for Beyond.

This module uses the Google Places API (New) to search for tourist-focused
locations and normalize the response into the same place-schema used by the
planner. It reads the API key from the .env variable `Google_places_api`.
"""

from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.getenv("Google_places_api")
GOOGLE_PLACES_BASE = "https://places.googleapis.com/v1"


def _google_text_search(query: str, max_results: int = 15) -> list[dict]:
    """Call the new Places API (v2) Text Search endpoint: places:searchText"""
    if not GOOGLE_PLACES_API_KEY:
        raise EnvironmentError("Google_places_api key is missing from environment.")

    url = f"{GOOGLE_PLACES_BASE}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.regularOpeningHours",
    }
    body = {
        "textQuery": query,
        "maxResultCount": min(max_results, 20),
        "languageCode": "en",
    }

    response = requests.post(url, json=body, headers=headers, timeout=20)
    
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        try:
            error_detail = response.json()
            message = error_detail.get("error", {}).get("message", response.text)
        except Exception:
            message = response.text
        raise RuntimeError(f"Google Places API error ({response.status_code}): {message}")
    
    payload = response.json()
    
    if "error" in payload:
        error_info = payload.get("error", {})
        message = error_info.get("message", "Unknown error")
        raise RuntimeError(f"Google Places API error: {message}")
    
    return payload.get("places", [])


def search_google_places(
    query: str,
    max_results: int = 15,
) -> list[dict]:
    """Search Google Places and return normalized place objects with only necessary details:
    - name: string
    - address: string
    - rating: float or None
    - timings: string (concatenated daily opening hours)
    """
    try:
        results = _google_text_search(query, max_results=max_results)
    except Exception as e:
        print(f"   ⚠️  Google Places text search failed: {e}")
        return []
    
    places: list[dict] = []
    for raw_place in results:
        try:
            name = raw_place.get("displayName", {}).get("text") or raw_place.get("name", "Unknown")
            address = raw_place.get("formattedAddress") or "Address not available"
            rating = raw_place.get("rating")

            # Extract opening hours / timings
            opening_hours = raw_place.get("regularOpeningHours", {})
            timings = "Timings not available"
            if opening_hours:
                weekday_text = opening_hours.get("weekdayDescriptions")
                if weekday_text and isinstance(weekday_text, list):
                    timings = " | ".join(weekday_text)
                else:
                    periods = opening_hours.get("periods")
                    if periods:
                        timings = "Opening hours available — check Google Maps"

            place = {
                "name": name,
                "address": address,
                "rating": rating,
                "timings": timings,
            }
            places.append(place)
        except Exception:
            continue
            
    return places


if __name__ == "__main__":
    import sys
    if not GOOGLE_PLACES_API_KEY:
        print("❌ Error: Google_places_api key not found in .env")
        sys.exit(1)

    print("🧪 Testing Google Places API...")
    print("\n📋 Setup Status:")
    print(f"   ✓ API Key: {'Found' if GOOGLE_PLACES_API_KEY else 'Missing'}")
    print(f"   Endpoint: {GOOGLE_PLACES_BASE}")
    
    try:
        places = search_google_places(
            query="Paris, France romantic luxury attractions",
            max_results=5,
        )
        if places:
            print(f"✅ Found {len(places)} places:")
            for place in places:
                print(f"\n   📍 {place['name']}")
                print(f"      Address: {place['address']}")
                print(f"      Rating: {place['rating']}")
                print(f"      Timings: {place['timings']}")
        else:
            print("⚠️  No places found.")
    except Exception as e:
        print(f"ℹ️  Note: {e}")
        import traceback
        traceback.print_exc()
