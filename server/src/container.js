/**
 * Composition root: the ONLY file that knows concrete classes.
 * Everything else receives its collaborators through constructors (dependency inversion),
 * so swapping mock → real is a config change, not a code change.
 */
import { env } from './config/env.js';
import { createLogger } from './core/logger.js';
import { EventBus } from './realtime/EventBus.js';
import { TopicClassifier } from './domain/TopicClassifier.js';
import { PiiMasker } from './domain/PiiMasker.js';
import { MockTriageProvider } from './modules/triage/providers/MockTriageProvider.js';
import { HttpTriageProvider } from './modules/triage/providers/HttpTriageProvider.js';
import { PipelineResultMapper } from './modules/triage/providers/PipelineResultMapper.js';
import { TriageService } from './modules/triage/TriageService.js';
import { InMemoryTicketRepository } from './modules/tickets/repositories/InMemoryTicketRepository.js';
import { MongoTicketRepository } from './modules/tickets/repositories/MongoTicketRepository.js';
import { TicketFactory } from './modules/tickets/TicketFactory.js';
import { TicketService } from './modules/tickets/TicketService.js';
import { BurstDetector } from './modules/incidents/BurstDetector.js';
import { IncidentService } from './modules/incidents/IncidentService.js';
import { AnalyticsService } from './modules/analytics/AnalyticsService.js';
import { DemoSeeder } from './seed/DemoSeeder.js';

const log = createLogger('container');

function pick(name, choice, options) {
  const make = options[choice];
  if (!make) throw new Error(`Unknown ${name} "${choice}". Use one of: ${Object.keys(options).join(', ')}`);
  log.info(`${name} → ${choice}`);
  return make();
}

export function buildContainer(config = env) {
  const events = new EventBus();
  const topicClassifier = new TopicClassifier();

  const provider = pick('triage provider', config.triageProvider, {
    mock: () => new MockTriageProvider({ topicClassifier }),
    http: () => new HttpTriageProvider({ url: config.pipelineUrl, mapper: new PipelineResultMapper({ topicClassifier }) }),
  });

  const repository = pick('ticket store', config.ticketStore, {
    memory: () => new InMemoryTicketRepository(),
    mongo: () => new MongoTicketRepository({ uri: config.mongoUri }),
  });

  const factory = new TicketFactory();
  const burstDetector = new BurstDetector(config.burst);
  const ticketService = new TicketService({ repository, events });
  const triageService = new TriageService({ provider, repository, factory, burstDetector, events, piiMasker: new PiiMasker() });

  return {
    config,
    events,
    repository,
    factory,
    triageService,
    ticketService,
    incidentService: new IncidentService({ repository, burstDetector }),
    analyticsService: new AnalyticsService({ repository, topicClassifier, burstDetector }),
    seeder: new DemoSeeder({ triageService, ticketService, repository }),
  };
}
