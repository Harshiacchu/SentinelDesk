import { NotFoundError } from '../../core/errors.js';

/**
 * Ticket-scoped assistant. Answers ONLY from the stored ticket and its precedents,
 * so it can never invent policy. Each intent is a small strategy object.
 * Swap in an LLM later by adding an intent that calls it with the same evidence.
 */
const INTENTS = [
  {
    id: 'why', label: 'Why this decision?',
    match: /why|reason|warum|decision|escalat/i,
    answer: (t) => (t.reasons.length
      ? `${t.headline}. Checks that fired: ${t.reasons.join(', ')}.`
      : `${t.headline}. All checks passed and the reply is grounded in ${t.precedents.filter((p) => p.cited).length} past ticket(s).`),
  },
  {
    id: 'similar', label: 'Similar past tickets?',
    match: /similar|past|precedent|ähnlich|history/i,
    answer: (t) => t.precedents.slice(0, 3).map((p) => `${p.ticketId} (${p.similarity}): ${p.snippet}`).join('\n'),
  },
  {
    id: 'outage', label: 'Is this part of an outage?',
    match: /outage|incident|others|burst|ausfall/i,
    answer: (t) => (t.incidentKey ? `Yes. It is linked to ${t.incidentKey} with other ${t.topic} reports in the last few minutes.` : `No. No other ${t.topic} incidents cluster with it right now.`),
  },
  {
    id: 'checks', label: 'Which checks passed?',
    match: /check|safe|gate|pass/i,
    answer: (t) => `${t.checks.filter((c) => c.passed).length} of ${t.checks.length} passed.` + (t.reasons.length ? ` Failed: ${t.reasons.join(', ')}.` : ''),
  },
];

export class ChatService {
  constructor({ repository }) {
    this.repo = repository;
  }

  get suggestions() {
    return INTENTS.map(({ id, label }) => ({ id, label }));
  }

  async answer(ticketId, question) {
    const ticket = await this.repo.findById(ticketId);
    if (!ticket) throw new NotFoundError(`Ticket ${ticketId}`);
    const intent = INTENTS.find((i) => i.match.test(question));
    return {
      question,
      answer: intent ? intent.answer(ticket) : 'I can only answer from this ticket and its past resolved tickets. Try asking why it was routed this way, or for similar tickets.',
      grounded: Boolean(intent),
      sources: intent?.id === 'similar' ? ticket.precedents.slice(0, 3).map((p) => p.ticketId) : [],
    };
  }
}
