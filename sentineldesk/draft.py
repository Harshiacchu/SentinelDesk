"""Grounded multilingual reply drafting with an LLM (Gemini by default, Claude optional). Owner: P4.

Contract section 8:
  generate(masked_text, lang, hits) -> {reply, cited_ids, not_found, stop_reason, model, latency_ms, error}
plus extras: mode ("llm" | "mock" | "offline"), provider, ticket_text (read by gate.post for the number check).

generate() never raises. Any failure comes back in `error` (or as stop_reason
"refusal" / "max_tokens") and gate.post() turns it into an escalation.

.env:
  LLM_PROVIDER=gemini | anthropic   (default gemini)
  GEMINI_USE_VERTEX=true | false    (true: Google Cloud Gemini platform / Vertex key; false: AI Studio key)
  LLM_MODEL=<model name>            (default per provider, see DEFAULT_MODELS)
  GEMINI_API_KEY=... / ANTHROPIC_API_KEY=...
  LLM_TIMEOUT_S=15                  (per request; contract section 8)
  OFFLINE=1                         serve cache/demo_drafts.json instead of calling the LLM
  RECORD_DRAFTS=1                   save every good live draft into that cache (run the demo tickets once with it)
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

from . import config  # loads .env
from . import gate
from .gate import hit_answer

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "draft_system.md").read_text(encoding="utf-8")

# gemini-3.5-flash-lite: p50 ~1.2 s, p95 ~1.6 s in scripts/bench_draft.py (gemini-3.5-flash: p50 ~10 s, p95 ~30 s), same gate pass rate.
DEFAULT_MODELS = {"gemini": "gemini-3.5-flash-lite", "anthropic": "claude-opus-5-5"}
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
LLM_MODEL = (os.getenv("LLM_MODEL") or os.getenv("SENTINEL_LLM_MODEL")
             or DEFAULT_MODELS.get(LLM_PROVIDER, DEFAULT_MODELS["gemini"]))
LLM_EFFORT = getattr(config, "LLM_EFFORT", "low")            # Claude only
LLM_MAX_TOKENS = getattr(config, "LLM_MAX_TOKENS", 16000)    # covers thinking + reply
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S") or getattr(config, "LLM_TIMEOUT_S", 15.0))
RETRY_BACKOFF_S = 2.0                                        # one retry on HTTP 429
GEMINI_USE_VERTEX = os.getenv("GEMINI_USE_VERTEX", "false").strip().lower() in ("1", "true", "yes")

# Latency / cost knobs. None = leave at the provider default. generate(opts=...) overrides per call
# (pass False to switch a default off for one call). The defaults below come from scripts/bench_draft.py:
# minimal thinking + a 150-word reply (contract section 8). Override in .env: LLM_THINKING=HIGH|off, LLM_MAX_WORDS=200|0.
#   thinking      Gemini thinking level: "MINIMAL" | "LOW" | "MEDIUM" | "HIGH" (a model that rejects it is retried without)
#   top_cases     send only the first N retrieved cases to the LLM
#   answer_chars  trim each case's resolution to about this many characters
#   max_words     ask for a reply under N words (and cap output tokens to match, unless max_tokens is set)
#   max_tokens    hard output-token limit (thinking tokens count against it on Gemini)
def _env_opt(name: str, cast, default):
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    if raw.lower() in ("0", "none", "off", "default"):
        return None
    try:
        return cast(raw)
    except ValueError:
        return default


DEFAULT_OPTS = {"thinking": _env_opt("LLM_THINKING", str, "MINIMAL"), "top_cases": None, "answer_chars": None,
                "max_words": _env_opt("LLM_MAX_WORDS", int, 150), "max_tokens": None}

try:  # P1's harness keys its draft cache on config.LLM_MODEL: keep it equal to the model actually used
    config.LLM_MODEL = LLM_MODEL
except Exception:
    pass

OFFLINE = os.getenv("OFFLINE", "").strip().lower() in ("1", "true", "yes")
RECORD_DRAFTS = os.getenv("RECORD_DRAFTS", "").strip().lower() in ("1", "true", "yes")
DEMO_CACHE = Path(__file__).resolve().parent.parent / "cache" / "demo_drafts.json"

# Longest ticket text sent to the LLM. Real tickets are ~170 words at most; a pasted log can be huge.
MAX_TICKET_CHARS = int(os.getenv("LLM_MAX_TICKET_CHARS") or 6000)

LANG_NAMES = {"en": "English", "de": "German"}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "cited_ids": {"type": "array", "items": {"type": "string"}},
        "not_found": {"type": "boolean"},
    },
    "required": ["reply", "cited_ids", "not_found"],
    "additionalProperties": False,
}

# Gemini finish / block reasons that mean "declined for safety" -> gate REFUSAL.
GEMINI_REFUSAL = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY",
                  "IMAGE_PROHIBITED_CONTENT", "MODEL_ARMOR", "JAILBREAK"}
GEMINI_OK = {"STOP", "FINISH_REASON_UNSPECIFIED", ""}

_ID_RE = re.compile(r"TKT-\d{5}")
_OUR_TAGS = re.compile(r"</?\s*(case|cases|ticket)\b[^>]*>", re.IGNORECASE)

_clients: dict = {}


def provider_for(model: str) -> str:
    """Pick the provider from the model name, so --models can mix Gemini and Claude."""
    m = (model or "").lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith(("gemini", "gemma")):
        return "gemini"
    return LLM_PROVIDER


def _gemini_client():
    if "gemini" not in _clients:
        from google import genai
        from google.genai import types

        # GEMINI_USE_VERTEX=true: Vertex AI "express mode" (a Gemini platform API key,
        # sent to aiplatform.googleapis.com). The key is already bound to its project,
        # so project/location must NOT be passed. false: AI Studio (Gemini Developer API) key.
        _clients["gemini"] = genai.Client(
            vertexai=GEMINI_USE_VERTEX,
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=int(LLM_TIMEOUT_S * 1000)),
        )
    return _clients["gemini"]


def _anthropic_client():
    if "anthropic" not in _clients:
        import anthropic

        # max_retries=0: the single 429 retry is done by _with_retry, same as for Gemini.
        _clients["anthropic"] = anthropic.Anthropic(timeout=LLM_TIMEOUT_S, max_retries=0)
    return _clients["anthropic"]


# ---------------------------------------------------------------- prompt building

def _mask(text: str) -> str:
    """PII masking (pii.py, owned by P3). The pipeline masks too; masking twice is harmless."""
    try:
        from . import pii

        out = pii.mask(text or "")
        if isinstance(out, tuple):  # (text, entities)
            out = out[0]
        if isinstance(out, dict):  # contract: {text, entities}
            out = out.get("text", text or "")
        return _extra_mask(str(out))
    except Exception:
        return _extra_mask(text or "")


# Safety net behind pii.py (P3): its patterns miss compact IBANs ("DE89370400440532013000") and IPv6.
# Nothing may reach the LLM unmasked, so these run after pii.mask. Masking twice is harmless.
_EXTRA_PII = (
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b")),
    ("IP", re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}\b"
                      r"|\b[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,6}::(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,6})?(?![\w:])")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
)


def _extra_mask(text: str) -> str:
    for label, pattern in _EXTRA_PII:
        text = pattern.sub(f"[{label}]", text)
    return text


def _clean(text: str) -> str:
    """Mask PII and strip tags that could break out of our <case>/<ticket> blocks."""
    return _OUR_TAGS.sub("", _mask(text)).strip()


_TEMPLATE_PLACEHOLDER = re.compile(r"<[A-Za-z_]+>|\[Your Name\]|\[Ihr Name\]")
_NAME_PLACEHOLDER = re.compile(r"<(?:first_|last_|full_)?name>|\[Your Name\]|\[Ihr Name\]", re.IGNORECASE)
_LINE_BREAK_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


_MASK_TOKEN = re.compile(r"\[(?:EMAIL|PHONE|IP|IBAN|CARD|ACCOUNT)\]")
_NAME_TOKEN = re.compile(r"\[NAME\]")


def _drop_sentences_with(text: str, pattern: re.Pattern) -> str:
    return " ".join(sent for sent in _SENTENCE_END.split(text) if not pattern.search(sent))


def _clean_case(text: str) -> str:
    """Case text from the KB, without placeholders or contact details the model could copy into a reply.

    Order matters. (1) Dataset placeholders are handled on the RAW text, because pii.py rewrites <name> to [NAME] and
    <tel_num> to [PHONE] and they would no longer be recognised. A name placeholder is removed ("Dear <name>," ->
    "Dear ,"); a sentence with any other placeholder (phone, account number, link) is dropped whole, so no broken
    half-sentence is left ("call us at <tel_num> to book a time" must not become "call us at to book a time").
    (2) PII is masked. (3) A sentence that now holds a masked contact detail is dropped, and [NAME] is removed.
    """
    text = _NAME_PLACEHOLDER.sub("", _LINE_BREAK_TAG.sub("\n", text or ""))
    text = _drop_sentences_with(text, _TEMPLATE_PLACEHOLDER)
    text = _NAME_TOKEN.sub("", _clean(text))
    text = _drop_sentences_with(text, _MASK_TOKEN)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _trim(text: str, limit: int | None) -> str:
    """Cut to about `limit` characters, preferably at a sentence end, otherwise at a word."""
    if not limit or len(text) <= limit:
        return text
    cut = text[:limit]
    ends = [cut.rfind(x) for x in (". ", "! ", "? ", ".\n", "\n")]
    best = max(ends)
    if best >= int(limit * 0.6):
        return cut[: best + 1].rstrip()
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip() + "…"


def _merged(opts: dict | None) -> dict:
    merged = {**DEFAULT_OPTS, **{k: v for k, v in (opts or {}).items() if v is not None}}
    return {k: (None if v is False else v) for k, v in merged.items()}  # False = off for this call


def _token_limit(o: dict) -> int:
    if o["max_tokens"]:
        return int(o["max_tokens"])
    if o["max_words"]:  # ~1.3 tokens per English word, ~2 for German, plus JSON overhead
        return int(o["max_words"] * 2.5) + 80
    return LLM_MAX_TOKENS


def _ticket_for_llm(text: str) -> str:
    """Masked ticket text, cut to about MAX_TICKET_CHARS.

    The cut happens BEFORE masking, at a word boundary (so an email or IBAN is never split in half):
    pii.py's email pattern gets quadratically slower on long input (200k characters would take over a minute).
    """
    text = text or ""
    was_cut = len(text) > MAX_TICKET_CHARS
    if was_cut:
        head = text[:MAX_TICKET_CHARS]
        m = re.search(r"\s\S*$", head)
        text = head[: m.start()] if m else head
    return _clean(text) + (" [...text cut]" if was_cut else "")


def build_user_message(text: str, lang: str, hits: list[dict], opts: dict | None = None) -> str:
    o = _merged(opts)
    used = hits[: o["top_cases"]] if o["top_cases"] else hits
    cases = "\n\n".join(
        f'<case id="{h.get("ticket_id", "")}" language="{h.get("language", "")}">\n'
        f"Subject: {_clean_case(h.get('subject') or '')}\n"
        f"Resolution: {_trim(_clean_case(hit_answer(h)), o['answer_chars'])}\n"
        f"</case>"
        for h in used
    )
    msg = (
        f"<cases>\n{cases}\n</cases>\n\n"
        f"<ticket>\n{_ticket_for_llm(text)}\n</ticket>\n\n"
        f"Reply language: {LANG_NAMES.get(lang, 'English')}"
    )
    if o["max_words"]:
        msg += f"\nKeep the reply under {int(o['max_words'])} words."
    return msg


# ---------------------------------------------------------------- results and parsing

def _result(reply="", cited_ids=None, not_found=False, stop_reason=None, error=None, mode="llm"):
    return {
        "reply": reply,
        "cited_ids": list(cited_ids or []),
        "not_found": bool(not_found),
        "stop_reason": stop_reason,  # normalised: end_turn | refusal | max_tokens | None
        "error": error,
        "mode": mode,  # "llm" or "mock": the UI labels mock drafts as offline
    }


_NUMBERED_ITEM = re.compile(r"(?:^|[ \t])\d{1,2}[.)][ \t]+\S")
_INLINE_ITEM_START = re.compile(r"(?<=[.!?\])])[ \t]+(?=\d{1,2}[.)][ \t]+\S)")


_STEP_TAIL = re.compile(r"(?<=[.!?\]])[ \t]{2,}(?=[A-ZÄÖÜ])")
_STEP_LINE = re.compile(r"\s*\d{1,2}[.)]\s")


def _tidy_reply(reply: str) -> str:
    """Layout fixes: the model sometimes writes "... text. 1. Step one. 2. Step two." on one line, or glues the closing
    sentence to the last step with a double space. Put each numbered step, and the closing, on its own line."""
    lines = []
    for line in reply.split("\n"):
        if len(_NUMBERED_ITEM.findall(line)) >= 2:
            line = _INLINE_ITEM_START.sub("\n", line)
        lines.append(line)
    out = []
    for line in "\n".join(lines).split("\n"):
        out.append(_STEP_TAIL.sub("\n\n", line) if _STEP_LINE.match(line) else line)
    return "\n".join(out)


def _parse(raw: str) -> dict | None:
    """Parse and type-check the model's JSON. Returns None if it is not what we asked for."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    reply, cited, not_found = data.get("reply"), data.get("cited_ids"), data.get("not_found")
    if not isinstance(reply, str) or not isinstance(cited, list) or not isinstance(not_found, bool):
        return None
    ids = []  # accept "[TKT-00012]" or "TKT-00012", keep order, drop duplicates
    for c in cited:
        m = _ID_RE.search(str(c))
        if m and m.group(0) not in ids:
            ids.append(m.group(0))
    return {"reply": _tidy_reply(reply.strip()), "cited_ids": ids, "not_found": not_found}


