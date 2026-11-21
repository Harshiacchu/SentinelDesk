import { ValidationError } from '../../core/errors.js';
import { TicketFactory } from '../tickets/TicketFactory.js';
import { TicketService } from '../tickets/TicketService.js';

/**
 * Use case: a new ticket arrives.
 *   provider.analyze → build record → outage check → save → notify live clients
 * Depends only on abstractions (provider, repository, detector, events).
 */
export class TriageService {
  constructor({ provider, repository, factory, burstDetector, events }) {
    Object.assign(this, { provider, repository, factory, burstDetector, events });
  }

  async triage(input, { receivedAt = new Date(), silent = false } = {}) {
    if (!input?.body?.trim()) throw new ValidationError('body is required');
    const result = await this.provider.analyze({ subject: input.subject, body: input.body });
    let record = this.factory.create({ input, result, receivedAt });

    const recent = await this.repository.findSince(this.burstDetector.windowStart(receivedAt));
    const incident = this.burstDetector.detect([...recent, record], receivedAt).find((i) => i.topic === record.topic);
    if (incident) {
      record = TicketFactory.withSeverity({
        ...record,
        incidentKey: incident.key,
        decision: 'ESCALATE',
        reasons: record.reasons.includes('BURST') ? record.reasons : [...record.reasons, 'BURST'],
        activity: [...record.activity, { who: 'System', what: `Linked to ${incident.key} (${incident.count} reports)`, at: receivedAt }],
      });
      await this.#linkSiblings(incident);
    }

    await this.repository.save(record);
    if (!silent) {
      this.events.emit('ticket.created', TicketService.summary(record));
      if (incident) this.events.emit('incident.updated', { key: incident.key, count: incident.count });
    }
    return record;
  }

  /** Earlier reports in the same outage get the incident key too, so the inbox groups them. */
  async #linkSiblings(incident) {
    for (const id of incident.ticketIds) {
      const t = await this.repository.findById(id);
      if (!t || t.incidentKey === incident.key) continue;
      const updated = TicketFactory.withSeverity({
        ...t, incidentKey: incident.key, decision: 'ESCALATE',
        reasons: t.reasons.includes('BURST') ? t.reasons : [...t.reasons, 'BURST'],
      });
      await this.repository.update(id, {
        incidentKey: updated.incidentKey, decision: updated.decision, reasons: updated.reasons,
        severity: updated.severity, severityRank: updated.severityRank, headline: updated.headline,
      });
    }
  }
}
