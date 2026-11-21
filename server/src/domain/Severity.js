/**
 * Turns a raw gate result into what the operator needs to see.
 *   critical: page someone now (outage / high-priority incident)
 *   review:   a person must handle it (money, injection, low confidence…)
 *   ready:    safe to send
 * rank drives the smart inbox order (lower = higher up).
 */
const CRITICAL_CODES = new Set(['HIGH_INCIDENT', 'BURST']);

export const Severity = Object.freeze({
  CRITICAL: { level: 'critical', rank: 0 },
  REVIEW: { level: 'review', rank: 1 },
  READY: { level: 'ready', rank: 2 },
});

export function severityFor(decision, reasons = []) {
  if (decision !== 'ESCALATE') return Severity.READY;
  return reasons.some((r) => CRITICAL_CODES.has(r)) ? Severity.CRITICAL : Severity.REVIEW;
}

const HEADLINES = {
  critical: 'Escalate now',
  review: 'Needs a person',
  ready: 'Ready to send',
};

export const headlineFor = (level) => HEADLINES[level];
