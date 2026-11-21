import { Pagination } from '../../components/ui/Pagination.jsx';
import { Dot } from '../../components/ui/Tone.jsx';
import { timeAgo } from '../../lib/format.js';

const FILTERS = [
  { id: 'needs', label: 'Needs you' },
  { id: 'ready', label: 'Ready' },
  { id: 'done', label: 'Done' },
];

/** Smart inbox: server already sorts by severity, so critical work is always on top. */
export function InboxPanel({ filter, onFilter, data, loading, selectedId, onSelect, onPage }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="seg" role="group" aria-label="Inbox filter">
        {FILTERS.map((f) => (
          <button key={f.id} aria-pressed={filter === f.id} onClick={() => onFilter(f.id)}>{f.label}</button>
        ))}
      </div>

      {loading && !data && [0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 48 }} />)}
      {data?.items.length === 0 && <p className="empty" style={{ padding: 20 }}>Nothing here.</p>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {data?.items.map((t) => (
          <InboxItem key={t.ticketId} ticket={t} active={t.ticketId === selectedId} onSelect={() => onSelect(t.ticketId)} />
        ))}
      </div>
      {data && data.total > 0 && <Pagination {...data} onPage={onPage} />}
    </div>
  );
}

function InboxItem({ ticket, active, onSelect }) {
  const style = {
    width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px 9px', borderRadius: 10, textAlign: 'left', color: 'var(--text)',
    border: `1px solid ${active ? 'color-mix(in srgb, var(--accent) 35%, transparent)' : 'transparent'}`,
    background: active ? 'linear-gradient(90deg, var(--accent-soft), transparent)' : 'transparent',
  };
  return (
    <button className="row-hover" style={style} onClick={onSelect} aria-current={active ? 'true' : 'false'}>
      <Dot tone={ticket.severity} pulse={ticket.severity === 'critical'} />
      <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {ticket.subject || ticket.bodyPreview}
        </span>
        <span className="muted" style={{ fontSize: 11 }}>
          {ticket.queue} · {ticket.language?.toUpperCase()}{ticket.incidentKey ? ' · outage' : ''}
        </span>
      </span>
      <span className="faint" style={{ fontSize: 11 }}>{timeAgo(ticket.receivedAt)}</span>
    </button>
  );
}
