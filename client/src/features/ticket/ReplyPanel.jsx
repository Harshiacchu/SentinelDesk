import { useState } from 'react';
import { Icon } from '../../components/ui/Icon.jsx';
import { Dot } from '../../components/ui/Tone.jsx';

/**
 * The draft with the Evidence Lens: every sentence shows where it came from,
 * unsupported promises are struck out, and clicking a sentence highlights its source.
 */
export function ReplyPanel({ ticket }) {
  const [lens, setLens] = useState(false);
  const [picked, setPicked] = useState(null);
  const { draft, precedents } = ticket;
  if (!draft) return null;

  const totalDraftMs = ticket.latency.find((s) => /draft/i.test(s.stage) && !/check/i.test(s.stage))?.ms;
  const used = precedents.filter((p) => p.cited).length;
  const hasUnsupported = draft.lines.some((l) => l.unsupported);
  const title = ticket.severity === 'critical' ? 'Holding update' : ticket.severity === 'review' ? 'Safe acknowledgement' : `Reply in ${draft.language === 'de' ? 'German' : 'English'}`;

  return (
    <section aria-label="Reply" className="glass card rise" style={{ animationDelay: '.14s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h2 className="card-title">{title}</h2>
          <span className="shimmer" style={{ fontSize: 12, fontWeight: 500 }}>
            Drafted from {used} past ticket{used === 1 ? '' : 's'}{totalDraftMs ? ` in ${(totalDraftMs / 1000).toFixed(1)} s` : ''}
          </span>
        </div>
        <button className="pill-toggle press" aria-pressed={lens} onClick={() => setLens((v) => !v)} style={{ marginLeft: 'auto' }}>
          <Icon name="search" size={13} /> Show sources
        </button>
      </div>

      <p style={{ margin: 0, fontSize: 17, lineHeight: 1.85 }} lang={draft.language}>
        {draft.lines.map((line, i) => (
          <Sentence key={i} line={line} lens={lens} picked={picked === line.source && line.source !== null}
            onPick={() => { if (line.source !== null) { setPicked(line.source); setLens(true); } }} />
        ))}
      </p>

      {hasUnsupported && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--red-text)' }}>
          <Dot tone="critical" pulse size={7} /> The struck-out promise has no source. It won’t be sent.
        </span>
      )}

      {lens && (
        <ul className="list fade" style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
          {precedents.map((p, i) => (
            <li key={p.ticketId} style={{ display: 'flex', alignItems: 'baseline', gap: 12, padding: '9px 10px', borderRadius: 10, transition: 'background .2s', background: picked === i ? 'var(--accent-soft)' : 'transparent', opacity: p.cited ? 1 : 0.6 }}>
              <span className="mono" style={{ fontSize: 12, color: 'var(--accent-text)', flex: 'none' }}>[{i + 1}] {p.ticketId}</span>
              <span style={{ fontSize: 13, color: 'var(--text-2)', flex: 1, minWidth: 0 }}>{p.snippet}</span>
              <span className="mono faint" style={{ fontSize: 12, flex: 'none' }}>{p.similarity}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Sentence({ line, lens, picked, onPick }) {
  const style = {
    display: 'inline', border: 0, padding: '2px 1px', margin: 0, font: 'inherit', lineHeight: 'inherit', textAlign: 'left',
    color: line.unsupported ? 'var(--red-text)' : 'var(--text)', background: picked ? 'var(--accent-soft)' : 'transparent', borderRadius: 4,
    textDecoration: line.unsupported ? 'line-through' : 'none', textDecorationColor: 'var(--red)',
    boxShadow: lens && line.source !== null ? 'inset 0 -2px 0 color-mix(in srgb, var(--accent) 60%, transparent)' : 'none',
    cursor: line.source !== null ? 'pointer' : 'default', transition: 'background .2s',
  };
  const tag = line.unsupported ? 'no source' : line.source !== null ? `[${line.source + 1}]` : null;
  return (
    <button type="button" style={style} onClick={onPick} tabIndex={line.source !== null ? 0 : -1}>
      {line.text}
      {lens && tag && <sup className="mono" style={{ fontSize: 10, margin: '0 4px 0 1px', color: line.unsupported ? 'var(--red)' : 'var(--accent-text)' }}>{tag}</sup>}
    </button>
  );
}
