import React, { useState } from 'react';
import { FlightSearch } from './components/FlightSearch';
import { GroundRealityCard } from './components/GroundRealityCard';
import { InboundVisualizer } from './components/InboundVisualizer';
import { useFlightStream } from './hooks/useFlightStream';
import { RealityAssessment } from './types/flight';
import { Activity, Radio, AlertCircle } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const App: React.FC = () => {
  const [activeQuery, setActiveQuery] = useState<{
    carrier: string;
    flightNumber: string;
    date: string;
  } | null>({
    carrier: 'UA',
    flightNumber: '1422',
    date: new Date().toISOString().split('T')[0],
  });

  const [isLoading, setIsLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [initialAssessment, setInitialAssessment] = useState<RealityAssessment | null>(null);

  // Subscribe to real-time SSE stream
  const {
    assessment: streamedAssessment,
    isConnected,
    isReconnecting,
    error: streamError,
    lastTickTime,
  } = useFlightStream(
    activeQuery?.carrier || null,
    activeQuery?.flightNumber || null,
    activeQuery?.date || null
  );

  const handleSearch = async (carrier: string, flightNumber: string, date: string) => {
    setIsLoading(true);
    setFetchError(null);
    setActiveQuery({ carrier, flightNumber, date });

    try {
      const resp = await fetch(
        `${API_BASE_URL}/api/v1/flights/evaluate?carrier=${carrier}&flight_num=${flightNumber}&date=${date}`
      );

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

        {/* Live SSE Status Indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px]">
          <Radio className={`w-3 h-3 ${isConnected ? 'text-emerald-400 animate-pulse' : 'text-slate-500'}`} />
          <span className="text-slate-300 font-mono text-[10px]">
            {isReconnecting ? 'Reconnecting' : isConnected ? 'Live SSE' : 'Offline'}
          </span>
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
            <GroundRealityCard assessment={displayAssessment} />
            {/* Live Inbound Visualizer */}
            <InboundVisualizer
              turnaround={{
                previous_legs: [
                  {
                    flight_number: 'UA210',
                    origin_iata: 'SFO',
                    destination_iata: 'DEN',
                    scheduled_departure: '2026-10-24T06:00:00Z',
                    scheduled_arrival: '2026-10-24T09:30:00Z',
                    actual_arrival: '2026-10-24T10:15:00Z',
                    status: 'LANDED',
                  },
                  {
                    flight_number: 'UA584',
                    origin_iata: 'DEN',
                    destination_iata: 'ORD',
                    scheduled_departure: '2026-10-24T11:00:00Z',
                    scheduled_arrival: '2026-10-24T14:30:00Z',
                    actual_arrival: '2026-10-24T15:40:00Z',
                    status: 'LANDED',
                  },
                ],
                assigned_aircraft: {
                  icao_type: 'B738',
                  tail_number: 'N123UA',
                  category: 'NARROWBODY',
                },
                mtt_minutes: 45,
                estimated_touchdown: '2026-10-24T15:40:00Z',
                earliest_possible_departure: '2026-10-24T16:25:00Z',
              }}
              liveTelemetry={{
                callsign: `${displayAssessment.flight_query.carrier}${displayAssessment.flight_query.flight_number}`,
                baro_altitude_ft: 28000,
                ground_speed_kts: 445,
                on_ground: false,
              }}
            />
          </div>
        )}
      </main>

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
