import { useEffect, useRef, useState, useCallback } from 'react';
import { RealityAssessment } from '../types/flight';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
export const MAX_RECONNECT_ATTEMPTS = 0;

interface UseFlightStreamResult {
  assessment: RealityAssessment | null;
  isConnected: boolean;
  isReconnecting: boolean;
  error: string | null;
  lastTickTime: number | null;
}

export function useFlightStream(
  carrier: string | null,
  flightNum: string | null,
  date: string | null,
  origin?: string | null,
  destination?: string | null,
  scanTrigger?: number
): UseFlightStreamResult {
  const [assessment, setAssessment] = useState<RealityAssessment | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastTickTime, setLastTickTime] = useState<number | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!carrier || !flightNum || !date) {
      return;
    }

    // Close any prior connection immediately
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    let streamUrl = `${API_BASE_URL}/api/v1/flights/${carrier.toUpperCase()}/${flightNum}/${date}/stream`;
    const params = new URLSearchParams();
    if (origin) params.set('origin', origin);
    if (destination) params.set('destination', destination);
    const qs = params.toString();
    if (qs) {
      streamUrl += `?${qs}`;
    }
    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setIsReconnecting(false);
      setError(null);
    };

    es.addEventListener('INITIAL', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as RealityAssessment;
        setAssessment(data);
        setLastTickTime(Date.now());
      } catch (err) {
        console.error('Failed to parse INITIAL event', err);
      }
    });

    es.addEventListener('UPDATE', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as RealityAssessment;
        setAssessment(data);
        setLastTickTime(Date.now());
      } catch (err) {
        console.error('Failed to parse UPDATE event', err);
      }
    });

    es.addEventListener('TICK', () => {
      setLastTickTime(Date.now());
    });

    es.onerror = () => {
      // Zero-Auto-Retry: strictly manual-only.
      // Immediately close connection, do NOT initiate any setTimeout reconnections.
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
      setIsReconnecting(false);
      setError('Live stream disconnected. Scan again to reconnect.');
    };
  }, [carrier, flightNum, date, origin, destination]);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [connect, scanTrigger]);

  return { assessment, isConnected, isReconnecting, error, lastTickTime };
}
