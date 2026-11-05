import React, { useState } from 'react';
import { Search, Plane } from 'lucide-react';

export interface QuickScenario {
  id: string;
  name: string;
  carrier: string;
  flightNumber: string;
  description: string;
}

export const QUICK_SCENARIOS: QuickScenario[] = [
  {
    id: 'scenario-1',
    name: 'Scenario 1: UA 1422',
    carrier: 'UA',
    flightNumber: '1422',
    description: 'ORD Ground Stop + High Crew Timeout Risk',
  },
  {
    id: 'scenario-2',
    name: 'Scenario 2: DL 450',
    carrier: 'DL',
    flightNumber: '450',
    description: 'Hub Spare Available / Low Risk Turnaround',
  },
  {
    id: 'scenario-3',
    name: 'Scenario 3: AA 1200',
    carrier: 'AA',
    flightNumber: '1200',
    description: 'Outstation Inbound Delay Trap',
  },
];

interface FlightSearchProps {
  onSearch: (carrier: string, flightNumber: string, date: string) => void;
  isLoading: boolean;
}

export const formatLocalDate = (d: Date = new Date()): string => {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const getTimeZoneAbbr = (): string => {
  try {
    return (
      new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' })
        .formatToParts(new Date())
        .find((p) => p.type === 'timeZoneName')?.value || 'local'
    );
  } catch {
    return 'local';
  }
};

export const FlightSearch: React.FC<FlightSearchProps> = ({ onSearch, isLoading }) => {
  const getToday = () => formatLocalDate(new Date());
  const getTomorrow = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return formatLocalDate(d);
  };

  const today = getToday();
  const tomorrow = getTomorrow();

  const [carrier, setCarrier] = useState('UA');
  const [flightNumber, setFlightNumber] = useState('1422');
  const [departureDate, setDepartureDate] = useState(today);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const cleanCarrier = carrier.trim().toUpperCase();
    const cleanFlightNum = flightNumber.trim();
    const cleanDate = departureDate.trim();

    // Client-side regex validations
    if (!/^[A-Z]{2}$/.test(cleanCarrier)) {
      setValidationError('Carrier must be exactly 2 uppercase letters (e.g., UA, DL, AA).');
      return;
    }

    if (!/^[A-Za-z0-9]{1,4}$/.test(cleanFlightNum)) {
      setValidationError('Flight number must be 1 to 4 alphanumeric characters.');
      return;
    }

    if (!/^\d{4}-\d{2}-\d{2}$/.test(cleanDate)) {
      setValidationError('Date must be in YYYY-MM-DD format.');
      return;
    }

    setValidationError(null);
    onSearch(cleanCarrier, cleanFlightNum, cleanDate);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-xl backdrop-blur-md">
      <div className="flex items-center gap-2 mb-4">
        <Plane className="w-5 h-5 text-blue-400" />
        <h2 className="text-lg font-bold text-slate-100">Assess Flight Reality</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {/* Carrier Input */}
          <div>
            <label htmlFor="carrier-input" className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Carrier
            </label>
            <input
              id="carrier-input"
              type="text"
              maxLength={2}
              value={carrier}
              onChange={(e) => setCarrier(e.target.value.toUpperCase())}
              placeholder="UA"
              className="w-full bg-slate-950 border border-slate-750 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-3 py-2.5 text-center font-mono text-lg font-bold uppercase tracking-wider text-slate-100 placeholder-slate-600 outline-none transition"
              disabled={isLoading}
            />
          </div>

          {/* Flight Number Input */}
          <div>
            <label htmlFor="flight-num-input" className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Flight #
            </label>
            <input
              id="flight-num-input"
              type="text"
              maxLength={4}
              value={flightNumber}
              onChange={(e) => setFlightNumber(e.target.value)}
              placeholder="1422"
              className="w-full bg-slate-950 border border-slate-750 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-3 py-2.5 text-center font-mono text-lg font-bold text-slate-100 placeholder-slate-600 outline-none transition"
              disabled={isLoading}
            />
          </div>

          {/* Departure Date Input & Quick Presets */}
          <div className="col-span-2 sm:col-span-1">
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="date-input" className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Date <span className="text-[10px] text-slate-500 font-mono font-normal lowercase">({getTimeZoneAbbr()})</span>
              </label>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  data-testid="preset-today-btn"
                  onClick={() => {
                    setDepartureDate(getToday());
                    setValidationError(null);
                  }}
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded transition cursor-pointer border ${
                    departureDate === today
                      ? 'bg-blue-600 border-blue-500 text-white shadow-sm'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  Today
                </button>
                <button
                  type="button"
                  data-testid="preset-tomorrow-btn"
                  onClick={() => {
                    setDepartureDate(getTomorrow());
                    setValidationError(null);
                  }}
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded transition cursor-pointer border ${
                    departureDate === tomorrow
                      ? 'bg-blue-600 border-blue-500 text-white shadow-sm'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  Tomorrow
                </button>
              </div>
            </div>
            <div className="relative">
              <input
                id="date-input"
                type="date"
                value={departureDate}
                onChange={(e) => setDepartureDate(e.target.value)}
                onClick={(e) => e.currentTarget.showPicker?.()}
                className="w-full bg-slate-950 border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-3 py-2.5 text-center font-sans text-sm font-medium text-slate-200 outline-none transition cursor-pointer"
                disabled={isLoading}
              />
            </div>
          </div>
        </div>

        {/* Quick Scenarios Demonstration Selector */}
        <div className="space-y-1.5 pt-1" data-testid="quick-scenarios-container">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Quick Scenarios
            </span>
            <span className="text-[10px] text-slate-500 font-medium">1-click demo</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {QUICK_SCENARIOS.map((s) => {
              const isSelected = carrier === s.carrier && flightNumber === s.flightNumber;
              return (
                <button
                  key={s.id}
                  type="button"
                  data-testid={`scenario-btn-${s.carrier}-${s.flightNumber}`}
                  onClick={() => {
                    setCarrier(s.carrier);
                    setFlightNumber(s.flightNumber);
                    setDepartureDate(getToday());
                    setValidationError(null);
                  }}
                  className={`p-2 rounded-xl text-left border transition text-xs flex flex-col justify-center cursor-pointer ${
                    isSelected
                      ? 'bg-blue-950/70 border-blue-500 text-blue-200 shadow-sm shadow-blue-500/20'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <span className="font-bold text-slate-100 font-mono text-xs flex items-center justify-between">
                    {s.carrier} {s.flightNumber}
                    {isSelected && (
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                    )}
                  </span>
                  <span className="text-[10px] text-slate-400 leading-tight mt-0.5 line-clamp-2">
                    {s.description}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {validationError && (
          <div className="text-xs text-rose-400 bg-rose-950/40 border border-rose-900/60 rounded-lg p-2.5 animate-fadeIn">
            {validationError}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 text-white font-semibold py-3 px-4 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-blue-600/30 transition duration-150 cursor-pointer"
        >
          {isLoading ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>Scan Turnaround Physics</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};
