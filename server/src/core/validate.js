import { ValidationError } from './errors.js';

export function requireString(value, field, { max = 10_000, optional = false } = {}) {
  if (value === undefined || value === null || value === '') {
    if (optional) return null;
    throw new ValidationError(`${field} is required`);
  }
  if (typeof value !== 'string') throw new ValidationError(`${field} must be a string`);
  if (value.length > max) throw new ValidationError(`${field} is too long (max ${max})`);
  return value;
}

export function oneOf(value, field, allowed) {
  if (!allowed.includes(value)) throw new ValidationError(`${field} must be one of: ${allowed.join(', ')}`);
  return value;
}

export function intInRange(value, field, { min, max, fallback }) {
  if (value === undefined) return fallback;
  const n = Number.parseInt(value, 10);
  if (Number.isNaN(n) || n < min || n > max) throw new ValidationError(`${field} must be between ${min} and ${max}`);
  return n;
}
