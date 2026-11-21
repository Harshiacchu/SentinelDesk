import { NotImplementedError } from '../../../core/errors.js';

/**
 * Port: anything that can triage a ticket.
 *
 * analyze({ subject, body }) resolves to a TriageResult:
 * {
 *   language: 'en' | 'de',
 *   topic: string,                                   // e.g. 'VPN', used for clustering + heatmap
 *   triage: { type, queue, priority },               // each { label, confidence }
 *   decision: 'AUTO_DRAFT' | 'ESCALATE',
 *   reasons: string[],                               // gate codes that fired
 *   checks: { code, passed }[],                      // all 10 gate checks
 *   precedents: { ticketId, similarity, subject, snippet, language, cited }[],
 *   draft: { language, lines: { text, source: number|null, unsupported: boolean }[] } | null,
 *   latency: { stage, ms }[]
 * }
 * @abstract
 */
export class TriageProvider {
  // eslint-disable-next-line no-unused-vars
  async analyze(ticket) {
    throw new NotImplementedError(this.constructor.name, 'analyze');
  }
}
