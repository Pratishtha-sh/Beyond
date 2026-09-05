import type { SwapAlternative, TripPlanResponse, TripWizardValues } from '../types';

const BASE_URL = '/api';

export interface SwapParams {
  place: string;
  category: string;
  city: string;
  destination: string;
  travel_style: string;
}

export async function fetchSwapAlternatives(params: SwapParams): Promise<SwapAlternative[]> {
  try {
    const response = await fetch(`${BASE_URL}/swap-alternatives`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!response.ok) return [];
    return (await response.json()) as SwapAlternative[];
  } catch {
    return [];
  }
}

export interface AddActivityParams {
  query: string;
  slot: string;
  day_date: string;
  destination: string;
  city?: string;
  travel_style?: string;
}

export async function addActivity(params: AddActivityParams): Promise<import('../types').ActivityItem | null> {
  try {
    const response = await fetch(`${BASE_URL}/add-activity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}



export interface ChatPlanParams {
  query: string;
  itinerary?: any;
  destination?: string;
  days?: number;
  travel_style?: string;
  hotel_type?: string;
  budget_tier?: string;
  transport_type?: string;
  number_of_people?: number;
  party_type?: string;
  start_date?: string;
}

export interface ChatPlanResult {
  intent: string;
  user_message: string;
  itinerary: TripPlanResponse | null;
  hotel_options?: any[];
  selected_hotel?: any;
  transport_options?: any[];
  selected_transport?: any;
  budget_analysis?: any;
  optimization_confirmation?: OptimizationConfirmation | null;
  api_errors?: string[];
}

export interface TransportAlternative {
  mode: string;
  provider: string;
  new_cost: number;
  savings: number;
  booking_link: string;
  estimated: boolean;
  details?: any;
}

export interface OptimizationConfirmation {
  requires_confirmation: boolean;
  total_savings: number;
  transport?: {
    original_mode: string;
    original_cost: number;
    alternatives: TransportAlternative[];
  };
  hotel?: {
    original_name: string;
    original_cost: number;
    suggested_name: string;
    new_cost: number;
    savings: number;
    booking_link: string;
    details: any;
  };
  api_errors?: string[];
}

export async function chatPlan(params: ChatPlanParams): Promise<ChatPlanResult> {
  const response = await fetch(`${BASE_URL}/chat-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    throw new Error(`Chat Plan API error: ${response.status}`);
  }
  const data = await response.json();
  if (data.itinerary && data.itinerary.days) {
    data.itinerary = normalizeTripResponse(data.itinerary);
  }
  return data;
}

function normalizeTripResponse(payload: any): TripPlanResponse {
  const source = payload?.source || payload?.planner_type || (payload?.best_flight || payload?.budget_breakdown ? 'planner_agent' : 'general_planner');
  const isPlannerAgent = source === 'planner_agent';

  const hotelOptions = isPlannerAgent ? (payload?.hotel_options || []) : undefined;
  const bestFlight = isPlannerAgent ? (payload?.best_flight || payload?.transport || undefined) : undefined;
  const budgetBreakdown = isPlannerAgent ? (payload?.budget_breakdown || undefined) : undefined;

  const mapSlotActivities = (acts: any) => {
    if (!Array.isArray(acts)) return [];
    return acts
      .filter((a: any) => a && a.place && a.place.trim() && a.place.trim() !== '-' && a.place.trim() !== '—')
      .map((a: any) => ({
        ...a,
        place: String(a.place).trim(),
        duration: a.duration || '1.5h',
        category: a.category || 'Explore',
        description: a.description || a.desc || '',
        tips: a.tips || a.tip || '',
        fun_fact: a.fun_fact || a.funFact || undefined,
        image: a.image || undefined,
      }));
  };

  const rawDays = Array.isArray(payload?.days) ? payload.days : [];
  const days = rawDays.map((d: any) => ({
    date: d?.date ?? '',
    theme: d?.theme ?? 'Day Exploration',
    weather: d?.weather ?? d?.weather_summary ?? 'Sunny & pleasant',
    morning: mapSlotActivities(d?.morning),
    afternoon: mapSlotActivities(d?.afternoon),
    evening: mapSlotActivities(d?.evening),
    notes: d?.notes ?? d?.daily_notes ?? '',
    hotel_options: isPlannerAgent ? (d?.hotel_options || hotelOptions) : undefined,
    selected_hotel: isPlannerAgent ? (d?.selected_hotel || (hotelOptions && hotelOptions.length > 0 ? hotelOptions[0] : undefined)) : undefined,
  }));

  return {
    source,
    planner_type: source,
    request: {
      destination: payload?.request?.destination ?? payload?.destination ?? 'Your Trip',
      trip_start_date: payload?.request?.trip_start_date ?? payload?.trip_start_date ?? '',
      days: payload?.request?.days ?? payload?.days ?? 1,
      travel_style: payload?.request?.travel_style ?? payload?.travel_style ?? 'calm',
      number_of_people: payload?.request?.number_of_people ?? payload?.number_of_people ?? 1,
      party_type: payload?.request?.party_type ?? payload?.party_type ?? 'solo',
    },
    summary: payload?.summary ?? 'A beautifully planned escape.',
    overview: payload?.overview,
    places_covered: payload?.places_covered,
    fun_facts: payload?.fun_facts,
    must_try_food: payload?.must_try_food,
    hidden_gems: payload?.hidden_gems,
    local_culture: payload?.local_culture,
    travel_hacks: payload?.travel_hacks,
    budget_info: payload?.budget_info,
    best_flight: bestFlight,
    transport: bestFlight,
    hotel_options: hotelOptions,
    selected_hotel: isPlannerAgent ? (payload?.selected_hotel || (hotelOptions && hotelOptions.length > 0 ? hotelOptions[0] : undefined)) : undefined,
    budget_breakdown: budgetBreakdown,
    days: days,
  };
}

function buildRequestBody(values: TripWizardValues) {
  return {
    destination: values.destination,
    trip_start_date: values.tripStartDate,
    days: values.days,
    travel_style: values.travelStyle,
    number_of_people: values.numberOfPeople,
    party_type: values.partyType,
  };
}

/**
 * Try the dataset-based general planner first.
 * Returns a normalized TripPlanResponse, or null if the endpoint returns 404
 * (destination not in dataset) or any other failure.
 */
async function tryGeneralPlanner(values: TripWizardValues): Promise<TripPlanResponse | null> {
  try {
    const response = await fetch(`${BASE_URL}/plan-trip-general`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildRequestBody(values)),
    });

    // 404 means destination not in dataset — expected, not an error
    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
    const normalized = normalizeTripResponse(payload);
    if (!normalized.days.length) {
      return null;
    }

    return normalized;
  } catch {
    return null;
  }
}

