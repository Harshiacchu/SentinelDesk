import { useState } from 'react';
import { api } from '../../api/sentinelApi.js';

const NAMES = { en: 'English', de: 'German' };
const OFF_HINT = 'Translation needs a Gemini key (GEMINI_API_KEY) or a Google Cloud Translation key';

/** "Show in English" under a piece of text. Fetches on demand; never shows made-up text. */
export function TranslateInline({ text, target = 'en', source, enabled }) {
  const [state, setState] = useState({ open: false, loading: false, text: null, error: null });

  const toggle = async () => {
    if (state.open) { setState((s) => ({ ...s, open: false })); return; }
    if (state.text) { setState((s) => ({ ...s, open: true })); return; }
    setState({ open: true, loading: true, text: null, error: null });
    try {
      const res = await api.translate(text, target, source);
      setState({ open: true, loading: false, text: res.text, error: null });
    } catch (err) {
      setState({ open: true, loading: false, text: null, error: err.message });
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <button type="button" className="btn-link" onClick={toggle} disabled={!enabled} title={enabled ? '' : OFF_HINT}
        style={{ alignSelf: 'flex-start', fontSize: 12, opacity: enabled ? 1 : 0.5, cursor: enabled ? 'pointer' : 'not-allowed' }}>
        {state.open ? 'Hide translation' : `Show in ${NAMES[target]}`}
      </button>
      {state.open && (
        <div className="fade" style={{ padding: '8px 12px', borderRadius: 10, background: 'var(--glass-soft)', border: '1px solid var(--border)' }}>
          {state.loading && <span className="shimmer" style={{ fontSize: 13 }}>Translating…</span>}
          {state.error && <span style={{ fontSize: 13, color: 'var(--red-text)' }}>{state.error}</span>}
          {state.text && (
            <>
              <span className="faint" style={{ display: 'block', fontSize: 11, marginBottom: 4 }}>{NAMES[target]} · machine translation</span>
              <span lang={target} style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-line' }}>{state.text}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export const translationOffHint = OFF_HINT;