def _from_json(raw: str, stop_reason: str = "end_turn") -> dict:
    parsed = _parse(raw)
    if parsed is None:
        return _result(stop_reason=stop_reason, error="bad_json")
    return _result(parsed["reply"], parsed["cited_ids"], parsed["not_found"], stop_reason)


def _with_retry(call, is_rate_limit):
    """Run call(); on a 429 wait RETRY_BACKOFF_S and try exactly once more."""
    try:
        return call()
    except Exception as e:
        if not is_rate_limit(e):
            raise
        time.sleep(RETRY_BACKOFF_S)
        return call()


def _name(reason) -> str:
    """Enum or string -> 'SAFETY' etc."""
    if reason is None:
        return ""
    return str(getattr(reason, "name", reason)).split(".")[-1].upper()


# ---------------------------------------------------------------- providers

def _call_gemini(model: str, user_msg: str, o: dict) -> dict:
    from google.genai import errors, types

    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_json_schema=DRAFT_SCHEMA,
        max_output_tokens=_token_limit(o),
    )
    if o["thinking"]:
        cfg.thinking_config = types.ThinkingConfig(thinking_level=str(o["thinking"]).upper())
    def generate():
        return _with_retry(
            lambda: _gemini_client().models.generate_content(model=model, contents=user_msg, config=cfg),
            lambda e: isinstance(e, errors.APIError) and e.code == 429,
        )

    try:
        try:
            resp = generate()
        except errors.APIError as e:
            if e.code != 400 or cfg.thinking_config is None:
                raise
            cfg.thinking_config = None  # this model rejects the thinking level: use its own default
            resp = generate()
    except errors.APIError as e:
        return _result(error="api_error: rate limited" if e.code == 429 else f"api_error: HTTP {e.code}")
    except Exception as e:  # missing key, timeout, network: never crash the console
        if "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower():
            return _result(error="api_error: timeout")
        return _result(error=f"api_error: {type(e).__name__}: {str(e)[:120]}")

    feedback = getattr(resp, "prompt_feedback", None)
    blocked = _name(getattr(feedback, "block_reason", None))
    if blocked and blocked != "BLOCKED_REASON_UNSPECIFIED":
        return _result(stop_reason="refusal")

    candidates = getattr(resp, "candidates", None) or []
    if not candidates:
        return _result(error="api_error: no candidates returned")
    finish = _name(candidates[0].finish_reason)
    if finish in GEMINI_REFUSAL:
        return _result(stop_reason="refusal")
    if finish == "MAX_TOKENS":
        return _result(stop_reason="max_tokens")
    if finish not in GEMINI_OK:
        return _result(error=f"api_error: finish_reason {finish}")
    return _from_json(resp.text or "")


