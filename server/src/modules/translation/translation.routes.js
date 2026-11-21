import { Router } from 'express';
import { asyncHandler } from '../../core/http.js';
import { requireString } from '../../core/validate.js';

export function translationRoutes({ translationService }) {
  const r = Router();
  r.post('/', asyncHandler(async (req, res) => {
    const text = requireString(req.body?.text, 'text', { max: 5000 });
    const target = requireString(req.body?.target, 'target', { max: 2 });
    const source = requireString(req.body?.source, 'source', { max: 2, optional: true });
    res.json(await translationService.translate(text, { target, source: source ?? undefined }));
  }));
  return r;
}
