import { ConfidenceBar } from '../../components/ui/Tone.jsx';

/** Top retrieved historical tickets: ID, similarity and answer snippet. Always visible. */
export function TopPrecedents({ ticket, picked }) {
  const { precedents } = ticket;
  return (
    <section aria-label="Top past tickets" className="glass card rise" style={{ animationDelay: '.16s', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h2 className="card-title">Top past tickets</h2>
        <span className="muted" style={{ fontSize: 12 }}>{precedents.length} most similar resolved tickets</span>
      </div>
      {precedents.length === 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>No similar past tickets were found.</p>}
      <ol className="list" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {precedents.map((p, i) => (
          <li key={p.ticketId} className="prec-row" style={{ display: 'grid', gap: 12, alignItems: 'start', padding: '10px 8px', borderRadius: 10,
            background: picked === i ? 'var(--accent-soft)' : 'transparent', transition: 'background .2s', borderTop: i ? '1px solid var(--border)' : 0 }}>
            <span className="mono faint" style={{ fontSize: 12, paddingTop: 1 }}>[{i + 1}]</span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span className="mono" style={{ fontSize: 12, color: 'var(--accent-text)' }}>{p.ticketId}</span>
              <span style={{ display: 'flex', gap: 4 }}>
                <span className={`chip ${p.language !== ticket.language ? 'tone-info' : ''}`} style={{ padding: '0 6px', fontSize: 10 }}>{(p.language ?? '').toUpperCase()}</span>
                {p.cited && <span className="chip tone-ready" style={{ padding: '0 6px', fontSize: 10 }}>cited</span>}
              </span>
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 1 }}>
              <span className="mono" style={{ fontSize: 12 }}>{Number(p.similarity).toFixed(2)}</span>
              <ConfidenceBar value={p.similarity * 100} />
            </span>
            <span className="prec-snippet" style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text-2)' }}>{p.snippet}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
