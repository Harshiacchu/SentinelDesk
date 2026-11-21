import { Router } from 'express';
import { LIVE_EVENTS } from './EventBus.js';

/** Server-Sent Events: one-way live feed to the console. Simpler than WebSockets for push-only. */
export function sseRoutes({ events }) {
  const r = Router();
  r.get('/', (req, res) => {
    res.set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' });
    res.flushHeaders();
    res.write('retry: 3000\n\n');

    const handlers = LIVE_EVENTS.map((name) => {
      const fn = (data) => res.write(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`);
      events.on(name, fn);
      return [name, fn];
    });
    const heartbeat = setInterval(() => res.write(': ping\n\n'), 25_000);

    req.on('close', () => {
      clearInterval(heartbeat);
      for (const [name, fn] of handlers) events.off(name, fn);
    });
  });
  return r;
}
