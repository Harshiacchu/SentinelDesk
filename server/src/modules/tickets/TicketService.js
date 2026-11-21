import { NotFoundError, ValidationError } from '../../core/errors.js';
import { TicketStatus } from '../../domain/constants.js';

const ACTIONS = {
  send: { status: TicketStatus.SENT, what: 'Sent the reply' },
  escalate: { status: TicketStatus.ESCALATED, what: 'Paged the on-call engineer' },
  handoff: { status: TicketStatus.ESCALATED, what: 'Handed to a specialist team' },
  resolve: { status: TicketStatus.RESOLVED, what: 'Resolved the ticket' },
  reopen: { status: TicketStatus.OPEN, what: 'Reopened the ticket' },
};

/** Read + operator actions on stored tickets. */
export class TicketService {
  constructor({ repository, events }) {
    this.repo = repository;
    this.events = events;
  }

  async list({ filter, page, limit }) {
    const { items, total } = await this.repo.list({ filter, page, limit });
    return { items: items.map(TicketService.summary), page, limit, total, pages: Math.max(1, Math.ceil(total / limit)) };
  }

  async get(id) {
    const ticket = await this.repo.findById(id);
    if (!ticket) throw new NotFoundError(`Ticket ${id}`);
    return ticket;
  }

  async addFeedback(id, { verdict, by = 'Operator' }) {
    if (!['right', 'wrong'].includes(verdict)) throw new ValidationError('verdict must be right or wrong');
    await this.get(id);
    const at = new Date();
    await this.repo.append(id, 'feedback', { verdict, by, at });
    const updated = await this.repo.append(id, 'activity', { who: by, what: `Said the AI was ${verdict}`, at });
    this.events.emit('ticket.updated', TicketService.summary(updated));
    return updated;
  }

  async addNote(id, { text, by = 'Operator' }) {
    await this.get(id);
    const at = new Date();
    await this.repo.append(id, 'notes', { text, by, at });
    return this.repo.append(id, 'activity', { who: by, what: `Added a note: “${text.slice(0, 60)}”`, at });
  }

  async act(id, { action, by = 'Operator' }) {
    const spec = ACTIONS[action];
    if (!spec) throw new ValidationError(`action must be one of: ${Object.keys(ACTIONS).join(', ')}`);
    await this.get(id);
    await this.repo.update(id, { status: spec.status });
    const updated = await this.repo.append(id, 'activity', { who: by, what: spec.what, at: new Date() });
    this.events.emit('ticket.updated', TicketService.summary(updated));
    return updated;
  }

  /** Light shape for inbox lists. */
  static summary(t) {
    return {
      ticketId: t.ticketId, receivedAt: t.receivedAt, subject: t.subject, bodyPreview: t.body.slice(0, 90),
      language: t.language, topic: t.topic, severity: t.severity, headline: t.headline,
      status: t.status, incidentKey: t.incidentKey, priority: t.triage?.priority?.label, queue: t.triage?.queue?.label,
    };
  }
}
