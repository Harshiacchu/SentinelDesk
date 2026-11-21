import { ValidationError } from '../../core/errors.js';

const LANGS = ['en', 'de'];

/** Masks PII before text leaves the server, then translates; results are cached in memory. */
export class TranslationService {
  #cache = new Map();

  constructor({ provider, piiMasker, maxEntries = 500 }) {
    this.provider = provider;
    this.masker = piiMasker;
    this.maxEntries = maxEntries;
  }

  get enabled() { return this.provider.enabled; }

  async translate(text, { target, source }) {
    if (!LANGS.includes(target)) throw new ValidationError('target must be en or de');
    if (source && !LANGS.includes(source)) throw new ValidationError('source must be en or de');
    const masked = this.masker.mask(text).text;
    const key = `${source ?? '?'}>${target}:${masked}`;
    if (this.#cache.has(key)) return { ...this.#cache.get(key), cached: true };
    const out = await this.provider.translate(masked, { target, source });
    if (this.#cache.size >= this.maxEntries) this.#cache.delete(this.#cache.keys().next().value);
    this.#cache.set(key, out);
    return { ...out, cached: false };
  }
}
