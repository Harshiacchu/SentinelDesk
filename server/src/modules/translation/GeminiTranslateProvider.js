import { TranslationProvider } from './TranslationProvider.js';
import { UpstreamError } from '../../core/errors.js';

const NAMES = { en: 'English', de: 'German' };

/**
 * Translation with Gemini (same key as the reply drafting).
 * Vertex keys use aiplatform.googleapis.com; AI Studio keys use generativelanguage.googleapis.com.
 */
export class GeminiTranslateProvider extends TranslationProvider {
  constructor({ apiKey, model, vertex, fallbackModel = 'gemini-flash-lite-latest', timeoutMs = 12_000 }) {
    super();
    Object.assign(this, { apiKey, model, vertex, fallbackModel, timeoutMs });
  }

  get enabled() { return true; }

  #url(model) {
    const base = this.vertex
      ? `https://aiplatform.googleapis.com/v1/publishers/google/models/${model}:generateContent`
      : `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
    return `${base}?key=${encodeURIComponent(this.apiKey)}`;
  }

  /** Gemini is sometimes overloaded (503) or slow: retry once on a second model before giving up. */
  async translate(text, opts) {
    try {
      return await this.#call(this.model, text, opts);
    } catch (err) {
      if (!err.retryable || !this.fallbackModel || this.fallbackModel === this.model) throw err;
      return this.#call(this.fallbackModel, text, opts);
    }
  }

  async #call(model, text, { target, source }) {
    const instruction = [
      `You are a professional translator for an IT helpdesk. Translate the user's text ${source ? `from ${NAMES[source]} ` : ''}into ${NAMES[target]}.`,
      'Keep the meaning, tone and formatting (line breaks, numbered lists).',
      'Keep placeholders such as [EMAIL], [PHONE], [IP] and ticket IDs such as [TKT-01234] exactly as they are.',
      'Do not add, remove or explain anything. Output only the translation.',
    ].join(' ');
    let res;
    try {
      res = await fetch(this.#url(model), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: instruction }] },
          contents: [{ role: 'user', parts: [{ text }] }],
          generationConfig: { maxOutputTokens: 2048 },
        }),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (err) {
      throw Object.assign(new UpstreamError('translation (Gemini)', err), { retryable: true });
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const e = new UpstreamError('translation (Gemini)', data?.error?.message ?? `HTTP ${res.status}`);
      throw Object.assign(e, { retryable: res.status === 429 || res.status >= 500 });
    }
    const out = (data?.candidates?.[0]?.content?.parts ?? []).map((p) => p.text ?? '').join('').trim();
    if (!out) throw new UpstreamError('translation (Gemini)', `empty response (${data?.candidates?.[0]?.finishReason ?? 'unknown'})`);
    return { text: out, detectedSource: source ?? null };
  }
}
