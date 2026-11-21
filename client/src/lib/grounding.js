/** Numbers, amounts, percentages and time promises in `text` that appear in none of the `sources`. */
const NUMBERISH = /(\d+(?:[.,]\d+)?\s?(?:%|eur|euro|usd|\$|€|minutes?|minuten|hours?|stunden|days?|tage?n?|h)\b|[$€£]\s?\d+(?:[.,]\d+)?|\b\d{2,}\b)/gi;

export function unsupportedNumbers(text, sources) {
  const haystack = sources.join(' ').toLowerCase();
  const found = [...new Set((text.match(NUMBERISH) ?? []).map((m) => m.trim()))];
  return found.filter((n) => !haystack.includes(n.toLowerCase()) && !haystack.includes(n.replace(/\D/g, '')));
}
