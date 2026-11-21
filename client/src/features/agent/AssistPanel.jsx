import { useState } from 'react';
import { Dot } from '../../components/ui/Tone.jsx';
import { reasonInfo } from '../../lib/severity.js';
import { timeAgo } from '../../lib/format.js';

/**
 * The live agent's co-pilot: why the ticket came to them, the facts that matter,
 * what to do, and what solved it before. Longer lists open only on request.
 */
export function AssistPanel({ assist, onOpenRelated }) {
  const [done, setDone] = useState({});
  const [morePast, setMorePast] = useState(false);
  const [showRelated, setShowRelated] = useState(false);
  const past = morePast ? assist.precedents : assist.precedents.slice(0, 1);

  return (
    <section aria-label="Triage assist" className="glass card rise" style={{ gap: 18, animationDelay: '.12s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ width: 28, height: 28, borderRadius: 9, background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 14 }} aria-hidden="true">✦</span>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 className="card-title">Triage assist</h2>
          <span className="muted" style={{ fontSize: 12 }}>{assist.summary}</span>
        </div>
      </div>

      <Block title="Why it came to you">
        {assist.whyHere.length === 0 && <span className="muted" style={{ fontSize: 13 }}>Sent to a person by an operator.</span>}
        {assist.whyHere.map((w) => {
          const info = reasonInfo(w.code);
          return (
            <div key={w.code} style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
              <Dot tone={info.tone.replace('tone-', '')} glow />
              <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <strong style={{ fontSize: 13 }}>{info.title}</strong>
                <span className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>{w.detail ?? info.text}</span>
              </span>
            </div>
          );
        })}
      </Block>

      <Block title="Key facts">
        <ul className="list" style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
          {assist.facts.map((f) => <li key={f} style={{ display: 'flex', gap: 8 }}><span className="faint">•</span>{f}</li>)}
        </ul>
      </Block>

      <Block title="Suggested steps">
        {assist.steps.map((s, i) => (
          <label key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13, lineHeight: 1.5, cursor: 'pointer', opacity: done[i] ? 0.55 : 1 }}>
            <input type="checkbox" checked={Boolean(done[i])} onChange={() => setDone((d) => ({ ...d, [i]: !d[i] }))} style={{ marginTop: 3, accentColor: 'var(--accent)' }} />
            <span style={{ textDecoration: done[i] ? 'line-through' : 'none' }}>{s}</span>
          </label>
        ))}
      </Block>

      <Block title="What solved it before">
        {past.map((p) => (
          <div key={p.ticketId} style={{ display: 'flex', flexDirection: 'column', gap: 3, padding: '8px 10px', borderRadius: 10, background: 'var(--glass-soft)', border: '1px solid var(--border)' }}>
            <span className="mono" style={{ fontSize: 11, color: 'var(--accent-text)' }}>{p.ticketId} · match {p.similarity} · {p.language?.toUpperCase()}</span>
            <span style={{ fontSize: 13, lineHeight: 1.5 }}>{p.snippet}</span>
          </div>
        ))}
        {assist.precedents.length > 1 && (
          <button className="btn-link" style={{ alignSelf: 'flex-start', fontSize: 12 }} onClick={() => setMorePast((v) => !v)}>
            {morePast ? 'Show less' : `Show ${assist.precedents.length - 1} more`}
          </button>
        )}
      </Block>

      {assist.related.length > 0 && (
        <Block title="Related live tickets">
          <button className="btn-link" style={{ alignSelf: 'flex-start', fontSize: 13 }} onClick={() => setShowRelated((v) => !v)}>
            {showRelated ? 'Hide' : `${assist.related.length} similar ticket${assist.related.length > 1 ? 's' : ''} in the last hour`}
          </button>
          {showRelated && assist.related.map((r) => (
            <button key={r.ticketId} className="row-hover fade" onClick={() => onOpenRelated(r.ticketId)}
              style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '8px 6px', border: 0, borderRadius: 8, background: 'transparent', textAlign: 'left', color: 'var(--text)', fontSize: 13 }}>
              <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.subject}</span>
              <span className="muted" style={{ fontSize: 11 }}>{r.branch} · {timeAgo(r.receivedAt)}</span>
            </button>
          ))}
        </Block>
      )}
    </section>
  );
}

function Block({ title, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span className="eyebrow">{title}</span>
      {children}
    </div>
  );
}
