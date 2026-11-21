import { useState } from 'react';
import { SAMPLE_TICKETS } from './samples.js';
import { filterSuggestions } from '../../lib/autocomplete.js';
import { SuggestionList, useTypeahead } from '../../components/ui/Typeahead.jsx';

const DE_HINT = /[äöüß]|\b(der|die|das|und|nicht|seit|bitte|ist)\b/i;

/** Reusable ticket form (⌘K palette + front page). Example tickets appear only as you type. */
export function TicketComposer({ branches = [], onSubmit, busy, error, autoFocus, compact }) {
  const [form, setForm] = useState({ subject: '', body: '', branch: branches[0] ?? 'Boston' });
  const set = (k) => (e) => { setForm((f) => ({ ...f, [k]: e.target.value })); ta.reset(); };
  const lang = form.body.trim() ? (DE_HINT.test(form.body) ? 'Deutsch erkannt · reply in German' : 'English detected · reply in English') : 'Language is detected automatically';

  // Suggest demo tickets that match what's typed in the subject (never shown up front).
  const matches = form.body ? [] : filterSuggestions(form.subject, SAMPLE_TICKETS, ['label', 'subject', 'body'], 4);
  const pick = (s) => setForm({ subject: s.subject, body: s.body, branch: branches.includes(s.branch) ? s.branch : form.branch });
  const ta = useTypeahead(matches, pick);

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (form.body.trim()) onSubmit(form); }} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '3 1 240px' }}>
          <input className="field" aria-label="Subject (optional)" placeholder="Subject (optional)" value={form.subject}
            onChange={set('subject')} onKeyDown={ta.onKeyDown} onBlur={ta.close} autoFocus={autoFocus}
            role="combobox" aria-expanded={ta.open} aria-controls="sample-list" aria-autocomplete="list" />
          <SuggestionList id="sample-list" open={ta.open} items={matches} active={ta.active} onPick={(s) => { pick(s); ta.close(); }} onHover={ta.setActive}
            render={(s) => (<span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}><strong style={{ fontSize: 13 }}>{s.subject || '(no subject)'}</strong><span className="muted" style={{ fontSize: 12 }}>{s.body.slice(0, 70)}…</span></span>)} />
        </div>
        <select className="field" aria-label="Branch" value={form.branch} onChange={set('branch')} style={{ flex: '1 1 140px' }}>
          {branches.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
      </div>
      <textarea className="field" aria-label="Customer message" placeholder="Paste the customer message (English or German)…" rows={compact ? 4 : 5} value={form.body} onChange={set('body')} style={{ resize: 'vertical', fontSize: 15, lineHeight: 1.5 }} />
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
