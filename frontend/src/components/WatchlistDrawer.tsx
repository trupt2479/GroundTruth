import React, { useEffect, useState } from 'react';
import { WatchlistItem } from '../types/flight';
import { X, Clock, Trash2, RefreshCw, Bookmark, Plane, ShieldCheck, AlertTriangle } from 'lucide-react';

interface WatchlistDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  userName?: string;
  onSelectFlight?: (carrier: string, flightNumber: string, date: string) => void;
  refreshTrigger?: number;
}

export const WatchlistDrawer: React.FC<WatchlistDrawerProps> = ({
  isOpen,
  onClose,
  userName = 'Trupti',
  onSelectFlight,
  refreshTrigger = 0,
}) => {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingMilestones, setIsCheckingMilestones] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWatchlist = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/v1/watchlist?user_name=${encodeURIComponent(userName)}`);
      if (!resp.ok) {
        throw new Error(`Failed to load watchlist (HTTP ${resp.status})`);
      }
      const data = (await resp.json()) as WatchlistItem[];
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading watchlist');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchWatchlist();
    }
  }, [isOpen, userName, refreshTrigger]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      const resp = await fetch(`/api/v1/watchlist/${id}`, { method: 'DELETE' });
      if (!resp.ok) {
        throw new Error('Failed to delete item');
      }
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  const handleCheckMilestones = async () => {
    setIsCheckingMilestones(true);
    try {
      const resp = await fetch('/api/v1/watchlist/check-milestones', { method: 'POST' });
      if (resp.ok) {
        await fetchWatchlist();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsCheckingMilestones(false);
    }
  };

  const getArmedCountdown = (t2Str?: string | null) => {
    if (!t2Str) return 'Armed for T-2h check';
    try {
      const t2Time = new Date(t2Str).getTime();
      const now = Date.now();
      const diffMins = Math.round((t2Time - now) / 60000);
      if (diffMins <= 0) return 'Armed for T-2h check (Due)';
      return `Checking in ${diffMins} minutes (T-2h window)`;
    } catch {
      return 'Armed for T-2h check';
    }
  };

  const formatTime = (isoString?: string | null) => {
    if (!isoString) return '--:--';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return isoString;
    }
  };

  if (!isOpen) return null;

  return (
    <div
      data-testid="watchlist-drawer"
      className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex justify-end animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-slate-900 border-l border-slate-800 h-full p-5 sm:p-6 overflow-y-auto space-y-5 shadow-2xl flex flex-col justify-between"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-400">
                <Bookmark className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>My Watchlist</span>
                  <span
                    data-testid="watchlist-counter-pill"
                    className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30"
                  >
                    {items.length}
                  </span>
                </h3>
                <span className="text-xs text-slate-400">Active tracked itineraries for {userName}</span>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
              aria-label="Close watchlist"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Quick Trigger: Check Milestones */}
          <div className="flex items-center justify-between bg-slate-950/60 border border-slate-800/80 rounded-xl p-3 text-xs">
            <div className="space-y-0.5">
              <span className="font-semibold text-slate-300">T-2h Milestone Watchdog</span>
              <p className="text-[11px] text-slate-500">Auto-evaluates physics 2h prior to gate departure</p>
            </div>
            <button
              type="button"
              onClick={handleCheckMilestones}
              disabled={isCheckingMilestones}
              data-testid="check-milestones-btn"
              className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 font-semibold text-xs flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isCheckingMilestones ? 'animate-spin' : ''}`} />
              <span>{isCheckingMilestones ? 'Checking...' : 'Check Now'}</span>
            </button>
          </div>

          {/* Error Notice */}
          {error && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300">
              {error}
            </div>
          )}

          {/* Items List */}
          {isLoading ? (
            <div className="space-y-3 pt-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-28 bg-slate-800/50 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div data-testid="empty-watchlist-msg" className="text-center py-12 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-slate-800/60 border border-slate-700/60 flex items-center justify-center mx-auto text-slate-400">
                <Plane className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-slate-200">No flights currently watched</h4>
                <p className="text-xs text-slate-400 max-w-xs mx-auto leading-relaxed">
                  Search any flight and click <strong>"⭐ Watch Flight"</strong> to monitor turnaround physics across restarts.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-3 pt-1">
              {items.map((item) => {
                const leadDelay = item.latest_assessment?.delay_lead_time_minutes ?? 0;
                const isArmed = item.status === 'ARMED';

                return (
                  <div
                    key={item.id}
                    data-testid={`watchlist-item-${item.carrier}-${item.flight_number}`}
                    onClick={() => {
                      onSelectFlight?.(item.carrier, item.flight_number, item.departure_date);
                      onClose();
                    }}
                    className="bg-slate-950/70 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 space-y-2.5 transition cursor-pointer group"
                  >
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-white text-base">
                            {item.carrier} {item.flight_number}
                          </span>
                          <span className="text-xs font-mono text-slate-400">
                            • {item.origin_iata} → {item.destination_iata}
                          </span>
                        </div>
                        <span className="text-[11px] font-mono text-slate-500 block">
                          {item.departure_date} • Sched: {formatTime(item.scheduled_departure)}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => handleDelete(e, item.id)}
                        data-testid={`delete-watchlist-${item.id}`}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-slate-800/80 transition cursor-pointer"
                        title="Remove from watchlist"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Status Badge */}
                    <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800/60">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {item.status === 'DEPARTED' ? (
                          <span data-testid="status-badge-departed" className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                            <span>Departed</span>
                          </span>
                        ) : isArmed ? (
                          <span data-testid="status-badge-armed" className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                            <Clock className="w-3 h-3" />
                            <span>{getArmedCountdown(item.t2_scheduled_fetch)}</span>
                          </span>
                        ) : (
                          <span data-testid="status-badge-evaluated" className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                            leadDelay > 0
                              ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                              : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                          }`}>
                            {leadDelay > 0 ? <AlertTriangle className="w-3 h-3" /> : <ShieldCheck className="w-3 h-3" />}
                            <span>T-2h Checked ({leadDelay > 0 ? `+${leadDelay}m early warning` : 'On Time'})</span>
                          </span>
                        )}

                        {item.latest_assessment?.rebooking_directive && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60">
                            {item.latest_assessment.rebooking_directive}
                          </span>
                        )}
                      </div>

                      {item.origin_name && (
                        <span className="text-[10px] text-slate-500 truncate max-w-[150px]">
                          {item.origin_name}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-slate-800 text-center">
          <span className="text-[10px] font-mono text-slate-600">
            GroundTruth Persistence Engine • PostgreSQL DB Backed
          </span>
        </div>
      </div>
    </div>
  );
};
