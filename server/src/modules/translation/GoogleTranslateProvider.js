import { TranslationProvider } from './TranslationProvider.js';
import { UpstreamError } from '../../core/errors.js';

/** Google Cloud Translation API (v2, API key). https://cloud.google.com/translate/docs/reference/rest/v2/translate */
export class GoogleTranslateProvider extends TranslationProvider {
  constructor({ apiKey, timeoutMs = 10_000 }) {
    super();
    this.apiKey = apiKey;
    this.timeoutMs = timeoutMs;
  }

  get enabled() { return true; }

  async translate(text, { target, source }) {
    let res;
    try {
      res = await fetch(`https://translation.googleapis.com/language/translate/v2?key=${encodeURIComponent(this.apiKey)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: text, target, ...(source ? { source } : {}), format: 'text' }),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (err) {
      throw new UpstreamError('translation', err);
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new UpstreamError('translation', data?.error?.message ?? `HTTP ${res.status}`);
    const t = data?.data?.translations?.[0];
    return { text: t?.translatedText ?? '', detectedSource: t?.detectedSourceLanguage ?? source ?? null };
  }
}
