import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowLeft,
  BrainCircuit,
  Bus,
  Car,
  Hotel,
  Loader2,
  Plane,
  Send,
  Sparkles,
  Train,
  Wallet,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatPlan } from '../services/api';

/* Types */

interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  text: string;
  timestamp: Date;
}

interface QuickFilters {
  hotel: string;
  budget: string;
  transport: string;
}

/* Constants */

const HOTEL_OPTIONS = ['Budget / Hostel', 'Mid-range', 'Boutique', 'Luxury / Resort'];
const BUDGET_OPTIONS = ['< ₹5K / day', '₹5K – ₹15K', '₹15K – ₹30K', '₹30K+'];
const TRANSPORT_OPTIONS = [
  { label: 'Flight', icon: Plane },
  { label: 'Train', icon: Train },
  { label: 'Bus', icon: Bus },
  { label: 'Self-drive', icon: Car },
];

/* Chip */

function Chip({
  label,
  selected,
  icon: Icon,
  onClick,
}: {
  label: string;
  selected: boolean;
  icon?: React.ElementType;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs transition-all duration-200 cursor-pointer select-none whitespace-nowrap ${selected
        ? 'bg-[#2d5a47] border-2 border-[#2d5a47] text-white font-bold shadow-sm'
        : 'bg-white border border-slate-300 dark:border-slate-700 text-slate-700 font-medium hover:bg-slate-50 hover:border-[#2d5a47]'
        }`}
    >
      {Icon && <Icon size={12} className={selected ? 'text-white' : 'text-[#2d5a47]'} />}
      {label}
    </button>
  );
}

/* FilterCard */

function FilterCard({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex-1 min-w-[200px] bg-white rounded-2xl border-2 border-[#cfe1d4] p-4 shadow-[0_4px_16px_rgba(45,90,71,0.06)] flex flex-col gap-3">
      <div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#edf6ef] border border-[#cfe1d4] text-[10px] font-bold uppercase tracking-[0.2em] text-[#2d5a47]">
          <Icon size={12} />
          {title}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

/* Typing / Planning Indicator */

function TypingIndicator({ status }: { status?: string }) {
  return (
    <div className="flex items-end gap-3 justify-start">
      <span className="w-8 h-8 rounded-full bg-gradient-to-br from-[#2d5a47] to-[#1c3d2f] flex items-center justify-center flex-shrink-0 shadow-md">
        <BrainCircuit size={14} className="text-white" />
      </span>
      <div className="bg-white border border-[#dfeae2] rounded-2xl rounded-bl-none px-4 py-3 shadow-sm flex gap-2.5 items-center">
        <Loader2 size={15} className="animate-spin text-[#2d5a47]" />
        <span className="text-xs sm:text-sm font-medium text-[#2d5a47]">
          {status || 'Generating itinerary with LangGraph Planner…'}
        </span>
      </div>
    </div>
  );
}

/* Message Bubble */

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex items-start gap-3 w-full ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {!isUser && (
        <span className="w-8 h-8 rounded-full bg-gradient-to-br from-[#2d5a47] to-[#1c3d2f] flex items-center justify-center flex-shrink-0 shadow-md mt-1">
          <BrainCircuit size={15} className="text-white" />
        </span>
      )}
      {isUser && (
        <span className="w-8 h-8 rounded-full bg-gradient-to-br from-[#f9c6d0] to-[#e8a0ac] flex items-center justify-center flex-shrink-0 shadow-md mt-1">
          <span className="text-[11px] font-bold text-[#6b2c3a]">You</span>
        </span>
      )}
      <div
        className={`max-w-[85%] sm:max-w-[78%] px-5 py-3.5 shadow-sm text-sm sm:text-base leading-relaxed whitespace-pre-wrap ${isUser
          ? 'bg-[#2d5a47] text-white rounded-2xl rounded-tr-none font-sans shadow-[0_4px_16px_rgba(45,90,71,0.15)]'
          : 'bg-white border border-[#cfe1d4] text-slate-800 rounded-2xl rounded-tl-none shadow-[0_4px_16px_rgba(45,90,71,0.06)]'
          }`}
      >
        {msg.text}
      </div>
    </motion.div>
  );
}

/* Starter Suggestions */

const STARTER_PROMPTS = [
  '🏖️ 5-day relaxing beach getaway in South Goa with seafood & sunset cruises',
  '🏰 7-day royal heritage & fort tour across Jaipur, Udaipur & Jodhpur with family',
  '🌲 4-day peaceful mountain retreat in Manali with cafe hopping & valley treks',
  '🕉️ 6-day spiritual & cultural journey through Varanasi, Rishikesh & Haridwar',
];

/* Main Component */

export default function BuildTripPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [planningStatus, setPlanningStatus] = useState('');
  const [filters, setFilters] = useState<QuickFilters>({ hotel: '', budget: '', transport: '' });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* Scroll page to top on mount */
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 140)}px`;
  }, [input]);

  const handleFilter = (key: keyof QuickFilters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: prev[key] === value ? '' : value }));
  };

  const buildContextMessage = () => {
    const parts: string[] = [];
    if (filters.hotel) parts.push(`Hotel preference: ${filters.hotel}`);
    if (filters.budget) parts.push(`Budget: ${filters.budget}`);
    if (filters.transport) parts.push(`Transport: ${filters.transport}`);
    if (parts.length === 0) return null;
    return `[Quick details — ${parts.join(' | ')}]`;
  };

  const [showOriginModal, setShowOriginModal] = useState(false);
  const [pendingText, setPendingText] = useState('');
  const [customOrigin, setCustomOrigin] = useState('');

  const COMMON_ORIGINS = ['Mumbai', 'Delhi', 'Bangalore', 'Kolkata', 'Hyderabad', 'Pune', 'Chennai', 'Ahmedabad'];

  const triggerSendWithOrigin = (chosenOrigin: string) => {
    setShowOriginModal(false);
    const query = pendingText ? `[Departing from: ${chosenOrigin}] ${pendingText}` : `Departing from ${chosenOrigin}`;
    setPendingText('');
    setCustomOrigin('');
    executeSendMessage(query);
  };

  const sendMessage = (customText?: string) => {
    const rawText = customText ?? input;
    const text = rawText.trim();
    if (!text || isTyping) return;

    // Check if origin/source is already mentioned in query or filters
    const hasOrigin = /\b(?:from|starting\s+from|departing\s+from|origin\s*:?|leaving\s+from)\s+[a-zA-Z]+/i.test(text);
    if (!hasOrigin && !filters.transport?.toLowerCase().includes('from')) {
      setPendingText(text);
      setShowOriginModal(true);
      return;
    }

    executeSendMessage(text);
  };

  const executeSendMessage = async (text: string) => {
    const contextNote = buildContextMessage();
    const fullText = contextNote ? `${contextNote}\n\n${text}` : text;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      text: fullText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);
    setPlanningStatus('Connecting with Planner Agent & LangGraph…');

    try {
      setPlanningStatus('Searching places, hotels & transport…');
      const result = await chatPlan({
        query: fullText,
        hotel_type: filters.hotel || undefined,
        budget_tier: filters.budget || undefined,
        transport_type: filters.transport || undefined,
      });

      if (result.itinerary && result.itinerary.days && result.itinerary.days.length > 0) {
        setPlanningStatus('Itinerary ready! Opening experience…');
        window.localStorage.setItem('beyond-itinerary', JSON.stringify(result.itinerary));
        // Direct navigation to standard itinerary output view
        navigate('/itinerary', { state: { itinerary: result.itinerary } });
      } else {
        const aiMsg: ChatMessage = {
          id: `a-${Date.now()}`,
          role: 'ai',
          text: result.user_message || 'I have processed your request.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMsg]);
      }
    } catch (err: any) {
      console.error('Chat plan error:', err);
      const aiMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: 'ai',
        text: 'Sorry, I encountered an issue connecting to the planner agent. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } finally {
      setIsTyping(false);
      setPlanningStatus('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const hasFilters = filters.hotel || filters.budget || filters.transport;

  return (
    <div className="flex flex-col min-h-[calc(100vh-72px)] bg-gradient-to-b from-[#eaf5ee] via-[#f4faf6] to-[#fef9f4]">
      {/* Page Header */}
      <div className="hero-stripes relative overflow-hidden border-b border-[#cfe1d4]/60">
        <div className="bg-white/25 backdrop-blur-[2px] px-6 py-5 md:py-6">
          <div className="mx-auto max-w-4xl">
            <button
              onClick={() => navigate(-1)}
              className="inline-flex items-center gap-1.5 text-[#2d5a47] hover:text-[#1b382c] text-xs font-semibold transition-colors mb-2 cursor-pointer border-0 bg-white/70 hover:bg-white px-2.5 py-1 rounded-full shadow-xs"
            >
              <ArrowLeft size={13} />
              Back
            </button>

            <div className="space-y-1">
              <h1 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-bold text-[#244b3d] leading-tight">
                Define your dream trip,{' '}
                <span className="text-[#2d5a47]">we'll make it real.</span>
              </h1>
              <p className="text-slate-600 text-xs sm:text-sm max-w-xl">
                Describe your ideal journey in your own words. Use the quick options below to give us a headstart, or just type freely.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="mx-auto w-full max-w-4xl px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6 flex-1">
        {/* Quick Filter Cards */}
        <div className="flex gap-3 flex-wrap">
          <FilterCard icon={Hotel} title="Hotel Type">
            {HOTEL_OPTIONS.map((opt) => (
              <Chip
                key={opt}
                label={opt}
                selected={filters.hotel === opt}
                onClick={() => handleFilter('hotel', opt)}
              />
            ))}
          </FilterCard>

          <FilterCard icon={Wallet} title="Budget">
            {BUDGET_OPTIONS.map((opt) => (
              <Chip
                key={opt}
                label={opt}
                selected={filters.budget === opt}
                onClick={() => handleFilter('budget', opt)}
              />
            ))}
          </FilterCard>

          <FilterCard icon={Plane} title="Transport">
            {TRANSPORT_OPTIONS.map(({ label, icon }) => (
              <Chip
                key={label}
                label={label}
                icon={icon}
                selected={filters.transport === label}
                onClick={() => handleFilter('transport', label)}
              />
            ))}
          </FilterCard>
        </div>

        {/* Starter Prompts (Shown when no messages yet) */}
        {messages.length === 0 && !isTyping && (
          <div className="mt-2 space-y-3">
            <p className="text-xs font-bold uppercase tracking-wider text-[#2d5a47]/70">
              Need inspiration? Try one of these:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  className="text-left p-3.5 rounded-xl bg-white/80 hover:bg-white border border-[#cfe1d4] hover:border-[#2d5a47] text-slate-700 hover:text-[#2d5a47] text-xs leading-relaxed transition-all shadow-xs hover:shadow-md cursor-pointer group"
                >
                  <span className="font-medium group-hover:underline">{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Conversation Stream */}
        {(messages.length > 0 || isTyping) && (
          <div className="flex flex-col gap-4 py-2">
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} />
              ))}
              {isTyping && (
                <motion.div
                  key="typing"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  <TypingIndicator status={planningStatus} />
                </motion.div>
              )}
            </AnimatePresence>
            <div ref={messagesEndRef} className="h-2" />
          </div>
        )}
      </div>

      {/* Sticky ChatGPT-Style Input Container */}
      <div className="sticky bottom-0 z-30 w-full bg-gradient-to-t from-[#fef9f4] via-[#fef9f4]/95 to-transparent backdrop-blur-[4px] pt-4 pb-5 px-4 sm:px-6 lg:px-8 border-t border-[#cfe1d4]/40 shadow-[0_-8px_24px_rgba(45,90,71,0.03)]">
        <div className="mx-auto max-w-4xl">
          {/* Active filter pills */}
          {hasFilters && (
            <div className="flex flex-wrap items-center gap-1.5 mb-2 px-1">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mr-1">Active filters:</span>
              {filters.hotel && (
                <button
                  onClick={() => handleFilter('hotel', filters.hotel)}
                  className="inline-flex items-center gap-1 bg-[#edf6ef] hover:bg-[#dfeee3] border border-[#cfe1d4] rounded-full px-2.5 py-0.5 text-[11px] font-semibold text-[#2d5a47] cursor-pointer transition-colors"
                >
                  <Hotel size={10} /> {filters.hotel} <span className="text-[#2d5a47]/60 ml-0.5">×</span>
                </button>
              )}
              {filters.budget && (
                <button
                  onClick={() => handleFilter('budget', filters.budget)}
                  className="inline-flex items-center gap-1 bg-[#edf6ef] hover:bg-[#dfeee3] border border-[#cfe1d4] rounded-full px-2.5 py-0.5 text-[11px] font-semibold text-[#2d5a47] cursor-pointer transition-colors"
                >
                  <Wallet size={10} /> {filters.budget} <span className="text-[#2d5a47]/60 ml-0.5">×</span>
                </button>
              )}
              {filters.transport && (
                <button
                  onClick={() => handleFilter('transport', filters.transport)}
                  className="inline-flex items-center gap-1 bg-[#edf6ef] hover:bg-[#dfeee3] border border-[#cfe1d4] rounded-full px-2.5 py-0.5 text-[11px] font-semibold text-[#2d5a47] cursor-pointer transition-colors"
                >
                  <Plane size={10} /> {filters.transport} <span className="text-[#2d5a47]/60 ml-0.5">×</span>
                </button>
              )}
            </div>
          )}

          {/* Floating ChatGPT input bar */}
          <div className="relative bg-white rounded-2xl sm:rounded-3xl border-2 border-[#2d5a47]/60 focus-within:border-[#2d5a47] shadow-[0_4px_24px_rgba(45,90,71,0.12)] focus-within:shadow-[0_8px_32px_rgba(45,90,71,0.18)] transition-all duration-200 overflow-hidden">
            <div className="flex items-end gap-2.5 px-4 sm:px-5 py-3">
              <textarea
                ref={textareaRef}
                id="trip-chat-input"
                value={input}
                disabled={isTyping}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe your dream trip… e.g. '7-day royal heritage & fort tour across Jaipur, Udaipur & Jodhpur with family'"
                rows={1}
                className="flex-1 resize-none border-0 outline-none bg-transparent text-slate-800 placeholder-slate-400 text-sm sm:text-base leading-relaxed py-1 disabled:opacity-60"
                style={{ minHeight: '28px', maxHeight: '140px', fontFamily: 'Outfit, sans-serif' }}
              />
              <button
                id="trip-chat-send"
                onClick={() => sendMessage()}
                disabled={!input.trim() || isTyping}
                aria-label="Send message"
                className={`flex-shrink-0 w-10 h-10 rounded-xl sm:rounded-2xl flex items-center justify-center transition-all duration-200 cursor-pointer border-0 ${input.trim() && !isTyping
                  ? 'bg-[#2d5a47] text-white shadow-md hover:bg-[#214334] hover:scale-105 active:scale-95'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  }`}
              >
                {isTyping ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between px-2 pt-2">
            <p className="text-[11px] text-slate-500 font-medium">
              Press{' '}
              <kbd className="bg-white border border-slate-200 rounded px-1.5 py-0.5 font-mono text-[10px] shadow-2xs">
                Enter ↵
              </kbd>{' '}
              to generate ·{' '}
              <kbd className="bg-white border border-slate-200 rounded px-1.5 py-0.5 font-mono text-[10px] shadow-2xs">
                Shift + Enter
              </kbd>{' '}
              for new line
            </p>
            <p className="text-[11px] text-slate-400 hidden sm:block">
              Beyond Multi-Agent AI Core
            </p>
          </div>
        </div>
      </div>

      {/* Missing Origin Dialog Pop-up Modal */}
      <AnimatePresence>
        {showOriginModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="w-full max-w-lg rounded-3xl bg-white p-6 sm:p-7 shadow-2xl border border-[#cfe1d4]"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf6ef] text-[#2d5a47]">
                  <Plane size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-800">Where are you starting from?</h3>
                  <p className="text-xs text-slate-500">
                    To calculate accurate transit options & budget, please select your departure city:
                  </p>
                </div>
              </div>

              {/* Quick city pills */}
              <div className="my-4">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2 block">
                  Popular Starting Cities
                </label>
                <div className="flex flex-wrap gap-2">
                  {COMMON_ORIGINS.map((city) => (
                    <button
                      key={city}
                      onClick={() => triggerSendWithOrigin(city)}
                      className="px-3.5 py-1.5 rounded-full text-xs font-semibold bg-[#f4faf6] hover:bg-[#2d5a47] text-[#244b3d] hover:text-white border border-[#cfe1d4] hover:border-[#2d5a47] transition-all cursor-pointer shadow-2xs"
                    >
                      {city}
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom input */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (customOrigin.trim()) {
                    triggerSendWithOrigin(customOrigin.trim());
                  }
                }}
                className="mt-4 pt-3 border-t border-slate-100"
              >
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1.5 block">
                  Or enter another departure city
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={customOrigin}
                    onChange={(e) => setCustomOrigin(e.target.value)}
                    placeholder="e.g. Lucknow, Chandigarh, Goa…"
                    className="flex-1 rounded-xl border border-[#cfe1d4] bg-[#fbfdfb] px-4 py-2.5 text-sm text-slate-800 outline-none focus:border-[#2d5a47] focus:ring-1 focus:ring-[#2d5a47]"
                  />
                  <button
                    type="submit"
                    disabled={!customOrigin.trim()}
                    className="rounded-xl bg-[#2d5a47] px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#214334] disabled:opacity-50 cursor-pointer shadow-sm"
                  >
                    Continue
                  </button>
                </div>
              </form>

              <div className="mt-5 flex items-center justify-between pt-2">
                <button
                  onClick={() => setShowOriginModal(false)}
                  className="text-xs text-slate-400 hover:text-slate-600 font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={() => triggerSendWithOrigin('Mumbai')}
                  className="text-xs text-[#2d5a47] hover:underline font-semibold cursor-pointer"
                >
                  Skip & Use Mumbai (Default) →
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
