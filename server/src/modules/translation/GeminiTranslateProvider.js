import { TranslationProvider } from './TranslationProvider.js';
import { UpstreamError } from '../../core/errors.js';

const NAMES = { en: 'English', de: 'German' };

/**
 * Translation with Gemini (same key as the reply drafting).
 * Vertex keys use aiplatform.googleapis.com; AI Studio keys use generativelanguage.googleapis.com.
 */
export class GeminiTranslateProvider extends TranslationProvider {
  constructor({ apiKey, model, vertex, timeoutMs = 15_000 }) {
    super();
    Object.assign(this, { apiKey, model, vertex, timeoutMs });
  }

  get enabled() { return true; }

  get #url() {
    const base = this.vertex
      ? `https://aiplatform.googleapis.com/v1/publishers/google/models/${this.model}:generateContent`
      : `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:generateContent`;
    return `${base}?key=${encodeURIComponent(this.apiKey)}`;
  }

  async translate(text, { target, source }) {
    const instruction = [
      `You are a professional translator for an IT helpdesk. Translate the user's text ${source ? `from ${NAMES[source]} ` : ''}into ${NAMES[target]}.`,
      'Keep the meaning, tone and formatting (line breaks, numbered lists).',
      'Keep placeholders such as [EMAIL], [PHONE], [IP] and ticket IDs such as [TKT-01234] exactly as they are.',
      'Do not add, remove or explain anything. Output only the translation.',
    ].join(' ');
    let res;
    try {
      res = await fetch(this.#url, {
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
      throw new UpstreamError('translation (Gemini)', err);
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new UpstreamError('translation (Gemini)', data?.error?.message ?? `HTTP ${res.status}`);
    const out = (data?.candidates?.[0]?.content?.parts ?? []).map((p) => p.text ?? '').join('').trim();
    if (!out) throw new UpstreamError('translation (Gemini)', `empty response (${data?.candidates?.[0]?.finishReason ?? 'unknown'})`);
    return { text: out, detectedSource: source ?? null };
  }
}
