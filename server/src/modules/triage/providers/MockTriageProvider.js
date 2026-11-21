import { TriageProvider } from './TriageProvider.js';
import { DRAFTS, PRECEDENTS, QUEUE_BY_TOPIC } from './fixtures.js';
import { GateChecks } from '../../../domain/constants.js';
import { guessLanguage } from '../../../domain/LanguageGuesser.js';
import { ticketText } from '../../../domain/ticketText.js';

const INJECTION = /ignore (all |your |the )?(previous |prior )?(instructions|rules)|ignoriere|system prompt/i;
const RISKY = /refund|erstattung|discount|rabatt|price|preis|\bsla\b|compensation|gutschrift|legal|lawyer|anwalt/i;
const SEVERE = /outage|\bdown\b|ausfall|ausgefallen|breach|sicherheitsvorfall|data loss|datenverlust|patient|telemedi|krankenhaus|hospital|cannot connect|kritisch|critical|urgent|dringend/i;
const INCIDENT_TOPICS = new Set(['VPN', 'Network', 'Database', 'Printer', 'Email']);

/** Deterministic 0..1 from a string, so the same ticket always gets the same scores. */
function seeded(text, salt) {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}
const conf = (text, salt, lo, hi) => Number((lo + seeded(text, salt) * (hi - lo)).toFixed(2));

/**
 * PLACEHOLDER provider: rule-based triage so the whole console works before the
 * Python models exist. Same output shape as the real pipeline adapter.
 */
export class MockTriageProvider extends TriageProvider {
  constructor({ topicClassifier }) {
    super();
    this.topics = topicClassifier;
  }

  async analyze(ticket) {
    const text = ticketText(ticket);
    const language = guessLanguage(text);
    const topic = this.topics.classify(text);
    const severe = SEVERE.test(text);
    const risky = RISKY.test(text);
    const injection = INJECTION.test(text);

    const typeLabel = severe || INCIDENT_TOPICS.has(topic) ? 'Incident' : topic === 'Billing' || risky ? 'Request' : 'Request';
    const priorityLabel = severe ? 'high' : risky || topic === 'Billing' ? 'medium' : topic === 'Other' ? 'low' : 'medium';
    const triage = {
      type: { label: typeLabel, confidence: conf(text, 1, severe ? 0.82 : 0.6, 0.96) },
      queue: { label: QUEUE_BY_TOPIC[topic], confidence: conf(text, 2, topic === 'Other' ? 0.4 : 0.66, 0.93) },
      priority: { label: priorityLabel, confidence: conf(text, 3, severe ? 0.8 : 0.55, 0.94) },
    };

    const precedents = (PRECEDENTS[topic] ?? PRECEDENTS.Other).map((p, i) => ({
      ...p,
      similarity: Number((p.similarity - seeded(text, 10 + i) * 0.04).toFixed(2)),
      cited: false,
    }));

    const lines = (DRAFTS[topic] ?? DRAFTS.Other)[language].map(([t, source]) => ({ text: t, source, unsupported: false }));
    const promised = text.match(/\d+\s?%/);
    if (risky && promised) {
      const promise = language === 'de' ? `Wir erstatten Ihnen ${promised[0]} Ihrer Monatsgebühr. ` : `We will refund ${promised[0]} of your monthly fee. `;
      lines.splice(1, 0, { text: promise, source: null, unsupported: true });
    }
    for (const l of lines) if (l.source !== null && precedents[l.source]) precedents[l.source].cited = true;

    const reasons = [];
    if (injection) reasons.push('INJECTION');
    if (severe && typeLabel === 'Incident' && priorityLabel === 'high') reasons.push('HIGH_INCIDENT');
    if (risky) reasons.push('RISKY_ASK');
    if (Math.min(triage.type.confidence, triage.queue.confidence) < 0.55) reasons.push('LOW_CONFIDENCE');
    if (precedents[0].similarity < 0.6) reasons.push('NO_PRECEDENT');
    if (lines.some((l) => l.unsupported)) reasons.push('UNSUPPORTED_NUMBER');

    const draftMs = 900 + Math.round(seeded(text, 20) * 600);
    return {
      language,
      topic,
      triage,
      decision: reasons.length ? 'ESCALATE' : 'AUTO_DRAFT',
      reasons,
      checks: GateChecks.map((code) => ({ code, passed: !reasons.includes(code) })),
      precedents,
      draft: { language, lines },
      latency: [
        { stage: 'Mask PII', ms: 1 }, { stage: 'Language', ms: 2 },
        { stage: 'Embed', ms: 30 + Math.round(seeded(text, 21) * 15) }, { stage: 'Classify', ms: 9 + Math.round(seeded(text, 22) * 6) },
        { stage: 'Search', ms: 15 + Math.round(seeded(text, 23) * 10) }, { stage: 'Gate', ms: 3 },
        { stage: 'Draft', ms: draftMs }, { stage: 'Check draft', ms: 6 },
      ],
    };
  }
}
