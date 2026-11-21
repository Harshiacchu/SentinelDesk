import { TranslationProvider } from './TranslationProvider.js';
import { AppError } from '../../core/errors.js';

/** Used when no translation key is configured: says so instead of returning fake text. */
export class DisabledTranslationProvider extends TranslationProvider {
  async translate() {
    throw new AppError('Translation is not configured: add GOOGLE_TRANSLATE_API_KEY to server/.env', 503);
  }
}
