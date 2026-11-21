import { useState } from 'react';
import { Icon } from '../../components/ui/Icon.jsx';
import { Dot } from '../../components/ui/Tone.jsx';
import { unsupportedNumbers } from '../../lib/grounding.js';
import { api } from '../../api/sentinelApi.js';
import { TranslateInline, translationOffHint } from '../translation/TranslateInline.jsx';

/** Checks that run on a written draft (CONTRACT.md section 6, post stage). */
const POST_CHECKS = new Set(['NOT_FOUND', 'BAD_CITATION', 'UNSUPPORTED_NUMBER', 'LANG_MISMATCH', 'REFUSAL']);

/**
 * The draft with the Evidence Lens: every sentence shows where it came from,
 * unsupported promises are struck out, and clicking a sentence highlights its source.
 */
export function ReplyPanel({ ticket, busy, onEditDraft, translation, picked, onPick }) {
  const [lens, setLens] = useState(false);
  const [editing, setEditing] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [text, setText] = useState('');
  const [tr, setTr] = useState({ loading: false, back: null, error: null });
  const { draft, precedents } = ticket;
  if (!draft) {
    return (
      <section aria-label="Reply" className="glass card rise" style={{ animationDelay: '.14s' }}>
        <h2 className="card-title">No customer draft</h2>
        <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
          {ticket.reasons.includes('LLM_ERROR')
            ? 'The drafting model was unavailable, so this goes to an engineer. The past tickets are under Evidence.'
            : ticket.reasons.some((r) => POST_CHECKS.has(r))
              ? 'A draft was written but failed the safety checks, so it is not shown. An engineer takes over; see Why for what failed.'
              : 'The safety gate stopped this before drafting, so no reply was written. An engineer takes over, with the past tickets under Evidence.'}
        </p>
      </section>
    );
  }

  const totalDraftMs = ticket.latency.find((s) => /draft/i.test(s.stage) && !/check/i.test(s.stage))?.ms;
  const used = precedents.filter((p) => p.cited).length;
  const LANG = { en: 'English', de: 'German' };
  const foreign = [...new Set(precedents.filter((p) => p.cited && p.language && p.language !== draft.language).map((p) => p.language))];
  const crossLingual = foreign.length > 0;
  const hasUnsupported = draft.lines.some((l) => l.unsupported);
  const title = `Reply in ${draft.language === 'de' ? 'German' : 'English'}`;
  const aiText = draft.lines.filter((l) => !l.unsupported).map((l) => l.text).join('').trim();
  const edited = ticket.editedDraft;
  const sources = precedents.map((p) => p.snippet);
  const warn = unsupportedNumbers(editing ? text : edited?.text ?? '', sources);
  const startEdit = () => { setText(edited?.text ?? aiText); setEditing(true); };
  const save = async () => { await onEditDraft(text.trim()); setEditing(false); setShowOriginal(false); setTr({ loading: false, back: null, error: null }); };
  /** Engineer writes in English -> German for the customer, plus a back-translation to check the meaning. */
  const toGerman = async () => {
    setTr({ loading: true, back: null, error: null });
    try {
      const de = await api.translate(text, 'de', 'en');
      const back = await api.translate(de.text, 'en', 'de');
      setText(de.text);
      setTr({ loading: false, back: back.text, error: null });
    } catch (err) { setTr({ loading: false, back: null, error: err.message }); }
  };

  return (
    <section aria-label="Reply" className="glass card rise" style={{ animationDelay: '.14s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h2 className="card-title">{title}</h2>
          <span className="shimmer" style={{ fontSize: 12, fontWeight: 500 }}>
            Drafted from {used} past ticket{used === 1 ? '' : 's'}{totalDraftMs ? ` in ${(totalDraftMs / 1000).toFixed(1)} s` : ''}
          </span>
          {crossLingual && (
            <span className="chip tone-info" style={{ alignSelf: 'flex-start', marginTop: 4, fontSize: 11 }}>
              Cross-lingual · {LANG[draft.language]} reply from {foreign.map((l) => LANG[l] ?? l).join(' + ')} past ticket{used > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {!editing && <button className="pill-toggle press" onClick={startEdit}>Edit</button>}
          {!editing && (!edited || showOriginal) && (
            <button className="pill-toggle press" aria-pressed={lens} onClick={() => setLens((v) => !v)}>
              <Icon name="search" size={13} /> Show sources
            </button>
          )}
        </span>
      </div>

      {editing && (
        <div className="fade" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <textarea className="field" rows={6} value={text} onChange={(e) => setText(e.target.value)} lang={draft.language} aria-label="Edit reply" style={{ resize: 'vertical', fontSize: 15, lineHeight: 1.6 }} />
          {warn.length > 0 && <Warning items={warn} />}
          {draft.language === 'de' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <button type="button" className="btn press" onClick={toGerman} disabled={!translation || tr.loading || !text.trim()} title={translation ? '' : translationOffHint} style={{ alignSelf: 'flex-start' }}>
                {tr.loading ? 'Translating…' : 'Translate my text to German'}
              </button>
              {tr.back && <span className="fade" style={{ fontSize: 13, color: 'var(--text-2)' }}><span className="muted">Back to English, to check the meaning:</span> {tr.back}</span>}
              {tr.error && <span style={{ fontSize: 13, color: 'var(--red-text)' }}>{tr.error}</span>}
              {!translation && <span className="faint" style={{ fontSize: 12 }}>{translationOffHint}</span>}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn press" onClick={() => setEditing(false)}>Cancel</button>
            <button className="btn btn-accent press" disabled={busy || !text.trim()} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>
          </div>
        </div>
      )}

      {!editing && edited && (
        <div className="fade" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span className="chip tone-review" style={{ fontSize: 11 }}>Edited by engineer</span>
            <button className="btn-link" style={{ fontSize: 12 }} onClick={() => setShowOriginal((v) => !v)}>{showOriginal ? 'Hide AI original' : 'Show AI original'}</button>
          </span>
          <p style={{ margin: 0, fontSize: 17, lineHeight: 1.85, whiteSpace: 'pre-line' }} lang={draft.language}>{edited.text}</p>
          {warn.length > 0 && <Warning items={warn} />}
          {draft.language === 'de' && <TranslateInline key={edited.text} text={edited.text} target="en" source="de" enabled={translation} />}
        </div>
      )}

      {!editing && (!edited || showOriginal) && (<>
      {edited && <span className="eyebrow" style={{ marginTop: 6 }}>AI original</span>}
      <p style={{ margin: 0, fontSize: 17, lineHeight: 1.85 }} lang={draft.language}>
        {draft.lines.map((line, i) => (
          <Sentence key={i} line={line} lens={lens} picked={picked === line.source && line.source !== null}
            onPick={() => { if (line.source !== null) { onPick(line.source); setLens(true); } }} />
        ))}
      </p>

      {hasUnsupported && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--red-text)' }}>
          <Dot tone="critical" pulse size={7} /> The struck-out promise has no source. It won’t be sent.
        </span>
      )}

      {draft.language === 'de' && !edited && <TranslateInline text={aiText} target="en" source="de" enabled={translation} />}
      </>)}
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

function Warning({ items }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--amber-text)' }}>
      <Dot tone="review" size={7} /> Not in any past ticket: {items.join(', ')}. Double-check before sending.
    </span>
  );
}
