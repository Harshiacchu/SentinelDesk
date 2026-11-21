import { Chip, Dot, toneClass } from '../../components/ui/Tone.jsx';
import { LANGUAGE_NAMES, timeAgo } from '../../lib/format.js';
import { STATUS_LABEL, reasonInfo } from '../../lib/severity.js';
import { TriageStrip } from './TriageStrip.jsx';

/** A readable title from the message itself (people type the problem, not a subject line). */
const titleFrom = (body) => {
  const first = body.split(/(?<=[.!?])\s|\n/)[0].trim();
  return first.length > 80 ? `${first.slice(0, 77)}…` : first;
};

export function TicketHeader({ ticket }) {
  const reason = ticket.reasons.length
    ? ticket.reasons.slice(0, 2).map((r) => reasonInfo(r).title).join(' · ')
    : 'every sentence has a source';
  return (
    <section className="rise" style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'stretch' }}>
      <div style={{ flex: '1 1 460px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12, justifyContent: 'center' }}>
        <span className="muted" style={{ fontSize: 13 }}>
          <span className="mono">{ticket.ticketId}</span> · {LANGUAGE_NAMES[ticket.language]} · {timeAgo(ticket.receivedAt)} ago
        </span>
        <h1 className="title-grad" style={{ margin: 0, fontSize: 32, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.15 }}>
          {ticket.subject || titleFrom(ticket.body)}
        </h1>
        <TriageStrip ticket={ticket} />
        {ticket.status !== 'open' && <span><Chip tone="info">{STATUS_LABEL[ticket.status]}</Chip></span>}
      </div>
      <div className={`glass ${toneClass(ticket.severity)} ${ticket.severity === 'ready' ? 'glow-still' : 'glow'}`}
        style={{ flex: '1 1 280px', maxWidth: 360, padding: '20px 22px', borderRadius: 18, display: 'flex', flexDirection: 'column', gap: 6, borderColor: 'transparent' }}>
        <span className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Dot tone={ticket.severity} pulse={ticket.severity === 'critical'} /> Decision</span>
        <span style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--tone)' }}>{ticket.headline}</span>
        <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text-2)' }}>{reason}</span>
      </div>
    </section>
  );
}
