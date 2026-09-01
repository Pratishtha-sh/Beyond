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

export interface DayPlan {
  date: string;
  theme: string;
  weather: string;
  morning: ActivityItem[];
  afternoon: ActivityItem[];
  evening: ActivityItem[];
  notes: string;
}

export interface TripPlanResponse {
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
  fun_facts?: string[];
  must_try_food?: string[];
  hidden_gems?: string[];
  local_culture?: string;
  travel_hacks?: string[];
  budget_info?: string;
  places_covered?: string[];
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
