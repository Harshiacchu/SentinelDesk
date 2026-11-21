/** UI meaning of each severity level: words, tone class and the primary action. */
export const SEVERITY = {
  critical: { tone: 'tone-critical', label: 'Critical', primary: { action: 'escalate', label: 'Page on-call engineer' }, lock: 'Auto-replies are off for critical incidents.' },
  review: { tone: 'tone-review', label: 'Needs a person', primary: { action: 'handoff', label: 'Hand to specialist team' }, lock: 'Money, overrides and low-confidence tickets always need a person.' },
  ready: { tone: 'tone-ready', label: 'Ready', primary: { action: 'send', label: 'Send reply' }, lock: 'You can undo for 5 seconds after sending.' },
};

export const STATUS_LABEL = { open: 'Open', sent: 'Sent', escalated: 'Escalated', resolved: 'Resolved' };

/** Plain-English meaning of every gate code. */
export const REASONS = {
  HIGH_INCIDENT: { title: 'High-priority incident', text: 'Classifier and severity words both point to an urgent incident.', tone: 'tone-critical' },
  BURST: { title: 'Part of an outage', text: 'Several similar incidents arrived within minutes.', tone: 'tone-critical' },
  INJECTION: { title: 'Tries to override rules', text: 'The message contains instructions aimed at the assistant.', tone: 'tone-critical' },
  RISKY_ASK: { title: 'Asks for money or guarantees', text: 'Refunds, prices, SLA credits and legal promises need a person.', tone: 'tone-review' },
  LOW_CONFIDENCE: { title: 'Low confidence', text: 'The classifier is unsure about type or department.', tone: 'tone-review' },
  NO_PRECEDENT: { title: 'No close precedent', text: 'No past ticket is similar enough to ground a reply.', tone: 'tone-review' },
  NOT_FOUND: { title: 'Not covered', text: 'The model said past cases do not cover this request.', tone: 'tone-review' },
  BAD_CITATION: { title: 'Bad citation', text: 'The draft cited a ticket it was not given.', tone: 'tone-review' },
  UNSUPPORTED_NUMBER: { title: 'Unsupported promise', text: 'The draft contains a number or promise no past ticket supports.', tone: 'tone-critical' },
  LANG_MISMATCH: { title: 'Wrong language', text: 'The reply language differs from the customer’s.', tone: 'tone-review' },
  REFUSAL: { title: 'Model refused', text: 'The language model declined to answer.', tone: 'tone-review' },
  LLM_ERROR: { title: 'Draft unavailable', text: 'The language model call failed or timed out, so a person takes over.', tone: 'tone-review' },
};

export const reasonInfo = (code) => REASONS[code] ?? { title: code, text: '', tone: 'tone-muted' };
