import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

/** JS-side colours for SVG/canvas (charts, rings) that can't read CSS variables. */
const PALETTES = {
  dark: { text: '#E5E9F2', muted: '#94A3B8', grid: 'rgba(148,163,184,0.12)', red: '#EF4444', amber: '#F59E0B', green: '#22C55E', blue: '#3B82F6', violet: '#8B5CF6', track: 0.16 },
  light: { text: '#0F172A', muted: '#475569', grid: 'rgba(15,23,42,0.08)', red: '#DC2626', amber: '#D97706', green: '#16A34A', blue: '#2563EB', violet: '#7C3AED', track: 0.14 },
};

const KEY = 'sentineldesk.theme';
const ThemeContext = createContext(null);

function initialTheme() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'light' || saved === 'dark') return saved;
  } catch { /* storage blocked: fall through */ }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(KEY, theme); } catch { /* ignore */ }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);
  const value = useMemo(() => ({ theme, toggle, colors: PALETTES[theme] }), [theme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider');
  return ctx;
}
