/**
 * PII guardrail: masks personal data BEFORE the text leaves the server for any AI/LLM call.
 * Placeholders match CONTRACT.md section 5: [EMAIL] [PHONE] [IP] [IBAN] [CARD] [ACCOUNT].
 * Order matters: specific patterns (IBAN, card, IP) run before the broad phone pattern.
 */
const RULES = [
  ['EMAIL', /[\w.+-]+@[\w-]+\.[\w.-]+/g],
  ['IBAN', /\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b/g],
  ['IP', /\b(?:\d{1,3}\.){3}\d{1,3}\b|\b(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}\b/gi],
  ['CARD', /\b\d{4}([ -]?)\d{4}\1\d{4}\1\d{1,4}\b/g], // 4-4-4-4 layout, so phone numbers don't match
  ['ACCOUNT', /\b(?:account|acct|konto|kundennummer|customer (?:no|number|id))[\s#:.-]*\d{4,}\b/gi],
  ['PHONE', /(?<![\w[])(?!\d{4}-\d{2}-\d{2}\b|\d{1,2}[./]\d{1,2}[./]\d{2,4}\b)(?:\(\d{2,4}\)\s?|\+)?\d[\d\s().-]{6,}\d\b/g], // dates are not phones
];

const LABELS = { EMAIL: 'email', PHONE: 'phone number', IP: 'IP address', IBAN: 'IBAN', CARD: 'card number', ACCOUNT: 'account number' };

export class PiiMasker {
  /** @returns {{ text: string, entities: { type: string, count: number }[] }} */
  mask(text) {
    if (!text) return { text: text ?? '', entities: [] };
    const counts = {};
    let out = text;
    for (const [type, re] of RULES) {
      out = out.replace(re, () => {
        counts[type] = (counts[type] ?? 0) + 1;
        return `[${type}]`;
      });
    }
    return { text: out, entities: Object.entries(counts).map(([type, count]) => ({ type, count })) };
  }

  static describe(entities) {
    return entities.map(({ type, count }) => `${count} ${LABELS[type] ?? type.toLowerCase()}${count > 1 ? 's' : ''}`).join(', ');
  }
}
