import { useEffect, useRef, useState, useCallback } from 'react';
import { RealityAssessment } from '../types/flight';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
  date: string | null
): UseFlightStreamResult {
  const [assessment, setAssessment] = useState<RealityAssessment | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastTickTime, setLastTickTime] = useState<number | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const connect = useCallback(() => {
    if (!carrier || !flightNum || !date) {
      return;
    }

    // Close any prior connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const streamUrl = `${API_BASE_URL}/api/v1/flights/${carrier.toUpperCase()}/${flightNum}/${date}/stream`;
    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setIsReconnecting(false);
      setError(null);
      reconnectAttemptsRef.current = 0;
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
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);

      // Reconnect with exponential backoff (max 30s)
      reconnectAttemptsRef.current += 1;
      setIsReconnecting(true);
      const backoffMs = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current - 1), 30000);

      setError(`Connection lost. Reconnecting in ${(backoffMs / 1000).toFixed(0)}s...`);

      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, backoffMs);
    };
  }, [carrier, flightNum, date]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [connect]);

  return { assessment, isConnected, isReconnecting, error, lastTickTime };
}
