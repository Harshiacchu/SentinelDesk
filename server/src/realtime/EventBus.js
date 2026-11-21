import { EventEmitter } from 'node:events';

/** In-process pub/sub. Services emit domain events; transports (SSE) subscribe. */
export class EventBus extends EventEmitter {
  constructor() {
    super();
    this.setMaxListeners(100);
  }
}

export const LIVE_EVENTS = ['ticket.created', 'ticket.updated', 'incident.updated'];