def _call_anthropic(model: str, user_msg: str, o: dict) -> dict:
    try:
        import anthropic
    except ImportError:
        return _result(error="api_error: anthropic package not installed")

    try:
        response = _with_retry(
            lambda: _anthropic_client().messages.create(
                model=model,
                max_tokens=int(o["max_tokens"] or LLM_MAX_TOKENS),  # no word-derived cap: thinking counts against it
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                output_config={
                    "effort": LLM_EFFORT,
                    "format": {"type": "json_schema", "schema": DRAFT_SCHEMA},
                },
            ),
            lambda e: isinstance(e, anthropic.RateLimitError),
        )
    except anthropic.APITimeoutError:
        return _result(error="api_error: timeout")
    except anthropic.RateLimitError:
        return _result(error="api_error: rate limited")
    except anthropic.APIStatusError as e:
        return _result(error=f"api_error: HTTP {e.status_code}")
    except anthropic.APIConnectionError:
        return _result(error="api_error: connection failed")
    except Exception as e:
        return _result(error=f"api_error: {type(e).__name__}: {str(e)[:120]}")

    if response.stop_reason in ("refusal", "max_tokens"):
        return _result(stop_reason=response.stop_reason)
    raw = next((b.text for b in response.content if b.type == "text"), "")
    return _from_json(raw, response.stop_reason or "end_turn")


