import { useState } from 'react';
import { SAMPLE_TICKETS } from './samples.js';

const DE_HINT = /[äöüß]|\b(der|die|das|und|nicht|seit|bitte|ist)\b/i;

/** Reusable ticket form (used by the ⌘K palette and the front page). */
export function TicketComposer({ branches = [], onSubmit, busy, error, autoFocus, compact }) {
  const [form, setForm] = useState({ subject: '', body: '', branch: branches[0] ?? 'Boston' });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const lang = form.body.trim() ? (DE_HINT.test(form.body) ? 'Deutsch erkannt · reply in German' : 'English detected · reply in English') : 'Language is detected automatically';

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (form.body.trim()) onSubmit(form); }} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input className="field" aria-label="Subject (optional)" placeholder="Subject (optional)" value={form.subject} onChange={set('subject')} style={{ flex: '3 1 240px' }} autoFocus={autoFocus} />
        <select className="field" aria-label="Branch" value={form.branch} onChange={set('branch')} style={{ flex: '1 1 140px' }}>
          {branches.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
      </div>
      <textarea className="field" aria-label="Customer message" placeholder="Paste the customer message (English or German)…" rows={compact ? 4 : 5} value={form.body} onChange={set('body')} style={{ resize: 'vertical', fontSize: 15, lineHeight: 1.5 }} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {SAMPLE_TICKETS.map((s) => (
          <button type="button" key={s.label} className="btn press" style={{ padding: '6px 11px', borderRadius: 999, fontSize: 12, fontWeight: 500 }}
            onClick={() => setForm({ subject: s.subject, body: s.body, branch: branches.includes(s.branch) ? s.branch : form.branch })}>{s.label}</button>
        ))}
      </div>
      {error && <p className="error-box" style={{ margin: 0 }}>{error}</p>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="mono muted" style={{ fontSize: 12 }}>{lang} · personal details masked</span>
        <button className="btn btn-accent press" disabled={busy || !form.body.trim()} style={{ marginLeft: 'auto', padding: '11px 20px' }}>
          {busy ? <span className="shimmer" style={{ WebkitTextFillColor: 'transparent' }}>Triaging…</span> : 'Triage ↵'}
        </button>
      </div>
    </form>
  );
}