export async function planTrip(values: TripWizardValues): Promise<TripPlanResponse> {
  // Step 1: Try the general (dataset-based) planner first
  const generalResult = await tryGeneralPlanner(values);
  if (generalResult) {
    console.log('[Beyond] Itinerary generated via general planner (dataset).');
    return generalResult;
  }

  // Step 2: Fall back to the full LangGraph planner
  try {
    console.log('[Beyond] General planner unavailable, trying full planner...');
    const response = await fetch(`${BASE_URL}/plan-trip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildRequestBody(values)),
    });

    if (!response.ok) {
      throw new Error(`Planner API error: ${response.status}`);
    }

    const payload = await response.json();
    const normalized = normalizeTripResponse(payload);

    if (!normalized.days.length) {
      throw new Error('Backend returned an empty itinerary');
    }

    return normalized;
  } catch (err) {
    console.warn('[Beyond] planTrip fell back to mock:', err);
    return mockTripPlan(values);
  }
}

/**
 * Dedicated function for the general planner — tries dataset endpoint,
 * falls back to full planner if not found.
 */
export async function planTripGeneral(values: TripWizardValues): Promise<TripPlanResponse> {
  return planTrip(values);
}

/**
 * Fetch the list of known destination names from the dataset.
 */
export async function fetchDestinations(): Promise<string[]> {
  try {
    const response = await fetch(`${BASE_URL}/destinations`);
    if (!response.ok) {
      return [];
    }
    const data = await response.json();
    return data.destinations ?? [];
  } catch {
    return [];
  }
}

const mockTripPlan = (values: TripWizardValues): TripPlanResponse => ({
  request: {
    destination: values.destination,
    trip_start_date: values.tripStartDate,
    days: values.days,
    travel_style: values.travelStyle,
    number_of_people: values.numberOfPeople,
    party_type: values.partyType,
  },
  summary: `${values.days}-day ${values.travelStyle} escape through ${values.destination} designed for ${values.numberOfPeople} ${values.partyType} travellers. ⚠️ Backend unavailable — showing preview only.`,
  days: [
    {
      date: values.tripStartDate,
      theme: 'Arrival & Heritage Walk',
      weather: 'Sunny with light breezes',
      morning: [{ place: 'Arrival brunch', time: '09:00', duration: '1.5h', category: 'Food', tips: 'Reserve a table with a rooftop view.' }],
      afternoon: [{ place: 'Local heritage trail', time: '14:00', duration: '3h', category: 'Culture', tips: 'Wear breathable layers and carry water.' }],
      evening: [{ place: 'Golden hour viewpoint', time: '18:30', duration: '2h', category: 'Scenic', tips: 'Arrive before sunset for the best light.' }],
      notes: 'Ease into the trip with a relaxed pace and a local dinner recommendation.',
    },
    {
      date: '2026-07-07',
      theme: 'Markets & Hidden Gems',
      weather: 'Warm and bright',
      morning: [{ place: 'Morning market stroll', time: '08:30', duration: '2h', category: 'Local', tips: 'Try the house special breakfast.' }],
      afternoon: [{ place: 'Craft workshop', time: '13:00', duration: '2h', category: 'Creative', tips: 'Booking ahead is recommended.' }],
      evening: [{ place: 'Dinner by the river', time: '19:00', duration: '2h', category: 'Dining', tips: 'Choose a terrace table for the evening breeze.' }],
      notes: 'Leave space for spontaneous browsing and slow coffee breaks.',
    },
  ],
});

export async function healthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}


export interface ApplyOptimizationParams {
  itinerary: any;
  category: 'transport' | 'hotel';
  selected_alternative: TransportAlternative | any;
  num_people?: number;
  days?: number;
}

export interface ApplyOptimizationResult {
  success: boolean;
  category: string;
  itinerary: any;
  message: string;
}

export async function applyOptimization(params: ApplyOptimizationParams): Promise<ApplyOptimizationResult> {
  const response = await fetch(`${BASE_URL}/apply-optimization`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    throw new Error(`Apply Optimization API error: ${response.status}`);
  }
  return response.json();
}
