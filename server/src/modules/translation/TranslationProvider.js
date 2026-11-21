import { NotImplementedError } from '../../core/errors.js';

/** Port: translate text between English and German. */
export class TranslationProvider {
  get enabled() { return false; }
  // eslint-disable-next-line no-unused-vars
  async translate(text, { target, source }) { throw new NotImplementedError(this.constructor.name, 'translate'); }
}
