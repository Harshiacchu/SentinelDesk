export function timeAgo(date, now = Date.now()) {
  const s = Math.max(0, Math.round((now - new Date(date).getTime()) / 1000));
  if (s < 45) return 'now';
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

export const clock = (date) => new Date(date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export const duration = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`);

export const percent = (x) => `${Math.round(x * 100)}%`;

export const LANGUAGE_NAMES = { en: 'English', de: 'German' };
