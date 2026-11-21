import { useState } from 'react';

/**
 * Dropdown that appears under an input only while the user types and something matches.
 * Keyboard: ↑ ↓ to move, Enter to pick, Esc to close.
 */
export function useTypeahead(suggestions, onPick) {
  const [active, setActive] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const open = suggestions.length > 0 && !dismissed;

  const onKeyDown = (e) => {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % suggestions.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i - 1 + suggestions.length) % suggestions.length); }
    else if (e.key === 'Enter') { e.preventDefault(); onPick(suggestions[active]); setDismissed(true); }
    else if (e.key === 'Escape') setDismissed(true);
  };
  const reset = () => { setActive(0); setDismissed(false); };
  return { open, active, setActive, onKeyDown, reset, close: () => setDismissed(true) };
}

export function SuggestionList({ id, open, items, active, onPick, onHover, render, placement = 'bottom' }) {
  if (!open) return null;
  return (
    <ul id={id} role="listbox" className="glass-strong fade" style={{ position: 'absolute', left: 0, right: 0, ...(placement === 'top' ? { bottom: 'calc(100% + 6px)' } : { top: 'calc(100% + 6px)' }), zIndex: 20, listStyle: 'none', margin: 0, padding: 6, borderRadius: 12, boxShadow: 'var(--shadow)' }}>
      {items.map((it, i) => (
        <li key={i} role="option" aria-selected={i === active}>
          <button type="button" onMouseDown={(e) => { e.preventDefault(); onPick(it); }} onMouseEnter={() => onHover(i)}
            style={{ width: '100%', textAlign: 'left', padding: '9px 10px', border: 0, borderRadius: 8, background: i === active ? 'var(--accent-soft)' : 'transparent', color: 'var(--text)' }}>
            {render(it)}
          </button>
        </li>
      ))}
    </ul>
  );
}
