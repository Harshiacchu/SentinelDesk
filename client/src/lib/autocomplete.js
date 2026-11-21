/** Pure helpers for "suggest as you type" behaviour. Nothing is shown until the user types. */

const norm = (s) => s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');

/** Items whose fields contain every typed word. Empty or 1-char queries return nothing. */
export function filterSuggestions(query, items, fields, max = 5) {
  const q = norm(query.trim());
  if (q.length < 2) return [];
  const words = q.split(/\s+/);
  return items.filter((it) => {
    const hay = norm(fields.map((f) => it[f] ?? '').join(' '));
    return words.every((w) => hay.includes(w));
  }).slice(0, max);
}

/** The unfinished sentence at the end of `text` (after the last . ! ? or line break). */
export function currentFragment(text) {
  const parts = text.split(/(?<=[.!?\n])/);
  return parts[parts.length - 1].replace(/^\s+/, '');
}

/** Inline completion: the rest of the first phrase that starts with the current fragment. */
export function completionFor(text, phrases) {
  const frag = currentFragment(text);
  if (frag.trim().length < 2) return '';
  const f = norm(frag);
  const hit = phrases.find((p) => norm(p).startsWith(f) && p.length > frag.length);
  return hit ? hit.slice(frag.length) : '';
}
