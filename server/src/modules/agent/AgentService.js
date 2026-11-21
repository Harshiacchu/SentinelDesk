import { NotFoundError, ValidationError } from '../../core/errors.js';
import { TicketStatus } from '../../domain/constants.js';
import { message, systemText } from '../../domain/conversation.js';
import { TicketService } from '../tickets/TicketService.js';

/** Live agent use cases: queue, claim, assist, chat with the customer, resolve. */
export class AgentService {
  constructor({ repository, events, assistBuilder }) {
    this.repo = repository;
    this.events = events;
    this.assist = assistBuilder;
  }

  async queue({ view, agent, page, limit }) {
    const filter = { unclaimed: 'unclaimed', mine: 'mine', resolved: 'resolved_by_agents' }[view];
    if (!filter) throw new ValidationError('view must be unclaimed, mine or resolved');
    const { items, total } = await this.repo.list({ filter, agent, page, limit });
    return { items: items.map(TicketService.summary), page, limit, total, pages: Math.max(1, Math.ceil(total / limit)) };
  }

  async claim(id, agent) {
    const t = await this.#get(id);
    if (t.assignee && t.assignee !== agent) throw new ValidationError(`Already claimed by ${t.assignee}`);
    if (t.assignee === agent) return t;
    await this.repo.update(id, { assignee: agent, claimedAt: new Date(), status: TicketStatus.IN_PROGRESS });
    await this.#say(id, message('system', systemText(t.language).joined(agent)));
    return this.#log(id, agent, 'Claimed the ticket');
  }

  async release(id, agent) {
    await this.#owned(id, agent);
    await this.repo.update(id, { assignee: null, claimedAt: null, status: TicketStatus.ESCALATED });
    return this.#log(id, agent, 'Released the ticket back to the queue');
  }

  async sendMessage(id, { agent, text }) {
    const t = await this.#owned(id, agent);
    if (t.status === TicketStatus.RESOLVED) await this.repo.update(id, { status: TicketStatus.IN_PROGRESS });
    return this.#say(id, message('agent', text, { name: agent }));
  }

  async resolve(id, agent) {
    const t = await this.#owned(id, agent);
    await this.repo.update(id, { status: TicketStatus.RESOLVED });
    await this.#say(id, message('system', systemText(t.language).resolved(agent)));
    return this.#log(id, agent, 'Resolved the ticket');
  }

  async assistFor(id) {
    const ticket = await this.#get(id);
    const recent = await this.repo.findSince(new Date(Date.now() - 60 * 60_000));
    const related = recent
      .filter((r) => r.ticketId !== id && ((ticket.incidentKey && r.incidentKey === ticket.incidentKey) || (r.topic === ticket.topic && r.topic !== 'Other')))
      .sort((a, b) => new Date(b.receivedAt) - new Date(a.receivedAt))
      .slice(0, 6);
    return this.assist.build(ticket, related);
  }

  async #get(id) {
    const t = await this.repo.findById(id);
    if (!t) throw new NotFoundError(`Ticket ${id}`);
    return t;
  }

  async #owned(id, agent) {
    const t = await this.#get(id);
    if (t.assignee !== agent) throw new ValidationError(t.assignee ? `Claimed by ${t.assignee}` : 'Claim the ticket first');
    return t;
  }

  async #say(id, msg) {
    const updated = await this.repo.append(id, 'messages', msg);
    this.events.emit('ticket.message', { ticketId: id, message: msg });
    return updated;
  }

  async #log(id, who, what) {
    const updated = await this.repo.append(id, 'activity', { who, what, at: new Date() });
    this.events.emit('ticket.updated', TicketService.summary(updated));
    return updated;
  }
}
