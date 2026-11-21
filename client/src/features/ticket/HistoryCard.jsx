import { useState } from 'react';
import { clock } from '../../lib/format.js';

/**
 * The ticket's text over time: the original message plus every follow-up.
 * Adding a follow-up re-runs triage on the whole history.
 */
export function HistoryCard({ ticket, busy, onFollowUp }) {
  const [text, setText] = useState('');
  const [error, setError] = useState(null);
  const entries = [{ who: 'Original message', text: ticket.body, at: ticket.receivedAt }, ...(ticket.followups ?? []).map((f) => ({ who: 'Follow-up', text: f.text, at: f.at }))];

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    try { await onFollowUp(text.trim()); setText(''); } catch (err) { setError(err.message); }
  };

  return (
    <section aria-label="Ticket history" className="glass card rise" style={{ animationDelay: '.18s' }}>
      <h2 className="card-title">History</h2>
      <ol className="list" style={{ display: 'flex', flexDirection: 'column', gap: 12, borderLeft: '2px solid var(--border)', paddingLeft: 14 }}>
        {entries.map((e, i) => (
          <li key={i} className="fade" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span className="faint" style={{ fontSize: 11 }}>{e.who} · {clock(e.at)}</span>
            <span style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-line' }}>{e.text}</span>
          </li>
        ))}
      </ol>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
        <label htmlFor="followup" className="muted" style={{ fontSize: 12 }}>New information about this problem</label>
        <textarea id="followup" className="field" rows={3} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="e.g. It's now affecting the whole floor, and email is down too" style={{ resize: 'vertical' }} />
        {error && <p className="error-box" style={{ margin: 0 }}>{error}</p>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="faint" style={{ fontSize: 12 }}>Triage runs again on the whole history.</span>
          <button className="btn btn-accent press" style={{ marginLeft: 'auto' }} disabled={busy || !text.trim()}>{busy ? 'Re-triaging…' : 'Add & re-triage'}</button>
        </div>
      </form>
    </section>
  );
}
