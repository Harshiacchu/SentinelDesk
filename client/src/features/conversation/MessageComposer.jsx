import { useMemo, useState } from 'react';
import { completionFor, currentFragment } from '../../lib/autocomplete.js';

/**
 * Chat input. Enter sends, Shift+Enter adds a line.
 * With `phrases`, the rest of a matching phrase appears as you type and Tab accepts it.
 * With `starter`, Tab in an empty box inserts the suggested reply.
 */
export function MessageComposer({ onSend, disabled, busy, placeholder, phrases = [], starter = '', lang }) {
  const [text, setText] = useState('');
  const completion = useMemo(() => (text && phrases.length ? completionFor(text, phrases) : ''), [text, phrases]);

  const send = async () => {
    const t = text.trim();
    if (!t || busy || disabled) return;
    await onSend(t);
    setText('');
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); return; }
    if (e.key !== 'Tab' || e.shiftKey) return;
    if (!text && starter) { e.preventDefault(); setText(starter); }
    else if (completion) { e.preventDefault(); setText((v) => `${v}${completion} `); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <textarea className="field" rows={text.split('\n').length > 2 ? 5 : 2} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKeyDown}
          disabled={disabled} lang={lang} aria-label="Message" placeholder={placeholder} style={{ resize: 'none', fontSize: 14, lineHeight: 1.5 }} />
        <button className="btn btn-accent press" disabled={disabled || busy || !text.trim()} onClick={send} style={{ padding: '11px 18px' }}>
          {busy ? '…' : 'Send'}
        </button>
      </div>
      <div aria-live="polite" style={{ minHeight: 18, fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        {completion ? (
          <span className="fade" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            <span className="kbd">Tab</span>
            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <span className="muted">{currentFragment(text).trim().slice(-24)}</span><span style={{ color: 'var(--accent-text)' }}>{completion}</span>
            </span>
          </span>
        ) : !text && starter && !disabled ? <span className="faint">Tab inserts a suggested reply built from past resolutions</span> : null}
      </div>
    </div>
  );
}
