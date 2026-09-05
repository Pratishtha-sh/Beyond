"""Map frontend trip request/response shapes to the planner agent."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.planner_agent import PlannerState, create_initial_state

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


def _map_activity(act: dict[str, Any]) -> dict[str, str] | None:
    if not isinstance(act, dict):
        return None

    place = (act.get("place") or act.get("name") or "").strip()
    if not place or place in ("-", "—", "Activity", "None", "null", "N/A", "TBD", "·", "•"):
        return None

    description = act.get("description") or act.get("desc") or ""
    tips = act.get("tips") or act.get("tip") or ""
    fun_fact = act.get("fun_fact") or act.get("funFact") or ""
    image = act.get("image") or ""

    result = {
        "place": place,
        "time": act.get("time") or "TBD",
        "duration": act.get("duration") or "1.5h",
        "category": act.get("category") or act.get("city") or "Explore",
        "description": description,
        "tips": tips,
    }
    if fun_fact:
        result["fun_fact"] = fun_fact
    if image:
        result["image"] = image
    return result


def _split_flat_activities(
    activities: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    if not activities:
        return [], [], []

    mapped = [_map_activity(a) for a in activities]
    valid = [a for a in mapped if a is not None]
    count = len(valid)
    if count == 0:
        return [], [], []
    if count == 1:
        return valid, [], []
    if count == 2:
        return [valid[0]], [valid[1]], []

    third = max(1, count // 3)
    return valid[:third], valid[third : 2 * third], valid[2 * third :]


def _transform_day(day: dict[str, Any]) -> dict[str, Any]:
    if day.get("morning") or day.get("afternoon") or day.get("evening") or day.get("night"):
        morning_raw = [_map_activity(a) for a in day.get("morning", [])]
        afternoon_raw = [_map_activity(a) for a in day.get("afternoon", [])]
        evening_raw = [_map_activity(a) for a in day.get("evening", [])]
        evening_raw.extend([_map_activity(a) for a in day.get("night", [])])

        morning = [a for a in morning_raw if a is not None]
        afternoon = [a for a in afternoon_raw if a is not None]
        evening = [a for a in evening_raw if a is not None]
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
                         "evening", "night", "hotel_options", "selected_hotel"}
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

    res_day: dict[str, Any] = {
        "date": day.get("date", ""),
        "theme": theme,
        "weather": day.get("weather") or day.get("weather_summary") or "Sunny & pleasant",
        "morning": morning,
        "afternoon": afternoon,
        "evening": evening,
        "notes": day.get("notes") or day.get("daily_notes") or "",
    }

    if day.get("hotel_options"):
        res_day["hotel_options"] = day["hotel_options"]
    if day.get("selected_hotel"):
        res_day["selected_hotel"] = day["selected_hotel"]

    return res_day


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

    source = final_state.get("source") or raw.get("source") or (
        "planner_agent" if ("budget_analysis" in final_state or "selected_transport" in final_state or "hotel_options" in final_state) else "general_planner"
    )

    res: dict[str, Any] = {
        "source": source,
        "planner_type": source,
        "request": req.model_dump(),
        "summary": summary,
        "days": days,
    }

    # Pass through rich dataset fields for general planner
    for field in ("overview", "fun_facts", "must_try_food", "hidden_gems", "local_culture", "travel_hacks", "budget_info", "places_covered"):
        if field in raw and raw[field]:
            res[field] = raw[field]

    # Pass through flight, transport, hotels, and budget breakdown ONLY for planner agent
    if source == "planner_agent":
        best_flight = raw.get("best_flight") or final_state.get("selected_transport") or raw.get("transport")
        if best_flight:
            res["best_flight"] = best_flight
            res["transport"] = best_flight

        hotel_options = raw.get("hotel_options") or final_state.get("hotel_options")
        if hotel_options:
            res["hotel_options"] = hotel_options
            for d in res["days"]:
                if not d.get("hotel_options"):
                    d["hotel_options"] = hotel_options
                    d["selected_hotel"] = hotel_options[0]

        budget_breakdown = raw.get("budget_breakdown") or (
            final_state.get("budget_analysis", {}).get("breakdown") if isinstance(final_state.get("budget_analysis"), dict) else None
        )
        if budget_breakdown:
            res["budget_breakdown"] = budget_breakdown

    return res
