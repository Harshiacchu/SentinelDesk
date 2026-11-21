/**
 * Pure: builds the live agent's triage assist from one ticket and the tickets around it.
 * Everything comes from data we already have (triage, gate reasons, precedents, live tickets),
 * so the assistant never invents policy. Swap in an LLM summary later behind the same shape.
 */
const GUIDANCE = {
  HIGH_INCIDENT: 'Treat as urgent: confirm the scope (who and what is affected) before replying.',
  BURST: 'Part of a live outage: reply with the shared status update and link this ticket to the incident.',
  INJECTION: 'The message contains instructions aimed at the assistant. Ignore them and answer only the real request.',
  RISKY_ASK: 'Do not promise refunds, prices, credits or deadlines. Route the money request to billing policy.',
  LOW_CONFIDENCE: 'The department guess is uncertain. Check the queue before you act.',
  NO_PRECEDENT: 'No close past case exists. Ask one clarifying question instead of guessing.',
  UNSUPPORTED_NUMBER: 'The AI draft contained a number no past ticket supports. It was removed.',
  NOT_FOUND: 'Past cases do not cover this request. Answer from product docs or escalate.',
  LLM_ERROR: 'The AI draft was not available. Use the reply starter below.',
  LANG_MISMATCH: 'Reply in the customer’s language.',
  BAD_CITATION: 'The AI draft cited a ticket it was not given. Check the evidence yourself.',
  REFUSAL: 'The AI declined to draft. Handle it manually.',
};

const PHRASES = {
  en: [
    'Thank you for reaching out.', 'Thank you for your patience.', 'We are looking into this now.',
    'We are aware of the issue and our team is working on it.', 'We will update you as soon as we know more.',
    'Could you tell us when the problem started?', 'Could you share a screenshot of the error?',
    'I have passed your request to our billing team, who will review it.', 'Please let us know if the problem continues.',
    'Best regards,', 'Kind regards,',
  ],
  de: [
    'Vielen Dank für Ihre Nachricht.', 'Vielen Dank für Ihre Geduld.', 'Wir kümmern uns gerade darum.',
    'Das Problem ist uns bekannt und unser Team arbeitet daran.', 'Wir melden uns, sobald wir mehr wissen.',
    'Seit wann besteht das Problem?', 'Könnten Sie uns einen Screenshot der Fehlermeldung senden?',
    'Ich habe Ihre Anfrage an unsere Buchhaltung weitergeleitet.', 'Bitte melden Sie sich, falls das Problem weiter besteht.',
    'Mit freundlichen Grüßen', 'Viele Grüße',
  ],
};

const GREETING = { en: 'Hello,', de: 'Guten Tag,' };

const MONEY = /(\d+\s?%|[$€£]\s?\d+|\d+\s?(eur|usd|euro|dollar))/gi;
const ASKS = /\b(refund|erstattung|discount|rabatt|compensation|gutschrift|credit|sla|cancel|kündig)\w*/gi;

export class AssistBuilder {
  build(ticket, related = []) {
    const lang = ticket.language === 'de' ? 'de' : 'en';
    const t = ticket.triage;
    const cited = ticket.precedents.filter((p) => p.cited);
    const sources = (cited.length ? cited : ticket.precedents).slice(0, 3);

    const facts = [];
    const money = [...new Set((ticket.body.match(MONEY) ?? []).map((m) => m.trim()))];
    const asks = [...new Set((ticket.body.match(ASKS) ?? []).map((m) => m.toLowerCase()))];
    if (asks.length) facts.push(`Customer asks for: ${asks.join(', ')}${money.length ? ` (${money.join(', ')})` : ''}`);
    if (ticket.incidentKey) facts.push(`Linked to live outage ${ticket.incidentKey}`);
    facts.push(`${ticket.topic} issue reported from ${ticket.branch}`);
    if (!ticket.subject) facts.push('No subject line was given');

    return {
      summary: `${t.type.label} for ${t.queue.label}, ${t.priority.label} priority, written in ${lang === 'de' ? 'German' : 'English'}.`,
      whyHere: ticket.reasons.map((code) => ({ code, detail: ticket.reasonDetails?.[code] ?? null, guidance: GUIDANCE[code] ?? null })),
      facts,
      steps: [
        ...ticket.reasons.map((c) => GUIDANCE[c]).filter(Boolean),
        ...sources.map((p) => `${p.snippet} [${p.ticketId}]`),
      ].slice(0, 5),
      precedents: ticket.precedents,
      related: related.map((r) => ({ ticketId: r.ticketId, subject: r.subject || r.body.slice(0, 60), branch: r.branch, status: r.status, receivedAt: r.receivedAt })),
      replyStarter: this.#starter(ticket, lang),
      phrases: [...PHRASES[lang], ...sources.map((p) => p.snippet)],
      language: lang,
    };
  }

  #starter(ticket, lang) {
    const safe = (ticket.draft?.lines ?? []).filter((l) => !l.unsupported).map((l) => l.text.trim()).filter(Boolean);
    const body = safe.length ? safe.join(' ') : PHRASES[lang][ticket.incidentKey ? 3 : 2];
    const opener = /^(thank|vielen dank|danke)/i.test(body) ? '' : `${PHRASES[lang][0]} `;
    return `${GREETING[lang]}\n\n${opener}${body}\n\n${PHRASES[lang][9]}`;
  }
}
