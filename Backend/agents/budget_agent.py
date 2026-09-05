"""Autonomous Budget Agent for dynamic allocations, feasibility checks, and live tool optimization."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Local paths & Tool imports
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

env_path = BACKEND_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("budget_agent")

# Safe imports from Tools
try:
    from Tools.hotel_search import hotel_search
except ImportError:
    logger.warning("Could not import hotel_search tool directly. Fallback available.")
    hotel_search = None

try:
    from Tools.transport_search import transport_search
except ImportError:
    logger.warning("Could not import transport_search tool directly. Fallback available.")
    transport_search = None

try:
    from Tools.google_places import search_google_places
except ImportError:
    logger.warning("Could not import search_google_places tool directly. Fallback available.")
    search_google_places = None

# Groq LLM setup
GROQ_API_KEY = os.getenv("Groq_api_key") or os.getenv("GROQ_API_KEY")
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        logger.warning(f"Groq client initialization failed: {e}")

LLM_MODEL = "openai/gpt-oss-120b"

# Data Models & Schemas

@dataclass
class BudgetAllocation:
    transport: float
    accommodation: float
    activities_sightseeing: float
    food_dining: float
    local_misc_buffer: float
    total_budget: float
    currency: str = "INR"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ExpenseItem:
    category: str  # "accommodation", "transport", "activities", "food_misc"
    name: str
    amount: float
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class OptimizationAlternative:
    category: str
    original_item: str
    original_cost: float
    suggested_alternative: str
    new_cost: float
    savings: float
    details: Dict[str, Any] = field(default_factory=dict)
    booking_link: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class BudgetResponse:
    action: str  # "reconfigured", "optimized", "infeasible_alert"
    is_feasible: bool
    total_budget: float
    budget_per_day: float
    days: int
    num_people: int
    currency: str
    allocation: BudgetAllocation
    current_or_expected_cost: Optional[float] = None
    cost_variance: Optional[float] = None  # negative if over budget
    user_alert_message: str = ""
    optimization_recommendations: List[str] = field(default_factory=list)
    alternatives_found: List[OptimizationAlternative] = field(default_factory=list)
    breakdown_summary: Dict[str, Any] = field(default_factory=dict)
    api_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        return res

# Emergency Offline Fallback Estimates (Used ONLY when live APIs are unreachable)
FALLBACK_COST_ESTIMATES = {
    "transport": {
        "flight": {"min_per_person_roundtrip": 4500.0, "avg_roundtrip": 8500.0},
        "train": {"min_per_person_roundtrip": 700.0, "avg_roundtrip": 1800.0},
        "bus": {"min_per_person_roundtrip": 500.0, "avg_roundtrip": 1200.0},
        "self-drive": {"min_total_per_day": 1000.0, "avg_per_day": 2000.0},
    },
    "hotel": {
        "budget / hostel": {"min_per_night": 700.0, "avg_per_night": 1400.0},
        "budget": {"min_per_night": 700.0, "avg_per_night": 1400.0},
        "mid-range": {"min_per_night": 2200.0, "avg_per_night": 4000.0},
        "boutique": {"min_per_night": 4500.0, "avg_per_night": 8000.0},
        "luxury / resort": {"min_per_night": 9000.0, "avg_per_night": 18000.0},
        "luxury": {"min_per_night": 9000.0, "avg_per_night": 18000.0},
    },
    "food_per_person_day": {
        "budget": 500.0,
        "standard": 1000.0,
        "luxury": 2500.0,
    },
    "local_commute_day": {
        "budget": 300.0,
        "standard": 600.0,
        "luxury": 1500.0,
    },
}

# Helper Utilities

def _clean_budget_tier(budget_val: Any) -> float:
    """Parse numeric budget or standard UI tier strings into a per-day numeric value."""
    if isinstance(budget_val, (int, float)) and budget_val > 0:
        return float(budget_val)
    
    if not budget_val:
        return 5000.0

    s = str(budget_val).strip().lower()
    if "<" in s or "5k" in s and ("<" in s or "below" in s):
        return 4000.0
    elif "5k" in s and "15k" in s:
        return 10000.0
    elif "15k" in s and "30k" in s:
        return 22500.0
    elif "30k" in s:
        return 35000.0
    
    nums = re.findall(r"\d+", s.replace(",", ""))
    if nums:
        return float(nums[0])
    
    return 5000.0

def _normalize_transport_type(ttype: str) -> str:
    t = (ttype or "").strip().lower()
    if "flight" in t or "air" in t:
        return "flight"
    elif "train" in t or "rail" in t:
        return "train"
    elif "bus" in t:
        return "bus"
    elif "drive" in t or "car" in t:
        return "self-drive"
    return "flight"

def _normalize_hotel_type(htype: str) -> str:
    h = (htype or "").strip().lower()
    if "hostel" in h or "budget" in h:
        return "budget / hostel"
    elif "boutique" in h:
        return "boutique"
    elif "luxury" in h or "resort" in h or "5 star" in h or "5-star" in h:
        return "luxury / resort"
    return "mid-range"

def _call_llm(system: str, user: str, temperature: float = 0.2) -> Optional[str]:
    """Safe call to Groq LLM with fallback."""
    if not groq_client:
        return None
    try:
        response = groq_client.chat.completions.create(
            model=LLM_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"LLM call error: {e}")
        return None

# Budget Agent Implementation

class BudgetAgent:
    """
    Autonomous Budget Agent for Beyond Travel Platform.
    Eliminates rigid percentage tables and hardcoded assumptions by combining
    LLM contextual allocation with live travel API pricing.
    """

    def __init__(self):
        self.logger = logger

    # USE CASE 1: Dynamic Allocation & Feasibility
    def reconfigure_budget(
        self,
        days: int,
        budget_per_day: Any,
        transport_type: str = "Flight",
        hotel_type: str = "Mid-range",
        num_people: int = 2,
        destination: str = "Destination",
        origin: str = "Origin",
        origin_code: Optional[str] = None,
        destination_code: Optional[str] = None,
        travel_date: Optional[str] = None,
        party_type: str = "friends",
        travel_style: str = "balanced",
        query: str = "",
    ) -> BudgetResponse:
        """
        Dynamically distributes the total trip budget using LLM reasoning based on
        user preferences, travel style, and transit mode. Validates feasibility against
        live flight and hotel APIs.
        """
        days = max(1, int(days))
        num_people = max(1, int(num_people))
        per_day = _clean_budget_tier(budget_per_day)
        total_budget = round(per_day * days, 2)

        norm_trans = _normalize_transport_type(transport_type)
        norm_hotel = _normalize_hotel_type(hotel_type)

        # Style & luxury determination: based on user choices, not arbitrary ₹30k cutoff
        is_luxury = (
            norm_hotel == "luxury / resort"
            or "luxury" in travel_style.lower()
            or "luxury" in (query or "").lower()
        )

        # 1. LLM-Driven Dynamic Budget Allocation
        allocation, rationale = self._llm_allocate_budget(
            days=days,
            total_budget=total_budget,
            budget_per_day=per_day,
            transport_type=transport_type,
            hotel_type=hotel_type,
            destination=destination,
            origin=origin,
            num_people=num_people,
            party_type=party_type,
            travel_style=travel_style,
            query=query,
        )

        # 2. Feasibility Check with Live APIs
        is_feasible, alert_msg, recommendations, api_errors = self._check_feasibility(
            destination=destination,
            days=days,
            num_people=num_people,
            per_day=per_day,
            total_budget=total_budget,
            transport_type=norm_trans,
            hotel_type=norm_hotel,
            allocation=allocation,
            origin=origin,
            origin_code=origin_code,
            destination_code=destination_code,
            travel_date=travel_date,
        )

        # 3. LLM Polish for user-facing feedback (if infeasible)
        if not is_feasible and groq_client:
            llm_system = (
                "You are an empathetic, intelligent travel budget expert for the Beyond app. "
                "The user's planned trip budget is INSUFFICIENT for their selected options. "
                "Explain the exact financial reality clearly, concisely, and offer specific alternatives."
            )
            llm_user = (
                f"Trip Details: {days}-day trip to {destination} from {origin} for {num_people} people ({party_type}).\n"
                f"Selected: Transport={transport_type}, Hotel={hotel_type}.\n"
                f"User Budget: ₹{per_day:,.0f}/day (Total ₹{total_budget:,.0f}).\n"
                f"Identified Issue: {alert_msg}\n"
                f"Actionable Alternatives: {recommendations}\n"
                "Please generate a polite, clear 2-sentence alert summarizing the exact shortfall and recommendations."
            )
            llm_alert = _call_llm(llm_system, llm_user)
            if llm_alert:
                alert_msg = llm_alert

        return BudgetResponse(
            action="infeasible_alert" if not is_feasible else "reconfigured",
            is_feasible=is_feasible,
            total_budget=total_budget,
            budget_per_day=per_day,
            days=days,
            num_people=num_people,
            currency="INR",
            allocation=allocation,
            user_alert_message=alert_msg,
            optimization_recommendations=recommendations,
            api_errors=api_errors,
            breakdown_summary={
                "is_luxury_trip": is_luxury,
                "allocation_rationale": rationale,
                "transport_allocated": allocation.transport,
                "hotel_allocated": allocation.accommodation,
                "hotel_per_night_budget": round(allocation.accommodation / days, 2),
                "daily_food_allowance_per_person": round(allocation.food_dining / (days * num_people), 2),
                "activities_budget": allocation.activities_sightseeing,
                "contingency_buffer": allocation.local_misc_buffer,
            },
        )

    # LLM Dynamic Allocation Strategy
    def _llm_allocate_budget(
        self,
        days: int,
        total_budget: float,
        budget_per_day: float,
        transport_type: str,
        hotel_type: str,
        destination: str,
        origin: str,
        num_people: int,
        party_type: str,
        travel_style: str,
        query: str,
    ) -> Tuple[BudgetAllocation, str]:
        """
        Uses LLM to decide percentage split across categories based on query context.
        Falls back to contextual dynamic defaults if LLM is offline.
        """
        if groq_client:
            system_prompt = (
                "You are a travel budget specialist. Allocate the traveler's total budget across 5 categories:\n"
                "1. transport (intercity transit: flights, trains, cabs)\n"
                "2. accommodation (hotels, resorts, stays)\n"
                "3. activities_sightseeing (tickets, tours, guides)\n"
                "4. food_dining (meals, cafes, street food)\n"
                "5. local_misc_buffer (local taxis, autos, metro, emergency buffer)\n\n"
                "CRITICAL RULES:\n"
                "- Output percentages that sum to exactly 1.0 (100%).\n"
                "- Tailor dynamically to the user's intent. Examples:\n"
                "  * If user requests luxury stay/resort with moderate budget: give accommodation 50-60%, reducing transport & dining.\n"
                "  * If transport is train/bus: reduce transport to 10-18%, giving more to hotel & activities.\n"
                "  * If user wants budget/hostel: lower accommodation to 20-25%, boosting food & experiences.\n"
                "  * If trip is food/nightlife focused: boost food_dining.\n"
                "- Return STRICTLY a JSON object with this structure:\n"
                "{\n"
                '  "transport_pct": 0.25,\n'
                '  "accommodation_pct": 0.40,\n'
                '  "activities_pct": 0.15,\n'
                '  "food_pct": 0.12,\n'
                '  "misc_pct": 0.08,\n'
                '  "rationale": "1 sentence explaining why this allocation suits their request."\n'
                "}"
            )

            user_prompt = (
                f"Trip Request:\n"
                f"- Destination: {destination} (Origin: {origin})\n"
                f"- Duration: {days} days | Travelers: {num_people} ({party_type})\n"
                f"- Preferred Transport: {transport_type}\n"
                f"- Accommodation Style: {hotel_type}\n"
                f"- Travel Style: {travel_style}\n"
                f"- Daily Budget: ₹{budget_per_day:,.0f} (Total: ₹{total_budget:,.0f})\n"
                f"- User Notes / Query: {query or 'Standard balanced itinerary'}\n"
            )

            raw_resp = _call_llm(system_prompt, user_prompt, temperature=0.1)
            if raw_resp:
                try:
                    clean = re.sub(r"^```json\s*", "", raw_resp, flags=re.MULTILINE)
                    clean = re.sub(r"^```\s*$", "", clean, flags=re.MULTILINE).strip()
                    data = json.loads(clean)

                    t_pct = float(data.get("transport_pct", 0.25))
                    h_pct = float(data.get("accommodation_pct", 0.38))
                    a_pct = float(data.get("activities_pct", 0.15))
                    f_pct = float(data.get("food_pct", 0.14))
                    m_pct = float(data.get("misc_pct", 0.08))

                    # Normalize sum to 1.0
                    tot = t_pct + h_pct + a_pct + f_pct + m_pct
                    if tot > 0:
                        t_pct, h_pct, a_pct, f_pct, m_pct = (
                            t_pct / tot,
                            h_pct / tot,
                            a_pct / tot,
                            f_pct / tot,
                            m_pct / tot,
                        )

                    alloc = BudgetAllocation(
                        transport=round(total_budget * t_pct, 2),
                        accommodation=round(total_budget * h_pct, 2),
                        activities_sightseeing=round(total_budget * a_pct, 2),
                        food_dining=round(total_budget * f_pct, 2),
                        local_misc_buffer=round(total_budget * m_pct, 2),
                        total_budget=total_budget,
                        currency="INR",
                    )
                    rationale = data.get(
                        "rationale",
                        f"Custom AI allocation prioritizing {hotel_type} stay and {transport_type} travel.",
                    )
                    return alloc, rationale
                except Exception as e:
                    self.logger.warning(f"Could not parse LLM budget allocation: {e}")

        # Intelligent dynamic fallback when LLM is unavailable
        norm_t = _normalize_transport_type(transport_type)
        norm_h = _normalize_hotel_type(hotel_type)

        if norm_h in ("luxury / resort", "boutique") or "luxury" in travel_style.lower():
            t_pct = 0.22 if norm_t == "flight" else 0.12
            h_pct = 0.50
            a_pct = 0.13
            f_pct = 0.10
            m_pct = 0.05
        elif norm_h == "budget / hostel":
            t_pct = 0.32 if norm_t == "flight" else 0.16
            h_pct = 0.24
            a_pct = 0.22
            f_pct = 0.20
            m_pct = 0.08
        else:
            t_pct = 0.28 if norm_t == "flight" else 0.18
            h_pct = 0.38
            a_pct = 0.16
            f_pct = 0.16
            m_pct = 0.06

        alloc = BudgetAllocation(
            transport=round(total_budget * t_pct, 2),
            accommodation=round(total_budget * h_pct, 2),
            activities_sightseeing=round(total_budget * a_pct, 2),
            food_dining=round(total_budget * f_pct, 2),
            local_misc_buffer=round(total_budget * m_pct, 2),
            total_budget=total_budget,
            currency="INR",
        )
        return alloc, f"Balanced dynamic allocation tailored for {transport_type} and {hotel_type} style."

    # USE CASE 2: Optimize Budget & Call Tools for Alternatives
    def optimize_budget(
        self,
        destination: str,
        days: int,
        allotted_budget: float,
        current_expenses: Dict[str, Any],
        num_people: int = 2,
        hotel_type: str = "Mid-range",
        transport_type: str = "Flight",
        origin: str = "Mumbai",
        origin_code: Optional[str] = None,
        destination_code: Optional[str] = None,
        travel_date: Optional[str] = None,
        travel_style: str = "balanced",
        party_type: str = "friends",
        user_query: str = "Optimize my expenses",
    ) -> BudgetResponse:
        """
        Analyzes expense divisions, identifies overspends, and calls live tools
        to fetch cheaper alternatives. No artificial 85% clamp; savings are strictly
        based on live alternative prices.
        """
        days = max(1, int(days))
        num_people = max(1, int(num_people))
        allotted_budget = float(allotted_budget)

        # Parse current expenses
        hotel_data = current_expenses.get("hotel", {})
        transport_data = current_expenses.get("transport", {})
        activities_data = current_expenses.get("activities", [])
        food_misc_cost = float(current_expenses.get("food_misc", 0.0))

        current_hotel_cost = float(
            hotel_data.get("total_cost")
            or (float(hotel_data.get("price_per_night", 0)) * days)
            or 0.0
        )
        current_transport_cost = float(
            transport_data.get("total_cost")
            or (float(transport_data.get("price", 0)) * num_people * 2)
            or 0.0
        )
        current_activities_cost = sum(
            float(item.get("ticket_price", item.get("price", 0))) * num_people
            for item in activities_data
            if isinstance(item, dict)
        )

        total_current_cost = (
            current_hotel_cost
            + current_transport_cost
            + current_activities_cost
            + food_misc_cost
        )

        cost_variance = round(allotted_budget - total_current_cost, 2)
        target_reduction = max(0.0, -cost_variance)

        self.logger.info(
            f"Budget Optimization for {destination}: "
            f"Allotted=₹{allotted_budget:,.0f}, Current=₹{total_current_cost:,.0f}, Deficit=₹{target_reduction:,.0f}"
        )

        alternatives_found: List[OptimizationAlternative] = []
        recommendations: List[str] = []
        api_errors: List[str] = []

        # Target budgets
        target_hotel_total = allotted_budget * 0.38
        target_hotel_per_night = target_hotel_total / days
        target_transport_total = allotted_budget * 0.28

        # Step A: Optimize Transport
        if (
            current_transport_cost > target_transport_total
            or "transport" in user_query.lower()
            or "flight" in user_query.lower()
            or target_reduction > 0
        ):
            opt_trans, t_errs = self._find_transport_alternatives(
                destination=destination,
                origin=origin,
                origin_code=origin_code,
                destination_code=destination_code,
                travel_date=travel_date or date.today().strftime("%Y-%m-%d"),
                current_mode=transport_data.get("mode", transport_type),
                current_cost=current_transport_cost,
                target_budget=target_transport_total,
                num_people=num_people,
            )
            api_errors.extend(t_errs)
            if opt_trans:
                alternatives_found.append(opt_trans)
                recommendations.append(
                    f"Switch transport from {opt_trans.original_item} (₹{opt_trans.original_cost:,.0f}) "
                    f"to {opt_trans.suggested_alternative} (₹{opt_trans.new_cost:,.0f}), "
                    f"saving ₹{opt_trans.savings:,.0f}."
                )

        # Step B: Optimize Hotel
        if (
            current_hotel_cost > target_hotel_total
            or "hotel" in user_query.lower()
            or "stay" in user_query.lower()
            or target_reduction > 0
        ):
            opt_hotel, h_errs = self._find_hotel_alternatives(
                destination=destination,
                days=days,
                num_people=num_people,
                current_hotel_name=hotel_data.get("name", "Current Hotel"),
                current_cost=current_hotel_cost,
                target_budget_per_night=target_hotel_per_night,
                hotel_type=hotel_type,
                travel_date=travel_date,
            )
            api_errors.extend(h_errs)
            if opt_hotel:
                alternatives_found.append(opt_hotel)
                recommendations.append(
                    f"Switch accommodation to '{opt_hotel.suggested_alternative}' "
                    f"(₹{opt_hotel.new_cost:,.0f} total) instead of '{opt_hotel.original_item}', "
                    f"saving ₹{opt_hotel.savings:,.0f}."
                )

        # Step C: Optimize Activities
        if (
            current_activities_cost > (allotted_budget * 0.15)
            or "activities" in user_query.lower()
            or "places" in user_query.lower()
        ):
            opt_activities = self._find_activity_alternatives(
                destination=destination,
                activities_data=activities_data,
                num_people=num_people,
            )
            if opt_activities:
                alternatives_found.append(opt_activities)
                recommendations.append(
                    f"Replace paid attractions with iconic free scenic landmarks "
                    f"({opt_activities.suggested_alternative}), saving ₹{opt_activities.savings:,.0f}."
                )

        # Real Optimization Total (NO ARTIFICIAL 85% FLOOR)
        total_savings = sum(a.savings for a in alternatives_found)
        new_projected_cost = round(max(0.0, total_current_cost - total_savings), 2)
        is_now_feasible = new_projected_cost <= (allotted_budget * 1.05)

        # Dynamic allocation for new target
        per_day = allotted_budget / days
        reconfig_response = self.reconfigure_budget(
            days=days,
            budget_per_day=per_day,
            transport_type=transport_type,
            hotel_type=hotel_type,
            num_people=num_people,
            destination=destination,
            origin=origin,
            origin_code=origin_code,
            destination_code=destination_code,
            travel_date=travel_date,
            party_type=party_type,
            travel_style=travel_style,
            query=user_query,
        )

        # Build user message
        if is_now_feasible:
            alert_msg = (
                f"✅ Budget optimized! Reduced estimated expenses from ₹{total_current_cost:,.0f} "
                f"to ₹{new_projected_cost:,.0f}, bringing your trip within your ₹{allotted_budget:,.0f} budget "
                f"(Total savings: ₹{total_savings:,.0f})."
            )
        else:
            alert_msg = (
                f"⚠️ Expenses reduced to ₹{new_projected_cost:,.0f} (saving ₹{total_savings:,.0f}), "
                f"which still exceeds your target of ₹{allotted_budget:,.0f}. "
                f"Consider adopting suggested transit and stay switches."
            )

        return BudgetResponse(
            action="optimized",
            is_feasible=is_now_feasible,
            total_budget=allotted_budget,
            budget_per_day=per_day,
            days=days,
            num_people=num_people,
            currency="INR",
            allocation=reconfig_response.allocation,
            current_or_expected_cost=total_current_cost,
            cost_variance=cost_variance,
            user_alert_message=alert_msg,
            optimization_recommendations=recommendations,
            alternatives_found=alternatives_found,
            api_errors=api_errors,
            breakdown_summary={
                "original_cost": total_current_cost,
                "optimized_cost": new_projected_cost,
                "total_savings": total_savings,
                "variance_after_optimization": round(allotted_budget - new_projected_cost, 2),
            },
        )

    # Tool Integration Helpers

    def _find_transport_alternatives(
        self,
        destination: str,
        origin: str,
        origin_code: Optional[str],
        destination_code: Optional[str],
        travel_date: str,
        current_mode: str,
        current_cost: float,
        target_budget: float,
        num_people: int,
    ) -> Tuple[Optional[OptimizationAlternative], List[str]]:
        """
        Searches all viable transport alternatives (train, bus, self-drive) via live APIs.
        Flags any API lookup failures explicitly without fabricating fake live quotes.
        """
        orig_mode = _normalize_transport_type(current_mode)
        alt_modes_to_search = [m for m in ["train", "bus"] if m != orig_mode]

        all_alternatives: List[Dict[str, Any]] = []
        api_errors: List[str] = []

        # Live Search for Train and Bus
        for alt_mode in alt_modes_to_search:
            o_code = origin_code or self._guess_station_or_airport_code(origin, alt_mode)
            d_code = destination_code or self._guess_station_or_airport_code(destination, alt_mode)

            api_results: List[Dict[str, Any]] = []
            if transport_search:
                try:
                    res = transport_search({
                        "transport_type": alt_mode,
                        "origin": origin,
                        "origin_code": o_code,
                        "destination": destination,
                        "destination_code": d_code,
                        "travel_date": travel_date,
                        "budget": target_budget / max(num_people * 2, 1),
                        "num_people": num_people,
                        "preferred_time": "morning",
                    })
                    api_results = res.get("results", [])
                except Exception as e:
                    err = f"Live transport search error for {alt_mode}: {e}"
                    logger.warning(err)
                    api_errors.append(err)

            if api_results:
                best = api_results[0]
                unit_price = float(best.get("price") or (target_budget / max(num_people * 2, 1)))
                new_total = round(unit_price * num_people * 2, 2)
                all_alternatives.append({
                    "mode": alt_mode.capitalize(),
                    "provider": best.get("provider", alt_mode.capitalize()),
                    "new_cost": new_total,
                    "savings": round(max(0.0, current_cost - new_total), 2),
                    "booking_link": best.get("booking_link", ""),
                    "details": best,
                    "estimated": False,
                })
            else:
                # Emergency fallback estimate: clearly marked as estimated
                api_errors.append(f"Live {alt_mode} options unavailable for {origin} -> {destination}. Using fallback estimate.")
                fallback_base = FALLBACK_COST_ESTIMATES["transport"].get(alt_mode, {})
                unit_price = fallback_base.get("avg_roundtrip", 1500.0) / 2
                new_total = round(unit_price * num_people * 2, 2)
                all_alternatives.append({
                    "mode": alt_mode.capitalize(),
                    "provider": f"{alt_mode.capitalize()} (Estimated - Live rates unavailable)",
                    "new_cost": new_total,
                    "savings": round(max(0.0, current_cost - new_total), 2),
                    "booking_link": "",
                    "details": {"is_fallback": True},
                    "estimated": True,
                })

        # Self-drive estimate (always marked estimated)
        if orig_mode != "self-drive":
            fuel_toll_per_km = 6.0
            avg_distance_km = 400
            self_drive_roundtrip = round(fuel_toll_per_km * avg_distance_km * 2, 2)
            all_alternatives.append({
                "mode": "Self-drive",
                "provider": "Self-drive / Cab Rental (Estimated)",
                "new_cost": self_drive_roundtrip,
                "savings": round(max(0.0, current_cost - self_drive_roundtrip), 2),
                "booking_link": "",
                "details": {"avg_distance_km": avg_distance_km, "fuel_toll_per_km": fuel_toll_per_km},
                "estimated": True,
            })

        if not all_alternatives:
            return None, api_errors

        all_alternatives.sort(key=lambda x: x["savings"], reverse=True)
        best_alt = all_alternatives[0]

        return OptimizationAlternative(
            category="transport",
            original_item=f"{current_mode.capitalize()} (Roundtrip)",
            original_cost=current_cost,
            suggested_alternative=f"{best_alt['mode']} via {best_alt['provider']}",
            new_cost=best_alt["new_cost"],
            savings=best_alt["savings"],
            details={
                "mode": best_alt["mode"].lower(),
                "provider": best_alt["provider"],
                "estimated": best_alt["estimated"],
                "all_alternatives": all_alternatives,
            },
            booking_link=best_alt["booking_link"],
        ), api_errors

    def _find_hotel_alternatives(
        self,
        destination: str,
        days: int,
        num_people: int,
        current_hotel_name: str,
        current_cost: float,
        target_budget_per_night: float,
        hotel_type: str,
        travel_date: Optional[str] = None,
    ) -> Tuple[Optional[OptimizationAlternative], List[str]]:
        """
        Calls live hotel_search tool with actual trip dates.
        Never fabricates a mock hotel name if API fails.
        """
        target_tier = "Budget/Hostel" if target_budget_per_night < 2500 else "Mid-range"
        api_errors: List[str] = []

        # Parse actual trip dates
        c_in = travel_date or (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
        try:
            dt_in = datetime.strptime(c_in, "%Y-%m-%d")
        except Exception:
            dt_in = date.today() + timedelta(days=14)

        check_in_str = dt_in.strftime("%Y-%m-%d")
        check_out_str = (dt_in + timedelta(days=days)).strftime("%Y-%m-%d")

        hotel_results = []
        if hotel_search:
            try:
                state = {
                    "destination": destination,
                    "check_in": check_in_str,
                    "check_out": check_out_str,
                    "num_people": num_people,
                    "budget_per_day": max(1000, int(target_budget_per_night)),
                    "hotel_type": target_tier,
                    "currency": "INR",
                }
                res = hotel_search(state)
                hotel_results = res.get("results", [])
            except Exception as e:
                err = f"hotel_search API error for {destination}: {e}"
                logger.warning(err)
                api_errors.append(err)

        if hotel_results:
            best_hotel = hotel_results[0]
            price_night = float(best_hotel.get("price_per_night") or target_budget_per_night)
            new_total = round(price_night * days, 2)
            savings = max(0.0, current_cost - new_total)

            return OptimizationAlternative(
                category="accommodation",
                original_item=current_hotel_name,
                original_cost=current_cost,
                suggested_alternative=best_hotel.get("name", f"Verified {target_tier} in {destination}"),
                new_cost=new_total,
                savings=savings,
                details=best_hotel,
                booking_link=best_hotel.get("booking_link", ""),
            ), api_errors

        # If live search fails, do NOT fabricate a fake hotel. Alert the user transparently.
        err_msg = f"Live hotel search returned no verified stays under ₹{target_budget_per_night:,.0f}/night in {destination}."
        api_errors.append(err_msg)
        return None, api_errors

    def _find_activity_alternatives(
        self,
        destination: str,
        activities_data: List[Dict[str, Any]],
        num_people: int,
    ) -> Optional[OptimizationAlternative]:
        """
        Calls search_google_places to locate free iconic attractions & viewpoints.
        Calculates savings directly from actual ticket prices saved (entry = ₹0).
        """
        curr_act_cost = sum(
            float(a.get("ticket_price", a.get("price", 0))) * num_people
            for a in activities_data
            if isinstance(a, dict)
        )

        if curr_act_cost <= 0:
            return None

        free_places = []
        if search_google_places:
            try:
                query = f"{destination} famous scenic viewpoints public parks heritage beaches free attractions"
                free_places = search_google_places(query=query, max_results=4)
            except Exception as e:
                logger.warning(f"search_google_places tool error: {e}")

        suggested_names = [p.get("name") for p in free_places if isinstance(p, dict) and p.get("name")]
        if not suggested_names:
            suggested_names = [
                f"Iconic Public Promenades & Viewpoints in {destination}",
                f"Heritage Walk & Architectural Squares in {destination}",
            ]

        # Free public landmarks have zero ticket entry cost
        new_act_cost = 0.0
        savings = round(curr_act_cost - new_act_cost, 2)

        return OptimizationAlternative(
            category="activities",
            original_item="High-ticket Commercial Activities",
            original_cost=curr_act_cost,
            suggested_alternative=", ".join(suggested_names[:3]),
            new_cost=new_act_cost,
            savings=savings,
            details={"free_or_low_cost_places": free_places},
        )

    # Live Feasibility Validator
    def _check_feasibility(
        self,
        destination: str,
        days: int,
        num_people: int,
        per_day: float,
        total_budget: float,
        transport_type: str,
        hotel_type: str,
        allocation: BudgetAllocation,
        origin: str = "Origin",
        origin_code: Optional[str] = None,
        destination_code: Optional[str] = None,
        travel_date: Optional[str] = None,
    ) -> Tuple[bool, str, List[str], List[str]]:
        """
        Validates feasibility using real live pricing from transport and hotel tools.
        If insufficient, computes the EXACT required budget and deficit.
        """
        issues: List[str] = []
        recommendations: List[str] = []
        api_errors: List[str] = []

        # 1. Live Transport Price Check
        real_trans_price: Optional[float] = None
        trans_is_fallback = False

        if transport_search and transport_type in ("flight", "train", "bus"):
            try:
                t_date = travel_date or (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
                o_code = origin_code or self._guess_station_or_airport_code(origin, transport_type)
                d_code = destination_code or self._guess_station_or_airport_code(destination, transport_type)
                res = transport_search({
                    "transport_type": transport_type,
                    "origin": origin,
                    "origin_code": o_code,
                    "destination": destination,
                    "destination_code": d_code,
                    "travel_date": t_date,
                    "budget": allocation.transport / max(num_people * 2, 1),
                    "num_people": num_people,
                })
                t_results = res.get("results", [])
                if t_results:
                    raw_p = t_results[0].get("price")
                    if raw_p is not None:
                        unit_p = float(raw_p)
                        if unit_p > 0:
                            real_trans_price = unit_p * num_people * 2
            except Exception as e:
                logger.warning(f"Feasibility live transport search failed: {e}")
                api_errors.append(f"Live {transport_type} pricing unavailable for {origin} -> {destination}")

        if real_trans_price is None:
            trans_is_fallback = True
            base = FALLBACK_COST_ESTIMATES["transport"].get(transport_type, {})
            unit_p = base.get("min_per_person_roundtrip", 3000.0)
            real_trans_price = unit_p * num_people

        # 2. Live Hotel Price Check
        real_hotel_total: Optional[float] = None
        hotel_is_fallback = False

        # Map to exact categories required by hotel_search tool
        valid_hotel_types = {
            "budget / hostel": "Budget/Hostel",
            "budget": "Budget/Hostel",
            "hostel": "Budget/Hostel",
            "boutique": "Boutique",
            "luxury / resort": "Luxury/Resort",
            "luxury": "Luxury/Resort",
            "resort": "Luxury/Resort",
            "mid-range": "Mid-range",
        }
        api_hotel_type = valid_hotel_types.get(hotel_type.strip().lower(), "Mid-range")

        if hotel_search:
            try:
                c_in = travel_date or (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
                try:
                    dt_in = datetime.strptime(c_in, "%Y-%m-%d")
                except Exception:
                    dt_in = date.today() + timedelta(days=14)

                c_in_str = dt_in.strftime("%Y-%m-%d")
                c_out_str = (dt_in + timedelta(days=days)).strftime("%Y-%m-%d")

                h_res = hotel_search({
                    "destination": destination,
                    "check_in": c_in_str,
                    "check_out": c_out_str,
                    "num_people": num_people,
                    "budget_per_day": max(1000, int(allocation.accommodation / days)),
                    "hotel_type": api_hotel_type,
                    "currency": "INR",
                })
                h_results = h_res.get("results", [])
                if h_results:
                    raw_night = h_results[0].get("price_per_night")
                    if raw_night is not None:
                        night_rate = float(raw_night)
                        if night_rate > 0:
                            real_hotel_total = night_rate * days
            except Exception as e:
                logger.warning(f"Feasibility live hotel search failed: {e}")
                api_errors.append(f"Live hotel pricing unavailable for {destination} ({hotel_type})")

        if real_hotel_total is None:
            hotel_is_fallback = True
            base_h = FALLBACK_COST_ESTIMATES["hotel"].get(hotel_type, {})
            min_night = base_h.get("min_per_night", 1500.0)
            real_hotel_total = min_night * days

        # 3. Realistic Subsistence (Dining + Local Commute)
        est_food_daily = 700.0 * num_people
        est_commute_daily = 400.0
        est_subsistence_total = (est_food_daily + est_commute_daily) * days
        est_activities = max(1000.0, allocation.activities_sightseeing * 0.5)

        # 4. True Required Budget & Deficit Calculation
        required_total = round(
            real_trans_price + real_hotel_total + est_subsistence_total + est_activities,
            2,
        )
        shortfall = max(0.0, round(required_total - total_budget, 2))
        extra_per_day = round(shortfall / days, 2)

        transit_source = "Live quotes" if not trans_is_fallback else "Estimated baseline"
        hotel_source = "Live search" if not hotel_is_fallback else "Estimated baseline"

        # Feasibility check: Can total budget cover real transport + hotel?
        if (real_trans_price + real_hotel_total) > total_budget:
            issues.append(
                f"{transport_type.capitalize()} (₹{real_trans_price:,.0f}, {transit_source}) and "
                f"{hotel_type.capitalize()} stay (₹{real_hotel_total:,.0f}, {hotel_source}) alone total "
                f"₹{real_trans_price + real_hotel_total:,.0f}, which exceeds your entire trip budget of ₹{total_budget:,.0f}."
            )
        elif (total_budget - (real_trans_price + real_hotel_total)) < est_subsistence_total:
            remaining = total_budget - (real_trans_price + real_hotel_total)
            issues.append(
                f"After booking {transport_type} (₹{real_trans_price:,.0f}) and {hotel_type} stay (₹{real_hotel_total:,.0f}), "
                f"only ₹{remaining:,.0f} remains for {days} days. This is insufficient to cover daily dining and local transit "
                f"for {num_people} travelers (minimum ₹{est_subsistence_total:,.0f} needed)."
            )

        if issues:
            if transport_type == "flight":
                recommendations.append(
                    "Switch from Flight to Train or Bus to significantly reduce transit expenses."
                )
            if hotel_type in ("luxury / resort", "boutique", "mid-range"):
                recommendations.append(
                    "Consider Budget / Hostel or Mid-range stays to save on accommodation."
                )
            recommendations.append(
                f"Increase total budget by ₹{shortfall:,.0f} (approx ₹{extra_per_day:,.0f}/day) "
                f"to reach the realistic minimum of ₹{required_total:,.0f}."
            )

        is_feasible = len(issues) == 0
        if not is_feasible:
            alert_msg = f"⚠️ Budget Shortfall: " + " ".join(issues)
        else:
            alert_msg = (
                f"✅ Budget verified: ₹{total_budget:,.0f} comfortably covers {transport_type} "
                f"(₹{real_trans_price:,.0f}), {hotel_type} stay (₹{real_hotel_total:,.0f}), dining, and local experiences."
            )

        return is_feasible, alert_msg, recommendations, api_errors

    def _guess_station_or_airport_code(self, city_name: str, mode: str) -> str:
        """Helper to provide standard fallback IATA / IRCTC codes."""
        c = (city_name or "").strip().lower()
        if mode == "flight":
            codes = {
                "mumbai": "BOM", "delhi": "DEL", "new delhi": "DEL", "goa": "GOI",
                "bangalore": "BLR", "bengaluru": "BLR", "jaipur": "JAI", "chennai": "MAA",
                "kolkata": "CCU", "hyderabad": "HYD", "kochi": "COK", "ahmedabad": "AMD",
                "srinagar": "SXR", "varanasi": "VNS", "udaipur": "UDR", "pune": "PNQ",
            }
            return codes.get(c, "DEL")
        else:  # Train
            codes = {
                "mumbai": "BVI", "delhi": "NDLS", "new delhi": "NDLS", "goa": "MAO",
                "bangalore": "SBC", "jaipur": "JP", "chennai": "MAS", "kolkata": "HWH",
                "hyderabad": "SC", "kochi": "ERS", "ahmedabad": "ADI", "varanasi": "BSB",
                "udaipur": "UDZ", "pune": "PUNE", "agra": "AGC", "amritsar": "ASR",
            }
            return codes.get(c, "NDLS")

# General Entry Point

def run_budget_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main dispatch function for the Budget Agent.
    """
    agent = BudgetAgent()
    action_type = payload.get("action", "").lower()

    if action_type in ("optimize", "optimize_budget") or "current_expenses" in payload:
        res = agent.optimize_budget(
            destination=payload.get("destination", "Goa"),
            days=int(payload.get("days", 3)),
            allotted_budget=float(payload.get("allotted_budget") or payload.get("total_budget", 15000)),
            current_expenses=payload.get("current_expenses", {}),
            num_people=int(payload.get("num_people", 2)),
            hotel_type=payload.get("hotel_type", "Mid-range"),
            transport_type=payload.get("transport_type", "Flight"),
            origin=payload.get("origin", "Mumbai"),
            origin_code=payload.get("origin_code"),
            destination_code=payload.get("destination_code"),
            travel_date=payload.get("travel_date"),
            travel_style=payload.get("travel_style", "balanced"),
            party_type=payload.get("party_type", "friends"),
            user_query=payload.get("query", "Optimize budget"),
        )
    else:
        res = agent.reconfigure_budget(
            days=int(payload.get("days", 3)),
            budget_per_day=payload.get("budget_per_day", 5000),
            transport_type=payload.get("transport_type", "Flight"),
            hotel_type=payload.get("hotel_type", "Mid-range"),
            num_people=int(payload.get("num_people", 2)),
            destination=payload.get("destination", "Goa"),
            origin=payload.get("origin", "Mumbai"),
            origin_code=payload.get("origin_code"),
            destination_code=payload.get("destination_code"),
            travel_date=payload.get("travel_date"),
            party_type=payload.get("party_type", "friends"),
            travel_style=payload.get("travel_style", "balanced"),
            query=payload.get("query", ""),
        )

    return res.to_dict()

