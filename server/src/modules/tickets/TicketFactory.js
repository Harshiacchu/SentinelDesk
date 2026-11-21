import { headlineFor, severityFor } from '../../domain/Severity.js';
import { TicketStatus } from '../../domain/constants.js';

/** Builds a persisted ticket record from raw input + a TriageResult. One place for that shape. */
export class TicketFactory {
  #counter = 0;

  /** Continue numbering after existing tickets (matters with a persistent store). */
  startAfter(count) {
    this.#counter = Math.max(this.#counter, count);
  }

  nextId() {
    this.#counter += 1;
    return `LIVE-${String(this.#counter).padStart(4, '0')}`;
  }

  create({ input, result, receivedAt = new Date() }) {
    const record = {
      ticketId: this.nextId(),
      receivedAt,
      subject: input.subject ?? null,
      body: input.body,
      branch: input.branch,
      ...result,
      incidentKey: null,
      status: TicketStatus.OPEN,
      feedback: [],
      notes: [],
      activity: [{ who: 'System', what: `Triaged in ${result.latency.reduce((a, s) => a + s.ms, 0)} ms`, at: receivedAt }],
    };
    return TicketFactory.withSeverity(record);
  }

  /** Recomputes the derived fields after reasons/decision change (e.g. a burst was detected). */
  static withSeverity(record) {
    const sev = severityFor(record.decision, record.reasons);
    return { ...record, severity: sev.level, severityRank: sev.rank, headline: headlineFor(sev.level) };
  }
}
