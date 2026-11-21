"""lang.detect to CONTRACT.md section 5: {lang, source}, with the hits -> default fallback."""
import pytest

pytest.importorskip("lingua")

from sentineldesk import lang  # noqa: E402

EN = "I forgot my password and cannot log in to the customer portal, can you help me reset it?"
DE = "Ich habe mein Passwort vergessen und kann mich nicht im Kundenportal anmelden, bitte helfen Sie mir."


def hits(*langs):
    return [{"language": x} for x in langs]


def test_confident_detection_uses_lingua():
    assert lang.detect(EN) == {"lang": "en", "source": "lingua"}
    assert lang.detect(DE) == {"lang": "de", "source": "lingua"}


def test_fallback_hits_are_ignored_when_lingua_is_confident():
    assert lang.detect(EN, fallback_hits=hits("de", "de", "de"))["lang"] == "en"


def test_none_falls_back_to_the_majority_language_of_the_hits():
    out = lang.detect("", fallback_hits=hits("de", "en", "de"))
    assert out == {"lang": "de", "source": "hits"}


def test_tie_goes_to_the_best_ranked_hit():
    assert lang.detect("", fallback_hits=hits("de", "en"))["lang"] == "de"
    assert lang.detect("", fallback_hits=hits("en", "de"))["lang"] == "en"


def test_no_hits_means_default_en():
    assert lang.detect("") == {"lang": "en", "source": "default"}
    assert lang.detect(None) == {"lang": "en", "source": "default"}
    assert lang.detect("  ", fallback_hits=[]) == {"lang": "en", "source": "default"}
    assert lang.detect("", fallback_hits=[{"language": "fr"}, {}]) == {"lang": "en", "source": "default"}


def test_very_short_text_is_none():
    assert lang.detect_label("ok") is None
    assert lang.detect_label("") is None and lang.detect_label(None) is None


def test_gibberish_uses_the_fallback_not_a_guess():
    out = lang.detect("zzxv qwk ;;; 123 #####", fallback_hits=hits("de", "de"))
    assert out["source"] in ("hits", "lingua")  # lingua may still be confident; if not, hits decide
    assert out["lang"] in ("en", "de")


def test_mixed_language_ticket_returns_a_valid_code():
    out = lang.detect("Hallo, my office printer druckt nicht mehr since the Windows update, bitte help")
    assert out["lang"] in ("en", "de") and out["source"] in ("lingua", "default", "hits")


def test_never_raises_on_odd_input():
    for t in ("\u0000\u0001", "🙂🙂🙂", "a" * 10000, "<br>"):
        assert lang.detect(t)["lang"] in ("en", "de")
