export interface Destination {
  id: string;
  name: string;
  image: string;
  description: string;
  accent: string;
  cities: string[];
}

export interface ActivityItem {
  place: string;
  time?: string;
  duration: string;
  category: string;
  description?: string;
  tips: string;
  fun_fact?: string;
  image?: string;
}

export interface SwapAlternative {
  name: string;
  address: string;
  rating?: number;
  place_id: string;
  description?: string;
  tips?: string;
  fun_fact?: string;
  image?: string;
}

export interface FlightInfo {
  mode?: string;
  airline?: string;
  provider?: string;
  identifier?: string;
  origin?: string;
  destination?: string;
  departure_time?: string;
  arrival_time?: string;
  duration?: string;
  price?: number;
  price_per_person?: number;
  total_price?: number;
  currency?: string;
  stops?: string;
  cabin_class?: string;
  booking_link?: string;
}

export interface HotelOption {
  name: string;
  category?: string;
  platform?: string;
  price_per_night?: number;
  currency?: string;
  rating?: number;
  description?: string;
  image_url?: string;
  booking_link?: string;
  selected?: boolean;
}

export interface BudgetBreakdown {
  hotel_total?: number;
  hotel_per_night?: number;
  transport_total?: number;
  transport_per_person?: number;
  food_restaurant_total?: number;
  food_per_day?: number;
  activities_total?: number;
  grand_total?: number;
  per_person_total?: number;
  currency?: string;
  tier?: string;
}

export interface DayPlan {
  date: string;
  theme: string;
  weather: string;
  morning: ActivityItem[];
  afternoon: ActivityItem[];
  evening: ActivityItem[];
  notes: string;
  hotel_options?: HotelOption[];
  selected_hotel?: HotelOption;
}

export interface TripPlanResponse {
  source?: 'general_planner' | 'planner_agent' | string;
  planner_type?: string;
  request: {
    destination: string;
    trip_start_date: string;
    days: number;
    travel_style: string;
    number_of_people: number;
    party_type: string;
  };
  summary: string;
  overview?: string;
  places_covered?: string[];
  fun_facts?: string[];
  must_try_food?: string[];
  hidden_gems?: string[];
  local_culture?: string;
  travel_hacks?: string[];
  budget_info?: string;
  best_flight?: FlightInfo;
  transport?: FlightInfo;
  hotel_options?: HotelOption[];
  selected_hotel?: HotelOption;
  budget_breakdown?: BudgetBreakdown;
  days: DayPlan[];
}

export interface TripWizardValues {
  destination: string;
  tripStartDate: string;
  days: number;
  travelStyle: string;
  numberOfPeople: number;
  partyType: string;
}
