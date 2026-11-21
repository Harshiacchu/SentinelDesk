import { NotFoundError, ValidationError } from '../../core/errors.js';
import { TicketStatus } from '../../domain/constants.js';
import { describeChanges } from '../../domain/changes.js';
import { TicketFactory } from '../tickets/TicketFactory.js';
import { TicketService } from '../tickets/TicketService.js';

/** Fields that come from triage and are replaced when a ticket is re-triaged. */
const TRIAGE_FIELDS = ['language', 'topic', 'triage', 'decision', 'reasons', 'reasonDetails', 'checks', 'precedents', 'draft', 'latency', 'pii'];

/**
 * Use cases:
 *   triage(input)          a new ticket arrives
 *   addFollowUp(id, text)  new information about an existing ticket -> re-triage the whole text
 * Both: mask PII -> provider.analyze -> outage check -> save -> notify live clients.
 * Depends only on abstractions (provider, repository, detector, events, masker).
 */
export class TriageService {
  constructor({ provider, repository, factory, burstDetector, events, piiMasker }) {
    Object.assign(this, { provider, repository, factory, burstDetector, events, piiMasker });
  }

  async triage(input, { receivedAt = new Date(), silent = false } = {}) {
    if (!input?.body?.trim()) throw new ValidationError('body is required');
    const result = await this.#analyze(input.subject, input.body);
    let record = this.factory.create({ input, result, receivedAt });

    const { record: withOutage, incident } = await this.#applyOutage(record, receivedAt);
    record = withOutage;

    await this.repository.save(record);
    if (!silent) {
      this.events.emit('ticket.created', TicketService.summary(record));
      if (incident) this.events.emit('incident.updated', { key: incident.key, count: incident.count });
    }
    return record;
  }

  async addFollowUp(id, { text, by = 'Operator' }) {
    if (!text?.trim()) throw new ValidationError('text is required');
    const before = await this.repository.findById(id);
    if (!before) throw new NotFoundError(`Ticket ${id}`);

    const at = new Date();
    const followups = [...(before.followups ?? []), { text: text.trim(), by, at }];
    const fullText = [before.body, ...followups.map((f) => f.text)].join('\n\n');
    const result = await this.#analyze(before.subject, fullText);

    let next = TicketFactory.withSeverity({ ...before, ...result, incidentKey: null, editedDraft: null });
    const others = (await this.repository.findSince(this.burstDetector.windowStart(at))).filter((t) => t.ticketId !== id);
    const { record: withOutage, incident } = await this.#applyOutage(next, at, others);
    next = withOutage;

    const changes = describeChanges(before, next);
    const reopened = before.status === TicketStatus.SENT || before.status === TicketStatus.RESOLVED;
    const patch = {
      ...Object.fromEntries(TRIAGE_FIELDS.map((f) => [f, next[f] ?? null])),
      incidentKey: next.incidentKey ?? null, severity: next.severity, severityRank: next.severityRank, headline: next.headline,
      followups, lastChange: { at, changes }, editedDraft: null,
      ...(reopened ? { status: TicketStatus.OPEN } : {}),
    };
    await this.repository.update(id, patch);
    const summary = changes.length ? changes.map((c) => `${c.label}: ${c.from} → ${c.to}`).join('; ') : 'no change to the decision';
    const updated = await this.repository.append(id, 'activity', { who: by, what: `Added a follow-up and re-ran triage (${summary})`, at });

    this.events.emit('ticket.updated', TicketService.summary(updated));
    if (incident) this.events.emit('incident.updated', { key: incident.key, count: incident.count });
    return updated;
  }

  /** PII guardrail + provider call. The AI side only ever receives masked text. */
  async #analyze(subject, body) {
    const maskedSubject = this.piiMasker.mask(subject ?? '');
    const maskedBody = this.piiMasker.mask(body);
    const result = await this.provider.analyze({ subject: maskedSubject.text || null, body: maskedBody.text });
    const entities = mergeEntities(maskedSubject.entities, maskedBody.entities);
    return { ...result, reasonDetails: result.reasonDetails ?? {}, pii: { entities, maskedBody: maskedBody.text } };
  }

  /** Links the record to a live outage when enough similar incidents arrived recently. */
  async #applyOutage(record, at, recent = null) {
    const pool = recent ?? (await this.repository.findSince(this.burstDetector.windowStart(at)));
    const incident = this.burstDetector.detect([...pool, record], at).find((i) => i.topic === record.topic);
    if (!incident) return { record, incident: null };
    const linked = TicketFactory.withSeverity({
      ...record,
      incidentKey: incident.key,
      decision: 'ESCALATE',
      reasons: record.reasons.includes('BURST') ? record.reasons : [...record.reasons, 'BURST'],
      activity: [...(record.activity ?? []), { who: 'System', what: `Linked to ${incident.key} (${incident.count} reports)`, at }],
    });
    await this.#linkSiblings(incident, record.ticketId);
    return { record: linked, incident };
  }

  /** Earlier reports in the same outage get the incident key too, so the inbox groups them. */
  async #linkSiblings(incident, selfId) {
    for (const id of incident.ticketIds) {
      if (id === selfId) continue;
      const t = await this.repository.findById(id);
      if (!t || t.incidentKey === incident.key) continue;
      const updated = TicketFactory.withSeverity({
        ...t, incidentKey: incident.key, decision: 'ESCALATE',
        reasons: t.reasons.includes('BURST') ? t.reasons : [...t.reasons, 'BURST'],
      });
      await this.repository.update(id, {
        incidentKey: updated.incidentKey, decision: updated.decision, reasons: updated.reasons,
        severity: updated.severity, severityRank: updated.severityRank, headline: updated.headline, draft: null,
      });
    }
  }
}

function mergeEntities(a, b) {
  const counts = {};
  for (const e of [...a, ...b]) counts[e.type] = (counts[e.type] ?? 0) + e.count;
  return Object.entries(counts).map(([type, count]) => ({ type, count }));
}
