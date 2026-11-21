"""Escalation gate: pre-LLM risk/confidence checks and post-LLM draft validation. Owner: P4.

Contract section 6:
  pre(triage, hits, text, lang)      -> {status, reasons}
  post(draft, hits, lang, text="")   -> {status, reasons}

status is "auto_draft" or "escalate"; each reason is {"code", "detail"} with one readable sentence.
Codes, in order:
  pre : INJECTION, HIGH_INCIDENT, RISKY_ASK, LOW_CONFIDENCE, NO_PRECEDENT
  post: NOT_FOUND, BAD_CITATION, UNSUPPORTED_NUMBER, LANG_MISMATCH, REFUSAL, LLM_ERROR
Every reason that fires is listed. Neither function raises: an internal failure escalates
(LOW_CONFIDENCE from pre, LLM_ERROR from post).

Thresholds come from config/thresholds.json (contract section 7: tau_c, tau_s, t_high_incident), then from
config.py (TAU_C, TAU_S, HIGH_INCIDENT_THRESHOLD), then from the defaults below.
`text` in post() is optional: when it is missing, the ticket text stored on the draft by draft.generate() is used,
so numbers the customer wrote themselves are not flagged.
"""
import json
import re
from pathlib import Path

from . import config

AUTO = "auto_draft"
ESCALATE = "escalate"
LABELS = {AUTO: "Auto-Draft Ready", ESCALATE: "Escalate to On-Call Engineer"}  # for the UI

_THRESHOLDS_FILE = Path(__file__).resolve().parent.parent / "config" / "thresholds.json"
_file_cache: dict = {"key": None, "data": {}}  # key = (path, mtime): a different file never reuses old data


def thresholds() -> dict:
    """{tau_c, tau_s, t_high_incident}. thresholds.json wins, then config.py, then defaults. Re-read when the file changes."""
    out = {
        "tau_c": float(getattr(config, "TAU_C", getattr(config, "MIN_CLASSIFIER_CONF", 0.55))),
        "tau_s": float(getattr(config, "TAU_S", getattr(config, "MIN_RETRIEVAL_SIM", 0.80))),
        "t_high_incident": float(getattr(config, "HIGH_INCIDENT_THRESHOLD", 0.5)),
    }
    try:
        key = (str(_THRESHOLDS_FILE), _THRESHOLDS_FILE.stat().st_mtime)
        if _file_cache["key"] != key:
            _file_cache["data"] = json.loads(_THRESHOLDS_FILE.read_text(encoding="utf-8"))
            _file_cache["key"] = key
        for key in out:
            val = _file_cache["data"].get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[key] = float(val)
    except (OSError, ValueError):
        pass
    return out

_F = re.IGNORECASE | re.UNICODE


def _rx(*parts: str, flags: int = _F) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in parts), flags)


# ---------------------------------------------------------------- patterns

INJECTION = _rx(
    # EN
    r"\b(ignore|disregard|forget|override|bypass)\b[^.!?\n]{0,30}\b(previous|prior|above|earlier|all|your|the|system)\b[^.!?\n]{0,20}\b(instructions?|prompts?|rules|guidelines|directions)\b",
    r"\b(reveal|show|print|repeat|output|leak|tell me)\b[^.!?\n]{0,20}\b(your|the)\s+(system\s+prompt|instructions|hidden\s+prompt|initial\s+prompt)\b",
    r"\byou are now (an? |the )?(unrestricted |jailbroken |different |new |evil )?(ai|assistant|bot|chatbot|model|agent)\b",
    r"\bact as (an? )?(admin|administrator|developer|system|unrestricted)\b",
    r"\b(developer|god|jailbreak)\s+mode\b|\bjailbreak\w*",
    r"^\s*(system|assistant)\s*:|\bnew instructions\s*:|\[/?INST\]|<\s*/?\s*(system|case|cases|ticket|instructions)\b[^>]*>",
    # DE
    r"\b(ignorier\w*|vergiss|vergessen sie|missachte\w*|überschreib\w*)\b[^.!?\n]{0,30}\b(anweisungen|instruktionen|regeln|vorgaben|befehle|prompts?)\b",
    r"\b(zeig\w*|gib|geben sie|verrat\w*|wiederhol\w*|nenn\w*)\b[^.!?\n]{0,20}\b(system-?\s?prompt|deine anweisungen|ihre anweisungen)\b",
    r"\b(du bist|sie sind|ab sofort bist du) (jetzt |ab sofort |nun )?(ein |eine |der |die )?\w*(assistent|bot|ki|modell|agent)\b",
    r"\bneue anweisungen\s*:",
    flags=_F | re.MULTILINE,
)

