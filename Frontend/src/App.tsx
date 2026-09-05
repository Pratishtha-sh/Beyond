import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, BrainCircuit, Bus, Calendar, Car, CheckCircle2, Clock, CloudSun, Compass, CreditCard, ExternalLink, Flame, Flower2, Heart, Home, Hotel, Landmark, Loader2, Map, MapPin, Mountain, Music, Navigation, Palmtree, Plane, Plus, RefreshCw, Send, Sparkles, Star, Train, Trash2, User, Users, Utensils, UtensilsCrossed, Wallet, Wand2, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import BuildTripPage from './components/BuildTripPage';
import Carousel from './components/Carousel';
import { destinations } from './data/destinations';
import logoImg from './data/images/logo.png';
import rajasthanImg from './data/images/rajasthan/rajasthan.jpg';
import kerelaImg from './data/images/kerela.jpg';
import goaImg from './data/images/Goa/goa.avif';
import { addActivity, applyOptimization, chatPlan, fetchSwapAlternatives, healthCheck, planTrip, planTripGeneral } from './services/api';
import type { OptimizationConfirmation, TransportAlternative } from './services/api';
import type { ActivityItem, DayPlan, Destination, SwapAlternative, TripPlanResponse, TripWizardValues } from './types';

const initialValues: TripWizardValues = {
  destination: 'Rajasthan',
  tripStartDate: '2026-07-06',
  days: 4,
  travelStyle: 'calm',
  numberOfPeople: 3,
  partyType: 'family',
};

const sanitizeText = (value?: string | null): string => {
  if (!value) return '';

  return String(value)
    .replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
};

