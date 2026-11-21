import { NotFoundError } from '../../core/errors.js';
import { TicketStatus } from '../../domain/constants.js';
import { customerView, message, systemText } from '../../domain/conversation.js';
import { headlineFor } from '../../domain/Severity.js';
import { TicketService } from '../tickets/TicketService.js';

/**
 * Customer side. Access is by ticket id + private access key (the link the customer gets),
 * so no accounts are needed. Unknown id and wrong key look identical (no ticket enumeration).
 */
export class SupportService {
  constructor({ repository, triageService, events }) {
    this.repo = repository;
    this.triage = triageService;
    this.events = events;
  }

  async open({ subject, body, branch }) {
    const t = await this.triage.triage({ subject, body, branch });
    return { ticketId: t.ticketId, key: t.accessKey, view: customerView(t) };
  }

  async view(id, key) {
    return customerView(await this.#authorised(id, key));
  }

  async say(id, key, text) {
    const t = await this.#authorised(id, key);
    const msg = message('customer', text);
    const reopen = t.status === TicketStatus.RESOLVED || t.status === TicketStatus.SENT;
    if (reopen) await this.repo.update(id, { status: t.assignee ? TicketStatus.IN_PROGRESS : TicketStatus.ESCALATED });
    const updated = await this.repo.append(id, 'messages', msg);
    this.events.emit('ticket.message', { ticketId: id, message: msg });
    if (reopen) this.events.emit('ticket.updated', TicketService.summary(updated));
    return customerView(updated);
  }

  /** "Talk to a person": moves an AI-answered ticket into the live agent queue. */
  async askForPerson(id, key) {
    const t = await this.#authorised(id, key);
    if (t.severity === 'ready') {
      await this.repo.update(id, {
        severity: 'review', severityRank: 1, headline: headlineFor('review'), status: TicketStatus.ESCALATED,
        reasons: [...t.reasons, 'CUSTOMER_REQUEST'],
        reasonDetails: { ...(t.reasonDetails ?? {}), CUSTOMER_REQUEST: 'The customer asked to talk to a person after the AI answer.' },
      });
    }
    const msg = message('system', systemText(t.language).handoff);
    await this.repo.append(id, 'messages', msg);
    const updated = await this.repo.append(id, 'activity', { who: 'Customer', what: 'Asked to talk to a person', at: new Date() });
    this.events.emit('ticket.message', { ticketId: id, message: msg });
    this.events.emit('ticket.updated', TicketService.summary(updated));
    return customerView(updated);
  }

  /** Lets the SSE route check a key without loading the whole view. */
  async authorise(id, key) {
    await this.#authorised(id, key);
  }

  async #authorised(id, key) {
    const t = await this.repo.findById(id);
    if (!t || !key || t.accessKey !== key) throw new NotFoundError('Ticket');
    return t;
  }
}
