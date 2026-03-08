import { useEffect, useRef, useCallback, useState } from 'react';

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

type EventHandler = (event: SSEEvent) => void;

/**
 * Hook for consuming Server-Sent Events from /api/events.
 *
 * Automatically connects, reconnects on failure, and dispatches
 * events to registered handlers.
 *
 * Usage:
 *   const { connected, lastEvent } = useEventStream({
 *     kill: (e) => console.log('New kill:', e),
 *     alert: (e) => showNotification(e),
 *   });
 */
export function useEventStream(
  handlers: Record<string, EventHandler>,
  enabled = true,
) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  const connect = useCallback(() => {
    if (!enabled) return null;

    const source = new EventSource('/api/events');

    source.onopen = () => setConnected(true);
    source.onerror = () => {
      setConnected(false);
      // EventSource auto-reconnects
    };

    // Listen for known event types
    const eventTypes = ['kill', 'alert', 'feed', 'status'];
    for (const type of eventTypes) {
      source.addEventListener(type, (e: MessageEvent) => {
        try {
          const parsed: SSEEvent = JSON.parse(e.data);
          setLastEvent(parsed);
          handlersRef.current[type]?.(parsed);
        } catch {
          // Ignore malformed events
        }
      });
    }

    return source;
  }, [enabled]);

  useEffect(() => {
    const source = connect();
    return () => {
      source?.close();
      setConnected(false);
    };
  }, [connect]);

  return { connected, lastEvent };
}
