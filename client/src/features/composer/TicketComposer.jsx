import { useState } from 'react';
import { SAMPLE_TICKETS } from './samples.js';
import { filterSuggestions } from '../../lib/autocomplete.js';
import { SuggestionList, useTypeahead } from '../../components/ui/Typeahead.jsx';

const DE_HINT = /[äöüß]|\b(der|die|das|und|nicht|seit|bitte|ist)\b/i;

/** One box: paste or type the problem. Demo messages are suggested only while a short query is typed. */
export function TicketComposer({ onSubmit, busy, error, autoFocus, compact }) {
  const [body, setBody] = useState('');
  const lang = body.trim() ? (DE_HINT.test(body) ? 'German detected · reply in German' : 'English detected · reply in English') : 'English or German, detected automatically';

  const matches = body.length <= 24 ? filterSuggestions(body, SAMPLE_TICKETS, ['label', 'body'], 4) : [];
  const ta = useTypeahead(matches, (s) => setBody(s.body));

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (body.trim()) onSubmit({ body }); }} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ position: 'relative' }}>
        <textarea className="field" aria-label="Problem description" placeholder="Paste or type the problem…" rows={compact ? 4 : 5}
          value={body} autoFocus={autoFocus} onChange={(e) => { setBody(e.target.value); ta.reset(); }} onKeyDown={ta.onKeyDown} onBlur={ta.close}
          role="combobox" aria-expanded={ta.open} aria-controls="sample-list" aria-autocomplete="list" style={{ resize: 'vertical', fontSize: 15, lineHeight: 1.5 }} />
        <SuggestionList id="sample-list" open={ta.open} items={matches} active={ta.active} onPick={(s) => { setBody(s.body); ta.close(); }} onHover={ta.setActive}
          render={(s) => (<span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}><strong style={{ fontSize: 13 }}>{s.label}</strong><span className="muted" style={{ fontSize: 12 }}>{s.body.slice(0, 80)}…</span></span>)} />
      </div>
      {error && <p className="error-box" style={{ margin: 0 }}>{error}</p>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="mono muted" style={{ fontSize: 12 }}>{lang} · personal details masked</span>
        <button className="btn btn-accent press" disabled={busy || !body.trim()} style={{ marginLeft: 'auto', padding: '11px 20px' }}>
          {busy ? <span className="shimmer" style={{ WebkitTextFillColor: 'transparent' }}>Triaging…</span> : 'Triage ↵'}
        </button>
      </div>
    </form>
  );
}
