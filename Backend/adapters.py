"""Map frontend trip request/response shapes to the planner agent."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from planner_agent import PlannerState, create_initial_state

TravelStyle = Literal[
    "calm",
    "adventure",
    "adventure-nature",
    "historical-cultural",
    "spiritual",
    "party",
    "party-nightlife",
    "culinary-foodie",
    "foodie",
]
PartyType = Literal["solo", "couple", "friends", "family", "adventure-group"]


class TripPlanRequest(BaseModel):
    destination: str = Field(min_length=1)
    trip_start_date: str
    days: int = Field(ge=1, le=30)
    travel_style: TravelStyle
    number_of_people: int = Field(ge=1, le=30)
    party_type: PartyType


def normalize_party_type(party_type: str) -> str:
    return party_type.replace("-", " ")


def trip_request_to_state(req: TripPlanRequest) -> PlannerState:
    return create_initial_state(
        destination=req.destination.strip(),
        days=req.days,
        travel_style=req.travel_style,
        number_of_people=req.number_of_people,
        party_type=normalize_party_type(req.party_type),
        start_date=req.trip_start_date,
    )


def _map_activity(act: dict[str, Any]) -> dict[str, str]:
    description = act.get("description") or act.get("desc") or ""
    tips = act.get("tips") or act.get("tip") or ""
    fun_fact = act.get("fun_fact") or act.get("funFact") or ""
    image = act.get("image") or ""

    result = {
        "place": act.get("place") or act.get("name") or "Activity",
        "time": act.get("time") or "TBD",
        "duration": act.get("duration") or "1h",
        "category": act.get("category") or act.get("city") or "Explore",
        "description": description,
        "tips": tips,
        "fun_fact": fun_fact,
    }
    if image:
        result["image"] = image
    return result


def _split_flat_activities(
    activities: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    if not activities:
        return [], [], []

    mapped = [_map_activity(a) for a in activities]
    count = len(mapped)
    if count == 1:
        return mapped, [], []
    if count == 2:
        return [mapped[0]], [mapped[1]], []

    third = max(1, count // 3)
    return mapped[:third], mapped[third : 2 * third], mapped[2 * third :]


def _transform_day(day: dict[str, Any]) -> dict[str, Any]:
    if day.get("morning") or day.get("afternoon") or day.get("evening") or day.get("night"):
        morning = [_map_activity(a) for a in day.get("morning", [])]
        afternoon = [_map_activity(a) for a in day.get("afternoon", [])]
        evening = [_map_activity(a) for a in day.get("evening", [])]
        evening.extend(_map_activity(a) for a in day.get("night", []))
    else:
        flat = (
            day.get("activities")
            or day.get("itinerary")
            or day.get("places_to_visit")
            or day.get("places")
            or day.get("events")
        )
        if not flat:
            skip_keys = {"date", "day", "theme", "weather", "weather_summary",
                         "notes", "daily_notes", "city", "morning", "afternoon",
                         "evening", "night"}
            for k, v in day.items():
                if k not in skip_keys and isinstance(v, list) and v and isinstance(v[0], dict):
                    flat = v
                    break
        if flat:
            morning, afternoon, evening = _split_flat_activities(flat)
        else:
            morning, afternoon, evening = [], [], []

    theme = day.get("theme")
    if not theme:
        day_num = day.get("day")
        theme = f"Day {day_num}" if day_num else "Explore"

    return {
        "date": day.get("date", ""),
        "theme": theme,
        "weather": day.get("weather") or day.get("weather_summary") or "Weather TBD",
        "morning": morning,
        "afternoon": afternoon,
        "evening": evening,
        "notes": day.get("notes") or day.get("daily_notes") or "",
    }


def to_frontend_itinerary(req: TripPlanRequest, final_state: PlannerState) -> dict[str, Any]:
    raw = final_state.get("itinerary") or {}
    if "raw" in raw:
        raise ValueError("Planner returned an unparseable itinerary")

    days_raw = raw.get("days") or []
    dest = raw.get("destination") or req.destination
    summary = (
        f"A {req.days}-day {req.travel_style.replace('-', ' ')} escape through {dest} "
        f"for {req.number_of_people} ({req.party_type})."
    )

    data_warning = raw.get("data_warning")
    if data_warning:
        summary += f" {data_warning}"

    general_tips = raw.get("general_tips") or []
    if isinstance(general_tips, str):
        general_tips = [general_tips] if general_tips.strip() else []
    days = [_transform_day(d) for d in days_raw]

    if general_tips and days:
        tips_text = " ".join(f"• {t}" for t in general_tips)
        last_notes = days[-1].get("notes", "")
        days[-1]["notes"] = f"{last_notes}\n\nTips: {tips_text}".strip()

    res = {
        "request": req.model_dump(),
        "summary": summary,
        "days": days,
    }

    # Pass through rich dataset fields if available
    for field in ("overview", "fun_facts", "must_try_food", "hidden_gems", "local_culture", "travel_hacks", "budget_info", "places_covered"):
        if field in raw and raw[field]:
            res[field] = raw[field]

    return res
