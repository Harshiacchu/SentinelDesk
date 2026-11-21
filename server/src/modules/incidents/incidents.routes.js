import { Router } from 'express';
import { asyncHandler } from '../../core/http.js';

export function incidentRoutes({ incidentService }) {
  const r = Router();
  r.get('/active', asyncHandler(async (_req, res) => res.json({ items: await incidentService.active() })));
  r.get('/:key', asyncHandler(async (req, res) => res.json(await incidentService.byKey(req.params.key))));
  return r;
}