RISKY_ASK = _rx(
    # money back, compensation, discounts, specific quotes
    r"\brefund\w*|\breimburse\w*|\bmoney back\b|\bchargeback\b|\bcompensat\w*|\bservice credits?\b",
    r"\bdiscount\w*|\bprice (reduction|match|cut)\b|\bspecial (price|offer|deal|rate)\b",
    r"\b(a|an|the|your|formal|binding|written|price|custom)\s+(quote|quotation|price offer)\b",
    r"\b(rück)?erstattung\w*|\bgeld zurück\b|\brückzahlung\w*|\bentschädigung\w*|\bkompensation\w*|\bschadensersatz\w*|\bgutschrift\w*",
    r"\brabatt\w*|\bpreisnachlass\w*|\bnachlass\b|\bkostenvoranschlag\w*|\b(verbindliches|individuelles|schriftliches)\s+angebot\b|\bpreisangebot\w*",
    # SLA guarantees
    r"\bSLAs?\b|\bservice[- ]level[- ]agreement\b",
    r"\bguarantee\w*\s+(\w+\s+)?(uptime|availability|response|resolution|fix)\b|\b(uptime|availability|response[- ]time)\s+guarantee\w*",
    r"\bgarantiert\w*\s+(\w+\s+)?(verfügbarkeit|reaktionszeit|lösung|behebung)\b|\b(verfügbarkeits|reaktionszeit)garantie\b",
    # legal
    r"\blawyer\w*|\battorney\w*|\blawsuit\w*|\bsue\b|\bsuing\b|\blegal (action|steps|proceedings|claim|team|department)\b|\bcourt\b|\bliab(le|ility)\b|\bbreach of contract\b",
    r"\banwalt\w*|\brechtsanwalt\w*|\bklage\b|\bverklag\w*|\brechtliche\w* (schritte|konsequenzen)\b|\bgericht\b|\bgerichtlich\w*|\bhaftung\w*|\bvertragsbruch\b",
    # data deletion / GDPR erasure
    r"\b(delete|erase|remove|wipe|purge)\b[^.!?\n]{0,30}\b(my|our|all|personal|customer|user)\b[^.!?\n]{0,20}\b(data|information|records|account)\b",
    r"\bright to (be forgotten|erasure)\b|\bGDPR\b|\bDSGVO\b|\brecht auf vergessen\w*",
    r"\b(meine|unsere|alle|persönliche\w*|personenbezogene\w*)\s+(daten|konto|account|informationen)\b[^.!?\n]{0,30}\blöschen\b",
    r"\blöschung\s+(meiner|unserer|aller|der personenbezogenen)\b|\bdatenlöschung\b",
)

# Asking us to share/reveal a password (not an ordinary reset or a policy question).
_PASSWORD_SHARE = _rx(
    r"\b(send|share|tell|give|email|disclose|reveal|what is|what's)\b[^.!?\n]{0,30}\b(password|passwords|credentials|login details)\b(\s+\w+)?",
    r"\b(schick\w*|send\w*|teil\w*|nenn\w*|gib|geben sie|verrat\w*|wie lautet)\b[^.!?\n]{0,30}\b(passwort|passwörter|kennwort|zugangsdaten)\b(\s+\w+)?",
)
_PASSWORD_OK = _rx(
    r"\breset\w*|\bnew\b|\btemporary\b|\bforgot\w*|\bpolicy\b|\brequirements?\b|\brules\b|\bexpir\w*|\bchange\w*",
    r"\bzurücksetz\w*|\bneue\w*\b|\bvergessen\b|\brichtlinie\w*|\banforderung\w*|\bänder\w*|\babgelaufen\w*",
)


def _risky_hits(text: str) -> list[str]:
    hits = [m.group(0) for m in RISKY_ASK.finditer(text)]
    for m in _PASSWORD_SHARE.finditer(text):
        if not _PASSWORD_OK.search(m.group(0)):
            hits.append(m.group(0))
    return hits


# ---------------------------------------------------------------- field helpers
# Tolerate both the contract field names and the old scaffold names.

def hit_score(hit: dict) -> float:
    return float(hit.get("score", hit.get("similarity", 0.0)) or 0.0)


def hit_answer(hit: dict) -> str:
    """Full answer first: answer_snippet is cut to 240 characters and would hide numbers the cited case really contains."""
    return hit.get("answer") or hit.get("answer_snippet") or ""


def _prob(head) -> float:
    if not isinstance(head, dict):
        return 0.0
    return float(head.get("prob", head.get("confidence", 0.0)) or 0.0)


