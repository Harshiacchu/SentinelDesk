import { GateChecks } from '../../../domain/constants.js';

const CITE = /\[(TKT-\d+)\]/g;
const STAGE_NAMES = {
  pii: 'Mask PII', lang: 'Language', embed: 'Embed', retrieve: 'Search', triage: 'Classify',
  gate_pre: 'Gate', draft: 'Draft', gate_post: 'Check draft',
};

/**
 * Adapter: Python pipeline.run() result (CONTRACT.md section 9) -> console TriageResult.
 * Keeping this in one class means a contract change on the Python side is a one-file change here.
 *
 * Input: { ticket_id, lang:{lang,source}, pii, triage, hits[], gate:{status, reasons:[{code,detail}]},
 *          draft:{reply, cited_ids, not_found, stop_reason, error}|null, burst, timings_ms }
 */
export class PipelineResultMapper {
  constructor({ topicClassifier }) {
    this.topics = topicClassifier;
  }

  toTriageResult(r, text) {
    const hits = r.hits ?? [];
    const ids = hits.map((h) => h.ticket_id);
    const cited = new Set(r.draft?.cited_ids ?? []);
    const { reasons, reasonDetails } = PipelineResultMapper.#reasons(r.gate?.reasons ?? []);
    // A burst only means an outage when the tickets are incidents (identical refund requests are not an outage).
    const incidentLike = r.triage?.type?.label === 'Incident' || reasons.includes('HIGH_INCIDENT');
    if (r.burst?.active && incidentLike && !reasons.includes('BURST')) {
      reasons.push('BURST');
      reasonDetails.BURST = `${r.burst.cluster_size} similar tickets arrived in a short window.`;
    }

    return {
      language: r.lang?.lang ?? r.triage?.language ?? 'en',
      topic: this.topics.classify(text),
      triage: {
        type: PipelineResultMapper.#head(r.triage?.type),
        queue: PipelineResultMapper.#head(r.triage?.queue),
        priority: PipelineResultMapper.#head(r.triage?.priority),
      },
      decision: r.gate?.status === 'auto_draft' ? 'AUTO_DRAFT' : 'ESCALATE',
      reasons,
      reasonDetails,
      checks: [...new Set([...GateChecks, ...reasons.filter((c) => c !== 'BURST')])].map((code) => ({ code, passed: !reasons.includes(code) })),
      precedents: hits.map((h) => ({
        ticketId: h.ticket_id, similarity: Number(h.score?.toFixed?.(2) ?? h.score), subject: h.subject,
        snippet: h.answer_snippet ?? (h.answer ?? '').slice(0, 240), language: h.language, cited: cited.has(h.ticket_id),
      })),
      // A draft is shown only if the gate approved it (status auto_draft).
      draft: r.gate?.status === 'auto_draft' && r.draft?.reply ? { language: r.lang?.lang ?? 'en', lines: PipelineResultMapper.#lines(r.draft.reply, ids) } : null,
      latency: Object.entries(r.timings_ms ?? {}).filter(([k]) => k !== 'total').map(([k, ms]) => ({ stage: STAGE_NAMES[k] ?? k, ms: Math.round(ms) })),
    };
  }

  static #head(h) {
    return { label: h?.label ?? 'Unknown', confidence: Number(h?.prob ?? h?.confidence ?? 0) };
  }

  /** Accepts contract reasons [{code, detail}] and legacy "CODE: detail" strings. */
  static #reasons(raw) {
    const reasons = [];
    const reasonDetails = {};
    for (const item of raw) {
      const [code, detail] = typeof item === 'string'
        ? [item.split(':')[0].trim().toUpperCase(), item.split(':').slice(1).join(':').trim()]
        : [item.code, item.detail];
      if (!reasons.includes(code)) reasons.push(code);
      if (detail) reasonDetails[code] = detail;
    }
    return { reasons, reasonDetails };
  }

  static #lines(reply, ids) {
    const sentences = reply.match(/[^.!?]+[.!?]*\s*/g) ?? [reply];
    return sentences.map((s) => {
      const ref = [...s.matchAll(CITE)][0]?.[1];
      const idx = ref ? ids.indexOf(ref) : -1;
      return { text: s.replace(CITE, '').replace(/\s+/g, ' '), source: idx >= 0 ? idx : null, unsupported: false };
    });
  }
}
