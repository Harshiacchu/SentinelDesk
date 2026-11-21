import { AppError } from './errors.js';
import { createLogger } from './logger.js';

const log = createLogger('http');

/** Wraps an async route handler so rejected promises reach the error middleware. */
export const asyncHandler = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

export function notFound(_req, res) {
  res.status(404).json({ error: 'Route not found' });
}

// eslint-disable-next-line no-unused-vars
export function errorHandler(err, _req, res, _next) {
  const status = err instanceof AppError ? err.status : 500;
  if (status >= 500) log.error(err);
  res.status(status).json({ error: status >= 500 && !(err instanceof AppError) ? 'Internal error' : err.message });
}