def _label(head) -> str:
    return str(head.get("label", "")) if isinstance(head, dict) else ""


def _r(code: str, detail: str) -> dict:
    return {"code": code, "detail": detail}


def _result(reasons: list[dict]) -> dict:
    return {"status": ESCALATE if reasons else AUTO, "reasons": reasons}


def reason_text(r) -> str:
    """'CODE: detail' for logs and the old UI; accepts a reason dict or a plain string."""
    return f"{r['code']}: {r['detail']}" if isinstance(r, dict) else str(r)


def _short(s: str, n: int = 40) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- pre-LLM gate

def pre(triage: dict, hits: list[dict], text: str, lang: str) -> dict:
    try:
        triage, hits, text = triage or {}, hits or [], text or ""
        thr = thresholds()
        reasons = []

        if not text.strip():  # nothing to classify or answer (empty or whitespace-only ticket)
            reasons.append(_r("LOW_CONFIDENCE", "The ticket has no text, so there is nothing to classify or answer."))

        m = INJECTION.search(text)
        if m:
            reasons.append(_r("INJECTION", f'The ticket contains instruction-like text ("{_short(m.group(0))}") aimed at the assistant.'))

        prob = triage.get("high_incident_prob")
        flags = [str(f) for f in (triage.get("severity_flags") or [])]
        if "high_incident_flag" in triage:  # P2 already applied its tuned threshold and the severity rules
            fire = bool(triage["high_incident_flag"])
        else:
            fire = (prob is not None and float(prob) >= thr["t_high_incident"]) or bool(flags) or (
                prob is None and _label(triage.get("priority")).lower() == "high"
                and _label(triage.get("type")).lower() == "incident")
        if fire:
            parts = []
            if prob is not None:
                parts.append(f"high-priority incident probability {float(prob):.2f}")
            if flags:
                parts.append("severity keywords: " + ", ".join(flags[:3]))
            if not parts:
                parts.append("predicted high-priority Incident")
            reasons.append(_r("HIGH_INCIDENT", f"This looks like a high-priority incident ({'; '.join(parts)}), so an on-call engineer should handle it."))

        risky = _risky_hits(text)
        if risky:
            unique = list({r.lower(): r for r in reversed(risky)}.values())[::-1]
            shown = ", ".join(f'"{_short(r, 25)}"' for r in unique[:3])
            reasons.append(_r("RISKY_ASK", f"The customer asks for something only a human can approve or promise ({shown})."))

        top = max((hit_score(h) for h in hits), default=0.0)
        margin = 1.0
        queue_probs = (triage.get("queue") or {}).get("probs") or {}
        if len(queue_probs) >= 2:
            top2 = sorted(queue_probs.values(), reverse=True)[:2]
            margin = top2[0] - top2[1]

        strong_precedent = (top >= 0.94) and (margin >= 0.05)

        if lang and lang not in config.LANGUAGES:
            reasons.append(_r("LOW_CONFIDENCE", f"Unsupported language detected ({lang})."))

        if triage.get("error"):
            reasons.append(_r("LOW_CONFIDENCE", f"Triage failed ({_short(str(triage['error']), 60)}), so the labels cannot be trusted."))
        elif not strong_precedent:
            for head in ("type", "queue"):
                p = _prob(triage.get(head))
                if p < thr["tau_c"]:
                    reasons.append(_r("LOW_CONFIDENCE", f"The {head} prediction '{_label(triage.get(head)) or 'unknown'}' has only {p:.0%} confidence (minimum {thr['tau_c']:.0%})."))
            if margin < 0.15:
                reasons.append(_r("LOW_CONFIDENCE", f"Ambiguous queue routing (margin {margin:.2f} < 0.15 between top candidates)."))

        if not hits:
            reasons.append(_r("NO_PRECEDENT", "No similar past tickets were found."))
        elif top < thr["tau_s"]:
            reasons.append(_r("NO_PRECEDENT", f"The closest past ticket matches only {top:.3f} (minimum {thr['tau_s']:.3f})."))

        return _result(reasons)
    except Exception as e:
        return _result([_r("LOW_CONFIDENCE", f"The pre-gate hit an internal error ({type(e).__name__}), so the ticket is escalated for safety.")])


# ---------------------------------------------------------------- post-LLM gate