# ---------------------------------------------------------------- public API

def _mock(lang: str, hits: list[dict]) -> dict:
    """Offline draft for demos without an API key (SENTINEL_USE_MOCKS=1). Passes gate.post."""
    if not hits:
        return _result(not_found=True, stop_reason="end_turn", mode="mock")
    tid = hits[0]["ticket_id"]
    if lang == "de":
        reply = (f"Guten Tag,\n\nvielen Dank für Ihre Nachricht. In einem ähnlichen Fall hat Folgendes "
                 f"geholfen [{tid}]. Bitte prüfen Sie diese Schritte und melden Sie sich, falls das "
                 f"Problem weiterhin besteht.\n\nMit freundlichen Grüßen\nIhr Support-Team")
    else:
        reply = (f"Hello,\n\nthank you for reaching out. In a similar case the following resolved the "
                 f"issue [{tid}]. Please check these steps and let us know if the problem persists."
                 f"\n\nBest regards\nYour Support Team")
    return _result(reply, [tid], False, "end_turn", mode="mock")


def offline_key(text: str, lang: str) -> str:
    return hashlib.sha256(f"{lang}|{(text or '').strip()}".encode("utf-8")).hexdigest()


def _offline_read() -> dict:
    try:
        return json.loads(DEMO_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def offline_put(text: str, lang: str, out: dict) -> None:
    """Save a good draft for OFFLINE=1 replay. Never raises."""
    try:
        data = _offline_read()
        data[offline_key(text, lang)] = {k: out.get(k) for k in ("reply", "cited_ids", "not_found", "stop_reason", "model")}
        DEMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        DEMO_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _offline(text: str, lang: str) -> dict:
    hit = _offline_read().get(offline_key(text, lang))
    if not hit:
        return _result(error="offline: no cached draft for this ticket", mode="offline")
    return _result(hit.get("reply", ""), hit.get("cited_ids"), hit.get("not_found", False),
                   hit.get("stop_reason") or "end_turn", mode="offline")


def generate(text: str, lang: str, hits: list[dict], model: str | None = None, opts: dict | None = None) -> dict:
    """Draft a grounded reply from the masked ticket text and the retrieved hits.

    `model` overrides LLM_MODEL; `opts` overrides DEFAULT_OPTS (see top of file). Never raises.
    """
    if isinstance(text, dict):  # legacy call from the old pipeline: generate(ticket, triage, cases)
        return _legacy_generate(text, lang, hits)

    t0 = time.perf_counter()
    model = model or LLM_MODEL
    provider = provider_for(model)
    hits = hits or []
    try:
        if OFFLINE:
            out = _offline(text, lang)
        elif getattr(config, "USE_MOCKS", False):
            out = _mock(lang, hits)
        elif not hits:
            out = _result(not_found=True)  # nothing to ground on: the gate reports NOT_FOUND
        else:
            o = _merged(opts)
            user_msg = build_user_message(text, lang, hits, o)  # PII is masked here, before any call
            call = _call_anthropic if provider == "anthropic" else _call_gemini
            out = call(model, user_msg, o)
            if RECORD_DRAFTS and out["reply"] and not out["error"] and out["stop_reason"] not in ("refusal", "max_tokens"):
                # only drafts the post-gate accepts are worth replaying
                if gate.post({**out, "ticket_text": _ticket_for_llm(text)}, hits, lang)["status"] == gate.AUTO:
                    offline_put(text, lang, {**out, "model": model})
    except Exception as e:
        out = _result(error=f"api_error: {type(e).__name__}: {str(e)[:120]}")
    out.update(provider=provider, model=model, ticket_text=_ticket_for_llm(text),
               latency_ms=round((time.perf_counter() - t0) * 1000))
    return out


def time_models(text: str, lang: str, hits: list[dict], models: list[str], opts: dict | None = None) -> list[dict]:
    """Run the same ticket on several models and report latency."""
    rows = []
    for m in models:
        t0 = time.perf_counter()
        out = generate(text, lang, hits, model=m, opts=opts)
        rows.append({**out, "ms": round((time.perf_counter() - t0) * 1000)})  # includes any 429 retry wait
    return rows


def warmup(model: str | None = None) -> dict:
    """One tiny request so the first real ticket does not pay for client setup and connection start.
    Never raises. Returns {ok, ms, note}. Skipped in mock mode."""
    if getattr(config, "USE_MOCKS", False):
        return {"ok": True, "ms": 0, "note": "mock mode: skipped"}
    model = model or LLM_MODEL
    t0 = time.perf_counter()
    try:
        if provider_for(model) == "anthropic":
            _anthropic_client().messages.create(
                model=model, max_tokens=16, messages=[{"role": "user", "content": "ok"}])
        else:
            _gemini_client().models.generate_content(
                model=model, contents="Reply with the word ok.", config={"max_output_tokens": 50})
        return {"ok": True, "ms": round((time.perf_counter() - t0) * 1000), "note": "warm"}
    except Exception as e:
        return {"ok": False, "ms": round((time.perf_counter() - t0) * 1000),
                "note": f"{type(e).__name__}: {str(e)[:100]}"}


# Names worth trying when the key cannot list models (Vertex express keys get a 401 on listing).
GEMINI_CANDIDATES = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-pro", "gemini-3.1-pro-preview", "gemini-3.1-flash",
                     "gemini-3-flash-preview", "gemini-3-pro-preview", "gemini-2.5-flash",
                     "gemini-2.5-flash-lite", "gemini-2.5-pro"]


