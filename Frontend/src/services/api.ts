import type { TripPlanResponse, TripWizardValues } from '../types';

const BASE_URL = '/api';

function normalizeTripResponse(payload: any): TripPlanResponse {
  return {
    request: {
      destination: payload?.request?.destination ?? payload?.destination ?? 'Your Trip',
      trip_start_date: payload?.request?.trip_start_date ?? payload?.trip_start_date ?? '',
      days: payload?.request?.days ?? payload?.days ?? 1,
      travel_style: payload?.request?.travel_style ?? payload?.travel_style ?? 'calm',
      number_of_people: payload?.request?.number_of_people ?? payload?.number_of_people ?? 1,
      party_type: payload?.request?.party_type ?? payload?.party_type ?? 'solo',
    },
    summary: payload?.summary ?? 'A beautifully planned escape.',
    days: Array.isArray(payload?.days) ? payload.days : [],
  };
}

export async function planTrip(values: TripWizardValues): Promise<TripPlanResponse> {
  // POST to /api/plan-trip — the backend will serve the saved itinerary output
  // (adapted to the requested start_date / days) or run the live planner if no
  // saved file exists. The mock is only used when the backend is unreachable.
  try {
    const response = await fetch(`${BASE_URL}/plan-trip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        destination: values.destination,
        trip_start_date: values.tripStartDate,
        days: values.days,
        travel_style: values.travelStyle,
        number_of_people: values.numberOfPeople,
        party_type: values.partyType,
      }),
    });

    if (!response.ok) {
      throw new Error(`Planner API error: ${response.status}`);
    }

    const payload = await response.json();
    const normalized = normalizeTripResponse(payload);

    // If the backend returned an empty days array something went wrong server-side;
    // surface a clear error so we don't silently show a blank itinerary.
    if (!normalized.days.length) {
      throw new Error('Backend returned an empty itinerary');
    }

    return normalized;
  } catch (err) {
    console.warn('[Beyond] planTrip fell back to mock:', err);
    return mockTripPlan(values);
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
