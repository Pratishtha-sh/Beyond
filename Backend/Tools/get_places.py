"""
get_places.py — Beyond Project
================================
Agent tool that accepts a raw Overpass QL query string and returns a
structured JSON list of tourist-relevant places with:
  - name, category, coordinates
  - opening / closing hours
  - entry fee (if tagged)
  - fun activities / description
  - website, wikipedia, and address info

Usage (by your agent):
    from get_places import get_places

    query = '''
    [out:json][timeout:90];
    area["name"="New Delhi"] -> .searchArea;
    (
      nwr["tourism"~"attraction|monument|theme_park|museum"](area.searchArea);
      nwr["historic"~"monument|memorial|castle|ruins"](area.searchArea);
      nwr["leisure"~"amusement_park|water_park|park|garden"](area.searchArea);
    );
    out center tags;
    '''
    result = get_places(query)
    print(result)  # returns JSON string
"""

import requests
import json
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Maps raw OSM tag values → human-readable category labels
CATEGORY_MAP = {
    # tourism
    "attraction": "Tourist Attraction",
    "monument": "Monument",
    "museum": "Museum",
    "theme_park": "Theme Park",
    "viewpoint": "Viewpoint",
    "zoo": "Zoo",
    "aquarium": "Aquarium",
    "gallery": "Art Gallery",
    "artwork": "Artwork / Installation",
    "information": "Visitor Information",
    # historic
    "castle": "Castle / Fort",
    "ruins": "Ruins",
    "memorial": "Memorial",
    "archaeological_site": "Archaeological Site",
    "aqueduct": "Historic Aqueduct",
    "building": "Historic Building",
    # leisure
    "amusement_park": "Amusement Park",
    "water_park": "Water Park",
    "park": "Park / Garden",
    "garden": "Garden",
    "nature_reserve": "Nature Reserve",
    "stadium": "Stadium",
    "sports_centre": "Sports Centre",
    # amenity
    "planetarium": "Planetarium",
    "theatre": "Theatre",
    "cinema": "Cinema",
    "arts_centre": "Arts Centre",
    "nightclub": "Nightclub / Entertainment",
}

# Tag priority order when determining the primary category of a POI
CATEGORY_TAG_PRIORITY = ["tourism", "historic", "leisure", "amenity", "sport"]

# Tags that represent "fun activities" on the element itself
ACTIVITY_TAGS = ["sport", "leisure", "activity", "attraction"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_category(tags: dict) -> str:
    """Return a human-readable category string from OSM tags."""
    for key in CATEGORY_TAG_PRIORITY:
        val = tags.get(key)
        if val:
            return CATEGORY_MAP.get(val, val.replace("_", " ").title())
    return "Point of Interest"


def _resolve_coordinates(element: dict) -> tuple[Optional[float], Optional[float]]:
    """Return (lat, lon) for nodes, ways, and relations uniformly."""
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lon = element.get("lon") or element.get("center", {}).get("lon")
    return lat, lon


def _parse_opening_hours(raw: Optional[str]) -> dict:
    """
    Convert a raw OSM opening_hours string into a structured dict.

    Example input:  "Mo-Fr 09:00-18:00; Sa-Su 10:00-17:00"
    Example output: {
        "raw": "Mo-Fr 09:00-18:00; Sa-Su 10:00-17:00",
        "open":  "09:00",
        "close": "18:00",
        "note":  "Mo-Fr 09:00-18:00; Sa-Su 10:00-17:00"
    }
    """
    if not raw or raw.strip().lower() in ("", "not specified"):
        return {
            "raw": None,
            "open": None,
            "close": None,
            "note": "Timings not available — contact the venue directly.",
        }

    result = {"raw": raw, "note": raw}

    # Try to extract first HH:MM-HH:MM pattern as a simple open/close
    time_match = re.search(r"(\d{2}:\d{2})\s*[-–]\s*(\d{2}:\d{2})", raw)
    if time_match:
        result["open"] = time_match.group(1)
        result["close"] = time_match.group(2)
    else:
        result["open"] = None
        result["close"] = None

    return result


def _parse_fee(tags: dict) -> dict:
    """
    Extract entry fee details from OSM tags.
    Relevant tags: fee, charge, fee:amount, charge:amount
    """
    fee_flag = tags.get("fee", "").strip().lower()
    charge = tags.get("charge") or tags.get("fee:amount") or tags.get("charge:amount")

    if fee_flag == "no":
        return {"required": False, "amount": "Free Entry", "raw": None}
    elif fee_flag == "yes" or charge:
        return {
            "required": True,
            "amount": charge if charge else "Entry fee applicable — check with venue",
            "raw": charge,
        }
    else:
        return {
            "required": None,
            "amount": "Fee information not available",
            "raw": None,
        }


def _extract_activities(tags: dict) -> list[str]:
    """Build a list of activities/features from OSM tags."""
    activities = []

    # sport tag can be semicolon-separated: "swimming;tennis"
    sport = tags.get("sport", "")
    if sport:
        activities += [s.strip().replace("_", " ").title() for s in sport.split(";")]

    # leisure sub-tags
    leisure = tags.get("leisure", "")
    if leisure and leisure not in ("park", "garden"):  # too generic
        activities.append(leisure.replace("_", " ").title())

    # explicit activity tag
    activity = tags.get("activity", "")
    if activity:
        activities += [a.strip().replace("_", " ").title() for a in activity.split(";")]

    # description gives context
    desc = tags.get("description") or tags.get("description:en", "")
    if desc:
        activities.append(f"Info: {desc[:200]}")

    return list(dict.fromkeys(activities))  # deduplicate while preserving order


def _build_address(tags: dict) -> str:
    """Construct a readable address from addr:* tags."""
    parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:suburb", ""),
        tags.get("addr:city", ""),
        tags.get("addr:postcode", ""),
        tags.get("addr:state", ""),
    ]
    address = ", ".join(p for p in parts if p)
    return address if address else tags.get("address", "Address not available")


