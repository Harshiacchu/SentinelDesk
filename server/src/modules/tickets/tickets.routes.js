import { Router } from 'express';
import { asyncHandler } from '../../core/http.js';
import { intInRange, oneOf, requireString } from '../../core/validate.js';

export function ticketRoutes({ ticketService, triageService }) {
  const r = Router();

  r.get('/', asyncHandler(async (req, res) => {
    const filter = oneOf(req.query.filter ?? 'all', 'filter', ['all', 'needs', 'ready', 'done']);
    const page = intInRange(req.query.page, 'page', { min: 1, max: 10_000, fallback: 1 });
    const limit = intInRange(req.query.limit, 'limit', { min: 1, max: 50, fallback: 8 });
    res.json(await ticketService.list({ filter, page, limit }));
  }));

  r.get('/:id', asyncHandler(async (req, res) => res.json(await ticketService.get(req.params.id))));

  r.post('/:id/feedback', asyncHandler(async (req, res) => {
    res.json(await ticketService.addFeedback(req.params.id, { verdict: req.body?.verdict }));
  }));

  r.post('/:id/notes', asyncHandler(async (req, res) => {
    const text = requireString(req.body?.text, 'text', { max: 1000 });
    res.status(201).json(await ticketService.addNote(req.params.id, { text }));
  }));

  r.post('/:id/actions', asyncHandler(async (req, res) => {
    res.json(await ticketService.act(req.params.id, { action: req.body?.action }));
  }));

  r.post('/:id/followups', asyncHandler(async (req, res) => {
    const text = requireString(req.body?.text, 'text', { max: 4000 });
    res.status(201).json(await triageService.addFollowUp(req.params.id, { text }));
  }));

  r.put('/:id/draft', asyncHandler(async (req, res) => {
    const text = requireString(req.body?.text, 'text', { max: 4000 });
    res.json(await ticketService.editDraft(req.params.id, { text }));
  }));

  return r;
}
