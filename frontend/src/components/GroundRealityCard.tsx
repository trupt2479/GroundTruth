import React, { useState } from 'react';
import { RealityAssessment } from '../types/flight';
import { Clock, AlertTriangle, ShieldCheck, RefreshCw, Zap, AlertOctagon, Plane, Copy, Check } from 'lucide-react';

interface GroundRealityCardProps {
  assessment: RealityAssessment;
}

export const GroundRealityCard: React.FC<GroundRealityCardProps> = ({ assessment }) => {
  const {
    flight_query,
    official_airline_departure,
    calculated_earliest_departure,
    delay_lead_time_minutes,
    is_unavoidable_delay,
    swap_evaluation,
    rebooking_directive,
    airspace_advisory,
    alternative_flights,
  } = assessment;

  const [copiedFlight, setCopiedFlight] = useState<string | null>(null);

  const handleCopy = (flightNum: string) => {
    navigator.clipboard?.writeText(flightNum);
    setCopiedFlight(flightNum);
    setTimeout(() => setCopiedFlight(null), 2000);
  };

  // Format datetimes to local display strings
  const formatTime = (isoString: string) => {
    try {
      const dt = new Date(isoString);
      return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return isoString;
    }
  };

  const officialTimeFormatted = formatTime(official_airline_departure);
  const calculatedTimeFormatted = formatTime(calculated_earliest_departure);

  // Directive Styling
  const directiveConfig = {
    RELAX_IN_LOUNGE: {
      bg: 'bg-emerald-950/40 border-emerald-800/80 text-emerald-300',
      badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
      icon: ShieldCheck,
      headline: 'Relax in Lounge',
      description: 'Physical turn buffer is intact. No downstream misconnection projected.',
    },
    MONITOR_CLOSELY: {
      bg: 'bg-amber-950/40 border-amber-800/80 text-amber-300',
      badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      icon: RefreshCw,
      headline: 'Tight Turnaround — Monitor Closely',
      description: 'Inbound delay detected. Airline hub may deploy a spare tail or squeeze turnaround.',
    },
    EXPEDITE_REBOOKING: {
      bg: 'bg-rose-950/50 border-rose-800/90 text-rose-300',
      badge: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
      icon: AlertTriangle,
      headline: 'Immediate Action: Expedite Rebooking',
      description: 'Unavoidable physical delay or ground stop active. Rebook seats before announcement.',
    },
  }[rebooking_directive];

  const DirectiveIcon = directiveConfig.icon;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-2xl space-y-5">
      {/* Flight Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Target Flight</span>
          <h3 className="text-2xl font-black text-white tracking-tight">
            {flight_query.carrier} {flight_query.flight_number}
          </h3>
          <span className="text-xs font-mono text-slate-400">{flight_query.departure_date}</span>
        </div>

        {/* Lead Time Badge */}
        {delay_lead_time_minutes > 0 ? (
          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-semibold text-amber-400 tracking-wider">Early Warning</span>
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 font-bold text-sm">
              <Zap className="w-3.5 h-3.5 fill-current" />
              <span>+{delay_lead_time_minutes} min ahead</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold text-xs">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>On Schedule</span>
          </div>
        )}
      </div>

      {/* Airspace Advisory Alert Banner (FAA NAS Ground Stop / GDP / Deicing) */}
      {airspace_advisory && airspace_advisory.advisory_active && (
        <div
          data-testid="airspace-advisory-banner"
          className={`border rounded-xl p-3.5 flex items-start gap-3 text-xs ${
            airspace_advisory.program_type === 'GROUND_STOP'
              ? 'bg-rose-950/70 border-rose-700/80 text-rose-200'
              : 'bg-amber-950/60 border-amber-700/80 text-amber-200'
          }`}
        >
          <AlertOctagon className="w-5 h-5 flex-shrink-0 mt-0.5 text-rose-400" />
          <div className="space-y-0.5">
            <span className="font-bold tracking-wide uppercase text-[11px]">
              FAA Airspace Alert: {airspace_advisory.program_type.replace(/_/g, ' ')} Active at {airspace_advisory.airport_iata}
            </span>
            <p className="opacity-90">
              Cause: {airspace_advisory.reason || 'Adverse Airspace Conditions'} • Average Delay:{' '}
              <strong className="font-mono">{airspace_advisory.avg_delay_minutes} min</strong>
            </p>
          </div>
        </div>
      )}

      {/* Side-by-Side Reality Comparison */}
      <div className="grid grid-cols-2 gap-3">
        {/* Official Airline Claim */}
        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[11px] font-semibold text-slate-400 uppercase">Airline Schedule</span>
          <div className="mt-1">
            <span className="text-xl sm:text-2xl font-bold font-mono text-slate-200">{officialTimeFormatted}</span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Published schedule</span>
        </div>

        {/* Physical Earliest Possible Departure */}
        <div className={`border rounded-xl p-3.5 flex flex-col justify-between ${
          is_unavoidable_delay ? 'bg-rose-950/20 border-rose-900/50' : 'bg-emerald-950/20 border-emerald-900/50'
        }`}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-300 uppercase">Earliest Possible</span>
            <Clock className="w-3 h-3 text-slate-400" />
          </div>
          <div className="mt-1">
            <span className={`text-xl sm:text-2xl font-bold font-mono ${
              is_unavoidable_delay ? 'text-rose-400' : 'text-emerald-400'
            }`}>
              {calculatedTimeFormatted}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 mt-1">Physics turnaround baseline</span>
        </div>
      </div>

      {/* Status Badges */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        {/* Delay Status */}
        <div className="bg-slate-950/40 border border-slate-800 rounded-lg p-2.5 flex items-center justify-between">
          <span className="text-slate-400 font-medium">Turn Physics</span>
          <span className={`font-semibold px-2 py-0.5 rounded text-[11px] ${
            is_unavoidable_delay ? 'bg-rose-500/20 text-rose-300' : 'bg-emerald-500/20 text-emerald-300'
          }`}>
            {is_unavoidable_delay ? 'Unavoidable Delay' : 'Feasible Turn'}
          </span>
        </div>

        {/* Tail Swap Heuristic */}
        <div className="bg-slate-950/40 border border-slate-800 rounded-lg p-2.5 flex items-center justify-between">
          <span className="text-slate-400 font-medium">Spare Swap</span>
          <span className="font-semibold px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-300">
            {swap_evaluation.swap_probability === 'NEAR_ZERO'
              ? 'Near 0% (Outstation)'
              : `${swap_evaluation.swap_probability} (${swap_evaluation.hub_type === 'FORTRESS_HUB' ? 'Hub' : 'Station'})`}
          </span>
        </div>
      </div>

      {/* Prescriptive Directive Banner */}
      <div className={`border rounded-xl p-4 flex gap-3 items-start ${directiveConfig.bg}`}>
        <DirectiveIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="font-bold text-sm tracking-tight">{directiveConfig.headline}</h4>
          <p className="text-xs leading-relaxed opacity-90">{directiveConfig.description}</p>
        </div>
      </div>

      {/* Alternative Flights Section (when rebooking is recommended/expedited) */}
      {alternative_flights && alternative_flights.length > 0 && (
        <div data-testid="alternative-flights-section" className="space-y-3 pt-2 border-t border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Plane className="w-3.5 h-3.5 text-blue-400" />
              <span>Recommended Alternative Flights</span>
            </span>
            <span className="text-[10px] text-slate-500 font-mono">Ranked by Departure</span>
          </div>

          <div className="space-y-2">
            {alternative_flights.map((alt) => (
              <div
                key={alt.flight_number}
                className="bg-slate-950/70 border border-slate-800/90 rounded-xl p-3 flex items-center justify-between text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-black text-sm text-white">{alt.flight_number}</span>
                    <span className="text-slate-400 text-[11px]">
                      {alt.origin_iata} → {alt.destination_iata}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    Dep: {formatTime(alt.departure_time)} • Arr: {formatTime(alt.arrival_time)}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {alt.seats_available ? (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      Seats Available
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      Standby Recommended
                    </span>
                  )}

                  <button
                    onClick={() => handleCopy(alt.flight_number)}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                    title="Copy flight number"
                  >
                    {copiedFlight === alt.flight_number ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
