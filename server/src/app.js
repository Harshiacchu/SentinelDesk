import express from 'express';
import cors from 'cors';
import { errorHandler, notFound } from './core/http.js';
import { Branches } from './domain/constants.js';
import { triageRoutes } from './modules/triage/triage.routes.js';
import { ticketRoutes } from './modules/tickets/tickets.routes.js';
import { incidentRoutes } from './modules/incidents/incidents.routes.js';
import { analyticsRoutes } from './modules/analytics/analytics.routes.js';
import { sseRoutes } from './realtime/sse.routes.js';
import { agentRoutes } from './modules/agent/agent.routes.js';
import { supportRoutes } from './modules/support/support.routes.js';

/** HTTP layer only: routing + middleware. Business logic lives in the services. */
export function createApp(c) {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: '100kb' }));

  app.get('/api/health', (_req, res) => res.json({ ok: true }));
  app.get('/api/meta', (_req, res) => res.json({
    branches: Branches,
    provider: c.config.triageProvider,
    store: c.config.ticketStore,
    chatSuggestions: c.chatService.suggestions,
  }));

  app.use('/api/triage', triageRoutes(c));
  app.use('/api/tickets', ticketRoutes(c));
  app.use('/api/incidents', incidentRoutes(c));
  app.use('/api/analytics', analyticsRoutes(c));
  app.use('/api/agent', agentRoutes(c));
  app.use('/api/support', supportRoutes(c));
  app.use('/api/events', sseRoutes(c));

  app.use(notFound);
  app.use(errorHandler);
  return app;
}
