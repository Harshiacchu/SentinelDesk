"""PII masking. Owner: P3. CONTRACT.md section 5.

    mask(text) -> {"text": masked_text, "entities": [{"type", "start", "end"}, ...]}

Placeholders are exactly [EMAIL] [PHONE] [IP] [IBAN] [CARD] [ACCOUNT]. `start`/`end` are
offsets in the ORIGINAL text, so the original values are never copied into the result.
Apply before any LLM call. The dataset's own anonymisation tokens (<tel_num>, <acc_num>,
<name>, ...) are mapped to the same placeholders ([NAME] is the one extra tag).

Spans are found on the original text in priority order (EMAIL, IBAN, CARD, IP, ACCOUNT,
PHONE, dataset tokens); a lower-priority match that overlaps a higher one is dropped, so an
IBAN is never also reported as a phone number.
"""
from __future__ import annotations

import re

# Bounded quantifiers keep this linear on long unbroken text (unbounded took ~6 s on 50,000 chars).
_EMAIL = re.compile(r"[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b")
_CARD = re.compile(r"(?<![\w.])(?:\d[ -]?){12,18}\d(?!\w)")
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
_ACCOUNT = re.compile(
    r"\b(?:account|acct|konto|customer|kunden|kunde)\s*(?:number|nummer|no\.?|nr\.?|id|#)?\s*[:#]?\s*\d{5,}\b",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<![\w.])\+?\(?\d[\d \t().-]{6,}\d")  # no newlines: a number never spans lines
_PLUS_BREAK = re.compile(r"\s+(?=\+)")  # "+49 170 1 +49 171 2": a "+" starts the next number
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATASET_TOKEN = re.compile(r"<(tel_num|acc_num|name|email|address|ip_address)>", re.IGNORECASE)
_TOKEN_TYPE = {"tel_num": "PHONE", "acc_num": "ACCOUNT", "name": "NAME", "email": "EMAIL",
               "address": "ADDRESS", "ip_address": "IP"}


def _digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def _luhn_ok(number: str) -> bool:
    d = [int(c) for c in number][::-1]
    total = sum(d[0::2]) + sum(sum(divmod(2 * x, 10)) for x in d[1::2])
    return total % 10 == 0


def _is_card(s: str) -> bool:
    n = _digits(s)
    return 13 <= len(n) <= 19 and _luhn_ok(n)


def _is_ipv6(s: str) -> bool:
    # Real addresses are fully written (8 groups) or use "::". This keeps times like 10:30:45.
    return "::" in s or s.count(":") == 7


def _is_phone(s: str) -> bool:
    return 9 <= len(_digits(s)) <= 15 and not _ISO_DATE.match(s)


_MAX_PHONE_RUN_DIGITS = 30  # a longer digit run is a log line or a list, not phone numbers


def _phone_spans(text: str):
    """(start, end) of phone numbers. A run of digits with more than 15 digits (two numbers written
    next to each other) is split at "+" boundaries; if it is still too long it is masked whole,
    because leaking a number is worse than over-masking a digit list."""
    for m in _PHONE.finditer(text):
        s0, run = m.start(), m.group(0)
        parts, pos = [], 0
        for b in _PLUS_BREAK.finditer(run):
            parts.append((pos, b.start()))
            pos = b.end()
        parts.append((pos, len(run)))
        for a, b in parts:
            piece = run[a:b]
            n = len(_digits(piece))
            if _ISO_DATE.match(piece) or n < 9:
                continue
            if n <= 15 or n <= _MAX_PHONE_RUN_DIGITS:
                yield s0 + a, s0 + b


def find_entities(text: str) -> list[dict]:
    """Non-overlapping PII spans on the original text, sorted by position.

    Each pattern runs on a copy of the text where the spans found so far are blanked out, so a
    greedy pattern (phone) can never swallow an e-mail, IBAN or IP address that is next to it.
    """
    spans: list[tuple[int, int, str]] = []
    work = text

    def claim(s: int, e: int, kind: str) -> None:
        nonlocal work
        spans.append((s, e, kind))
        work = work[:s] + "\x00" * (e - s) + work[e:]

    def add(pattern: re.Pattern, kind: str, check=None) -> None:
        for m in list(pattern.finditer(work)):
            if check and not check(m.group(0)):
                continue
            claim(m.start(), m.end(), kind)

    add(_EMAIL, "EMAIL")
    add(_IBAN, "IBAN")
    add(_CARD, "CARD", _is_card)
    add(_IPV4, "IP")
    add(_IPV6, "IP", _is_ipv6)
    add(_ACCOUNT, "ACCOUNT")
    for s, e in list(_phone_spans(work)):
        claim(s, e, "PHONE")
    for m in list(_DATASET_TOKEN.finditer(work)):
        claim(m.start(), m.end(), _TOKEN_TYPE[m.group(1).lower()])
    spans.sort()
    return [{"type": k, "start": s, "end": e} for s, e, k in spans]


def mask(text: str | None) -> dict:
    """Replace PII with [TYPE] placeholders. Never raises; None/empty give an empty result."""
    text = text or ""
    entities = find_entities(text)
    out, pos = [], 0
    for ent in entities:
        out.append(text[pos:ent["start"]])
        out.append(f"[{ent['type']}]")
        pos = ent["end"]
    out.append(text[pos:])
    return {"text": "".join(out), "entities": entities}
