import { Router } from 'express';
import { asyncHandler } from '../../core/http.js';
import { requireString } from '../../core/validate.js';

export function triageRoutes({ triageService }) {
  const r = Router();
  r.post('/', asyncHandler(async (req, res) => {
    const body = requireString(req.body?.body, 'body', { max: 8000 });
    const subject = requireString(req.body?.subject, 'subject', { max: 300, optional: true });
    const branch = requireString(req.body?.branch, 'branch', { max: 60, optional: true });
    res.status(201).json(await triageService.triage({ subject, body, branch }));
  }));
  return r;
}
