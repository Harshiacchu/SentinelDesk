import { randomBytes } from 'node:crypto';

/**
 * Pure rules for the customer <-> AI <-> agent conversation on a ticket.
 * Message: { id, from: 'customer' | 'ai' | 'agent' | 'system', name, text, sources?, at }
 */
const TEXT = {
  en: {
    waiting: (p) => `Thanks, we've got your message. This one needs a person, so it's been passed to our support team (priority: ${p}). An agent will join this chat shortly.`,
    joined: (n) => `${n} joined the conversation.`,
    resolved: (n) => `${n} marked this as resolved. Reply here if you still need help.`,
    handoff: 'You asked to talk to a person. An agent will join this chat shortly.',
  },
  de: {
    waiting: (p) => `Danke, wir haben Ihre Nachricht erhalten. Das übernimmt eine Person aus unserem Support-Team (Priorität: ${p}). Ein Mitarbeiter meldet sich gleich hier im Chat.`,
    joined: (n) => `${n} ist dem Gespräch beigetreten.`,
    resolved: (n) => `${n} hat das Anliegen als gelöst markiert. Antworten Sie hier, falls Sie noch Hilfe brauchen.`,
    handoff: 'Sie möchten mit einer Person sprechen. Ein Mitarbeiter meldet sich gleich hier im Chat.',
  },
};

const PRIORITY = { en: { high: 'high', medium: 'medium', low: 'low' }, de: { high: 'hoch', medium: 'mittel', low: 'niedrig' } };

export const newAccessKey = () => randomBytes(6).toString('base64url');

export function message(from, text, { name = null, sources = [], at = new Date() } = {}) {
  return { id: randomBytes(5).toString('hex'), from, name, text, sources, at };
}

export const systemText = (lang) => TEXT[lang === 'de' ? 'de' : 'en'];

/** First messages of a new ticket: the customer's own words, then the AI answer or a hand-off note. */
export function openingMessages(record) {
  const lang = record.language === 'de' ? 'de' : 'en';
  const at = new Date(record.receivedAt);
  const first = message('customer', record.body, { at });
  const safeLines = (record.draft?.lines ?? []).filter((l) => !l.unsupported).map((l) => l.text.trim()).filter(Boolean);
  if (record.severity === 'ready' && safeLines.length) {
    const sources = record.precedents.filter((p) => p.cited).map((p) => p.ticketId);
    return [first, message('ai', safeLines.join(' '), { name: 'SentinelDesk', sources, at })];
  }
  const priority = PRIORITY[lang][record.triage?.priority?.label] ?? record.triage?.priority?.label ?? '';
  return [first, message('system', TEXT[lang].waiting(priority), { at })];
}

/** What the customer may see: no gate codes, scores or internal notes. */
export function customerView(t) {
  const done = t.status === 'resolved' || t.status === 'sent';
  let stage = 'waiting_for_agent';
  if (done) stage = 'resolved';
  else if (t.assignee) stage = 'with_agent';
  else if (t.severity === 'ready') stage = 'answered_by_ai';
  return {
    ticketId: t.ticketId, subject: t.subject, receivedAt: t.receivedAt, language: t.language,
    priority: t.triage?.priority?.label, stage, agentName: t.assignee ?? null, messages: t.messages ?? [],
  };
}