function App() {
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

  const scrollToChooseTravel = (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    if (location.pathname !== '/') {
      navigate('/', { state: { scrollToDestinations: true } });
    } else {
      const el = document.getElementById('destinations') || document.getElementById('choose-travel');
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  useEffect(() => {
    if (location.pathname === '/' && (location.state as any)?.scrollToDestinations) {
      setTimeout(() => {
        const el = document.getElementById('destinations') || document.getElementById('choose-travel');
        el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }, [location]);

  const handleSubmit = async () => {
    setIsLoading(true);
    try {
      const suggestion = await planTripGeneral(values);
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
              className="w-full border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-850 px-5 py-3 outline-none text-lg text-slate-800 dark:text-slate-100 placeholder-slate-400 font-semibold focus:border-[#2d5a47] dark:focus:border-slate-400 transition-all rounded-none"
              placeholder="e.g. Rajasthan, Kerala backwaters..."
            />
            <div className="flex flex-wrap gap-2">
              {['Rajasthan', 'Kerala', 'Himachal Pradesh', 'Goa', 'Kashmir', 'Meghalaya'].map((dest) => (
                <button
                  key={dest}
                  onClick={() => setValues((prev) => ({ ...prev, destination: dest }))}
                  className={`px-4 py-2 text-sm font-semibold border-2 transition-all cursor-pointer rounded-none ${values.destination === dest ? 'bg-[#2d5a47] text-white border-[#2d5a47]' : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'}`}
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
              className="w-full border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-850 px-5 py-3 outline-none text-lg text-slate-800 dark:text-slate-100 font-semibold focus:border-[#2d5a47] dark:focus:border-slate-400 transition-all rounded-none"
            />
          </div>
        );
      case 2:
        return (
          <div className="flex flex-col items-center gap-5">
            <div className="w-full border-2 border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-850 p-5 flex items-center justify-between rounded-none">
              <button
                onClick={() => setValues((prev) => ({ ...prev, days: Math.max(1, prev.days - 1) }))}
                className="w-10 h-10 border border-slate-300 bg-white dark:bg-slate-700 flex items-center justify-center text-xl font-bold cursor-pointer hover:bg-slate-100 select-none text-slate-800 dark:text-slate-100 rounded-none"
              >
                -
              </button>
              <div className="text-center">
                <p className="font-serif text-5xl font-bold text-slate-900 dark:text-slate-100">{values.days}</p>
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-bold mt-1">DAYS</p>
              </div>
              <button
                onClick={() => setValues((prev) => ({ ...prev, days: Math.min(14, prev.days + 1) }))}
                className="w-10 h-10 border border-slate-300 bg-white dark:bg-slate-700 flex items-center justify-center text-xl font-bold cursor-pointer hover:bg-slate-100 select-none text-slate-800 dark:text-slate-100 rounded-none"
              >
                +
              </button>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {[3, 5, 7, 10, 14].map((d) => (
                <button
                  key={d}
                  onClick={() => setValues((prev) => ({ ...prev, days: d }))}
                  className={`px-4 py-1.5 text-sm font-semibold border-2 transition-all cursor-pointer rounded-none ${values.days === d ? 'bg-[#2d5a47] text-white border-[#2d5a47]' : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'}`}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>
        );
      case 3:
        return (
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { id: 'calm', name: 'Calm & Relaxed', desc: 'Quiet mornings, scenic views & slow days', icon: Palmtree },
              { id: 'adventure-nature', name: 'Adventure & Nature', desc: 'Treks, rapids, ridgelines & wilderness', icon: Mountain },
              { id: 'historical-cultural', name: 'Historical & Cultural', desc: 'Forts, palaces, heritage & lore', icon: Landmark },
              { id: 'spiritual', name: 'Spiritual & Peace', desc: 'Temples, shrines, sacred ghats & calm', icon: Flower2 },
              { id: 'party-nightlife', name: 'Party & Nightlife', desc: 'Beach shacks, live beats & sunset vibes', icon: Music },
              { id: 'culinary-foodie', name: 'Foodie & Culinary', desc: 'Street food trails, iconic eats & cafes', icon: UtensilsCrossed },
            ].map((style) => {
              const isSelected = values.travelStyle === style.id;
              const Icon = style.icon;
              return (
                <button
                  key={style.id}
                  type="button"
                  onClick={() => setValues((prev) => ({ ...prev, travelStyle: style.id as any }))}
                  className={`p-3.5 sm:p-4 text-left border-2 transition-all cursor-pointer flex flex-col justify-between min-h-[118px] h-full rounded-none ${isSelected
                    ? 'bg-[#2d5a47] text-white border-[#2d5a47] shadow-sm'
                    : 'bg-slate-50 border-slate-300 text-slate-800 hover:bg-slate-100 hover:border-slate-400 dark:bg-slate-850 dark:border-slate-700 dark:text-slate-100'
                    }`}
                >
                  <div
                    className={`w-8 h-8 flex items-center justify-center mb-2 transition-colors ${isSelected ? 'bg-white/15 text-white' : 'bg-[#edf6ef] text-[#2d5a47] dark:bg-slate-750 dark:text-[#a3d9bc]'
                      }`}
                  >
                    <Icon size={16} strokeWidth={2.2} />
                  </div>
                  <div>
                    <h4 className="font-semibold text-xs sm:text-[13px] leading-snug">{style.name}</h4>
                    <p className={`text-[11px] leading-relaxed mt-1 ${isSelected ? 'text-slate-200' : 'text-slate-500 dark:text-slate-400'}`}>
                      {style.desc}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        );
      case 4:
        return (
          <div className="flex flex-col items-center gap-5">
            <div className="w-full border-2 border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-850 p-5 flex items-center justify-between rounded-none">
              <button
                onClick={() => setValues((prev) => ({ ...prev, numberOfPeople: Math.max(1, prev.numberOfPeople - 1) }))}
                className="w-10 h-10 border border-slate-300 bg-white dark:bg-slate-700 flex items-center justify-center text-xl font-bold cursor-pointer hover:bg-slate-100 select-none text-slate-800 dark:text-slate-100 rounded-none"
              >
                -
              </button>
              <div className="text-center">
                <p className="font-serif text-5xl font-bold text-slate-900 dark:text-slate-100">{values.numberOfPeople}</p>
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-bold mt-1">TRAVELLERS</p>
              </div>
              <button
                onClick={() => setValues((prev) => ({ ...prev, numberOfPeople: Math.min(12, prev.numberOfPeople + 1) }))}
                className="w-10 h-10 border border-slate-300 bg-white dark:bg-slate-700 flex items-center justify-center text-xl font-bold cursor-pointer hover:bg-slate-100 select-none text-slate-800 dark:text-slate-100 rounded-none"
              >
                +
              </button>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {[1, 2, 3, 4, 5, 8].map((n) => (
                <button
                  key={n}
                  onClick={() => setValues((prev) => ({ ...prev, numberOfPeople: n }))}
                  className={`px-4 py-1.5 text-sm font-semibold border-2 transition-all cursor-pointer rounded-none ${values.numberOfPeople === n ? 'bg-[#2d5a47] text-white border-[#2d5a47]' : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'}`}
                >
                  {n === 1 ? '1 (Solo)' : n === 2 ? '2 (Couple)' : n}
                </button>
              ))}
            </div>
          </div>
        );
      case 5:
        return (
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { id: 'solo', name: 'Solo Explorer', desc: 'Just you and the open road', icon: User },
              { id: 'couple', name: 'Couple', desc: 'Romantic stays, cozy spots', icon: Heart },
              { id: 'friends', name: 'Friends', desc: 'Group fun, sights, and food', icon: Users },
              { id: 'family', name: 'Family', desc: 'Kid-friendly pacing & comfort', icon: Home },
              { id: 'adventure-group', name: 'Adventure Group', desc: 'High energy outdoor trails', icon: Flame },
            ].map((party) => {
              const isSelected = values.partyType === party.id;
              const Icon = party.icon;
              return (
                <button
                  key={party.id}
                  type="button"
                  onClick={() => setValues((prev) => ({ ...prev, partyType: party.id as any }))}
                  className={`p-3.5 sm:p-4 text-left border-2 transition-all cursor-pointer flex flex-col justify-between min-h-[118px] h-full rounded-none ${isSelected
                    ? 'bg-[#2d5a47] text-white border-[#2d5a47] shadow-sm'
                    : 'bg-slate-50 border-slate-300 text-slate-800 hover:bg-slate-100 hover:border-slate-400 dark:bg-slate-850 dark:border-slate-700 dark:text-slate-100'
                    }`}
                >
                  <div
                    className={`w-8 h-8 flex items-center justify-center mb-2 transition-colors ${isSelected ? 'bg-white/15 text-white' : 'bg-[#edf6ef] text-[#2d5a47] dark:bg-slate-750 dark:text-[#a3d9bc]'
                      }`}
                  >
                    <Icon size={16} strokeWidth={2.2} />
                  </div>
                  <div>
                    <h4 className="font-semibold text-xs sm:text-[13px] leading-snug">{party.name}</h4>
                    <p className={`text-[11px] leading-relaxed mt-1 ${isSelected ? 'text-slate-200' : 'text-slate-500 dark:text-slate-400'}`}>
                      {party.desc}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        );
      case 6:
        return (
          <div className="border-2 border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-850 p-5 space-y-3 rounded-none">
            <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-700 pb-2">
              <span className="text-xs text-slate-500 font-medium">Destination</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100 text-sm">{values.destination}</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-700 pb-2">
              <span className="text-xs text-slate-500 font-medium">Start Date</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100 text-sm">{values.tripStartDate}</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-700 pb-2">
              <span className="text-xs text-slate-500 font-medium">Duration</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100 text-sm">{values.days} Days</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-700 pb-2">
              <span className="text-xs text-slate-500 font-medium">Travel Style</span>
              <span className="font-semibold capitalize text-slate-800 dark:text-slate-100 text-sm">{values.travelStyle.replace('-', ' ')}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-500 font-medium">Travellers</span>
              <span className="font-semibold text-slate-800 dark:text-slate-100 text-sm">{values.numberOfPeople} ({values.partyType})</span>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-pastel-cream text-slate-800 transition-colors overflow-x-hidden">
      <header className="fixed top-0 left-0 right-0 z-40 h-[72px] bg-white/80 backdrop-blur-md border-b border-solid border-pastel-green/10 shadow-sm flex items-center">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-3">
            <img src={logoImg} alt="Beyond" className="h-12 w-auto" />
            <span className="text-2xl font-bold tracking-[0.2em] text-[#2d5a47] font-serif">BEYOND</span>
          </Link>
          <nav className="hidden md:flex items-center gap-8">
            <Link to="/" className="text-sm font-medium text-[#2d5a47]/70 hover:text-[#2d5a47] transition-colors">Home</Link>
            <a href="#destinations" className="text-sm font-medium text-[#2d5a47]/70 hover:text-[#2d5a47] transition-colors" onClick={scrollToChooseTravel}>Destinations</a>
            <Link to="/itinerary" className="text-sm font-medium text-[#2d5a47]/70 hover:text-[#2d5a47] transition-colors">My Trips</Link>
          </nav>
          <button
            onClick={() => {
              setStep(0);
              setIsWizardOpen(true);
            }}
            className="rounded-full bg-[#2d5a47] px-5 py-2.5 text-sm font-medium text-white border-0 cursor-pointer hover:bg-[#234a3a] transition-colors shadow-sm"
          >
            Plan a Trip
          </button>
        </div>
      </header>
      {/* Spacer for fixed header */}
      <div className="h-[72px]" />

      <Routes>
        <Route
          path="/"
          element={
            <>
              <main>
                {/* Hero Section — full bleed diagonal stripes */}
                <section className="hero-stripes relative overflow-hidden">
                  <div className="bg-white/25 backdrop-blur-[2px] px-6 py-8 md:py-16 flex flex-col items-center text-center">
                    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="space-y-3 mb-4">
                      <h1 className="text-6xl sm:text-7xl lg:text-8xl font-bold leading-none font-serif text-[#2d5a47] drop-shadow-sm">
                        BEYOND
                      </h1>
                      <p className="text-xl md:text-2xl text-[#2d5a47]/80 font-medium tracking-wide max-w-2xl">
                        Where every mile tells a story — discover the soul of India
                      </p>
                    </motion.div>

                    {/* Carousel */}
                    <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.2 }} className="relative w-full py-2 overflow-hidden flex justify-center">
                      <Carousel
                        onPlanTrip={(destName) => {
                          setValues((prev) => ({ ...prev, destination: destName }));
                          setStep(0);
                          setIsWizardOpen(true);
                        }}
                      />
                    </motion.div>

                    {/* CTAs below carousel */}
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, delay: 0.5 }} className="mt-12 flex flex-wrap gap-3 justify-center">
                      <button
                        onClick={scrollToChooseTravel}
                        className="rounded-full bg-[#2d5a47] px-6 py-3 text-sm font-medium text-white shadow-soft border-0 cursor-pointer hover:bg-[#234a3a] transition-colors"
                      >
                        Explore Destinations
                      </button>
                      <button
                        onClick={() => {
                          setStep(0);
                          setIsWizardOpen(true);
                        }}
                        className="rounded-full border border-solid border-white/60 bg-white/80 px-6 py-3 text-sm font-medium text-[#2d5a47] cursor-pointer hover:bg-white transition-colors backdrop-blur"
                      >
                        Plan a Trip
                      </button>
                    </motion.div>

                  </div>
                </section>

                {/* SECTION 1 — Choose how you want to travel */}
                <section id="destinations" className="scroll-mt-20 py-16 md:py-24 bg-gradient-to-b from-[#f2f8f3] to-[#eaf4ed] border-y border-[#d0e2d5]">
                  <div className="mx-auto max-w-7xl px-6 lg:px-8">
                    <div className="text-center max-w-3xl mx-auto mb-14">
                      <p className="text-xs font-bold uppercase tracking-[0.35em] text-[#2d5a47]/75 mb-2">
                        CHOOSE HOW YOU WANT TO TRAVEL
                      </p>
                      <h2 className="text-4xl sm:text-5xl font-bold font-serif text-[#244b3d] tracking-tight">
                        Your journey. Your way.
                      </h2>
                      <p className="mt-4 text-base sm:text-lg text-slate-600 leading-relaxed font-sans">
                        Whether you know exactly where you're going or only have an idea in mind, Beyond builds the trip around you.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                      {/* CARD 1 — I know where I want to go */}
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="group relative flex flex-col justify-between rounded-[2rem] border-2 border-[#cfe1d4] bg-white p-7 sm:p-9 shadow-[0_12px_32px_rgba(45,90,71,0.06)] hover:shadow-[0_20px_48px_rgba(45,90,71,0.12)] hover:border-[#8ec5a7] transition-all duration-300 overflow-hidden"
                      >
                        <div className="relative z-10">
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#edf6ef] border border-[#cfe1d4] text-[10px] font-bold uppercase tracking-[0.2em] text-[#2d5a47] mb-4">
                            <MapPin size={12} /> I know where I want to go
                          </span>
                          <h3 className="text-2xl sm:text-3xl font-bold font-serif text-[#244b3d] mb-3">
                            Explore a destination
                          </h3>
                          <p className="text-sm sm:text-base text-slate-600 leading-relaxed mb-6">
                            Choose a state or city and start with a curated itinerary built around the best experiences, places and local highlights.
                          </p>

                          <button
                            onClick={() => {
                              setStep(0);
                              setIsWizardOpen(true);
                            }}
                            className="inline-flex items-center gap-2 rounded-full bg-[#2d5a47] px-6 py-3 text-sm font-semibold text-white shadow-md hover:bg-[#214334] transition-all cursor-pointer border-0 group-hover:gap-3"
                          >
                            Explore Destinations <ArrowRight size={15} />
                          </button>
                        </div>

                        {/* Visual Preview */}
                        <div className="mt-8 pt-6 border-t border-[#edf3ee] relative">
                          <div className="grid grid-cols-3 gap-3">
                            {[
                              { name: 'Rajasthan', tag: 'Royal Forts', img: rajasthanImg },
                              { name: 'Kerala', tag: 'Backwaters', img: kerelaImg },
                              { name: 'Goa', tag: 'Coastal Vibe', img: goaImg },
                            ].map((item) => (
                              <div
                                key={item.name}
                                onClick={() => {
                                  setValues((prev) => ({ ...prev, destination: item.name }));
                                  setStep(0);
                                  setIsWizardOpen(true);
                                }}
                                className="relative rounded-xl overflow-hidden h-28 border border-slate-200/80 shadow-sm hover:scale-[1.03] transition-transform duration-300 cursor-pointer"
                              >
                                <img src={item.img} alt={item.name} className="h-full w-full object-cover" />
                                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent flex flex-col justify-end p-2 text-white">
                                  <p className="text-xs font-bold font-serif leading-tight">{item.name}</p>
                                  <p className="text-[9px] text-white/80 uppercase tracking-wider">{item.tag}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </motion.div>

                      {/* CARD 2 — I already have a trip in mind */}
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="group relative flex flex-col justify-between rounded-[2rem] border-2 border-[#cfe1d4] bg-gradient-to-br from-white via-[#f8fcf9] to-[#edf6f0] p-7 sm:p-9 shadow-[0_12px_32px_rgba(45,90,71,0.06)] hover:shadow-[0_20px_48px_rgba(45,90,71,0.12)] hover:border-[#8ec5a7] transition-all duration-300 overflow-hidden"
                      >
                        <div className="relative z-10">
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#edf6ef]/40 border border-[#cfe1d4] text-[10px] font-bold uppercase tracking-[0.2em] text-[#2d5a47] mb-4">
                            <Sparkles size={12} /> I already have a trip in mind
                          </span>
                          <h3 className="text-2xl sm:text-3xl font-bold font-serif text-[#244b3d] mb-3">
                            Build my own trip
                          </h3>
                          <p className="text-sm sm:text-base text-slate-600 leading-relaxed mb-6">
                            Tell Beyond what you want from your journey. Share your destination, dates, budget, interests and travel style, or simply describe the trip in your own words.
                          </p>

                          <button
                            onClick={() => navigate('/build-trip')}
                            className="inline-flex items-center gap-2 rounded-full bg-[#1c3d2f] px-6 py-3 text-sm font-semibold text-white shadow-md hover:bg-[#12281e] transition-all cursor-pointer border-0 group-hover:gap-3"
                          >
                            Build My Trip <ArrowRight size={15} />
                          </button>
                        </div>

                        {/* Abstract AI / Travel Planning Visual */}
                        <div className="mt-8 pt-6 border-t border-[#edf3ee] relative">
                          <div className="rounded-xl border border-[#cfe1d4] bg-white/90 p-3.5 shadow-sm space-y-2.5">
                            <div className="flex items-center justify-between">
                              <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-[#2d5a47]">
                                <BrainCircuit size={13} className="text-[#2d5a47]" /> Beyond Intelligence Core
                              </span>
                              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                Ready to plan
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#edf6ef] text-[11px] font-semibold text-[#2d5a47]">
                                <MapPin size={12} className="text-[#2d5a47]" /> Any Destination in India
                              </span>
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#edf6ef] text-[11px] font-semibold text-[#2d5a47]">
                                <Calendar size={12} className="text-[#2d5a47]" /> Flexible Dates
                              </span>
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#edf6ef] text-[11px] font-semibold text-[#2d5a47]">
                                <Users size={12} className="text-[#2d5a47]" /> Solo to Big Groups
                              </span>
                            </div>
                          </div>
                        </div>
                      </motion.div>
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
        <Route path="/build-trip" element={<BuildTripPage />} />
      </Routes>

      {/* Global Footer */}
      {location.pathname !== '/build-trip' && <Footer />}

      <AnimatePresence>
        {isWizardOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/65 dark:bg-slate-950/85 px-4 py-8 backdrop-blur-md overflow-y-auto">
            {/* 1) Green Stripe Bigger Outer Box (same hero-stripes pattern as in hero section) */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="hero-stripes w-full max-w-4xl p-5 sm:p-9 border-4 border-solid border-[#2d5a47] shadow-2xl relative rounded-none"
            >
              {/* Wizard Content Card */}
              <div className="bg-white dark:bg-slate-900 border-2 border-solid border-slate-300 dark:border-slate-800 p-6 sm:p-10 shadow-xl relative rounded-none">
                <button
                  onClick={() => setIsWizardOpen(false)}
                  className="absolute right-6 top-6 border border-solid border-slate-300 dark:border-slate-700 w-8 h-8 flex items-center justify-center text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 text-sm font-bold select-none cursor-pointer bg-white dark:bg-slate-800 hover:bg-slate-100 transition-colors rounded-none"
                  aria-label="Close"
                >
                  ✕
                </button>

                {/* Top header inside white box */}
                <div className="mb-6 border-b border-solid border-slate-200 dark:border-slate-800 pb-4">
                  <p className="text-xs font-extrabold uppercase tracking-[0.3em] text-[#2d5a47] dark:text-slate-400">TRIP PLANNER</p>
                  <h2 className="font-serif text-3xl sm:text-4xl font-bold text-slate-900 dark:text-slate-100 mt-1">Let's sketch your trip</h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-medium">Six tiny questions. One dreamy itinerary at the end.</p>
                </div>

                {/* Step content container */}
                <div className="w-full space-y-4">
                  {/* Progress bar */}
                  <div>
                    <div className="flex justify-between items-center text-[10px] font-extrabold uppercase tracking-wider text-slate-400 mb-1.5">
                      <span>STEP {step + 1} OF 7</span>
                      <span>{Math.round(((step + 1) / 7) * 100)}%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-200 dark:bg-slate-800 overflow-hidden border border-solid border-slate-300 dark:border-slate-700 rounded-none">
                      <div
                        className="h-full bg-[#2d5a47] transition-all duration-300"
                        style={{ width: `${((step + 1) / 7) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Question title & subtitle */}
                  <div>
                    <h3 className="font-serif text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">{stepTitles[step]}</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{stepSubtitles[step]}</p>
                  </div>

                  {/* Render Step Content */}
                  <div className="min-h-[190px] pt-1">
                    {renderStepContent(step)}
                  </div>
                </div>

                {/* Bottom Action Buttons */}
                <div className="mt-8 flex items-center justify-between border-t border-solid border-slate-200 dark:border-slate-800 pt-5">
                  <button
                    onClick={() => setStep((prev) => Math.max(prev - 1, 0))}
                    className={`border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-5 py-2.5 text-xs font-bold text-slate-700 dark:text-slate-200 transition-all cursor-pointer rounded-none hover:bg-slate-100 ${step === 0 ? 'opacity-0 pointer-events-none' : ''}`}
                    disabled={step === 0}
                  >
                    ← Back
                  </button>
                  {step < 6 ? (
                    <button
                      onClick={() => setStep((prev) => prev + 1)}
                      className="border-2 border-[#2d5a47] bg-[#2d5a47] hover:bg-[#234a3a] px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-white transition-all shadow-md cursor-pointer rounded-none"
                    >
                      Continue →
                    </button>
                  ) : (
                    <button
                      onClick={handleSubmit}
                      className="border-2 border-[#2d5a47] bg-[#2d5a47] hover:bg-[#234a3a] px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-white transition-all shadow-md cursor-pointer rounded-none"
                    >
                      {isLoading ? 'Generating…' : 'Generate Trip →'}
                    </button>
                  )}
                </div>
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
            <button onClick={onPlan} className="rounded-full bg-[#2d5a47] px-5 py-3 text-sm font-medium text-white shadow-soft dark:bg-slate-100 dark:text-slate-900 border-0 cursor-pointer">
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

/* Undo Toast */

interface UndoToast {
  id: string;
  message: string;
  onUndo: () => void;
}

function UndoToastContainer({ toasts, onDismiss }: { toasts: UndoToast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 items-end pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.92 }}
            transition={{ duration: 0.22 }}
            className="pointer-events-auto flex items-center gap-3 rounded-xl bg-[#1c3d2f] text-white px-4 py-3 shadow-xl border border-[#2d5a47] min-w-[240px]"
          >
            <span className="text-sm font-medium flex-1">{toast.message}</span>
            <button
              onClick={toast.onUndo}
              className="text-[#7ecfa1] font-bold text-sm hover:text-white transition-colors cursor-pointer border-0 bg-transparent px-1"
            >
              Undo
            </button>
            <button
              onClick={() => onDismiss(toast.id)}
              className="text-white/50 hover:text-white transition-colors cursor-pointer border-0 bg-transparent"
            >
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

/* Reschedule Picker */

function ReschedulePicker({
  currentSlot,
  onSelect,
  onClose,
}: {
  currentSlot: string;
  onSelect: (slot: 'morning' | 'afternoon' | 'evening') => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  const slots = [
    { id: 'morning' as const, label: 'Morning', icon: '🌅' },
    { id: 'afternoon' as const, label: 'Afternoon', icon: '☀️' },
    { id: 'evening' as const, label: 'Evening', icon: '🌙' },
  ];

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, scale: 0.92, y: -6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.92 }}
      transition={{ duration: 0.15 }}
      className="absolute top-9 right-0 z-50 bg-white rounded-xl shadow-xl border border-[#cfe1d4] p-2 flex flex-col gap-1 min-w-[160px]"
    >
      <p className="text-[10px] font-bold uppercase tracking-widest text-[#2d5a47]/60 px-2 pt-1 pb-0.5">Move to slot</p>
      {slots.map((slot) => (
        <button
          key={slot.id}
          onClick={() => { if (slot.id !== currentSlot) { onSelect(slot.id); onClose(); } }}
          disabled={slot.id === currentSlot}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer border-0 text-left ${slot.id === currentSlot
            ? 'bg-[#edf6ef] text-[#2d5a47]/40 cursor-not-allowed'
            : 'hover:bg-[#f0f9f3] text-slate-700 hover:text-[#2d5a47]'
            }`}
        >
          <span>{slot.icon}</span>
          {slot.label}
          {slot.id === currentSlot && (
            <span className="ml-auto text-[9px] font-bold uppercase tracking-wider text-[#2d5a47]/40">current</span>
          )}
        </button>
      ))}
    </motion.div>
  );
}

/* Swap Drawer */

function SwapDrawer({
  activity,
  slot,
  dayIndex,
  actIndex,
  destination,
  travelStyle,
  onSwap,
  onClose,
}: {
  activity: ActivityItem;
  slot: string;
  dayIndex: number;
  actIndex: number;
  destination: string;
  travelStyle: string;
  onSwap: (alt: SwapAlternative) => void;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [alternatives, setAlternatives] = useState<SwapAlternative[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    // Parse city from place string "Place Name,City" format
    const placeParts = activity.place.split(',');
    const city = placeParts.length > 1 ? placeParts[placeParts.length - 1].trim() : destination;

    fetchSwapAlternatives({
      place: activity.place,
      category: activity.category,
      city,
      destination,
      travel_style: travelStyle,
    }).then((results) => {
      if (cancelled) return;
      if (results.length === 0) setError(true);
      setAlternatives(results);
      setLoading(false);
    });

    return () => { cancelled = true; };
  }, [activity.place, activity.category, destination, travelStyle]);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[9998] bg-slate-900/40 backdrop-blur-[2px] flex items-end sm:items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ y: 60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 60, opacity: 0 }}
          transition={{ type: 'spring', damping: 28, stiffness: 340 }}
          className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-[#cfe1d4] overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-3 p-5 border-b border-[#e7efe9]">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#2d5a47]/60">Swap Activity</p>
              <p className="text-base font-semibold text-slate-800 mt-0.5 leading-tight">{activity.place.split(',')[0]}</p>
              <span className="inline-flex items-center gap-1 mt-1 rounded-full bg-[#e8f3eb] px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-[#2d5a47]">
                {activity.category}
              </span>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-700 transition-colors cursor-pointer border-0 bg-transparent mt-0.5">
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="p-4 space-y-2.5 max-h-[55vh] overflow-y-auto">
            {loading && (
              <div className="flex flex-col items-center justify-center py-10 gap-3">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  className="w-8 h-8 rounded-full border-2 border-[#2d5a47] border-t-transparent"
                />
                <p className="text-sm text-slate-500">Finding alternatives nearby…</p>
              </div>
            )}

            {!loading && error && (
              <div className="text-center py-8 text-slate-500 text-sm">
                No alternatives found. Try again later.
              </div>
            )}

            {!loading && !error && alternatives.map((alt, idx) => (
              <motion.button
                key={alt.place_id || idx}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.07 }}
                onClick={() => { onSwap(alt); onClose(); }}
                className="w-full text-left rounded-xl border border-[#dfeae2] bg-[#f9fcfa] hover:bg-[#edf6ef] hover:border-[#aac7b4] p-3.5 transition-all cursor-pointer group border-0 shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    {alt.image && (
                      <img
                        src={alt.image}
                        alt={alt.name}
                        className="w-10 h-10 rounded-lg object-cover flex-shrink-0 border border-[#dfeae2]"
                        loading="lazy"
                      />
                    )}
                    <p className="font-semibold text-slate-800 text-sm leading-snug group-hover:text-[#2d5a47] transition-colors">{alt.name}</p>
                  </div>
                  {alt.rating != null && (
                    <span className="flex items-center gap-0.5 flex-shrink-0 bg-amber-50 border border-amber-200 rounded-full px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                      <Star size={9} className="fill-amber-500 text-amber-500" />
                      {alt.rating.toFixed(1)}
                    </span>
                  )}
                </div>
                {alt.description ? (
                  <p className="mt-1.5 text-xs text-slate-600 leading-relaxed line-clamp-2">
                    {alt.description}
                  </p>
                ) : alt.address ? (
                  <p className="mt-1 flex items-start gap-1 text-[11px] text-slate-500 leading-snug">
                    <MapPin size={10} className="flex-shrink-0 mt-0.5 text-[#2d5a47]/60" />
                    {alt.address.replace(/^[A-Z0-9+]+\s*,\s*/i, '').slice(0, 70)}
                  </p>
                ) : null}
                <p className="mt-2 text-[10px] font-bold uppercase tracking-wider text-[#2d5a47] opacity-0 group-hover:opacity-100 transition-opacity">
                  Tap to swap →
                </p>
              </motion.button>
            ))}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/* Activity Card */

function ActivityCard({
  activity,
  actIdx,
  slot,
  dayIndex,
  destination,
  travelStyle,
  onRemove,
  onSwap,
  onReschedule,
}: {
  activity: ActivityItem;
  actIdx: number;
  slot: string;
  dayIndex: number;
  destination: string;
  travelStyle: string;
  onRemove: () => void;
  onSwap: (alt: SwapAlternative) => void;
  onReschedule: (toSlot: 'morning' | 'afternoon' | 'evening') => void;
}) {
  const [showReschedule, setShowReschedule] = useState(false);
  const [showSwap, setShowSwap] = useState(false);

  if (!activity || !activity.place || !activity.place.trim() || activity.place.trim() === '-' || activity.place.trim() === '—') {
    return null;
  }

  return (
    <>
      <motion.div
        layout
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.2 }}
        className="rounded-xl border border-[#dfeae2] bg-[#f9fcfa] p-4 shadow-sm relative"
      >
        {/* Top row: category badge + duration + quick-action buttons */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            <span className="rounded-full bg-[#e8f3eb] px-2.5 py-0.5 text-[8px] font-bold uppercase tracking-[0.18em] text-[#2d5a47] whitespace-nowrap">
              {activity.category || 'Explore'}
            </span>
            <span className="text-[11px] sm:text-[12px] font-semibold text-slate-500 whitespace-nowrap">
              {activity.duration || '1.5h'}
            </span>
          </div>

          {/* Quick-action icon buttons */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {/* Remove */}
            <button
              onClick={(e) => { e.stopPropagation(); onRemove(); }}
              title="Remove this activity"
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-red-50 border border-red-200 text-red-600 hover:bg-red-100 hover:border-red-300 transition-all cursor-pointer text-[10px] font-bold uppercase tracking-wide"
            >
              <Trash2 size={11} />
              <span className="hidden sm:inline">Remove</span>
            </button>

            {/* Swap */}
            <button
              onClick={(e) => { e.stopPropagation(); setShowSwap(true); }}
              title="Find alternatives"
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-[#edf6ef] border border-[#aac7b4] text-[#2d5a47] hover:bg-[#dff0e5] hover:border-[#7ab898] transition-all cursor-pointer text-[10px] font-bold uppercase tracking-wide"
            >
              <RefreshCw size={11} />
              <span className="hidden sm:inline">Swap</span>
            </button>

            {/* Reschedule */}
            <div className="relative">
              <button
                onClick={(e) => { e.stopPropagation(); setShowReschedule((v) => !v); }}
                title="Move to a different time slot"
                className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 hover:bg-amber-100 hover:border-amber-300 transition-all cursor-pointer text-[10px] font-bold uppercase tracking-wide"
              >
                <Clock size={11} />
                <span className="hidden sm:inline">Move</span>
              </button>
              <AnimatePresence>
                {showReschedule && (
                  <ReschedulePicker
                    currentSlot={slot}
                    onSelect={(toSlot) => { onReschedule(toSlot); }}
                    onClose={() => setShowReschedule(false)}
                  />
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* Place name row with optional image */}
        <div className="flex gap-3 items-start">
          {activity.image && (
            <img
              src={activity.image}
              alt={activity.place}
              className="w-16 h-16 sm:w-20 sm:h-20 rounded-xl object-cover flex-shrink-0 border border-[#dfeae2] shadow-sm"
              loading="lazy"
            />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-base sm:text-lg font-semibold text-slate-800">{activity.place}</p>
            {activity.description && (
              <p className="mt-1 text-sm sm:text-[15px] leading-relaxed text-slate-700">{sanitizeText(activity.description)}</p>
            )}
          </div>
        </div>
        {activity.fun_fact && (
          <div className="mt-2 rounded-md bg-[#f0f7f2] p-2 text-[12px] sm:text-[13px] text-[#244b3d] border border-[#d6e8dc]">
            <span className="font-semibold mr-1">Fun Fact:</span>
            {sanitizeText(activity.fun_fact)}
          </div>
        )}
        {activity.tips && (
          <div className="mt-2 border-t border-[#e9f0eb] pt-2 text-[12px] sm:text-[13px] text-slate-600">
            <span className="mr-2 text-[#2d5a47]">•</span>
            {sanitizeText(activity.tips)}
          </div>
        )}
      </motion.div>

      {/* Swap Drawer — rendered as portal-level overlay */}
      {showSwap && (
        <SwapDrawer
          activity={activity}
          slot={slot}
          dayIndex={dayIndex}
          actIndex={actIdx}
          destination={destination}
          travelStyle={travelStyle}
          onSwap={onSwap}
          onClose={() => setShowSwap(false)}
        />
      )}
    </>
  );
}

/* Add Activity Drawer */

function AddActivityDrawer({
  slot,
  day,
  destination,
  travelStyle,
  onAdd,
  onClose,
}: {
  slot: string;
  day: DayPlan;
  destination: string;
  travelStyle: string;
  onAdd: (activity: ActivityItem) => void;
  onClose: () => void;
}) {
  const slotLabel = slot === 'morning' ? 'Morning' : slot === 'afternoon' ? 'Afternoon' : 'Evening';
  const slotIcon = slot === 'morning' ? '🌅' : slot === 'afternoon' ? '☀️' : '🌙';
  const placeholders = [
    `e.g. a famous local restaurant for ${slotLabel.toLowerCase()}`,
    `e.g. a heritage walk in the old city`,
    `e.g. riverside cafe with a view`,
    `e.g. top-rated museum nearby`,
  ];
  const placeholder = placeholders[Math.floor(Math.random() * placeholders.length)];

  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setTimeout(() => inputRef.current?.focus(), 120); }, []);

  // Parse city from first activity's place field, or fall back to destination
  const city = (() => {
    const allActivities = [...(day.morning ?? []), ...(day.afternoon ?? []), ...(day.evening ?? [])];
    if (allActivities.length > 0) {
      const parts = allActivities[0].place.split(',');
      if (parts.length > 1) return parts[parts.length - 1].trim();
    }
    return destination;
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    try {
      const result = await addActivity({
        query: query.trim(),
        slot,
        day_date: day.date,
        destination,
        city,
        travel_style: travelStyle,
      });
      if (!result) { setError('Could not find a matching place. Try a different description.'); setLoading(false); return; }
      onAdd(result);
      onClose();
    } catch {
      setError('Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[9998] bg-slate-900/40 backdrop-blur-[2px] flex items-end sm:items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ y: 50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 50, opacity: 0 }}
          transition={{ type: 'spring', damping: 28, stiffness: 340 }}
          className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-[#cfe1d4] overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-3 px-5 py-4 bg-[#2d5a47]">
            <div className="flex items-center gap-2">
              <span className="text-lg">{slotIcon}</span>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-white/60">Add to {slotLabel}</p>
                <p className="text-sm font-semibold text-white">{day.date} · {day.theme}</p>
              </div>
            </div>
            <button onClick={onClose} className="text-white/60 hover:text-white transition-colors cursor-pointer border-0 bg-transparent">
              <X size={18} />
            </button>
          </div>

          {/* Chat body */}
          <div className="px-5 pt-5 pb-4">
            <div className="mb-4 rounded-xl bg-[#f0f9f3] border border-[#cfe1d4] p-3.5">
              <p className="text-[11px] font-bold uppercase tracking-widest text-[#2d5a47]/60 mb-1">Beyond AI</p>
              <p className="text-sm text-slate-700 leading-relaxed">
                What would you like to add to your <span className="font-semibold text-[#2d5a47]">{slotLabel.toLowerCase()}</span> in <span className="font-semibold text-[#2d5a47]">{city}</span>? Describe it naturally and I'll find a real place for you.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div className="flex gap-2 items-center rounded-xl border-2 border-[#cfe1d4] bg-[#f9fcfa] px-3 py-2.5 focus-within:border-[#2d5a47] transition-colors">
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={placeholder}
                  disabled={loading}
                  className="flex-1 bg-transparent text-sm text-slate-800 placeholder-slate-400 outline-none border-0"
                />
                <button
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="flex-shrink-0 w-8 h-8 rounded-lg bg-[#2d5a47] text-white flex items-center justify-center disabled:opacity-40 hover:bg-[#234a3a] transition-colors cursor-pointer border-0"
                >
                  {loading ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}
                      className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent"
                    />
                  ) : (
                    <Send size={13} />
                  )}
                </button>
              </div>
              {error && <p className="text-xs text-red-500 font-medium">{error}</p>}
              {loading && (
                <p className="text-xs text-[#2d5a47]/70 animate-pulse">Finding and enriching your activity...</p>
              )}
            </form>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {['Local restaurant', 'Famous temple', 'Scenic viewpoint', 'Market walk'].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setQuery(suggestion + ' in ' + city)}
                  disabled={loading}
                  className="px-2.5 py-1 rounded-full border border-[#cfe1d4] bg-white text-[10px] font-medium text-slate-600 hover:bg-[#edf6ef] hover:border-[#aac7b4] hover:text-[#2d5a47] transition-all cursor-pointer"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/* Expandable Day Cards for Itinerary */

function DayCardList({
  days,
  destination,
  travelStyle,
  isPlannerAgent = false,
  onDaysChange,
}: {
  days: DayPlan[];
  destination: string;
  travelStyle: string;
  isPlannerAgent?: boolean;
  onDaysChange: (days: DayPlan[]) => void;
}) {
  const [expandedDays, setExpandedDays] = useState<Set<number>>(() => new Set(days.map((_, i) => i)));
  const [toasts, setToasts] = useState<UndoToast[]>([]);

  useEffect(() => {
    setExpandedDays(new Set(days.map((_, i) => i)));
  }, [days.length]);

  const toggleDay = useCallback((index: number) => {
    setExpandedDays((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addUndoToast = useCallback((message: string, undoFn: () => void) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, onUndo: () => { undoFn(); dismissToast(id); } }]);
    setTimeout(() => dismissToast(id), 5000);
  }, [dismissToast]);

  const removeActivity = useCallback((dayIdx: number, slot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, actIdx: number) => {
    const removed = days[dayIdx][slot][actIdx];
    const updatedDays = days.map((d, di) => {
      if (di !== dayIdx) return d;
      return { ...d, [slot]: d[slot].filter((_, ai) => ai !== actIdx) };
    });
    onDaysChange(updatedDays);
    addUndoToast(`Removed "${removed.place.split(',')[0]}"`, () => {
      onDaysChange(days);
    });
  }, [days, onDaysChange, addUndoToast]);

  const swapActivity = useCallback((dayIdx: number, slot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, actIdx: number, alt: SwapAlternative) => {
    const original = days[dayIdx][slot][actIdx];
    const cityName = original.place.split(',').slice(-1)[0]?.trim() || '';
    const cleanAddress = alt.address ? alt.address.replace(/^[A-Z0-9+]+\s*,\s*/i, '').trim() : '';

    const replacement: ActivityItem = {
      ...original,
      place: `${alt.name}, ${cityName}`.trim().replace(/,\s*$/, ''),
      description: alt.description || (alt.rating ? `A highly-rated destination (${alt.rating} stars) in ${cityName}.` : `A great spot in ${cityName}.`),
      tips: alt.tips || (cleanAddress ? `Located near ${cleanAddress}. Check opening hours before visiting.` : 'Check opening hours before visiting.'),
      fun_fact: alt.fun_fact || undefined,
      image: alt.image || undefined,
    };
    onDaysChange(days.map((d, di) => {
      if (di !== dayIdx) return d;
      const newSlot = [...(Array.isArray(d[slot]) ? d[slot] : [])];
      newSlot[actIdx] = replacement;
      return { ...d, [slot]: newSlot };
    }));
  }, [days, onDaysChange]);

  const rescheduleActivity = useCallback((dayIdx: number, fromSlot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, actIdx: number, toSlot: 'morning' | 'afternoon' | 'evening') => {
    if (fromSlot === toSlot) return;
    const fromList = Array.isArray(days[dayIdx][fromSlot]) ? days[dayIdx][fromSlot] : [];
    const activity = fromList[actIdx];
    if (!activity) return;
    onDaysChange(days.map((d, di) => {
      if (di !== dayIdx) return d;
      const toList = Array.isArray(d[toSlot]) ? d[toSlot] : [];
      return {
        ...d,
        [fromSlot]: (Array.isArray(d[fromSlot]) ? d[fromSlot] : []).filter((_, ai) => ai !== actIdx),
        [toSlot]: [...toList, { ...activity }],
      };
    }));
  }, [days, onDaysChange]);

  const addActivityToDay = useCallback((dayIdx: number, slot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, activity: ActivityItem) => {
    onDaysChange(days.map((d, di) => {
      if (di !== dayIdx) return d;
      const currentList = Array.isArray(d[slot]) ? d[slot] : [];
      return { ...d, [slot]: [...currentList, activity] };
    }));
  }, [days, onDaysChange]);

  return (
    <>
      <div className="space-y-5">
        {days.map((day, index) => (
          <DayCard
            key={`${day.date}-${index}`}
            day={day}
            index={index}
            isExpanded={expandedDays.has(index)}
            onToggle={() => toggleDay(index)}
            destination={destination}
            travelStyle={travelStyle}
            isPlannerAgent={isPlannerAgent}
            onRemoveActivity={(slot, actIdx) => removeActivity(index, slot, actIdx)}
            onSwapActivity={(slot, actIdx, alt) => swapActivity(index, slot, actIdx, alt)}
            onRescheduleActivity={(fromSlot, actIdx, toSlot) => rescheduleActivity(index, fromSlot, actIdx, toSlot)}
            onAddActivity={(slot, activity) => addActivityToDay(index, slot, activity)}
            onUpdateDay={(updated) => onDaysChange(days.map((d, di) => di === index ? updated : d))}
          />
        ))}
      </div>
      <UndoToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}

function DayCard({
  day,
  index,
  isExpanded,
  onToggle,
  destination,
  travelStyle,
  isPlannerAgent = false,
  onRemoveActivity,
  onSwapActivity,
  onRescheduleActivity,
  onAddActivity,
  onUpdateDay,
}: {
  day: DayPlan;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  destination: string;
  travelStyle: string;
  isPlannerAgent?: boolean;
  onRemoveActivity: (slot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, actIdx: number) => void;
  onSwapActivity: (slot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, actIdx: number, alt: SwapAlternative) => void;
  onRescheduleActivity: (fromSlot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, actIdx: number, toSlot: 'morning' | 'afternoon' | 'evening') => void;
  onAddActivity: (slot: keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>, activity: ActivityItem) => void;
  onUpdateDay?: (updated: DayPlan) => void;
}) {
  const slots = (['morning', 'afternoon', 'evening'] as const).filter(
    (slot) => Array.isArray(day[slot]) && day[slot].length > 0
  );

  const [activeSlot, setActiveSlot] = useState<string>(slots[0] || 'morning');
  const [showAddDrawer, setShowAddDrawer] = useState(false);

  // Close the add-activity drawer whenever the active slot changes
  useEffect(() => { setShowAddDrawer(false); }, [activeSlot]);

  // Build a short description from notes or first activity places
  const shortDesc = sanitizeText(day.notes)
    ? sanitizeText(day.notes).slice(0, 140) + (sanitizeText(day.notes).length > 140 ? '…' : '')
    : slots
      .map((s) => {
        const acts = day[s] as DayPlan['morning'];
        return acts?.[0]?.place;
      })
      .filter(Boolean)
      .join(' → ');

  return (
    <div className="rounded-[1.4rem] border-2 border-[#cfe1d4] bg-white shadow-[0_10px_24px_rgba(45,90,71,0.06)] overflow-hidden transition-all duration-300">
      {/* Day Card Header — Title of that day prominently on top */}
      <div
        onClick={onToggle}
        className="w-full text-left px-5 py-4 sm:px-6 sm:py-5 flex items-center justify-between gap-4 cursor-pointer hover:bg-[#f9fcfa] transition-colors border-b border-[#e7efe9] bg-gradient-to-r from-[#fbfdfb] via-[#f7fbf8] to-[#edf6ef]"
      >
        <div className="flex items-center gap-3.5 sm:gap-4 min-w-0">
          {/* Day number badge */}
          <div className="flex-shrink-0 w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-[#2d5a47] to-[#1c3d2f] flex flex-col items-center justify-center shadow-md border border-[#2d5a47]/20">
            <span className="text-[9px] font-bold uppercase tracking-widest text-white/70">Day</span>
            <span className="text-lg sm:text-xl font-bold text-white leading-none">{index + 1}</span>
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider text-[#2d5a47] bg-[#edf6ef] border border-[#cfe1d4] px-2.5 py-0.5 rounded-full">
                {day.date}
              </span>
              <span className="text-[11px] font-medium text-slate-400 hidden sm:inline">
                • {slots.length} time slots
              </span>
            </div>
            <h3 className="font-serif text-xl sm:text-2xl font-bold text-[#244b3d] leading-snug">
              {day.theme ? sanitizeText(day.theme) : `Day ${index + 1} Itinerary`}
            </h3>
            {shortDesc && !isExpanded && (
              <p className="text-xs text-slate-500 truncate mt-0.5">{shortDesc}</p>
            )}
          </div>
        </div>

        <button
          type="button"
          aria-label={isExpanded ? "Collapse Day" : "Expand Day"}
          className="flex-shrink-0 flex items-center gap-1.5 text-[11px] font-bold text-[#2d5a47] bg-white hover:bg-[#edf6ef] border border-[#cfe1d4] px-3.5 py-1.5 rounded-full shadow-2xs cursor-pointer transition-all"
        >
          <span>{isExpanded ? 'Collapse' : 'Expand'}</span>
          <span className={`transition-transform duration-300 text-xs ${isExpanded ? 'rotate-180' : ''}`}>▾</span>
        </button>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-5 pb-5 sm:px-6 sm:pb-6 pt-2">
          {/* Thin Interactive Slot Card Strip */}
          <div className="slot-card-strip mt-3">
            {(['morning', 'afternoon', 'evening'] as const).map((slot) => (
              <div
                key={slot}
                className={`slot-card-panel ${activeSlot === slot ? 'active' : ''}`}
                onClick={() => setActiveSlot(slot)}
              >
                <span className="slot-card-label">
                  {slot === 'morning' ? '🌅' : slot === 'afternoon' ? '☀️' : '🌙'}{' '}
                  {slot}
                  {Array.isArray(day[slot]) && day[slot].length > 0 && (
                    <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#2d5a47]/10 text-[9px] font-bold text-[#2d5a47]">
                      {day[slot].length}
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>

          {/* Expanded Slot Detail */}
          {activeSlot && (() => {
            const slotKey = activeSlot as keyof Pick<DayPlan, 'morning' | 'afternoon' | 'evening'>;
            return (
              <div key={activeSlot} className="mt-4 space-y-3 animate-fadeIn">
                <h4 className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#2d5a47]/80 mb-2">
                  {activeSlot} Plan
                </h4>
                {(() => {
                  const rawActivities = (day[slotKey] as ActivityItem[]) || [];
                  const activities = rawActivities.filter(
                    (a) => a && typeof a.place === 'string' && a.place.trim() && a.place.trim() !== '-' && a.place.trim() !== '—'
                  );
                  if (!activities || activities.length === 0) {
                    return (
                      <div className="rounded-xl border border-dashed border-[#cfe1d4] bg-[#f9fcfa]/50 p-5 text-center text-sm text-slate-400">
                        No activities planned for this slot.
                      </div>
                    );
                  }
                  return (
                    <AnimatePresence>
                      {activities.map((activity, actIdx) => (
                        <ActivityCard
                          key={`${slotKey}-${actIdx}-${activity.place}`}
                          activity={activity}
                          actIdx={actIdx}
                          slot={activeSlot}
                          dayIndex={index}
                          destination={destination}
                          travelStyle={travelStyle}
                          onRemove={() => onRemoveActivity(slotKey, actIdx)}
                          onSwap={(alt) => onSwapActivity(slotKey, actIdx, alt)}
                          onReschedule={(toSlot) => onRescheduleActivity(slotKey, actIdx, toSlot)}
                        />
                      ))}
                    </AnimatePresence>
                  );
                })()}

                {/* Add to this slot button */}
                <motion.button
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  onClick={() => setShowAddDrawer(true)}
                  className="w-full flex items-center justify-center gap-2 mt-2 py-2.5 rounded-xl border-2 border-dashed border-[#b8d4c1] bg-transparent hover:bg-[#edf6ef] hover:border-[#7ab898] transition-all cursor-pointer text-[#2d5a47]/70 hover:text-[#2d5a47] text-xs font-bold uppercase tracking-widest group"
                >
                  <Plus size={14} className="group-hover:scale-110 transition-transform" />
                  Add to {activeSlot}
                </motion.button>

                {showAddDrawer && (
                  <AddActivityDrawer
                    slot={activeSlot}
                    day={day}
                    destination={destination}
                    travelStyle={travelStyle}
                    onAdd={(activity) => onAddActivity(slotKey, activity)}
                    onClose={() => setShowAddDrawer(false)}
                  />
                )}
              </div>
            );
          })()}

          {/* Daily Notes */}
          {day.notes && (
            <div className="mt-4 rounded-xl border border-[#dfeae2] bg-[#edf6ef] p-3 text-sm sm:text-base leading-relaxed text-[#284b3d]">
              <span className="mr-2 font-semibold">Daily Note:</span>
              {sanitizeText(day.notes)}
            </div>
          )}

          {/* Stay for the Night — Hotel Options (Planner Agent only) */}
          {isPlannerAgent && day.hotel_options && day.hotel_options.length > 0 && (
            <div className="mt-5 rounded-2xl border border-[#cfe1d4] bg-[#f7faf8] p-4 sm:p-5 shadow-xs">
              <div className="flex items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#2d5a47]/10 text-[#2d5a47]">
                    <Hotel size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-[#244b3d]">
                      Stay for the Night — Hotel Options
                    </h4>
                    <p className="text-[11px] text-slate-500">Choose your preferred accommodation for Day {index + 1}</p>
                  </div>
                </div>
                {day.selected_hotel && (
                  <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-[#e3efe6] px-2.5 py-1 text-[10px] font-bold text-[#204437]">
                    ✓ Chosen: {day.selected_hotel.name}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {day.hotel_options.map((hotel, hIdx) => {
                  const isSelected = day.selected_hotel?.name === hotel.name || (!day.selected_hotel && hIdx === 0);
                  return (
                    <div
                      key={hotel.name}
                      className={`flex flex-col justify-between rounded-xl border p-3 transition-all ${isSelected
                        ? 'border-[#2d5a47] bg-white ring-2 ring-[#2d5a47]/20 shadow-sm'
                        : 'border-[#dfeae2] bg-white hover:border-[#b4d2be]'
                        }`}
                    >
                      <div>
                        {hotel.image_url && (
                          <img
                            src={hotel.image_url}
                            alt={hotel.name}
                            className="w-full h-24 rounded-lg object-cover mb-2 border border-[#dfeae2]"
                            loading="lazy"
                          />
                        )}
                        <div className="flex items-start justify-between gap-1">
                          <span className="text-[9px] font-bold uppercase tracking-wider text-[#2d5a47] bg-[#edf6ef] px-2 py-0.5 rounded">
                            {hotel.category || 'Hotel'}
                          </span>
                          {hotel.rating && (
                            <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">
                              ★ {hotel.rating}
                            </span>
                          )}
                        </div>
                        <h5 className="mt-1.5 text-xs sm:text-sm font-bold text-slate-800 line-clamp-1">{hotel.name}</h5>
                        {hotel.description && (
                          <p className="mt-1 text-[11px] text-slate-600 line-clamp-2 leading-relaxed">{hotel.description}</p>
                        )}
                      </div>

                      <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between">
                        <div>
                          <span className="text-xs sm:text-sm font-bold text-[#2d5a47]">
                            ₹{(hotel.price_per_night || 3500).toLocaleString('en-IN')}
                          </span>
                          <span className="text-[10px] text-slate-500"> / night</span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {hotel.booking_link && (
                            <a
                              href={hotel.booking_link}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-slate-500 hover:text-slate-800 px-2 py-1 rounded bg-slate-100 hover:bg-slate-200"
                            >
                              <span>View</span>
                              <ExternalLink size={9} />
                            </a>
                          )}
                          <button
                            onClick={() => {
                              onUpdateDay?.({ ...day, selected_hotel: hotel });
                            }}
                            className={`text-[10px] font-bold px-2.5 py-1 rounded-lg transition-all cursor-pointer ${isSelected
                              ? 'bg-[#2d5a47] text-white shadow-2xs'
                              : 'bg-[#edf6ef] text-[#2d5a47] hover:bg-[#dff0e5]'
                              }`}
                          >
                            {isSelected ? '✓ Chosen' : 'Select'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function ItineraryPage({ itinerary }: { itinerary: TripPlanResponse | null }) {
  const location = useLocation();
  const [resolvedItinerary, setResolvedItinerary] = useState<TripPlanResponse | null>(itinerary);
  // Mutable days — allows Remove / Swap / Reschedule without regenerating the trip
  const [mutableDays, setMutableDays] = useState<DayPlan[]>([]);

  useEffect(() => {
    const locationItinerary = (location.state as { itinerary?: TripPlanResponse } | null)?.itinerary;
    if (locationItinerary) {
      setResolvedItinerary(locationItinerary);
      setMutableDays(locationItinerary.days ?? []);
      window.localStorage.setItem('beyond-itinerary', JSON.stringify(locationItinerary));
      return;
    }

    try {
      const saved = window.localStorage.getItem('beyond-itinerary');
      if (saved) {
        const parsed = JSON.parse(saved) as TripPlanResponse;
        setResolvedItinerary(parsed);
        setMutableDays(parsed.days ?? []);
      }
    } catch {
      setResolvedItinerary(itinerary);
      setMutableDays(itinerary?.days ?? []);
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

  const { overview, fun_facts, must_try_food, hidden_gems, local_culture, travel_hacks, budget_info, places_covered } = resolvedItinerary;
  const isPlannerAgent = resolvedItinerary.source === 'planner_agent' || resolvedItinerary.planner_type === 'planner_agent';

  const [modifyQuery, setModifyQuery] = useState('');
  const [isModifying, setIsModifying] = useState(false);
  const [modifyToast, setModifyToast] = useState<{ type: 'info' | 'error'; text: string } | null>(null);
  const [optimizationConfirmation, setOptimizationConfirmation] = useState<OptimizationConfirmation | null>(null);
  const [isApplyingOptimization, setIsApplyingOptimization] = useState(false);

  const handleDismissOptimization = () => setOptimizationConfirmation(null);

  const handleApplyOptimization = async (category: 'transport' | 'hotel', selectedAlt: TransportAlternative | any) => {
    if (!resolvedItinerary || isApplyingOptimization) return;
    setIsApplyingOptimization(true);
    try {
      const result = await applyOptimization({
        itinerary: { ...resolvedItinerary, days: mutableDays },
        category,
        selected_alternative: selectedAlt,
        num_people: resolvedItinerary.request.number_of_people,
        days: resolvedItinerary.request.days,
      });
      if (result.success && result.itinerary) {
        const updated = result.itinerary;
        setResolvedItinerary(updated);
        if (updated.days) setMutableDays(updated.days);
        window.localStorage.setItem('beyond-itinerary', JSON.stringify(updated));
        setModifyToast({ type: 'info', text: result.message || 'Optimization applied!' });
      }
      setOptimizationConfirmation(null);
    } catch {
      setModifyToast({ type: 'error', text: 'Failed to apply optimization. Please try again.' });
    } finally {
      setIsApplyingOptimization(false);
    }
  };

  const handleModifyItinerary = async () => {
    const text = modifyQuery.trim();
    if (!text || isModifying || !resolvedItinerary) return;

    setIsModifying(true);
    setModifyToast(null);

    try {
      const currentPayload = {
        ...resolvedItinerary,
        days: mutableDays,
      };

      const result = await chatPlan({
        query: text,
        itinerary: currentPayload,
        destination: resolvedItinerary.request.destination,
        days: resolvedItinerary.request.days,
        travel_style: resolvedItinerary.request.travel_style,
        number_of_people: resolvedItinerary.request.number_of_people,
        party_type: resolvedItinerary.request.party_type,
      });

      // Budget optimization: show confirmation card, don't auto-mutate
      if (result.intent === 'budget_optimization' && result.optimization_confirmation?.requires_confirmation) {
        setOptimizationConfirmation(result.optimization_confirmation);
        setModifyToast({
          type: result.api_errors && result.api_errors.length > 0 ? 'error' : 'info',
          text: result.user_message || 'We found cheaper options. Review and confirm below.',
        });
        setModifyQuery('');
        return;
      }

      // Unsupported / out-of-scope query: show warning toast, preserve existing itinerary
      if (result.intent === 'unsupported_query') {
        setModifyToast({
          type: 'error',
          text: result.user_message || 'I cannot answer that query. Please ask a travel planning request.',
        });
        setModifyQuery('');
        return;
      }

      // Show error toast if any live API failed
      if (result.api_errors && result.api_errors.length > 0) {
        setModifyToast({
          type: 'error',
          text: result.api_errors.join(' | '),
        });
      }

      if (result.itinerary && result.itinerary.days && result.itinerary.days.length > 0) {
        setResolvedItinerary(result.itinerary);
        setMutableDays(result.itinerary.days);
        window.localStorage.setItem('beyond-itinerary', JSON.stringify(result.itinerary));
      }

      if (!result.api_errors || result.api_errors.length === 0) {
        setModifyToast({
          type: 'info',
          text: result.user_message || 'Itinerary updated according to your request.',
        });
      }
      setModifyQuery('');
    } catch {
      setModifyToast({
        type: 'error',
        text: 'Failed to update itinerary. Please try again with different phrasing.',
      });
    } finally {
      setIsModifying(false);
    }
  };

  return (
    <main className={`relative overflow-hidden bg-[#dfeee5] px-4 py-8 ${isPlannerAgent ? 'pb-24' : 'pb-12'} sm:px-6 lg:px-8`}>
      <div className="relative mx-auto max-w-5xl rounded-[2rem] border border-[#aac7b4] bg-[#f2f8f3]/90 p-4 shadow-[0_18px_40px_rgba(45,90,71,0.08)] sm:p-6 lg:p-8">
        <header className="pb-6 text-center border-b border-[#cfe1d4] mb-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.55em] text-[#2d5a47]/75">BEYOND TRAVEL GUIDE</p>
          <h1 className="mt-2 font-serif text-4xl italic text-[#274b3d] sm:text-5xl">{resolvedItinerary.request.destination}</h1>

          <div className="mt-3 flex flex-wrap items-center justify-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-[#2d5a47]">
            <span className="rounded-full bg-[#dbe8de] px-3 py-1">{resolvedItinerary.request.days} Days</span>
            <span>•</span>
            <span className="rounded-full bg-[#dbe8de] px-3 py-1">{resolvedItinerary.request.travel_style.replace('-', ' ')}</span>
            <span>•</span>
            <span className="rounded-full bg-[#dbe8de] px-3 py-1">{resolvedItinerary.request.party_type} ({resolvedItinerary.request.number_of_people} people)</span>
          </div>

          {places_covered && places_covered.length > 1 && (
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#274b3d]/80">Places Covered:</span>
              {places_covered.map((place) => (
                <span key={place} className="rounded-md border border-[#aac7b4] bg-white px-2.5 py-0.5 text-xs font-medium text-[#274b3d] shadow-sm">
                  {sanitizeText(place)}
                </span>
              ))}
            </div>
          )}
        </header>

        {/* Recommended Transit & Travel Option at Start (Planner Agent only) */}
        {isPlannerAgent && resolvedItinerary.best_flight && (() => {
          const trans = resolvedItinerary.best_flight;
          const modeLabel = trans.mode || 'Travel';
          const modeLower = modeLabel.toLowerCase();
          const renderTransitIcon = (size = 18) => {
            if (modeLower.includes('train') || modeLower.includes('rail')) return <Train size={size} />;
            if (modeLower.includes('bus')) return <Bus size={size} />;
            if (modeLower.includes('car') || modeLower.includes('drive') || modeLower.includes('cab') || modeLower.includes('road')) return <Car size={size} />;
            if (modeLower.includes('flight') || modeLower.includes('air') || modeLower.includes('plane')) return <Plane size={size} />;
            return <Navigation size={size} />;
          };
          const priceVal = trans.price_per_person || trans.price;
          const totalVal = trans.total_price || (priceVal ? priceVal * resolvedItinerary.request.number_of_people : null);

          const isTrainOrBus = modeLower.includes('train') || modeLower.includes('rail') || modeLower.includes('bus');
          const originCity = trans.origin || 'Origin';
          // If multiple destinations are listed (e.g. "Varanasi, Rishikesh, Haridwar"), pick the first one for transit
          const rawDest = trans.destination || resolvedItinerary.request.destination || '';
          const primaryDest = rawDest.split(/[,;/]|\s+and\s+|\s+&\s+/i)[0]?.trim() || rawDest;
          const transitHeading = isTrainOrBus
            ? `${originCity} to ${primaryDest} ${modeLabel}`
            : (trans.airline || trans.provider || `${modeLabel} Transit`) + (trans.identifier ? ` • ${trans.identifier}` : '');

          return (
            <div className="mb-6 rounded-[1.5rem] border border-[#a2c9b2] bg-gradient-to-br from-[#ffffff] via-[#f7fbf8] to-[#edf6f0] p-5 sm:p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4 border-b border-[#dfeae2] pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#2d5a47] text-white shadow-2xs">
                    {renderTransitIcon(18)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-[#2d5a47]">
                        RECOMMENDED {modeLabel.toUpperCase()} OPTION
                      </span>
                      <span className="rounded bg-[#e4f1e7] px-2 py-0.5 text-[10px] font-bold text-[#204437]">
                        {modeLabel}
                      </span>
                    </div>
                    <h3 className="text-base sm:text-lg font-bold text-slate-800">
                      {transitHeading}
                    </h3>
                  </div>
                </div>

                {priceVal ? (
                  <div className="text-right">
                    <div className="text-lg sm:text-2xl font-bold font-serif text-[#2d5a47]">
                      ₹{priceVal.toLocaleString('en-IN')}
                    </div>
                    <div className="text-[10px] font-medium text-slate-500">per person (one way)</div>
                  </div>
                ) : null}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                {/* Departure & Arrival Time Strip */}
                <div className="md:col-span-2 flex items-center justify-between rounded-xl bg-white p-3.5 border border-[#e4eee7] shadow-2xs">
                  <div>
                    <div className="text-xs text-slate-500 font-medium">
                      {trans.departure_time ? 'Departure' : 'Origin'}
                    </div>
                    {trans.departure_time && (
                      <div className="text-base sm:text-lg font-bold text-slate-800">
                        {trans.departure_time}
                      </div>
                    )}
                    <div className="text-[11px] font-semibold text-[#2d5a47]">
                      {trans.origin || 'Departure Point'}
                    </div>
                  </div>

                  <div className="flex flex-col items-center px-3">
                    <div className="text-[10px] font-bold text-slate-500">
                      {trans.duration || 'Direct Journey'}
                    </div>
                    <div className="w-24 sm:w-32 h-0.5 bg-[#aac7b4] my-1 relative flex items-center justify-center">
                      <div className="p-0.5 rounded-full bg-white border border-[#aac7b4] text-[#2d5a47]">
                        {renderTransitIcon(11)}
                      </div>
                    </div>
                    <div className="text-[9px] font-bold uppercase tracking-wider text-emerald-700">
                      {trans.stops || 'Direct Route'}
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-xs text-slate-500 font-medium">
                      {trans.arrival_time ? 'Arrival' : 'Destination'}
                    </div>
                    {trans.arrival_time && (
                      <div className="text-base sm:text-lg font-bold text-slate-800">
                        {trans.arrival_time}
                      </div>
                    )}
                    <div className="text-[11px] font-semibold text-[#2d5a47]">
                      {isTrainOrBus ? primaryDest : (trans.destination || resolvedItinerary.request.destination)}
                    </div>
                  </div>
                </div>

                {/* Action Button */}
                <div className="flex flex-col gap-1.5">
                  {modeLower.includes('drive') || modeLower.includes('car') || modeLower.includes('road') || modeLower.includes('self') ? (
                    <>
                      <div className="flex items-center justify-center gap-1.5 w-full py-2.5 px-3 rounded-xl bg-[#edf6ef] border border-[#b8d4c1] text-[#244b3d] font-bold text-xs uppercase tracking-wider text-center">
                        <Car size={14} />
                        <span>Self-Drive / Personal Vehicle</span>
                      </div>
                      <a
                        href={`https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(trans.origin || 'Mumbai')}&destination=${encodeURIComponent(primaryDest || resolvedItinerary.request.destination)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center justify-center gap-1 w-full py-1 text-[11px] font-semibold text-[#2d5a47] hover:underline cursor-pointer"
                      >
                        <span>View Route on Google Maps</span>
                        <ExternalLink size={10} />
                      </a>
                    </>
                  ) : (
                    <a
                      href={trans.booking_link || 'https://www.makemytrip.com'}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center justify-center gap-1.5 w-full py-3 px-4 rounded-xl bg-[#2d5a47] text-white font-bold text-xs uppercase tracking-wider hover:bg-[#234737] shadow-sm transition-all cursor-pointer"
                    >
                      <span>Book {modeLabel}</span>
                      <ExternalLink size={13} />
                    </a>
                  )}
                  {totalVal ? (
                    <div className="text-center text-[10px] text-slate-500">
                      Total for {resolvedItinerary.request.number_of_people} travellers: ₹{totalVal.toLocaleString('en-IN')}
                    </div>
                  ) : (
                    <div className="text-center text-[10px] text-slate-500">
                      Estimated travel for {resolvedItinerary.request.number_of_people} travellers
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })()}

        {/* Whole Budget Breakdown Card (Hotel + Transport + Restaurant) (Planner Agent only) */}
        {isPlannerAgent && resolvedItinerary.budget_breakdown && (
          <div className="mb-8 rounded-[1.5rem] border border-[#a8ceb8] bg-white p-5 sm:p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#edf6ef] text-[#2d5a47]">
                  <Wallet size={18} />
                </div>
                <div>
                  <h3 className="text-base sm:text-lg font-bold text-slate-800">
                    Total Estimated Trip Budget Breakdown
                  </h3>
                  <p className="text-xs text-slate-500">
                    All-inclusive estimate for {resolvedItinerary.request.days} days & {resolvedItinerary.request.number_of_people} travellers
                  </p>
                </div>
              </div>

              <div className="text-right">
                <div className="text-xl sm:text-2xl font-bold font-serif text-[#244b3d]">
                  ₹{(resolvedItinerary.budget_breakdown.grand_total || 0).toLocaleString('en-IN')}
                </div>
                <div className="text-[11px] font-semibold text-[#2d5a47]">
                  ≈ ₹{(resolvedItinerary.budget_breakdown.per_person_total || 0).toLocaleString('en-IN')} / person
                </div>
              </div>
            </div>

            {/* 3 Main Categories: Hotel + Transport + Restaurant */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 mb-4">
              {/* Hotel */}
              <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-3.5">
                <div className="flex items-center gap-1.5 text-blue-800 text-xs font-bold uppercase tracking-wider mb-1">
                  <Hotel size={14} />
                  <span>Hotel & Stay</span>
                </div>
                <div className="text-lg font-bold text-slate-800">
                  ₹{(resolvedItinerary.budget_breakdown.hotel_total || 0).toLocaleString('en-IN')}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  ₹{(resolvedItinerary.budget_breakdown.hotel_per_night || 0).toLocaleString('en-IN')} / night
                </div>
              </div>

              {/* Transport */}
              <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3.5">
                <div className="flex items-center gap-1.5 text-emerald-800 text-xs font-bold uppercase tracking-wider mb-1">
                  <Navigation size={14} />
                  <span>Transport & Travel</span>
                </div>
                <div className="text-lg font-bold text-slate-800">
                  ₹{(resolvedItinerary.budget_breakdown.transport_total || 0).toLocaleString('en-IN')}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Roundtrip for {resolvedItinerary.request.number_of_people} people
                </div>
              </div>

              {/* Restaurant */}
              <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3.5">
                <div className="flex items-center gap-1.5 text-amber-800 text-xs font-bold uppercase tracking-wider mb-1">
                  <Utensils size={14} />
                  <span>Food & Restaurants</span>
                </div>
                <div className="text-lg font-bold text-slate-800">
                  ₹{(resolvedItinerary.budget_breakdown.food_restaurant_total || 0).toLocaleString('en-IN')}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  ₹{(resolvedItinerary.budget_breakdown.food_per_day || 0).toLocaleString('en-IN')} / day for meals
                </div>
              </div>
            </div>

            {/* Extra Activities info */}
            {resolvedItinerary.budget_breakdown.activities_total ? (
              <div className="flex flex-wrap items-center justify-between text-xs text-slate-600 px-1 pt-2 border-t border-slate-100">
                <span>Sightseeing & Activities entry: <strong className="text-slate-800">₹{(resolvedItinerary.budget_breakdown.activities_total).toLocaleString('en-IN')}</strong></span>
                <span className="text-[11px] text-slate-500 font-medium">Estimated for {resolvedItinerary.budget_breakdown.tier || 'Mid-range'} travel tier</span>
              </div>
            ) : null}
          </div>
        )}



        {/* Day-by-Day Experience — Collapsible Cards */}
        <h2 className="mb-4 text-xl sm:text-2xl font-bold font-serif text-[#274b3d]">Day-by-Day Experience</h2>
        <DayCardList
          days={mutableDays}
          destination={resolvedItinerary.request.destination}
          travelStyle={resolvedItinerary.request.travel_style}
          isPlannerAgent={isPlannerAgent}
          onDaysChange={setMutableDays}
        />
      </div>

      {/* Sticky Live AI Itinerary Modification Dock at Screen Bottom (Planner Agent only) */}
      {isPlannerAgent && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t-2 border-[#2d5a47]/30 px-4 py-3 shadow-[0_-12px_40px_rgba(45,90,71,0.18)]">
          <div className="mx-auto max-w-5xl">
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-[#2d5a47] animate-pulse" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#244b3d]">
                  Modify Itinerary with AI
                </h4>
                <span className="text-[10px] text-slate-500 hidden sm:inline">• Ask to swap places, optimize budget, or change transport</span>
              </div>
            </div>

            {/* Optimization Confirmation Card */}
            {optimizationConfirmation?.requires_confirmation && (
              <div className="mb-3 rounded-2xl border border-[#2d5a47]/30 bg-gradient-to-br from-[#edf6ef] to-[#f4fbf5] p-4 shadow-md">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Wallet size={15} className="text-[#2d5a47]" />
                      <span className="text-xs font-bold uppercase tracking-wider text-[#2d5a47]">Budget Optimization Found</span>
                    </div>
                    {optimizationConfirmation.total_savings > 0 && (
                      <p className="mt-1 text-[11px] text-slate-500">
                        Potential savings up to{' '}
                        <strong className="text-[#2d5a47]">₹{optimizationConfirmation.total_savings.toLocaleString('en-IN')}</strong>
                      </p>
                    )}
                  </div>
                  <button onClick={handleDismissOptimization} className="text-slate-400 hover:text-slate-600 transition-colors" title="Dismiss">
                    <X size={14} />
                  </button>
                </div>

                {/* API Warning / Error banner if live search had issues */}
                {optimizationConfirmation.api_errors && optimizationConfirmation.api_errors.length > 0 && (
                  <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-800 flex items-start gap-1.5">
                    <span className="font-bold">Notice:</span>
                    <span>{optimizationConfirmation.api_errors.join('. ')}</span>
                  </div>
                )}

                {/* Transport alternatives */}
                {optimizationConfirmation.transport && (
                  <div className="mb-3">
                    <p className="text-[11px] font-semibold text-slate-600 mb-2">
                      Currently: <span className="text-slate-800">{optimizationConfirmation.transport.original_mode}</span>
                      {' '}·{' '}
                      <span className="text-slate-500">₹{optimizationConfirmation.transport.original_cost.toLocaleString('en-IN')}</span>
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      {optimizationConfirmation.transport.alternatives.map((alt, idx) => {
                        const isBest = idx === 0;
                        return (
                          <div
                            key={alt.mode}
                            className={`relative rounded-xl border p-2.5 flex flex-col gap-1.5 ${isBest
                              ? 'border-[#2d5a47] bg-[#2d5a47]/5 shadow-sm'
                              : 'border-slate-200 bg-white'
                              }`}
                          >
                            {isBest && (
                              <span className="absolute -top-2 left-2 rounded-full bg-[#2d5a47] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white">
                                Best Saving
                              </span>
                            )}
                            <div className="flex items-center gap-1.5">
                              {alt.mode.toLowerCase().includes('train') ? <Train size={13} className="text-[#2d5a47]" />
                                : alt.mode.toLowerCase().includes('bus') ? <Bus size={13} className="text-[#2d5a47]" />
                                  : <Car size={13} className="text-[#2d5a47]" />}
                              <span className="text-xs font-bold text-slate-800">{alt.mode}</span>
                              {alt.estimated && (
                                <span className="ml-auto text-[9px] text-slate-400 italic">est.</span>
                              )}
                            </div>
                            <p className="text-[10px] text-slate-500 truncate">
                              {alt.mode.toLowerCase().includes('train') || alt.mode.toLowerCase().includes('bus')
                                ? `${resolvedItinerary.best_flight?.origin || 'Origin'} to ${resolvedItinerary.request.destination.split(/[,;/]|\s+and\s+|\s+&\s+/i)[0]?.trim() || resolvedItinerary.request.destination} ${alt.mode}`
                                : alt.provider}
                            </p>
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-bold text-slate-800">₹{alt.new_cost.toLocaleString('en-IN')}</span>
                              {alt.savings > 0 && (
                                <span className="rounded-full bg-green-100 px-1.5 py-0.5 text-[9px] font-bold text-green-700">
                                  Save ₹{alt.savings.toLocaleString('en-IN')}
                                </span>
                              )}
                            </div>
                            <button
                              onClick={() => handleApplyOptimization('transport', alt)}
                              disabled={isApplyingOptimization}
                              className="mt-1 w-full rounded-lg bg-[#2d5a47] py-1.5 text-[10px] font-bold uppercase tracking-wider text-white hover:bg-[#214334] transition-colors disabled:opacity-50 cursor-pointer border-0"
                            >
                              {isApplyingOptimization ? <Loader2 size={11} className="animate-spin mx-auto" /> : `Switch to ${alt.mode}`}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Hotel alternative */}
                {optimizationConfirmation.hotel && (
                  <div className="border-t border-[#cfe1d4] pt-2 mt-2">
                    <p className="text-[11px] font-semibold text-slate-600 mb-1.5">
                      Hotel swap: <span className="line-through text-slate-400">{optimizationConfirmation.hotel.original_name}</span>
                      {' → '}
                      <span className="text-slate-800">{optimizationConfirmation.hotel.suggested_name}</span>
                      {' '}
                      <span className="text-green-600 font-bold">Save ₹{optimizationConfirmation.hotel.savings.toLocaleString('en-IN')}</span>
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApplyOptimization('hotel', {
                          ...optimizationConfirmation.hotel!.details,
                          name: optimizationConfirmation.hotel!.suggested_name,
                          new_cost: optimizationConfirmation.hotel!.new_cost,
                          booking_link: optimizationConfirmation.hotel!.booking_link,
                        })}
                        disabled={isApplyingOptimization}
                        className="flex-1 rounded-lg bg-[#2d5a47] py-1.5 text-[10px] font-bold uppercase tracking-wider text-white hover:bg-[#214334] transition-colors disabled:opacity-50 cursor-pointer border-0"
                      >
                        Switch Hotel
                      </button>
                    </div>
                  </div>
                )}

                <button
                  onClick={handleDismissOptimization}
                  className="mt-2 w-full rounded-lg border border-slate-200 bg-white py-1.5 text-[10px] font-semibold text-slate-500 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  Keep Current Options
                </button>
              </div>
            )}

            {modifyToast && (
              <div className={`mb-2 rounded-lg px-3 py-1.5 text-xs font-medium ${modifyToast.type === 'info' ? 'bg-[#edf6ef] text-[#244b3d] border border-[#cfe1d4]' : 'bg-red-50 text-red-700 border border-red-200'}`}>
                {modifyToast.text}
              </div>
            )}

            <form onSubmit={(e) => { e.preventDefault(); handleModifyItinerary(); }} className="flex items-center gap-2">
              <input
                type="text"
                value={modifyQuery}
                onChange={(e) => setModifyQuery(e.target.value)}
                placeholder="e.g. 'Optimize budget and switch to train' or 'Add more riverside cafes on day 2'…"
                disabled={isModifying}
                className="flex-1 rounded-xl border border-[#cfe1d4] bg-[#fbfdfb] px-4 py-2.5 text-sm text-slate-800 outline-none focus:border-[#2d5a47] focus:ring-1 focus:ring-[#2d5a47] disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={!modifyQuery.trim() || isModifying}
                className={`flex-shrink-0 h-[42px] px-5 rounded-xl flex items-center justify-center gap-1.5 text-xs font-bold uppercase tracking-wider transition-all cursor-pointer border-0 ${modifyQuery.trim() && !isModifying
                  ? 'bg-[#2d5a47] text-white hover:bg-[#214334] shadow-md hover:scale-105 active:scale-95'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  }`}
              >
                {isModifying ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                <span>{isModifying ? 'Updating…' : 'Update'}</span>
              </button>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

/* Footer */

function Footer() {
  return (
    <footer className="border-t border-[#c6dccb] bg-[#1a382b] text-white">
      <div className="mx-auto max-w-7xl px-6 py-14 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10">
          {/* Brand Info */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center gap-3">
              <img src={logoImg} alt="Beyond Logo" className="h-12 w-auto brightness-0 invert" />
              <span className="text-2xl font-bold tracking-[0.2em] font-serif text-white">BEYOND</span>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed max-w-sm">
              Intelligent travel planning crafted for the spirit of India. Adaptive day-by-day itineraries tailored around your pace, verified places, live weather, and seamless flexibility.
            </p>
            <div className="pt-2 flex flex-wrap items-center gap-2 text-xs text-[#a3d9bc]">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 border border-white/15">
                <Sparkles size={13} className="text-[#f9c6d0]" /> Multi-Agent AI Core
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 border border-white/15">
                <CheckCircle2 size={13} className="text-[#a3d9bc]" /> Verified Google Places
              </span>
            </div>
          </div>

          {/* Explore */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-[0.25em] text-[#a3d9bc] mb-4">Explore</h4>
            <ul className="space-y-2.5 text-sm text-slate-300">
              <li><a href="#destinations" className="hover:text-white transition-colors">Rajasthan Heritage</a></li>
              <li><a href="#destinations" className="hover:text-white transition-colors">Kerala Backwaters</a></li>
              <li><a href="#destinations" className="hover:text-white transition-colors">Kashmir Valleys</a></li>
              <li><a href="#destinations" className="hover:text-white transition-colors">Himachal Heights</a></li>
              <li><a href="#destinations" className="hover:text-white transition-colors">Goa Coastline</a></li>
              <li><a href="#destinations" className="hover:text-white transition-colors">Meghalaya Trails</a></li>
            </ul>
          </div>

          {/* How It Works */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-[0.25em] text-[#a3d9bc] mb-4">How It Works</h4>
            <ul className="space-y-2.5 text-sm text-slate-300">
              <li><a href="#how-it-works" className="hover:text-white transition-colors">Adaptive Weather Sync</a></li>
              <li><a href="#how-it-works" className="hover:text-white transition-colors">1-Tap Place Swapper</a></li>
              <li><a href="#how-it-works" className="hover:text-white transition-colors">Smart Pacing Engine</a></li>
              <li><a href="#how-it-works" className="hover:text-white transition-colors">Zero-Friction Reschedule</a></li>
              <li><Link to="/itinerary" className="hover:text-white transition-colors">My Itinerary View</Link></li>
            </ul>
          </div>

          {/* Travel Styles */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-[0.25em] text-[#a3d9bc] mb-4">Travel Styles</h4>
            <ul className="space-y-2.5 text-sm text-slate-300">
              <li className="flex items-center gap-2"><Palmtree size={14} className="text-[#a3d9bc]" /><span>Calm & Relaxed</span></li>
              <li className="flex items-center gap-2"><Mountain size={14} className="text-[#a3d9bc]" /><span>Adventure & Nature</span></li>
              <li className="flex items-center gap-2"><Landmark size={14} className="text-[#a3d9bc]" /><span>Historical & Cultural</span></li>
              <li className="flex items-center gap-2"><Flower2 size={14} className="text-[#a3d9bc]" /><span>Spiritual & Peace</span></li>
              <li className="flex items-center gap-2"><Music size={14} className="text-[#a3d9bc]" /><span>Party & Nightlife</span></li>
              <li className="flex items-center gap-2"><UtensilsCrossed size={14} className="text-[#a3d9bc]" /><span>Foodie & Culinary</span></li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-12 pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
          <p>© {new Date().getFullYear()} Beyond Travel Technologies. All rights reserved.</p>
          <p className="flex items-center gap-1.5">
            Made with <Heart size={13} className="text-red-400 fill-red-400 inline" /> by <span className="text-white font-semibold">Pratishtha Sharma</span>
          </p>
          <div className="flex gap-6">
            <a href="#privacy" className="hover:text-white transition-colors">Privacy Policy</a>
            <a href="#terms" className="hover:text-white transition-colors">Terms of Service</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default App;
