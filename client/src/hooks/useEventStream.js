import { useEffect, useRef } from 'react';

/** Subscribes to one SSE URL (e.g. a single ticket's customer stream). */
export function useEventStream(url, events, onEvent) {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  const names = events.join(',');

  useEffect(() => {
    if (!url || typeof EventSource === 'undefined') return undefined;
    const source = new EventSource(url);
    const fns = names.split(',').map((n) => {
      const fn = (e) => handler.current(n, e.data ? JSON.parse(e.data) : null);
      source.addEventListener(n, fn);
      return [n, fn];
    });
    return () => { fns.forEach(([n, fn]) => source.removeEventListener(n, fn)); source.close(); };
  }, [url, names]);
}
