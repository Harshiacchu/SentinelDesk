import { reasonInfo } from '../../lib/severity.js';
import { LANGUAGE_NAMES, clock, duration } from '../../lib/format.js';

/**
 * Pure mapping: ticket → the six summary cards and their full detail rows.
 * Keeping this out of components makes the UI dumb and this logic easy to test.
 * Row shape: { key, title, text, meta, tone, bar? }
 */
export function buildDetails(ticket) {
  const t = ticket.triage;
  const totalMs = ticket.latency.reduce((a, s) => a + s.ms, 0);
  const failed = ticket.checks.filter((c) => !c.passed);
  const cited = ticket.precedents.filter((p) => p.cited);
  const latest = ticket.activity[ticket.activity.length - 1];

  return [
    {
      id: 'why', name: 'Why', tone: ticket.severity,
      partial: ticket.headline, hint: ticket.reasons.length ? `${ticket.reasons.length} reason${ticket.reasons.length > 1 ? 's' : ''}` : 'all checks passed',
      rows: ticket.reasons.length
        ? ticket.reasons.map((code) => { const r = reasonInfo(code); return { key: code, title: r.title, text: ticket.reasonDetails?.[code] ?? r.text, meta: code, tone: r.tone.replace('tone-', '') }; })
        : [{ key: 'ok', title: 'Safe to send', text: `Every sentence is grounded in ${cited.length} past ticket(s) and no checks fired.`, tone: 'ready' }],
    },
    {
      id: 'classification', name: 'Classification', tone: 'info',
      partial: `${t.type.label} · ${Math.round(t.type.confidence * 100)}%`, hint: `${t.queue.label} · ${t.priority.label} priority`,
      rows: [
        ...['type', 'queue', 'priority'].map((k) => ({
          key: k, title: k === 'queue' ? 'Department' : k[0].toUpperCase() + k.slice(1), text: t[k].label,
          meta: `${Math.round(t[k].confidence * 100)}%`, tone: t[k].confidence >= 0.8 ? 'ready' : t[k].confidence >= 0.6 ? 'review' : 'critical', bar: t[k].confidence * 100,
        })),
        { key: 'lang', title: 'Language', text: `${LANGUAGE_NAMES[ticket.language] ?? ticket.language}, detected automatically`, meta: ticket.language.toUpperCase(), tone: 'info' },
        { key: 'topic', title: 'Problem type', text: `${ticket.topic}, used to spot outages (many tickets about the same thing)`, meta: '', tone: 'info' },
      ],
    },
    {
      id: 'evidence', name: 'Evidence', tone: 'info',
      partial: `${ticket.precedents.length} past tickets`, hint: `best match ${ticket.precedents[0]?.similarity ?? '—'}`,
      rows: ticket.precedents.map((p) => ({
        key: p.ticketId, title: `${p.ticketId}${p.cited ? ' · cited' : ''}`, text: p.snippet, meta: String(p.similarity), tone: p.cited ? 'ready' : 'muted', bar: p.similarity * 100,
      })),
    },
    {
      id: 'checks', name: 'Safety checks', tone: failed.length ? 'critical' : 'ready',
      partial: `${ticket.checks.length - failed.length} of ${ticket.checks.length} passed`, hint: failed.length ? failed.map((c) => reasonInfo(c.code).title).join(', ') : 'nothing stopped it',
      rows: ticket.checks.map((c) => ({ key: c.code, title: reasonInfo(c.code).title, text: c.passed ? 'Passed' : ticket.reasonDetails?.[c.code] ?? reasonInfo(c.code).text, meta: c.passed ? 'ok' : 'fail', tone: c.passed ? 'ready' : 'critical' })),
    },
    {
      id: 'pipeline', name: 'Speed', tone: 'info',
      partial: duration(totalMs), hint: `total time across ${ticket.latency.length} steps`,
      rows: ticket.latency.map((s) => ({
        key: s.stage, title: s.stage, text: /draft/i.test(s.stage) && !/check/i.test(s.stage) ? 'Language model, grounded in evidence' : 'Local, no AI call',
        meta: `${s.ms} ms`, tone: s.ms > 500 ? 'review' : 'info', bar: Math.max(2, (s.ms / totalMs) * 100),
      })),
    },
    {
      id: 'activity', name: 'Activity & notes', tone: 'muted',
      partial: `${ticket.activity.length} event${ticket.activity.length === 1 ? '' : 's'}`, hint: latest ? `latest: ${latest.what.toLowerCase()}` : '',
      rows: [...ticket.activity].reverse().map((a, i) => ({ key: `${i}-${a.at}`, title: a.who, text: a.what, meta: clock(a.at), tone: a.who === 'System' ? 'info' : 'ready' })),
    },
  ];
}