_TICKET_ID = re.compile(r"TKT-\d{5}")
# List numbering: "1. " at line start, or inline after ":" / "." / "!" / "?" ("...steps: 1. Update ... 2. Restart").
_LIST_NUMBER = re.compile(r"^\s*[\[(]?\d{1,2}[.)]\s|(?<=[:.!?;])\s+[\[(]?\d{1,2}[.)](?=\s+[A-ZÄÖÜ\"'(\[])", re.MULTILINE)
_STEP_NUMBER = re.compile(r"\b(step|schritt)\s+\d{1,2}\b", _F)
# Digits glued to a preceding letter are identifiers (IPv4, Win10, E5), not claims.
_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,:]\d+)*")

_WORD_NUMBERS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "twelve": "12", "fifteen": "15", "twenty": "20",
    "thirty": "30", "forty-eight": "48", "twenty-four": "24",
    "ein": "1", "eine": "1", "einen": "1", "einem": "1", "einer": "1", "zwei": "2", "drei": "3",
    "vier": "4", "fünf": "5", "sechs": "6", "sieben": "7", "acht": "8", "neun": "9", "zehn": "10",
    "zwölf": "12", "fünfzehn": "15", "zwanzig": "20", "dreißig": "30", "vierundzwanzig": "24",
    "achtundvierzig": "48",
}
_UNITS = r"(minutes?|hours?|days?|business days?|working days?|weeks?|months?|minuten|stunden?|tagen?|werktagen?|arbeitstagen?|wochen?|monaten?)"
_WORD_TIME = re.compile(r"\b(" + "|".join(sorted(map(re.escape, _WORD_NUMBERS), key=len, reverse=True)) + r")\s+" + _UNITS + r"\b", _F)
_TIME_PROMISE = _rx(
    r"\bby (tomorrow|tonight|end of (the )?(day|week)|eod|monday|tuesday|wednesday|thursday|friday)\b",
    r"\bwithin (the|an|one) hour\b|\bsame[- ]day\b|\bguarantee\w*",
    r"\bbis (morgen|heute abend|ende der woche|montag|dienstag|mittwoch|donnerstag|freitag)\b",
    r"\binnerhalb (einer|der nächsten) stunde\b|\bnoch heute\b|\bgarantie\w*|\bgarantier\w*",
)


def _norm(num: str) -> str:
    return num.replace(",", ".").rstrip(".:")


def _numbers(s: str) -> set[str]:
    return {_norm(n) for n in _NUMBER.findall(s)}


def unsupported_numbers(reply: str, sources: str) -> list[str]:
    """Numbers, number words with a time unit, and time promises in the reply that no source contains."""
    body = _TICKET_ID.sub(" ", reply)
    body = _LIST_NUMBER.sub(" ", body)
    body = _STEP_NUMBER.sub(" ", body)

    src_lower = sources.lower()
    src_nums = _numbers(_TICKET_ID.sub(" ", sources))
    bad = [n for n in _NUMBER.findall(body) if _norm(n) not in src_nums]

    for m in _WORD_TIME.finditer(body):
        digit = _WORD_NUMBERS[m.group(1).lower()]
        if digit not in src_nums and m.group(0).lower() not in src_lower:
            bad.append(m.group(0))

    for m in _TIME_PROMISE.finditer(body):
        if m.group(0).lower() not in src_lower:
            bad.append(m.group(0))

    return list(dict.fromkeys(bad))



def _detect_lang(text: str) -> str | None:
    """Language of the reply via lang.py (P3). Handles both a plain 'en'/'de' and the contract's {lang, source}.
    Returns None when detection is unavailable or only fell back to a default."""
    try:
        from . import lang as lang_mod

        out = lang_mod.detect(text)
        if isinstance(out, dict):
            if out.get("source") == "default":
                return None
            out = out.get("lang")
        return out if out in ("en", "de") else None
    except Exception:
        return None


# Offers the reply may only make when a cited case makes them too (a call, or an escalation / hand-over).
_OFFER_KINDS = {
    "a call": _rx(
        r"\b(schedule|arrange|book|set up|organi[sz]e|propose|offer|plan)\b[^.!?\n]{0,40}\b(call|callback|phone call|video call|meeting)\b",
        r"\b(call|phone|ring)\s+(you|us)\b|\bcall[- ]?back\b|\bgive you a call\b",
        r"\b(Anruf|Anrufe|Rückruf|Telefonat|Telefonkonferenz|telefonisch\w*|anrufen|Videoanruf)\b",
        r"\b(Termin|Gespräch)\b[^.!?\n]{0,30}\b(vereinbar\w*|ausmachen)\b",
    ),
    "an escalation": _rx(
        r"\bescalat\w+\b",
        r"\b(forward|pass|hand)\w*\b[^.!?\n]{0,30}\b(specialist|specialists|colleague|engineer|manager|senior)\b",
        r"\beskalier\w*\b|\bEskalation\b|\bweiterleit\w*\b|\bSpezialist\w*\b|\bExperten\b",
    ),
}


