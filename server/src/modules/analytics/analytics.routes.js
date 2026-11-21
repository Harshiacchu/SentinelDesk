import { Router } from 'express';
import { asyncHandler } from '../../core/http.js';
import { intInRange } from '../../core/validate.js';

export function analyticsRoutes({ analyticsService }) {
  const r = Router();
  r.get('/overview', asyncHandler(async (req, res) => {
    const hours = intInRange(req.query.hours, 'hours', { min: 1, max: 72, fallback: 6 });
    res.json(await analyticsService.overview({ hours }));
  }));
  r.get('/heatmap', asyncHandler(async (req, res) => {
    const minutes = intInRange(req.query.minutes, 'minutes', { min: 5, max: 1440, fallback: 60 });
    res.json(await analyticsService.heatmap({ minutes }));
  }));
  return r;
}
