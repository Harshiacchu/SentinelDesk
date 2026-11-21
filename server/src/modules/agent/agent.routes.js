import { Router } from 'express';
import { asyncHandler } from '../../core/http.js';
import { intInRange, requireString } from '../../core/validate.js';
import { TicketService } from '../tickets/TicketService.js';

export function agentRoutes({ agentService }) {
  const r = Router();
  const agentOf = (req) => requireString(req.body?.agent ?? req.query.agent, 'agent', { max: 60 });

  r.get('/queue', asyncHandler(async (req, res) => {
    const page = intInRange(req.query.page, 'page', { min: 1, max: 10_000, fallback: 1 });
    const limit = intInRange(req.query.limit, 'limit', { min: 1, max: 50, fallback: 8 });
    res.json(await agentService.queue({ view: req.query.view ?? 'unclaimed', agent: req.query.agent ?? '', page, limit }));
  }));
  r.get('/tickets/:id/assist', asyncHandler(async (req, res) => res.json(await agentService.assistFor(req.params.id))));
  r.post('/tickets/:id/claim', asyncHandler(async (req, res) => res.json(TicketService.withoutSecrets(await agentService.claim(req.params.id, agentOf(req))))));
  r.post('/tickets/:id/release', asyncHandler(async (req, res) => res.json(TicketService.withoutSecrets(await agentService.release(req.params.id, agentOf(req))))));
  r.post('/tickets/:id/messages', asyncHandler(async (req, res) => {
    const text = requireString(req.body?.text, 'text', { max: 4000 });
    res.status(201).json(TicketService.withoutSecrets(await agentService.sendMessage(req.params.id, { agent: agentOf(req), text })));
  }));
  r.post('/tickets/:id/resolve', asyncHandler(async (req, res) => res.json(TicketService.withoutSecrets(await agentService.resolve(req.params.id, agentOf(req))))));
  return r;
}
