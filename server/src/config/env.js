import dotenv from 'dotenv';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// server/.env first, then the repo-root .env (shared with the Python pipeline, e.g. GEMINI_API_KEY).
const here = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(here, '../../.env') });
dotenv.config({ path: path.resolve(here, '../../../.env') });

const num = (value, fallback) => (value === undefined || value === '' ? fallback : Number(value));

/** Single source of runtime configuration. Nothing else reads process.env. */
export const env = Object.freeze({
  port: num(process.env.PORT, 4000),
  triageProvider: process.env.TRIAGE_PROVIDER || 'mock',
  pipelineUrl: process.env.PIPELINE_URL || 'http://localhost:8000/triage',
  ticketStore: process.env.TICKET_STORE || 'memory',
  mongoUri: process.env.MONGODB_URI || '',
  seedDemo: (process.env.SEED_DEMO ?? 'true') === 'true',
  translateApiKey: process.env.GOOGLE_TRANSLATE_API_KEY || '',
  gemini: Object.freeze({
    apiKey: process.env.GEMINI_API_KEY || '',
    model: process.env.LLM_MODEL || 'gemini-3-flash-preview',
    translateModel: process.env.TRANSLATE_MODEL || 'gemini-3.1-flash-lite',
    vertex: ['1', 'true', 'yes'].includes((process.env.GEMINI_USE_VERTEX ?? 'false').toLowerCase()),
  }),
  burst: Object.freeze({
    windowMin: num(process.env.BURST_WINDOW_MIN, 15),
    minTickets: num(process.env.BURST_MIN_TICKETS, 3),
  }),
});
