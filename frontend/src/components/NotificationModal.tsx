import React, { useState } from 'react';
import { FlightQuery, NotificationSubscription, NotificationResponse } from '../types/flight';
import { Bell, Check, MessageSquare, Webhook, X, AlertCircle } from 'lucide-react';

interface NotificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  flightQuery: FlightQuery;
}

export const NotificationModal: React.FC<NotificationModalProps> = ({
  isOpen,
  onClose,
  flightQuery,
}) => {
  const [recipientType, setRecipientType] = useState<'SMS' | 'WEBHOOK'>('SMS');
  const [destination, setDestination] = useState('');
  const [alertOnDelay, setAlertOnDelay] = useState(true);
  const [alertOnCrewTimeout, setAlertOnCrewTimeout] = useState(true);
  const [alertOnSwap, setAlertOnSwap] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const validateInput = (): boolean => {
    setErrorMsg(null);
    const dest = destination.trim();
    if (!dest) {
      setErrorMsg('Please enter a destination address.');
      return false;
    }

    if (recipientType === 'SMS') {
      const e164Regex = /^\+[1-9]\d{7,14}$/;
      if (!e164Regex.test(dest)) {
        setErrorMsg('Please enter a valid E.164 phone number (e.g. +15551234567).');
        return false;
      }
    } else {
      const urlRegex = /^https?:\/\/.+/i;
      if (!urlRegex.test(dest)) {
        setErrorMsg('Please enter a valid webhook URL (e.g. https://api.example.com/webhook).');
        return false;
      }
    }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateInput()) return;

    setIsSubmitting(true);
    setErrorMsg(null);

    const payload: NotificationSubscription = {
      flight_carrier: flightQuery.carrier,
      flight_number: flightQuery.flight_number,
      flight_date: flightQuery.departure_date,
      recipient_type: recipientType,
      destination: destination.trim(),
      alert_on_delay: alertOnDelay,
      alert_on_crew_timeout: alertOnCrewTimeout,
      alert_on_swap: alertOnSwap,
    };

    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/api/v1/notifications/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data: NotificationResponse = await response.json();
        setSuccessMsg(data.message || 'Successfully subscribed to real-time alerts!');
      } else {
        const errorData = await response.json().catch(() => null);
        setErrorMsg(errorData?.detail || 'Failed to register subscription. Please try again.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Network error connecting to subscription service.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="notification-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl relative space-y-5 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2 text-white">
            <div className="p-2 bg-indigo-500/20 text-indigo-400 rounded-lg border border-indigo-500/30">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h3 id="notification-modal-title" className="font-bold text-base">Proactive Alert Dispatch</h3>
              <p className="text-xs text-slate-400">
                {flightQuery.carrier} {flightQuery.flight_number} • {flightQuery.departure_date}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Success State */}
        {successMsg ? (
          <div className="space-y-4 py-2">
            <div className="bg-emerald-950/50 border border-emerald-800/80 rounded-xl p-4 flex items-start gap-3 text-emerald-300">
              <Check className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-bold text-sm">Alert Registered</span>
                <p className="text-xs leading-relaxed opacity-90">{successMsg}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-full py-2.5 rounded-xl font-bold text-sm bg-slate-800 hover:bg-slate-700 text-white transition"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Channel Toggle */}
            <div className="grid grid-cols-2 gap-2 p-1 bg-slate-950 rounded-xl border border-slate-800">
              <button
                type="button"
                onClick={() => {
                  setRecipientType('SMS');
                  setErrorMsg(null);
                }}
                className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition ${
                  recipientType === 'SMS'
                    ? 'bg-indigo-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>SMS Alert</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setRecipientType('WEBHOOK');
                  setErrorMsg(null);
                }}
                className={`flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition ${
                  recipientType === 'WEBHOOK'
                    ? 'bg-indigo-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Webhook className="w-3.5 h-3.5" />
                <span>Webhook URL</span>
              </button>
            </div>

            {/* Destination Input */}
            <div className="space-y-1.5">
              <label htmlFor="destination-input" className="block text-xs font-medium text-slate-300">
                {recipientType === 'SMS' ? 'Mobile Phone Number (E.164)' : 'Webhook Endpoint (HTTPS)'}
              </label>
              <input
                id="destination-input"
                type={recipientType === 'SMS' ? 'tel' : 'url'}
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                placeholder={recipientType === 'SMS' ? '+15551234567' : 'https://api.example.com/webhook'}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition font-mono"
              />
              <span className="text-[10px] text-slate-500 block">
                {recipientType === 'SMS'
                  ? 'Format: +[Country Code][Number] without spaces or dashes.'
                  : 'Receives POST requests with full RealityAssessment JSON payloads.'}
              </span>
            </div>

            {/* Trigger Criteria Checkboxes */}
            <div className="space-y-2 pt-1 border-t border-slate-800/80">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Trigger Alerts On:
              </span>
              <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={alertOnDelay}
                  onChange={(e) => setAlertOnDelay(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0"
                />
                <span>Confirmed Physical Turnaround Delays</span>
              </label>
              <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={alertOnCrewTimeout}
                  onChange={(e) => setAlertOnCrewTimeout(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0"
                />
                <span>FAA Part 117 Crew Timeout / Cancellation Risk</span>
              </label>
              <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={alertOnSwap}
                  onChange={(e) => setAlertOnSwap(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0"
                />
                <span>Equipment Spare Swap Advisories</span>
              </label>
            </div>

            {/* Error Message */}
            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white transition shadow-lg shadow-indigo-600/30"
              >
                {isSubmitting ? 'Registering...' : 'Activate Alerts'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
