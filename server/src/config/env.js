import 'dotenv/config';

const num = (value, fallback) => (value === undefined || value === '' ? fallback : Number(value));

/** Single source of runtime configuration. Nothing else reads process.env. */
export const env = Object.freeze({
  port: num(process.env.PORT, 4000),
  triageProvider: process.env.TRIAGE_PROVIDER || 'mock',
  pipelineUrl: process.env.PIPELINE_URL || 'http://localhost:8000/triage',
  ticketStore: process.env.TICKET_STORE || 'memory',
  mongoUri: process.env.MONGODB_URI || '',
  seedDemo: (process.env.SEED_DEMO ?? 'true') === 'true',
  burst: Object.freeze({
    windowMin: num(process.env.BURST_WINDOW_MIN, 15),
    minTickets: num(process.env.BURST_MIN_TICKETS, 3),
  }),
});
