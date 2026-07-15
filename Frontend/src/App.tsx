import { AnimatePresence, motion } from 'framer-motion';
import { Compass, Sparkles, Map, MoonStar, SunMedium } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { destinations } from './data/destinations';
import { healthCheck, planTrip } from './services/api';
import type { DayPlan, Destination, TripPlanResponse, TripWizardValues } from './types';

const initialValues: TripWizardValues = {
  destination: 'Rajasthan',
  tripStartDate: '2026-07-06',
  days: 4,
  travelStyle: 'calm',
  numberOfPeople: 3,
  partyType: 'family',
};

function App() {
  const [darkMode, setDarkMode] = useState(false);
  const [selectedDestination, setSelectedDestination] = useState<Destination | null>(destinations[0]);
  const [isWizardOpen, setIsWizardOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [values, setValues] = useState<TripWizardValues>(initialValues);
  const [itinerary, setItinerary] = useState<TripPlanResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [backendReady, setBackendReady] = useState<boolean | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
  }, [darkMode]);

  useEffect(() => {
    void healthCheck().then(setBackendReady);
  }, []);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem('beyond-itinerary');
      if (saved) {
        setItinerary(JSON.parse(saved) as TripPlanResponse);
      }
    } catch {
      // Ignore invalid stored data.
    }
  }, []);

  useEffect(() => {
    if (itinerary) {
      window.localStorage.setItem('beyond-itinerary', JSON.stringify(itinerary));
    } else {
      window.localStorage.removeItem('beyond-itinerary');
    }
  }, [itinerary]);

  const handleSubmit = async () => {
    setIsLoading(true);
    try {
      const suggestion = await planTrip(values);
      setItinerary(suggestion);
      window.localStorage.setItem('beyond-itinerary', JSON.stringify(suggestion));
      setIsWizardOpen(false);
      navigate('/itinerary', { state: { itinerary: suggestion } });
    } finally {
      setIsLoading(false);
    }
  };

  const stepTitles = [
    'Where to?',
    'When are you going?',
    'How many days?',
    'Your travel style',
    'How many travellers?',
    "Who's on the guest list?",
    'Ready for your escape?',
  ];

  const stepSubtitles = [
    'Type a city, state, or feeling.',
    'Choose a departure date to set the season.',
    'Slow, medium, or marathon.',
    'How do you like to move through a place?',
    'A solo escape or a group expedition.',
    'Define the dynamic of your travel companions.',
    'Double-check your choices before we sketch the perfect plan.',
  ];

  const renderStepContent = (currentStep: number) => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-4">
            <input
              value={values.destination}
              onChange={(event) => setValues((prev) => ({ ...prev, destination: event.target.value }))}
              className="w-full rounded-2xl border-0 bg-[#FAF6F0] dark:bg-slate-850 px-6 py-4 outline-none text-lg text-slate-800 dark:text-slate-100 placeholder-slate-400 font-semibold focus:ring-2 focus:ring-slate-300 dark:focus:ring-slate-700 transition-all border-solid"
              placeholder="e.g. Rajasthan, Kerala backwaters..."
            />
            <div className="flex flex-wrap gap-2">
              {['Rajasthan', 'Kerala', 'Himachal Pradesh', 'Goa', 'Kashmir', 'Meghalaya'].map((dest) => (
                <button
                  key={dest}
                  onClick={() => setValues((prev) => ({ ...prev, destination: dest }))}
                  className={`rounded-full px-4 py-2 text-sm font-medium border border-solid border-slate-200 dark:border-slate-700 transition-all cursor-pointer ${values.destination === dest ? 'bg-[#0B1528] text-white border-[#0B1528] dark:bg-slate-100 dark:text-slate-900 dark:border-slate-100' : 'bg-white/85 text-slate-700 hover:bg-slate-100 dark:bg-slate-900/60 dark:text-slate-300 dark:hover:bg-slate-800'}`}
                >
                  {dest === 'Himachal Pradesh' ? 'Himachal' : dest}
                </button>
              ))}
            </div>
          </div>
        );
      case 1:
        return (
          <div className="space-y-4">
            <input
              type="date"
              value={values.tripStartDate}
              onChange={(event) => setValues((prev) => ({ ...prev, tripStartDate: event.target.value }))}
              className="w-full rounded-2xl border-0 bg-[#FAF6F0] dark:bg-slate-850 px-6 py-4 outline-none text-lg text-slate-800 dark:text-slate-100 font-semibold focus:ring-2 focus:ring-slate-300 dark:focus:ring-slate-700 transition-all border-solid"
            />
          </div>
        );
      case 2:
        return (
          <div className="flex flex-col items-center gap-6">
            <div className="w-full rounded-3xl bg-[#FAF6F0] dark:bg-slate-850 p-6 flex items-center justify-between">
              <button
                onClick={() => setValues((prev) => ({ ...prev, days: Math.max(1, prev.days - 1) }))}
                className="w-12 h-12 rounded-full bg-white dark:bg-slate-700 shadow-sm flex items-center justify-center text-2xl font-bold cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-600 transition-all select-none border-0 text-slate-800 dark:text-slate-100"
              >
                -
              </button>
              <div className="text-center">
                <p className="font-serif text-6xl font-bold text-slate-900 dark:text-slate-100">{values.days}</p>
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-455 dark:text-slate-400 font-bold mt-1">DAYS</p>
              </div>
              <button
                onClick={() => setValues((prev) => ({ ...prev, days: Math.min(14, prev.days + 1) }))}
                className="w-12 h-12 rounded-full bg-white dark:bg-slate-700 shadow-sm flex items-center justify-center text-2xl font-bold cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-600 transition-all select-none border-0 text-slate-800 dark:text-slate-100"
              >
                +
              </button>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {[3, 5, 7, 10, 14].map((d) => (
                <button
                  key={d}
                  onClick={() => setValues((prev) => ({ ...prev, days: d }))}
                  className={`rounded-full px-5 py-2 text-sm font-medium border border-solid border-slate-200 dark:border-slate-700 transition-all cursor-pointer ${values.days === d ? 'bg-[#0B1528] text-white border-[#0B1528] dark:bg-slate-100 dark:text-slate-900 dark:border-slate-100' : 'bg-white/85 text-slate-700 hover:bg-slate-100 dark:bg-slate-900/60 dark:text-slate-300 dark:hover:bg-slate-800'}`}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>
        );
      case 3:
        return (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { id: 'calm', name: 'Calm', desc: 'Quiet mornings, soft days', emoji: '🧘' },
              { id: 'adventure', name: 'Adventure', desc: 'Treks, rapids, ridgelines', emoji: '🏔️' },
            ]
              .concat([
                { id: 'historical-cultural', name: 'Historical & Cultural', desc: 'Forts, palaces, tombs, heritage', emoji: '🏛️' },
                { id: 'spiritual', name: 'Spiritual', desc: 'Temples, shrines, sacred lore', emoji: '🙏' },
              ])
              .map((style) => {
                const isSelected = values.travelStyle === style.id;
                return (
                  <button
                    key={style.id}
                    onClick={() => setValues((prev) => ({ ...prev, travelStyle: style.id as any }))}
                    className={`rounded-3xl p-5 text-left border-0 transition-all cursor-pointer flex flex-col justify-between h-36 ${isSelected ? 'bg-[#0B1528] text-white shadow-lg dark:bg-slate-100 dark:text-slate-900' : 'bg-[#FAF6F0] dark:bg-slate-850 text-slate-800 dark:text-slate-100 hover:bg-slate-100/80 dark:hover:bg-slate-750'}`}
                  >
                    <span className="text-3xl">{style.emoji}</span>
                    <div>
                      <h4 className="font-semibold text-base">{style.name}</h4>
                      <p className={`text-[11px] mt-1 leading-relaxed ${isSelected ? 'text-slate-300 dark:text-slate-700' : 'text-slate-500 dark:text-slate-405'}`}>{style.desc}</p>
                    </div>
                  </button>
                );
              })}
          </div>
        );
      case 4:
        return (
          <div className="flex flex-col items-center gap-6">
            <div className="w-full rounded-3xl bg-[#FAF6F0] dark:bg-slate-850 p-6 flex items-center justify-between">
              <button
                onClick={() => setValues((prev) => ({ ...prev, numberOfPeople: Math.max(1, prev.numberOfPeople - 1) }))}
                className="w-12 h-12 rounded-full bg-white dark:bg-slate-700 shadow-sm flex items-center justify-center text-2xl font-bold cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-600 transition-all select-none border-0 text-slate-800 dark:text-slate-100"
              >
                -
              </button>
              <div className="text-center">
                <p className="font-serif text-6xl font-bold text-slate-900 dark:text-slate-100">{values.numberOfPeople}</p>
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-455 dark:text-slate-400 font-bold mt-1">TRAVELLERS</p>
              </div>
              <button
                onClick={() => setValues((prev) => ({ ...prev, numberOfPeople: Math.min(12, prev.numberOfPeople + 1) }))}
                className="w-12 h-12 rounded-full bg-white dark:bg-slate-700 shadow-sm flex items-center justify-center text-2xl font-bold cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-600 transition-all select-none border-0 text-slate-800 dark:text-slate-100"
              >
                +
              </button>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {[1, 2, 3, 4, 5, 8].map((n) => (
                <button
                  key={n}
                  onClick={() => setValues((prev) => ({ ...prev, numberOfPeople: n }))}
                  className={`rounded-full px-5 py-2 text-sm font-medium border border-solid border-slate-200 dark:border-slate-700 transition-all cursor-pointer ${values.numberOfPeople === n ? 'bg-[#0B1528] text-white border-[#0B1528] dark:bg-slate-100 dark:text-slate-900 dark:border-slate-100' : 'bg-white/85 text-slate-700 hover:bg-slate-100 dark:bg-slate-900/60 dark:text-slate-300 dark:hover:bg-slate-800'}`}
                >
                  {n === 1 ? '1 (Solo)' : n === 2 ? '2 (Couple)' : n}
                </button>
              ))}
            </div>
          </div>
        );
      case 5:
        return (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { id: 'solo', name: 'Solo Explorer', desc: 'Just you and the open road', emoji: '👤' },
              { id: 'couple', name: 'Couple', desc: 'Romantic stays, cozy spots', emoji: '💕' },
              { id: 'friends', name: 'Friends', desc: 'Group fun, sights, and food', emoji: '🍻' },
              { id: 'family', name: 'Family', desc: 'Kid-friendly pacing, cozy stays', emoji: '👪' },
              { id: 'adventure-group', name: 'Adventure Group', desc: 'High energy, outdoor actions', emoji: '🧗' },
            ].map((party) => {
              const isSelected = values.partyType === party.id;
              return (
                <button
                  key={party.id}
                  onClick={() => setValues((prev) => ({ ...prev, partyType: party.id as any }))}
                  className={`rounded-3xl p-5 text-left border-0 transition-all cursor-pointer flex flex-col justify-between h-36 ${isSelected ? 'bg-[#0B1528] text-white shadow-lg dark:bg-slate-100 dark:text-slate-900' : 'bg-[#FAF6F0] dark:bg-slate-855 text-slate-800 dark:text-slate-100 hover:bg-slate-100/80 dark:hover:bg-slate-750'}`}
                >
                  <span className="text-3xl">{party.emoji}</span>
                  <div>
                    <h4 className="font-semibold text-base">{party.name}</h4>
                    <p className={`text-[11px] mt-1 leading-relaxed ${isSelected ? 'text-slate-300 dark:text-slate-700' : 'text-slate-500 dark:text-slate-405'}`}>{party.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        );
      case 6:
        return (
          <div className="rounded-3xl bg-[#FAF6F0] dark:bg-slate-850 p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-solid border-slate-200/50 dark:border-slate-700/50 pb-3">
              <span className="text-sm text-slate-550 dark:text-slate-400">Destination</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100">{values.destination}</span>
            </div>
            <div className="flex justify-between items-center border-b border-solid border-slate-200/50 dark:border-slate-700/50 pb-3">
              <span className="text-sm text-slate-550 dark:text-slate-400">Start Date</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100">{values.tripStartDate}</span>
            </div>
            <div className="flex justify-between items-center border-b border-solid border-slate-200/50 dark:border-slate-700/50 pb-3">
              <span className="text-sm text-slate-550 dark:text-slate-400">Duration</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100">{values.days} Days</span>
            </div>
            <div className="flex justify-between items-center border-b border-solid border-slate-200/50 dark:border-slate-700/50 pb-3">
              <span className="text-sm text-slate-550 dark:text-slate-400">Travel Style</span>
              <span className="font-semibold capitalize text-slate-800 dark:text-slate-100">{values.travelStyle.replace('-', ' ')}</span>
            </div>
            <div className="flex justify-between items-center pb-1">
              <span className="text-sm text-slate-550 dark:text-slate-400">Travellers</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100">{values.numberOfPeople} ({values.partyType})</span>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(223,238,252,0.6),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(233,230,255,0.4),_transparent_25%),linear-gradient(135deg,_#fffaf3_0%,_#fff8ee_100%)] text-slate-800 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-8">
        <Link to="/" className="flex items-center gap-3 text-lg font-semibold tracking-[0.2em] text-slate-700 dark:text-slate-100">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/80 shadow-soft dark:bg-slate-900">✈️</div>
          BEYOND
        </Link>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setDarkMode((prev) => !prev)}
            className="rounded-full border border-solid border-slate-200 bg-white/70 p-3 shadow-sm backdrop-blur dark:bg-slate-900 dark:border-slate-800"
            aria-label="Toggle theme"
          >
            {darkMode ? <SunMedium size={18} /> : <MoonStar size={18} />}
          </button>
          <button
            onClick={() => {
              setStep(0);
              setIsWizardOpen(true);
            }}
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-soft dark:bg-slate-100 dark:text-slate-900 border-0 cursor-pointer"
          >
            Create My Trip
          </button>
        </div>
      </header>

      <Routes>
        <Route
          path="/"
          element={
            <>
              <main className="mx-auto max-w-7xl px-6 pb-20 lg:px-8">
                <section className="grid items-center gap-10 rounded-[2rem] border border-solid border-white/60 bg-white/70 px-6 py-10 shadow-soft backdrop-blur dark:bg-slate-900/50 dark:border-slate-800 xl:grid-cols-[1.1fr_0.9fr] xl:px-10 xl:py-14">
                  <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="space-y-6">
                    <div className="inline-flex items-center gap-2 rounded-full border border-solid border-slate-200 bg-slate-50/80 px-3 py-2 text-sm text-slate-650 dark:bg-slate-800/80 dark:border-slate-700 dark:text-slate-300">
                      <Sparkles size={16} className="text-amber-500" />
                      Beyond destinations. Into experiences.
                    </div>
                    <div className="space-y-4">
                      <h1 className="text-5xl font-semibold leading-tight sm:text-6xl lg:text-7xl font-serif">
                        Plan less.<br />
                        Explore more.
                      </h1>
                      <p className="max-w-xl text-lg text-slate-650 dark:text-slate-350">
                        Discover India in a way that feels effortless, warm, and beautifully curated from first spark to final itinerary.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <button
                        onClick={() => {
                          document.getElementById('destinations')?.scrollIntoView({ behavior: 'smooth' });
                        }}
                        className="rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white shadow-soft dark:bg-slate-100 dark:text-slate-900 border-0 cursor-pointer"
                      >
                        Explore Destinations
                      </button>
                      <button
                        onClick={() => {
                          setStep(0);
                          setIsWizardOpen(true);
                        }}
                        className="rounded-full border border-solid border-slate-200 bg-white/80 px-5 py-3 text-sm font-medium text-slate-750 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-200 cursor-pointer"
                      >
                        Create My Trip
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-slate-600 dark:text-slate-400">
                      <div className="flex items-center gap-2 rounded-full bg-sky/40 px-3 py-2"><Map size={16} /> Curated itineraries</div>
                      <div className="flex items-center gap-2 rounded-full bg-mint/50 px-3 py-2"><Compass size={16} /> Travel style matched</div>
                    </div>
                  </motion.div>

                  <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7 }} className="relative">
                    <div className="absolute left-6 top-6 animate-float text-3xl">✈️</div>
                    <div className="absolute right-4 top-10 animate-float text-2xl">🧳</div>
                    <div className="absolute bottom-8 left-3 animate-float text-3xl">🌄</div>
                    <div className="absolute bottom-4 right-8 animate-float text-2xl">🗺️</div>
                    <div className="rounded-[2rem] border border-solid border-white/70 bg-gradient-to-br from-sky via-white to-lilac p-6 shadow-soft dark:from-slate-900 dark:to-slate-850 dark:border-slate-800">
                      <div className="rounded-[1.5rem] bg-white/80 p-6 dark:bg-slate-900/80">
                        <img
                          src="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1000&q=80"
                          alt="Travel illustration"
                          className="h-72 w-full rounded-[1.25rem] object-cover"
                        />
                        <div className="mt-4 flex items-center justify-between">
                          <div>
                            <p className="text-sm text-slate-500">Featured this week</p>
                            <p className="text-xl font-semibold font-serif">Coastal escapes & mountain air</p>
                          </div>
                          <div className="rounded-full bg-cream px-3 py-2 text-sm dark:bg-slate-800">🌴</div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                </section>

                <section id="destinations" className="mt-16">
                  <div className="mb-8 flex items-end justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium uppercase tracking-[0.3em] text-slate-500">Explore India</p>
                      <h2 className="text-3xl font-semibold font-serif mt-1">Inspiring destinations for every kind of traveler</h2>
                    </div>
                    <div className="hidden rounded-full border border-solid border-slate-200 bg-white/70 px-4 py-2 text-sm text-slate-650 md:block dark:bg-slate-900 dark:border-slate-800 dark:text-slate-350">
                      {backendReady ? 'Planner API ready' : 'Mock mode active'}
                    </div>
                  </div>
                  <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
                    {destinations.map((destination, index) => (
                      <motion.button
                        key={destination.id}
                        initial={{ opacity: 0, y: 16 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, amount: 0.2 }}
                        transition={{ duration: 0.35, delay: index * 0.06 }}
                        whileHover={{ y: -6, scale: 1.01 }}
                        onClick={() => {
                          setSelectedDestination(destination);
                          navigate(`/destination/${destination.id}`);
                        }}
                        className="group overflow-hidden rounded-[1.75rem] border border-solid border-white/70 bg-white/80 text-left shadow-soft dark:bg-slate-900/80 dark:border-slate-800"
                      >
                        <div className={`h-44 bg-gradient-to-br ${destination.accent}`}>
                          <img src={destination.image} alt={destination.name} className="h-full w-full object-cover transition duration-500 group-hover:scale-110" />
                        </div>
                        <div className="p-5">
                          <div className="flex items-center justify-between gap-2">
                            <h3 className="text-xl font-semibold font-serif">{destination.name}</h3>
                            <Compass size={18} className="text-slate-400" />
                          </div>
                          <p className="mt-2 text-sm text-slate-650 dark:text-slate-400">{destination.description}</p>
                        </div>
                      </motion.button>
                    ))}
                  </div>
                </section>

                <section className="mt-16 rounded-[2rem] border border-solid border-slate-200 bg-gradient-to-r from-sky/40 via-white/80 to-lilac/40 p-8 shadow-soft dark:from-slate-900 dark:to-slate-850 dark:border-slate-800">
                  <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-sm font-medium uppercase tracking-[0.3em] text-slate-500">Future feature</p>
                      <h3 className="text-3xl font-semibold font-serif">Create a Fully Customized Trip</h3>
                      <p className="mt-2 max-w-xl text-slate-650 dark:text-slate-400">A deeply personalized planning experience with concierge-level recommendations is on the way.</p>
                    </div>
                    <div className="rounded-[1.5rem] border border-solid border-slate-200 bg-white/80 px-5 py-4 text-sm text-slate-650 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-400">
                      <p className="font-semibold text-slate-800 dark:text-slate-100">Coming Soon</p>
                      <p className="mt-1">Tailored to your pace, interests, and mood.</p>
                    </div>
                  </div>
                </section>
              </main>
            </>
          }
        />

        <Route
          path="/destination/:id"
          element={
            <DestinationPage
              selectedDestination={selectedDestination}
              onPlan={() => {
                setStep(0);
                setIsWizardOpen(true);
              }}
            />
          }
        />
        <Route
          path="/itinerary"
          element={<ItineraryPage itinerary={(location.state as { itinerary?: TripPlanResponse } | null)?.itinerary ?? itinerary} />}
        />
      </Routes>

      <AnimatePresence>
        {isWizardOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#FAF6F0]/90 dark:bg-slate-950/90 px-4 py-8 backdrop-blur-md overflow-y-auto">
            {/* Center Header outside card */}
            <div className="text-center mb-8 max-w-xl">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500 dark:text-slate-400">TRIP PLANNER</p>
              <h2 className="font-serif text-4xl sm:text-5xl font-bold text-slate-900 dark:text-slate-100 mt-2">Let's sketch your trip</h2>
              <p className="text-sm text-slate-650 dark:text-slate-400 mt-2 font-medium">Six tiny questions. One dreamy itinerary at the end.</p>
            </div>

            <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 20, opacity: 0 }} className="w-full max-w-2xl rounded-[2.5rem] border border-solid border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 p-8 shadow-soft relative">
              <button
                onClick={() => setIsWizardOpen(false)}
                className="absolute right-6 top-6 rounded-full border border-solid border-slate-200 dark:border-slate-700 w-8 h-8 flex items-center justify-center text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 text-sm font-semibold select-none cursor-pointer bg-transparent"
                aria-label="Close"
              >
                ✕
              </button>

              {/* Progress bar */}
              <div className="mb-6">
                <div className="flex justify-between items-center text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                  <span>STEP {step + 1} OF 7</span>
                  <span>{Math.round(((step + 1) / 7) * 100)}%</span>
                </div>
                <div className="h-1.5 w-full bg-slate-150 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-sky-400 via-purple-400 to-rose-400 transition-all duration-300"
                    style={{ width: `${((step + 1) / 7) * 100}%` }}
                  />
                </div>
              </div>

              {/* Question text */}
              <div className="mb-6">
                <h3 className="font-serif text-3xl font-bold text-slate-900 dark:text-slate-100">{stepTitles[step]}</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{stepSubtitles[step]}</p>
              </div>

              {/* Render Question Content */}
              <div className="min-h-[220px]">
                {renderStepContent(step)}
              </div>

              {/* Action Buttons */}
              <div className="mt-8 flex items-center justify-between border-t border-solid border-slate-100 dark:border-slate-800 pt-6">
                <button
                  onClick={() => setStep((prev) => Math.max(prev - 1, 0))}
                  className={`rounded-full px-5 py-2.5 text-sm font-medium transition-all border-0 bg-transparent cursor-pointer ${step === 0 ? 'opacity-0 pointer-events-none' : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'}`}
                  disabled={step === 0}
                >
                  ← Back
                </button>
                {step < 6 ? (
                  <button
                    onClick={() => setStep((prev) => prev + 1)}
                    className="rounded-full bg-[#0B1528] dark:bg-slate-100 hover:opacity-90 px-6 py-3 text-sm font-medium text-white dark:text-[#0B1528] flex items-center gap-1.5 transition-all shadow-md cursor-pointer border-0"
                  >
                    Continue →
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    className="rounded-full bg-[#0B1528] dark:bg-slate-100 hover:opacity-90 px-6 py-3 text-sm font-medium text-white dark:text-[#0B1528] flex items-center gap-1.5 transition-all shadow-md cursor-pointer border-0"
                  >
                    {isLoading ? 'Generating…' : 'Generate Trip →'}
                  </button>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DestinationPage({ selectedDestination, onPlan }: { selectedDestination: Destination | null; onPlan: () => void }) {
  const destination = selectedDestination;

  if (!destination) {
    return <div className="px-6 py-12 text-center">Choose a destination to continue.</div>;
  }

  return (
    <main className="mx-auto max-w-7xl px-6 pb-20 lg:px-8">
      <div className="overflow-hidden rounded-[2rem] border border-solid border-white/70 bg-white/80 shadow-soft dark:bg-slate-900/80 dark:border-slate-800">
        <img src={destination.image} alt={destination.name} className="h-72 w-full object-cover" />
        <div className="space-y-6 p-8 lg:p-10">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.3em] text-slate-500">Destination detail</p>
              <h2 className="text-4xl font-semibold font-serif mt-1">{destination.name}</h2>
              <p className="mt-3 max-w-2xl text-slate-600 dark:text-slate-400">{destination.description}</p>
            </div>
            <button onClick={onPlan} className="rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white shadow-soft dark:bg-slate-100 dark:text-slate-900 border-0 cursor-pointer">
              Plan My {destination.name} Trip
            </button>
          </div>

          <div>
            <h3 className="text-xl font-semibold font-serif">Popular cities</h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {destination.cities.map((city) => (
                <div key={city} className="rounded-[1.25rem] border border-solid border-slate-200 bg-slate-50/80 p-4 dark:bg-slate-900/40 dark:border-slate-800">
                  <p className="font-semibold">{city}</p>
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">A beautiful base for your getaway.</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function ItineraryPage({ itinerary }: { itinerary: TripPlanResponse | null }) {
  const location = useLocation();
  const [resolvedItinerary, setResolvedItinerary] = useState<TripPlanResponse | null>(itinerary);

  useEffect(() => {
    const locationItinerary = (location.state as { itinerary?: TripPlanResponse } | null)?.itinerary;
    if (locationItinerary) {
      setResolvedItinerary(locationItinerary);
      window.localStorage.setItem('beyond-itinerary', JSON.stringify(locationItinerary));
      return;
    }

    try {
      const saved = window.localStorage.getItem('beyond-itinerary');
      if (saved) {
        setResolvedItinerary(JSON.parse(saved) as TripPlanResponse);
      }
    } catch {
      setResolvedItinerary(itinerary);
    }
  }, [itinerary, location.state]);

  if (!resolvedItinerary) {
    return (
      <main className="mx-auto max-w-6xl px-6 py-16 text-center">
        <h2 className="text-3xl font-semibold font-serif">Your itinerary will appear here.</h2>
        <p className="mt-3 text-slate-650 dark:text-slate-400">Start planning to see a refined day-by-day experience.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 pb-20 lg:px-8">
      <div className="rounded-[2rem] border border-solid border-white/70 bg-white/80 p-8 shadow-soft dark:bg-slate-900/80 dark:border-slate-800">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.3em] text-slate-500">Itinerary preview</p>
            <h2 className="text-4xl font-semibold font-serif mt-1">{resolvedItinerary.request.destination}</h2>
            <p className="mt-3 max-w-2xl text-slate-650 dark:text-slate-400 leading-relaxed">{resolvedItinerary.summary}</p>
          </div>
          <div className="rounded-[1.5rem] border border-solid border-slate-200 bg-slate-50/80 p-5 dark:bg-slate-900 dark:border-slate-800">
            <p className="text-sm text-slate-500 dark:text-slate-400 font-semibold">Trip summary</p>
            <div className="mt-2 flex flex-wrap gap-3 text-sm">
              <span className="rounded-full bg-white dark:bg-slate-855 px-3 py-1 font-medium">Days: {resolvedItinerary.request.days}</span>
              <span className="rounded-full bg-white dark:bg-slate-855 px-3 py-1 font-medium capitalize">Style: {resolvedItinerary.request.travel_style.replace('-', ' ')}</span>
              <span className="rounded-full bg-white dark:bg-slate-855 px-3 py-1 font-medium capitalize">Group: {resolvedItinerary.request.party_type}</span>
            </div>
          </div>
        </div>

        <div className="mt-8 space-y-6">
          {resolvedItinerary.days.map((day, index) => (
            <div key={`${day.date}-${index}`} className="rounded-[1.5rem] border border-solid border-slate-200 dark:border-slate-800 bg-gradient-to-r from-sky/10 via-white to-lilac/10 dark:from-slate-900 dark:via-slate-900 dark:to-slate-850 p-6">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">Day {index + 1}</p>
                  <h3 className="text-2xl font-semibold font-serif mt-0.5">{day.theme}</h3>
                </div>
                <div className="rounded-full bg-white/80 dark:bg-slate-855 px-3 py-2 text-sm text-slate-650 dark:text-slate-400 border border-solid border-slate-100 dark:border-slate-800">{day.date}</div>
              </div>

              {/* Conditional weather rendering: hide if not visible, unknown or TBD */}
              {day.weather && day.weather.trim() !== '' && day.weather !== 'Weather TBD' && day.weather !== 'unknown' && day.weather !== 'Weather data not available' && (
                <div className="mt-4 rounded-[1.25rem] bg-white/80 dark:bg-slate-900/60 p-4 text-sm text-slate-655 dark:text-slate-350 border border-solid border-slate-100/50 dark:border-slate-800">
                  🌤️ {day.weather}
                </div>
              )}

              <div className="mt-6 grid gap-4 lg:grid-cols-3">
                {(['morning', 'afternoon', 'evening'] as Array<keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>>).map((slot) => {
                  const activities = Array.isArray(day[slot]) ? day[slot] : [];
                  return (
                    <div key={slot} className="rounded-[1.25rem] border border-solid border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/40 p-4 flex flex-col">
                      <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
                        <span>{slot}</span>
                      </div>
                      <div className="flex-1 space-y-3">
                        {activities.length ? activities.map((activity, activityIndex) => (
                          <div key={`${slot}-${activityIndex}`} className="rounded-2xl bg-slate-50 dark:bg-slate-900/80 p-4 border border-solid border-slate-100/50 dark:border-slate-850 flex flex-col justify-between">
                            <div>
                              <div className="flex items-start justify-between gap-2">
                                <p className="font-semibold text-slate-800 dark:text-slate-100 text-sm leading-snug">{activity.place}</p>
                              </div>
                              <p className="mt-1 text-[10px] font-bold text-slate-450 dark:text-slate-500 uppercase tracking-wider">{activity.time} • {activity.duration}</p>
                              <p className="mt-0.5 text-[10px] font-bold text-indigo-500 dark:text-indigo-400 uppercase tracking-widest">{activity.category}</p>

                              {activity.description && (
                                <p className="mt-2 text-xs text-slate-650 dark:text-slate-350 leading-relaxed font-medium">{activity.description}</p>
                              )}
                            </div>
                            {activity.tips && (
                              <p className="mt-3 text-[11px] font-medium text-slate-550 dark:text-slate-400 border-t border-solid border-slate-200/30 dark:border-slate-800 pt-2 flex items-start gap-1">
                                <span className="text-xs">💡</span>
                                <span>{activity.tips}</span>
                              </p>
                            )}
                          </div>
                        )) : (
                          <div className="h-full flex items-center justify-center py-6">
                            <p className="text-xs text-slate-400 dark:text-slate-500 italic">Free time to wander.</p>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {day.notes && (
                <div className="mt-5 rounded-[1.25rem] border border-solid border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/30 p-4 text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-medium">
                  {day.notes}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

export default App;
