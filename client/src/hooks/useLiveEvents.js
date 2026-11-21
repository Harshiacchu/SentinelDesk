import { useEffect, useRef } from 'react';

const EVENTS = ['ticket.created', 'ticket.updated', 'incident.updated', 'ticket.message'];

/** Subscribes to the server's SSE feed. The handler always sees the latest closure. */
export function useLiveEvents(onEvent) {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (typeof EventSource === 'undefined') return undefined;
    const source = new EventSource('/api/events');
    const listeners = EVENTS.map((name) => {
      const fn = (e) => handler.current(name, JSON.parse(e.data));
      source.addEventListener(name, fn);
      return [name, fn];
    });
    return () => {
      listeners.forEach(([name, fn]) => source.removeEventListener(name, fn));
      source.close();
    };
  }, []);
}
