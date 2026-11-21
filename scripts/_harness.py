"""Evaluation harness   (P1)

Runs the pipeline stage by stage using ONLY the agreed contracts (section 3), so
evaluate.py can time each stage and never hands labels to any module:

  PII mask -> language -> one embedding -> triage -> search -> gate.pre
  -> (draft -> gate.post)

pii / lang / embed function names were not fixed in the contracts, so the
adapters below try the common names. If yours differ, add the name to the tuple.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from sentineldesk import config
from sentineldesk.data import build_text

PII_NAMES = ("mask", "mask_pii", "redact", "scrub")
LANG_NAMES = ("detect", "detect_language", "detect_lang")
EMBED_NAMES = ("embed_queries", "encode_queries", "embed_query", "encode_query", "encode", "embed")


def is_escalated(status) -> bool:
    return "escal" in str(status or "").lower()


def _find(module, names):
    for n in names:
        f = getattr(module, n, None)
        if callable(f):
            return f
    raise AttributeError(f"{module.__name__} has none of {names}; add yours to scripts/_harness.py")


def _import(name):
    return importlib.import_module(f"sentineldesk.{name}")


class Harness:
    def __init__(self, use_llm: bool = True, cache_path: Path | None = None, fresh: bool = False):
        self.triage = _import("triage")
        self.retrieve = _import("retrieve")
        self.gate = _import("gate")
        self.use_llm = use_llm
        self.draft = _import("draft") if use_llm else None
        self._pii = self._lang = self._embed = None
        for mod, names, attr in (("pii", PII_NAMES, "_pii"), ("lang", LANG_NAMES, "_lang"),
                                 ("embed", EMBED_NAMES, "_embed")):
            try:
                setattr(self, attr, _find(_import(mod), names))
            except (ImportError, AttributeError) as e:
                print(f"[harness] {mod}: {e}")
        self.cache_path = cache_path
        self.cache = {} if fresh or not cache_path or not cache_path.exists() else {
            r["key"]: r for r in map(json.loads, cache_path.read_text(encoding="utf-8").splitlines()) if r}

    # ---------------------------------------------------------------- adapters
    def mask(self, text: str) -> str:
        if not self._pii:
            return text
        out = self._pii(text)
        if isinstance(out, tuple):
            out = out[0]
        if isinstance(out, dict):
            out = out.get("text") or out.get("masked") or text
        return str(out)

    def detect(self, text: str):
        if not self._lang:
            return None
        out = self._lang(text)
        if isinstance(out, dict):
            out = out.get("lang") or out.get("language")
        return out if out in config.LANGUAGES else None

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._embed:
            raise RuntimeError("no embed function available")
        out = np.asarray(self._embed(texts), dtype=np.float32)
        if out.ndim == 1:
            out = out[None, :]
        return out

    # ------------------------------------------------------------------ stages
    def pre_stages(self, text: str, vec: np.ndarray, lang=None, k: int = 5, exclude_id=None):
        """triage -> search -> language fallback -> gate.pre. Returns (record, timings_ms)."""
        t = {}
        s = time.perf_counter()
        tri = self.triage.predict(text, vec)
        t["triage_ms"] = (time.perf_counter() - s) * 1000
        s = time.perf_counter()
        hits = self.retrieve.search(vec, k=k, exclude_id=exclude_id)
        t["retrieve_ms"] = (time.perf_counter() - s) * 1000
        if lang is None:  # plan: None -> majority language of retrieved cases -> en
            langs = [h.get("language") for h in hits if h.get("language") in config.LANGUAGES]
            lang = Counter(langs).most_common(1)[0][0] if langs else "en"
        s = time.perf_counter()
        pre = self.gate.pre(tri, hits, text, lang)
        t["gate_pre_ms"] = (time.perf_counter() - s) * 1000
        return {"triage": tri, "hits": hits, "lang": lang, "pre": pre}, t

    def _draft_cached(self, key_payload: dict, text, lang, hits):
        key = hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode()).hexdigest()
        if key in self.cache:
            r = self.cache[key]
            return r["draft"], r["draft_ms"], True
        s = time.perf_counter()
        d = self.draft.generate(text, lang, hits)
        ms = (time.perf_counter() - s) * 1000
        rec = {"key": key, "draft": d, "draft_ms": ms}
        self.cache[key] = rec
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        return d, ms, False

    def run(self, ticket_id: str, subject, body) -> dict:
        """Full pipeline on raw subject/body only. Never sees labels."""
        rec = {"ticket_id": ticket_id, "error": None}
        t = {}
        t0 = time.perf_counter()
        try:
            text = build_text(subject, body)
            s = time.perf_counter()
            text = self.mask(text)
            t["pii_ms"] = (time.perf_counter() - s) * 1000
            s = time.perf_counter()
            lang = self.detect(text)
            t["lang_ms"] = (time.perf_counter() - s) * 1000
            s = time.perf_counter()
            vec = self.embed([text])[0]
            t["embed_ms"] = (time.perf_counter() - s) * 1000
            out, t2 = self.pre_stages(text, vec, lang=lang)
            t.update(t2)
            rec.update(out, masked_text=text, lang_detected_raw=lang)
            rec["status"], rec["reasons"] = out["pre"].get("status"), list(out["pre"].get("reasons", []))
            rec["drafted"] = False
            if not is_escalated(rec["status"]) and self.use_llm:
                payload = {"text": text, "lang": out["lang"], "model": config.LLM_MODEL,
                           "hits": [h["ticket_id"] for h in out["hits"]]}
                d, ms, cached = self._draft_cached(payload, text, out["lang"], out["hits"])
                t["draft_ms"], rec["draft_cached"] = ms, cached
                s = time.perf_counter()
                post = self.gate.post(d, out["hits"], out["lang"])
                t["gate_post_ms"] = (time.perf_counter() - s) * 1000
                rec.update(draft=d, post=post, drafted=True)
                rec["status"] = post.get("status")
                rec["reasons"] += list(post.get("reasons", []))
        except Exception as e:  # noqa: BLE001  record, don't crash the batch
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["status"] = "error"
        t["total_ms"] = (time.perf_counter() - t0) * 1000
        if "draft_ms" in t and rec.get("draft_cached"):
            t["total_ms"] += t["draft_ms"]  # cached run: count the original LLM time
        rec["latency"] = {k: round(v, 1) for k, v in t.items()}
        return rec