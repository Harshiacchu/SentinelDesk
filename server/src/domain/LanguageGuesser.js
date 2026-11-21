/** Tiny en/de guess used only by the mock provider. The real pipeline uses lingua. */
const DE = new Set(['der', 'die', 'das', 'und', 'ist', 'nicht', 'seit', 'ich', 'wir', 'bitte', 'kann', 'mein', 'unser', 'ein', 'eine', 'mit', 'aus', 'im']);
const EN = new Set(['the', 'and', 'is', 'not', 'since', 'i', 'we', 'please', 'can', 'my', 'our', 'a', 'an', 'with', 'to', 'cannot']);

export function guessLanguage(text) {
  const words = text.toLowerCase().match(/[a-zäöüß]+/g) ?? [];
  const de = words.filter((w) => DE.has(w)).length + (/[äöüß]/i.test(text) ? 2 : 0);
  const en = words.filter((w) => EN.has(w)).length;
  return de > en ? 'de' : 'en';
}