# ---------------------------------------------------------------------------
# Core tool
# ---------------------------------------------------------------------------

def get_places(overpass_ql_query: str) -> str:
    """
    Execute an Overpass QL query and return a JSON string of enriched POIs.

    Parameters
    ----------
    overpass_ql_query : str
        A valid Overpass QL query. The query MUST end with:
            out center tags;
        so that polygon/way elements return a center point + all tags.

    Returns
    -------
    str
        A JSON string with the schema:
        {
          "total": <int>,
          "places": [ { ...place fields... }, ... ]
        }
    """

    # ── Enforce correct output directive ──────────────────────────────────
    # Replace bare "out center;" with "out center tags;" if the agent forgot
    query = re.sub(r"\bout\s+center\s*;", "out center tags;", overpass_ql_query)
    # If there's no out directive at all, append one
    if "out center" not in query:
        query = query.rstrip().rstrip(";") + "\nout center tags;"

    # ── Call Overpass API ─────────────────────────────────────────────────
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=120,
            headers={"User-Agent": "BeyondApp/1.0 (tourist-places-tool)"},
        )
        response.raise_for_status()
        raw_data = response.json()
    except requests.exceptions.Timeout:
        return json.dumps({"error": "Overpass API timed out. Try narrowing your query area or reducing tag filters."})
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"Network error: {str(e)}"})
    except json.JSONDecodeError:
        return json.dumps({"error": "Overpass returned non-JSON response. Check your QL syntax."})

    elements = raw_data.get("elements", [])

    # ── Parse elements ────────────────────────────────────────────────────
    places = []
    seen_names = set()  # deduplicate by name+coords pair

    for element in elements:
        tags = element.get("tags", {})

        # Skip elements with no name — unhelpful to tourists
        name = (
            tags.get("name:en")
            or tags.get("name")
            or tags.get("official_name")
            or tags.get("alt_name")
        )
        if not name or name.strip() == "":
            continue

        lat, lon = _resolve_coordinates(element)
        if lat is None or lon is None:
            continue  # can't place it on a map

        # Deduplicate by name (case-insensitive)
        name_key = name.strip().lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        place = {
            "id": element.get("id"),
            "osm_type": element.get("type"),           # node / way / relation
            "name": name.strip(),
            "name_local": tags.get("name"),            # original script name
            "category": _resolve_category(tags),
            "coordinates": {"lat": lat, "lon": lon},
            "address": _build_address(tags),
            "opening_hours": _parse_opening_hours(tags.get("opening_hours")),
            "entry_fee": _parse_fee(tags),
            "activities": _extract_activities(tags),
            "website": tags.get("website") or tags.get("contact:website"),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "wikipedia": tags.get("wikipedia"),
            "wikidata": tags.get("wikidata"),
            "image": tags.get("image"),
            "wheelchair_accessible": tags.get("wheelchair", "unknown"),
            "tags_raw": tags,                          # full OSM tags for agent post-processing
        }

        places.append(place)

    # ── Sort: named places with hours first ───────────────────────────────
    places.sort(
        key=lambda p: (
            p["opening_hours"]["open"] is None,       # has hours → first
            p["entry_fee"]["required"] is None,       # has fee info → first
            p["name"],
        )
    )

    output = {
        "total": len(places),
        "places": places,
    }

    return json.dumps(output, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI / quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_query = """
    [out:json][timeout:90];
    area["name"="Rajasthan"] -> .searchArea;
    (
      nwr["tourism"~"attraction|monument|theme_park|museum|zoo"](area.searchArea);
      nwr["historic"~"monument|memorial|castle|ruins|archaeological_site"](area.searchArea);
      nwr["leisure"~"amusement_park|water_park|park|garden|sports_centre"](area.searchArea);
      nwr["amenity"~"planetarium|theatre|arts_centre"](area.searchArea);
    );
    out center tags;
    """

    print("Fetching places from Overpass API...")
    result_json = get_places(sample_query)
    result = json.loads(result_json)

    print(f"\nTotal places found: {result['total']}\n")
    for place in result["places"][:25]:   # preview first 5
        print(f"   {place['name']} ({place['category']})")
        hours = place["opening_hours"]
        if hours["open"]:
            print(f"      {hours['open']} – {hours['close']}")
        else:
            print(f"      {hours['note']}")
        fee = place["entry_fee"]
        print(f"      {fee['amount']}")
        if place["activities"]:
            print(f"      {', '.join(place['activities'][:3])}")
        print()