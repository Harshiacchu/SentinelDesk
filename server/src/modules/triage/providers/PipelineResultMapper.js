import { GateChecks } from '../../../domain/constants.js';

const CITE = /\[(TKT-\d+)\]/g;

/**
 * Adapter: converts the Python pipeline's PipelineResult (sentineldesk/contracts.py)
 * into the console's TriageResult. Keeping this in one class means a contract change
 * on the Python side is a one-file change here.
 */
export class PipelineResultMapper {
  constructor({ topicClassifier }) {
    this.topics = topicClassifier;
  }

  toTriageResult(result, text) {
    const cases = result.cases ?? [];
    const ids = cases.map((c) => c.ticket_id);
    const cited = new Set(result.draft?.cited_ticket_ids ?? []);
    const reasons = (result.gate?.reasons ?? []).map((r) => String(r).split(':')[0].trim().toUpperCase());

    return {
      language: result.triage.language,
      topic: this.topics.classify(text),
      triage: { type: result.triage.type, queue: result.triage.queue, priority: result.triage.priority },
      decision: result.gate.decision,
      reasons,
      checks: GateChecks.map((code) => ({ code, passed: !reasons.includes(code) })),
      precedents: cases.map((c) => ({
        ticketId: c.ticket_id, similarity: c.similarity, subject: c.subject,
        snippet: (c.answer ?? '').slice(0, 220), language: c.language, cited: cited.has(c.ticket_id),
      })),
      draft: result.draft ? { language: result.triage.language, lines: this.#lines(result.draft, ids) } : null,
      latency: Object.entries(result.latency_ms ?? {}).filter(([k]) => k !== 'total').map(([stage, ms]) => ({ stage, ms })),
    };
  }

  #lines(draft, ids) {
    const sentences = draft.reply.match(/[^.!?]+[.!?]*\s*/g) ?? [draft.reply];
    const lines = sentences.map((s) => {
      const ref = [...s.matchAll(CITE)][0]?.[1];
      return { text: s.replace(CITE, '').replace(/\s+/g, ' '), source: ref ? ids.indexOf(ref) : null, unsupported: false };
    });
    for (const req of draft.unsupported_requests ?? []) lines.push({ text: `${req} `, source: null, unsupported: true });
    return lines;
  }
}
