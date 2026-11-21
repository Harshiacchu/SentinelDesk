import { useCallback, useState } from 'react';

const KEY = 'sentineldesk.agent';

/** Who is working the agent portal. A name, not an account: no login needed for the demo. */
export function useAgentName() {
  const [name, setName] = useState(() => {
    try { return localStorage.getItem(KEY) ?? ''; } catch { return ''; }
  });
  const save = useCallback((value) => {
    const v = value.trim().slice(0, 40);
    setName(v);
    try { localStorage.setItem(KEY, v); } catch { /* storage blocked: keep in memory */ }
  }, []);
  return [name, save];
}