def unsupported_offers(reply: str, cited_answers: str) -> list[str]:
    """Kinds of offer ("a call", "an escalation") that the reply makes but no cited case makes."""
    return [kind for kind, rx in _OFFER_KINDS.items() if rx.search(reply) and not rx.search(cited_answers)]


# Template placeholders copied from dataset answers ("Dear <name>, call <tel_num>").
_PLACEHOLDER = re.compile(r"<[A-Za-z_]+>|\[Your Name\]|\[Ihr Name\]|\[(?:NAME|EMAIL|PHONE|IP|IBAN|CARD|ACCOUNT)\]")
_LANG_NAME = {"en": "English", "de": "German"}


def post(draft: dict | None, hits: list[dict], lang: str = "", text: str = "") -> dict:
    try:
        hits = hits or []
        if not isinstance(draft, dict):
            return _result([_r("LLM_ERROR", "No draft was returned.")])

        error = draft.get("error")
        if error:
            if str(error).startswith("bad_json"):
                return _result([_r("LLM_ERROR", "The model's answer was not valid JSON.")])
            return _result([_r("LLM_ERROR", f"The LLM call failed ({_short(str(error), 80)}).")])
        stop = draft.get("stop_reason")
        if stop == "refusal":
            return _result([_r("REFUSAL", "The model declined to write a reply for this ticket.")])
        if stop == "max_tokens":
            return _result([_r("LLM_ERROR", "The reply was cut off at the output token limit.")])

        reply = (draft.get("reply") or "").strip()
        if draft.get("not_found") or not reply:
            return _result([_r("NOT_FOUND", "None of the retrieved past tickets addresses this problem.")])

        reasons = []
        retrieved = {h.get("ticket_id") for h in hits}
        cited = list(draft.get("cited_ids") or [])
        in_text = _TICKET_ID.findall(reply)
        if not cited and not in_text:
            reasons.append(_r("BAD_CITATION", "The reply does not cite any past ticket."))
        bad_ids = sorted(set(cited + in_text) - retrieved)
        if bad_ids:
            reasons.append(_r("BAD_CITATION", f"The reply cites {', '.join(bad_ids)}, which were not among the retrieved cases."))

        ticket_text = text or draft.get("ticket_text") or ""
        cited_hits = [h for h in hits if h.get("ticket_id") in set(cited + in_text)]
        sources = ticket_text + "\n" + "\n".join(hit_answer(h) for h in cited_hits)
        bad_nums = unsupported_numbers(reply, sources)
        if bad_nums:
            reasons.append(_r("UNSUPPORTED_NUMBER", f"The reply states {', '.join(bad_nums[:5])}, which appears in neither the ticket nor the cited cases."))

        detected = _detect_lang(_TICKET_ID.sub(" ", reply))
        if detected and lang and detected != lang:
            reasons.append(_r("LANG_MISMATCH", f"The reply is in {_LANG_NAME[detected]} but the ticket is in {_LANG_NAME.get(lang, lang)}."))

        leaked = sorted(set(_PLACEHOLDER.findall(reply)))
        if leaked:
            reasons.append(_r("LLM_ERROR", f"The reply contains template placeholders ({', '.join(leaked[:3])}) copied from a past answer."))

        offers = unsupported_offers(reply, "\n".join(hit_answer(h) for h in cited_hits))
        if offers:
            reasons.append(_r("LLM_ERROR", f"The reply offers {' and '.join(offers)}, but none of the cited past tickets does."))

        return _result(reasons)
    except Exception as e:
        return _result([_r("LLM_ERROR", f"The post-gate hit an internal error ({type(e).__name__}), so the draft is not trusted.")])


# --- Legacy adapter: remove once pipeline.py calls pre()/post() (P5) ----------------------------

def decide(ticket: dict, triage: dict, cases: list[dict]) -> dict:
    from .contracts import ticket_text

    res = pre(triage, cases, ticket_text(ticket), triage.get("language", "en"))
    return {"decision": "ESCALATE" if res["reasons"] else "AUTO_DRAFT", "status": res["status"],
            "reasons": [reason_text(r) for r in res["reasons"]]}


def check_draft(draft: dict, cases: list[dict]) -> list[str]:
    d = dict(draft or {})
    d.setdefault("cited_ids", d.get("cited_ticket_ids", []))
    if d.get("grounded") is False:
        d["not_found"] = True
    return [reason_text(r) for r in post(d, cases)["reasons"]]
