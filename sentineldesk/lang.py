"""Language detection restricted to English/German. Owner: P3."""
from functools import lru_cache


@lru_cache(maxsize=1)
def _detector():
    from lingua import Language, LanguageDetectorBuilder

    return LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.GERMAN).build()


def detect(text: str) -> str:
    """Return 'en' or 'de'. Defaults to 'en' for empty or ambiguous text."""
    if not text.strip():
        return "en"
    lang = _detector().detect_language_of(text)
    return "de" if lang is not None and lang.name == "GERMAN" else "en"
