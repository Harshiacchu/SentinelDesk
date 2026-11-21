import { useEffect } from 'react';

/** ⌘K / Ctrl+K style shortcut. */
export function useHotkey(key, callback, { meta = true } = {}) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key.toLowerCase() === key && (!meta || e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        callback();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [key, callback, meta]);
}
