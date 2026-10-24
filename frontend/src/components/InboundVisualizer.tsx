import React from 'react';
import { InboundTurnaround, LiveTelemetry } from '../types/flight';
import { PlaneTakeoff, Navigation, Gauge } from 'lucide-react';

interface InboundVisualizerProps {
  turnaround?: InboundTurnaround | null;
  liveTelemetry?: LiveTelemetry | null;
}

export const InboundVisualizer: React.FC<InboundVisualizerProps> = ({ turnaround, liveTelemetry }) => {
  if (!turnaround) {
    return null;
  }

  const { assigned_aircraft, mtt_minutes, estimated_touchdown, previous_legs } = turnaround;

  const formatTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-2xl space-y-4">
      {/* Aircraft Info Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2.5">
          <PlaneTakeoff className="w-5 h-5 text-indigo-400" />
          <div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Assigned Tail</span>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold font-mono text-white">{assigned_aircraft.tail_number}</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-medium">
                {assigned_aircraft.icao_type} ({assigned_aircraft.category})
              </span>
            </div>
          </div>
        </div>

        {/* Minimum Turnaround Time (MTT) Pill */}
        <div className="text-right">
          <span className="text-[10px] font-semibold text-slate-400 uppercase">MTT Window</span>
          <div className="text-sm font-bold font-mono text-indigo-400">{mtt_minutes} min buffer</div>
        </div>
      </div>

      {/* Live Transponder Telemetry Bar */}
      {liveTelemetry && (
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 grid grid-cols-3 gap-2 text-center">
          <div>
            <span className="text-[10px] text-slate-500 uppercase font-semibold">Live State</span>
            <div className="text-xs font-bold text-slate-200 mt-0.5 flex items-center justify-center gap-1">
              <span className={`w-2 h-2 rounded-full ${liveTelemetry.on_ground ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`} />
              <span>{liveTelemetry.on_ground ? 'On Ground' : 'Airborne'}</span>
            </div>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 uppercase font-semibold">Altitude</span>
            <div className="text-xs font-bold font-mono text-slate-200 mt-0.5 flex items-center justify-center gap-1">
              <Navigation className="w-3 h-3 text-slate-400" />
              <span>{liveTelemetry.baro_altitude_ft ? `${liveTelemetry.baro_altitude_ft.toLocaleString()} ft` : 'N/A'}</span>
            </div>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 uppercase font-semibold">Speed</span>
            <div className="text-xs font-bold font-mono text-slate-200 mt-0.5 flex items-center justify-center gap-1">
              <Gauge className="w-3 h-3 text-slate-400" />
              <span>{liveTelemetry.ground_speed_kts ? `${liveTelemetry.ground_speed_kts} kts` : 'N/A'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Inbound Touchdown Baseline */}
      <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-3.5 flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400">Projected Touchdown</span>
        <span className="text-sm font-bold font-mono text-slate-200">{formatTime(estimated_touchdown)}</span>
      </div>

      {/* Historical Rotation Legs */}
      {previous_legs && previous_legs.length > 0 && (
        <div className="space-y-2 pt-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Upstream Rotations (Delay Propagation)
          </span>
          <div className="space-y-1.5">
            {previous_legs.map((leg, index) => (
              <div
                key={`${leg.flight_number}-${index}`}
                className="bg-slate-950/50 border border-slate-800/80 rounded-lg p-2.5 flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-slate-300">{leg.flight_number}</span>
                  <span className="text-slate-400">{leg.origin_iata} → {leg.destination_iata}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-slate-400">
                    Arr: {formatTime(leg.actual_arrival || leg.scheduled_arrival)}
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300">
                    {leg.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
