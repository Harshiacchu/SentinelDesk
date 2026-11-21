import { Router } from 'express';
import { asyncHandler } from '../../core/http.js';
import { requireString } from '../../core/validate.js';

/** Public customer endpoints. Every ticket route needs ?key=<access key>. */
export function supportRoutes({ supportService, events }) {
  const r = Router();
  const key = (req) => String(req.query.key ?? req.body?.key ?? '');

  r.post('/tickets', asyncHandler(async (req, res) => {
    const body = requireString(req.body?.body, 'body', { max: 8000 });
    const subject = requireString(req.body?.subject, 'subject', { max: 300, optional: true });
    const branch = requireString(req.body?.branch, 'branch', { max: 60, optional: true });
    res.status(201).json(await supportService.open({ subject, body, branch }));
  }));

  r.get('/tickets/:id', asyncHandler(async (req, res) => res.json(await supportService.view(req.params.id, key(req)))));

  r.post('/tickets/:id/messages', asyncHandler(async (req, res) => {
    const text = requireString(req.body?.text, 'text', { max: 4000 });
    res.status(201).json(await supportService.say(req.params.id, key(req), text));
  }));

  r.post('/tickets/:id/person', asyncHandler(async (req, res) => res.json(await supportService.askForPerson(req.params.id, key(req)))));

  // Live updates for ONE ticket only: the customer never sees other tickets' events.
  r.get('/tickets/:id/events', asyncHandler(async (req, res) => {
    await supportService.authorise(req.params.id, key(req));
    res.set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' });
    res.flushHeaders();
    res.write('retry: 3000\n\n');
    const id = req.params.id;
    const onMessage = (e) => { if (e.ticketId === id) res.write(`event: message\ndata: ${JSON.stringify(e.message)}\n\n`); };
    const onUpdate = (s) => { if (s.ticketId === id) res.write(`event: update\ndata: {}\n\n`); };
    events.on('ticket.message', onMessage);
    events.on('ticket.updated', onUpdate);
    const beat = setInterval(() => res.write(': ping\n\n'), 25_000);
    req.on('close', () => { clearInterval(beat); events.off('ticket.message', onMessage); events.off('ticket.updated', onUpdate); });
  }));

  return r;
}