def list_gemini_models() -> list[dict]:
    """Gemini models this key can call: [{model, ok, note}].

    Tries the models.list API first; if the key may not list (Vertex API keys cannot),
    sends a one-word request to each name in GEMINI_CANDIDATES instead.
    """
    try:
        names = sorted(m.name.removeprefix("models/") for m in _gemini_client().models.list()
                       if "generateContent" in (m.supported_actions or []))
        if names:
            return [{"model": n, "ok": True, "note": "listed"} for n in names]
    except Exception:
        pass
    rows = []
    for name in GEMINI_CANDIDATES:
        try:
            _gemini_client().models.generate_content(
                model=name, contents="Reply with the word ok.",
                config={"max_output_tokens": 200})
            rows.append({"model": name, "ok": True, "note": "responded"})
        except Exception as e:
            code = getattr(e, "code", type(e).__name__)
            rows.append({"model": name, "ok": False, "note": f"HTTP {code}" if isinstance(code, int) else str(code)})
    return rows


# --- Legacy adapter: remove once pipeline.py calls generate(text, lang, hits) -------------------

def _legacy_generate(ticket: dict, triage: dict, cases: list[dict]) -> dict:
    from .contracts import ticket_text

    out = generate(ticket_text(ticket), triage.get("language", "en"), cases)
    out["cited_ticket_ids"] = out["cited_ids"]  # old app.py reads this key
    return out
