import { Pagination } from '../../components/ui/Pagination.jsx';
import { Dot } from '../../components/ui/Tone.jsx';
import { timeAgo } from '../../lib/format.js';

const VIEWS = [
  { id: 'unclaimed', label: 'Waiting' },
  { id: 'mine', label: 'Mine' },
  { id: 'resolved', label: 'Resolved' },
];

/** Tickets the AI could not safely answer, most urgent first. */
export function AgentQueue({ agent, onRename, view, onView, data, loading, selectedId, onSelect, onPage }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 4px', fontSize: 12 }} className="muted">
        <span>Working as <strong style={{ color: 'var(--text)' }}>{agent}</strong></span>
        <button className="btn-link" style={{ marginLeft: 'auto', fontSize: 12 }} onClick={onRename}>Change</button>
      </div>
      <div className="seg" role="group" aria-label="Queue">
        {VIEWS.map((v) => <button key={v.id} aria-pressed={view === v.id} onClick={() => onView(v.id)}>{v.label}</button>)}
      </div>
      {loading && !data && [0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 48 }} />)}
      {data?.items.length === 0 && <p className="empty" style={{ padding: 20 }}>{view === 'unclaimed' ? 'Queue is clear.' : 'Nothing here yet.'}</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {data?.items.map((t) => {
          const active = t.ticketId === selectedId;
          return (
            <button key={t.ticketId} className="row-hover" onClick={() => onSelect(t.ticketId)} aria-current={active ? 'true' : 'false'}
              style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px 9px', borderRadius: 10, textAlign: 'left', color: 'var(--text)',
                border: `1px solid ${active ? 'color-mix(in srgb, var(--accent) 35%, transparent)' : 'transparent'}`, background: active ? 'linear-gradient(90deg, var(--accent-soft), transparent)' : 'transparent' }}>
              <Dot tone={t.severity} pulse={t.severity === 'critical'} />
              <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.subject || t.bodyPreview}</span>
                <span className="muted" style={{ fontSize: 11 }}>{t.queue} · {t.language?.toUpperCase()}{t.assignee && view !== 'mine' ? ` · ${t.assignee}` : ''}</span>
              </span>
              <span className="faint" style={{ fontSize: 11 }}>{timeAgo(t.receivedAt)}</span>
            </button>
          );
        })}
      </div>
      {data && data.total > 0 && <Pagination {...data} onPage={onPage} />}
    </div>
  );
}
