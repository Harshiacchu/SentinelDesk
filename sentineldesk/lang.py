"""Language detection restricted to English/German. Owner: P3. CONTRACT.md section 5.

    detect(text, fallback_hits=None) -> {"lang": "en" | "de", "source": "lingua" | "hits" | "default"}

lingua decides when it is confident. When it is not (empty, very short, ambiguous or
gibberish text, i.e. lingua's `None`), the language falls back to the majority language of
the retrieved cases (`fallback_hits`), and finally to "en".

Do not trust the dataset's own `language` column: about 27% of the rows labelled "de" are
English text. `detect_label()` is used to re-label the KB when the index is built.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

LANGUAGES = ("en", "de")
MIN_CONFIDENCE = 0.60


@lru_cache(maxsize=1)
def _detector():
    from lingua import Language, LanguageDetectorBuilder

    return LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.GERMAN).build()


def warmup() -> None:
    """Build the detector and load both language models now (lingua loads each one on first use),
    so the first real ticket does not pay for it. Call once at start-up."""
    d = _detector()
    d.detect_language_of("Hello, this is a short test message to warm up the English model.")
    d.detect_language_of("Guten Tag, das ist eine kurze Testnachricht um das deutsche Modell zu laden.")


def detect_label(text: str | None, min_confidence: float = MIN_CONFIDENCE) -> str | None:
    """'en' / 'de', or None when lingua is not confident enough (or the text is too short)."""
    text = (text or "").strip()
    if len(text) < 3:
        return None
    values = _detector().compute_language_confidence_values(text)
    if not values or values[0].value < min_confidence:
        return None
    return "de" if values[0].language.name == "GERMAN" else "en"


def _majority(hits: list[dict] | None) -> str | None:
    langs = [h.get("language") for h in (hits or []) if h.get("language") in LANGUAGES]
    if not langs:
        return None
    counts = Counter(langs)
    best = max(counts.values())
    tied = [lang for lang, c in counts.items() if c == best]
    return next(lang for lang in langs if lang in tied)  # tie: the language of the best-ranked hit


def detect(text: str | None, fallback_hits: list[dict] | None = None) -> dict:
    """Never raises. See the module docstring for the fallback order."""
    try:
        label = detect_label(text)
    except Exception:  # noqa: BLE001  (e.g. lingua missing): fall through to hits / default
        label = None
    if label:
        return {"lang": label, "source": "lingua"}
    from_hits = _majority(fallback_hits)
    if from_hits:
        return {"lang": from_hits, "source": "hits"}
    return {"lang": "en", "source": "default"}
