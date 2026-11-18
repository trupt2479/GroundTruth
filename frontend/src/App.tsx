import React, { useState } from 'react';
import { FlightSearch } from './components/FlightSearch';
import { GroundRealityCard } from './components/GroundRealityCard';
import { InboundVisualizer } from './components/InboundVisualizer';
import { useFlightStream } from './hooks/useFlightStream';
import { RealityAssessment } from './types/flight';
import { Activity, Radio, AlertCircle, Bookmark } from 'lucide-react';
import { WatchlistDrawer } from './components/WatchlistDrawer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const App: React.FC = () => {
  const [activeQuery, setActiveQuery] = useState<{
    carrier: string;
    flightNumber: string;
    date: string;
    origin?: string;
    destination?: string;
    scanTrigger: number;
  } | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [initialAssessment, setInitialAssessment] = useState<RealityAssessment | null>(null);
  const [isWatchlistOpen, setIsWatchlistOpen] = useState(false);
  const [watchlistCount, setWatchlistCount] = useState<number>(0);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  const fetchWatchlistCount = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/watchlist?user_name=Trupti`);
      if (res.ok) {
        const data = await res.json();
        setWatchlistCount(Array.isArray(data) ? data.length : 0);
      }
    } catch {
      // ignore
    }
  };

  React.useEffect(() => {
    fetchWatchlistCount();
  }, [refreshTrigger]);

  // Subscribe to real-time SSE stream - fires ONLY when activeQuery is populated by clicking "Scan Turnaround Physics"
  const {
    assessment: streamedAssessment,
    isConnected,
    isReconnecting,
    error: streamError,
    lastTickTime,
  } = useFlightStream(
    activeQuery?.carrier || null,
    activeQuery?.flightNumber || null,
    activeQuery?.date || null,
    activeQuery?.origin || null,
    activeQuery?.destination || null,
    activeQuery?.scanTrigger
  );

  const handleSearch = async (
    carrier: string,
    flightNumber: string,
    date: string,
    origin?: string,
    destination?: string
  ) => {
    setIsLoading(true);
    setFetchError(null);
    setActiveQuery({ carrier, flightNumber, date, origin, destination, scanTrigger: Date.now() });

    try {
      const params = new URLSearchParams({
        carrier,
        flight_num: flightNumber,
        date,
      });
      if (origin) params.set('origin', origin);
      if (destination) params.set('destination', destination);

      const resp = await fetch(`${API_BASE_URL}/api/v1/flights/evaluate?${params.toString()}`);

      const contentType = resp.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        throw new Error(
          `Received non-JSON response from backend (${resp.status}). Ensure the backend is reachable.`
        );
      }

      if (!resp.ok) {
        const errorData = await resp.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned ${resp.status}`);
      }

      const data = (await resp.json()) as RealityAssessment;
      setInitialAssessment(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to evaluate flight';
      setFetchError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Assessment to display: prioritize real-time streamed assessment over initial fetch
  const displayAssessment = streamedAssessment || initialAssessment;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center p-4 sm:p-6 lg:p-8">
      {/* App Header */}
      <header className="w-full max-w-md mx-auto flex items-center justify-between mb-6">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white">GroundTruth</h1>
            <p className="text-[10px] text-slate-400 font-medium">Turnaround Physics vs. Airline Claims</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Watchlist Header Button with Counter */}
          <button
            type="button"
            onClick={() => setIsWatchlistOpen(true)}
            data-testid="header-watchlist-btn"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 hover:bg-slate-850 border border-slate-800 text-[11px] text-slate-300 font-medium transition cursor-pointer"
          >
            <Bookmark className="w-3 h-3 text-amber-400" />
            <span>My Watchlist</span>
            <span
              data-testid="header-watchlist-badge"
              className="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30"
            >
              {watchlistCount}
            </span>
          </button>

          {/* Live SSE Status Indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px]">
            <Radio className={`w-3 h-3 ${isConnected ? 'text-emerald-400 animate-pulse' : 'text-slate-500'}`} />
            <span className="text-slate-300 font-mono text-[10px]">
              {isReconnecting ? 'Reconnecting' : isConnected ? 'Live SSE' : 'Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="w-full max-w-md mx-auto space-y-4">
        {/* Search Input Form */}
        <FlightSearch onSearch={handleSearch} isLoading={isLoading} />

        {/* Error Alert */}
        {(fetchError || streamError) && (
          <div className="bg-rose-950/40 border border-rose-900/60 rounded-xl p-3 flex items-start gap-2.5 text-xs text-rose-300">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{fetchError || streamError}</span>
          </div>
        )}

        {/* Loading Skeleton */}
        {isLoading && !displayAssessment && (
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 space-y-4 animate-pulse">
            <div className="h-4 bg-slate-800 rounded w-1/3" />
            <div className="h-8 bg-slate-800 rounded w-2/3" />
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="h-16 bg-slate-800/80 rounded-xl" />
              <div className="h-16 bg-slate-800/80 rounded-xl" />
            </div>
            <div className="h-14 bg-slate-800/60 rounded-xl" />
          </div>
        )}

        {/* Ground Reality Card */}
        {displayAssessment && (
          <div className="space-y-4 animate-fadeIn">
            <GroundRealityCard assessment={displayAssessment} onWatchToggle={() => setRefreshTrigger((p) => p + 1)} />
            {/* Live Inbound Visualizer */}
            <InboundVisualizer
              assessment={displayAssessment}
            />
          </div>
        )}
      </main>

      {/* Watchlist Drawer */}
      <WatchlistDrawer
        isOpen={isWatchlistOpen}
        onClose={() => {
          setIsWatchlistOpen(false);
          setRefreshTrigger((p) => p + 1);
        }}
        userName="Trupti"
        onSelectFlight={(carrier, flightNum, date) => handleSearch(carrier, flightNum, date)}
        refreshTrigger={refreshTrigger}
      />

      {/* Footer */}
      <footer className="w-full max-w-md mx-auto text-center mt-8 text-[11px] text-slate-500 space-y-1">
        <p>GroundTruth v0.1 • Real-time deterministic delay telemetry</p>
        {lastTickTime && (
          <p className="font-mono text-[10px] text-slate-600">
            Last stream tick: {new Date(lastTickTime).toLocaleTimeString()}
          </p>
        )}
      </footer>
    </div>
  );
};
