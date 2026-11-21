"""Benchmark draft latency and gate pass rate across LLM settings. Owner: P4.

Same 15 tickets (5 EN, 5 DE, the 5 adversarial ones) for every config. Retrieval does not exist yet,
so each ticket gets a hand-written pool of 5 cases (see TOPICS). Configs are interleaved ticket by
ticket so API load drift affects all of them equally. Drafting is measured on all 15, even the
ones gate.pre would stop in production (that is reported separately).

Usage:
  python -m scripts.bench_draft                         # all built-in configs
  python -m scripts.bench_draft --only baseline think_min
  python -m scripts.bench_draft --extra '{"combo": {"model": "gemini-3.5-flash", "opts": {"thinking": "MINIMAL"}}}'
Writes results/bench_draft.json (raw rows) and prints a table.
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from sentineldesk import config, draft, gate

ROOT = Path(__file__).resolve().parent.parent
BASE = "gemini-3.5-flash"

CONFIGS = {
    "baseline":       {"model": BASE, "opts": {}},
    "baseline_rerun": {"model": BASE, "opts": {}},
    "think_min":      {"model": BASE, "opts": {"thinking": "MINIMAL"}},
    "lite_3.5":       {"model": "gemini-3.5-flash-lite", "opts": {}},
    "lite_3.1":       {"model": "gemini-3.1-flash-lite", "opts": {}},
    "top3_trim700":   {"model": BASE, "opts": {"top_cases": 3, "answer_chars": 700}},
    "words150":       {"model": BASE, "opts": {"max_words": 150}},
}

# ---------------------------------------------------------------- case library (synthetic)

TOPICS = {
    ("en", "vpn"): ("VPN connection drops", [
        "Restart the VPN client and check that your internet connection is stable before reconnecting.",
        "Remove the connection profile in the client and import it again from the self-service portal.",
        "Update the VPN client to version 4.2 or newer; older versions drop connections on Wi-Fi networks.",
        "Switch the VPN protocol from UDP to TCP in Settings > Connection and reconnect.",
        "Disable third-party firewall software for 10 minutes to test whether it blocks the tunnel.",
        "Reboot the computer after the update has finished so the new network driver is loaded.",
        "If the connection still drops, send us the client log from Settings > Diagnostics."]),
    ("en", "password"): ("Password reset and locked account", [
        "Open the self-service portal and choose 'Forgot password' on the sign-in page.",
        "Enter your username and confirm with the code sent to your registered phone number.",
        "Choose a new password with at least 12 characters, including a number and a symbol.",
        "Sign out on all devices and sign in again so the old password is no longer cached.",
        "A locked account unlocks automatically after 30 minutes; repeated attempts extend the lock.",
        "If you do not receive the code, contact the service desk so we can verify your identity.",
        "Update the saved password in your mail app and on mobile devices afterwards."]),
    ("en", "printer"): ("Printer shows offline", [
        "Check that the printer is switched on and shows a network connection on its display.",
        "On your computer, open Printers & Scanners, remove the printer and add it again.",
        "Make sure you are on the office network or connected through the VPN, not a guest network.",
        "Restart the print spooler service from the Services panel and send the job again.",
        "Install the latest driver from the software center; driver version 7.1 fixes the offline status.",
        "Clear stuck jobs from the print queue before printing a test page.",
        "If the problem remains, note the printer name on its label and open a ticket with it."]),
    ("en", "email"): ("Email not syncing on phone", [
        "Check that the phone has a working internet connection and that airplane mode is off.",
        "Open the mail app settings and verify the account shows as signed in with no warning.",
        "Remove the work account from the phone and add it again with your company address.",
        "Make sure the sync period is set to 'All' or at least 30 days in the account settings.",
        "Install the latest version of the mail app from the app store and restart the phone.",
        "If you changed your password recently, enter the new password when the app asks for it.",
        "Check the storage on the phone; the app stops syncing when less than 500 MB is free."]),
    ("en", "wifi"): ("Wi-Fi keeps disconnecting", [
        "Forget the office network on your device and connect again using your company login.",
        "Move closer to an access point and check that the signal shows at least two bars.",
        "Update the wireless adapter driver from the software center and restart the laptop.",
        "Turn off power saving for the wireless adapter in the device manager settings.",
        "Switch from the 2.4 GHz network to the 5 GHz network if both are available.",
        "Restart the laptop's network service by turning Wi-Fi off and on again.",
        "If it keeps happening in one room, tell us the room number so we can check the access point."]),
    ("en", "invoice"): ("Invoice download error", [
        "Sign in to the billing portal and open Billing > Invoices, then pick the month you need.",
        "Use the Download PDF button; if nothing happens, allow pop-ups for the billing portal.",
        "Clear the browser cache or try a private window; an old cached page can break the download.",
        "Check that your account has the billing role; without it the invoice list stays empty.",
        "If the PDF is blank, try another browser and wait 15 minutes after the invoice was created.",
        "Invoices for the previous month are created on the 3rd working day of the new month.",
        "If the problem remains, send us the invoice number and a screenshot of the error."]),
    ("de", "vpn"): ("VPN trennt die Verbindung", [
        "Starten Sie den VPN-Client neu und prüfen Sie, ob Ihre Internetverbindung stabil ist.",
        "Entfernen Sie das Verbindungsprofil im Client und importieren Sie es erneut aus dem Self-Service-Portal.",
        "Aktualisieren Sie den VPN-Client auf Version 4.2 oder neuer; ältere Versionen brechen im WLAN ab.",
        "Wechseln Sie in den Einstellungen das VPN-Protokoll von UDP auf TCP und verbinden Sie neu.",
        "Deaktivieren Sie Firewall-Software von Drittanbietern für 10 Minuten, um einen Block zu testen.",
        "Starten Sie den Rechner nach dem Update neu, damit der neue Netzwerktreiber geladen wird.",
        "Besteht das Problem weiter, senden Sie uns das Client-Protokoll aus Einstellungen > Diagnose."]),
    ("de", "passwort"): ("Passwort zurücksetzen", [
        "Öffnen Sie das Self-Service-Portal und wählen Sie auf der Anmeldeseite 'Passwort vergessen'.",
        "Geben Sie Ihren Benutzernamen ein und bestätigen Sie mit dem Code auf Ihrem registrierten Telefon.",
        "Wählen Sie ein neues Passwort mit mindestens 12 Zeichen, einer Zahl und einem Sonderzeichen.",
        "Melden Sie sich auf allen Geräten ab und neu an, damit das alte Passwort nicht mehr gespeichert ist.",
        "Ein gesperrtes Konto wird nach 30 Minuten automatisch entsperrt; weitere Versuche verlängern die Sperre.",
        "Erhalten Sie keinen Code, wenden Sie sich an den Service Desk, damit wir Ihre Identität prüfen.",
        "Aktualisieren Sie danach das gespeicherte Passwort in der Mail-App und auf mobilen Geräten."]),
    ("de", "drucker"): ("Drucker wird offline angezeigt", [
        "Prüfen Sie, ob der Drucker eingeschaltet ist und im Display eine Netzwerkverbindung anzeigt.",
        "Öffnen Sie auf dem Rechner Drucker & Scanner, entfernen Sie den Drucker und fügen Sie ihn neu hinzu.",
        "Stellen Sie sicher, dass Sie im Firmennetz oder über das VPN verbunden sind, nicht im Gastnetz.",
        "Starten Sie den Druckerspooler-Dienst neu und senden Sie den Auftrag erneut.",
        "Installieren Sie den neuesten Treiber aus dem Softwarecenter; Treiberversion 7.1 behebt den Offline-Status.",
        "Löschen Sie hängende Aufträge aus der Druckwarteschlange, bevor Sie eine Testseite drucken.",
        "Besteht das Problem weiter, nennen Sie uns den Druckernamen vom Etikett in einem neuen Ticket."]),
    ("de", "email"): ("E-Mail wird nicht synchronisiert", [
        "Prüfen Sie, ob das Telefon eine funktionierende Internetverbindung hat und der Flugmodus aus ist.",
        "Öffnen Sie die Einstellungen der Mail-App und prüfen Sie, ob das Konto ohne Warnung angemeldet ist.",
        "Entfernen Sie das Firmenkonto vom Telefon und fügen Sie es mit Ihrer Firmenadresse neu hinzu.",
        "Stellen Sie den Synchronisierungszeitraum auf 'Alle' oder mindestens 30 Tage.",
        "Installieren Sie die neueste Version der Mail-App aus dem App Store und starten Sie das Telefon neu.",
        "Haben Sie kürzlich Ihr Passwort geändert, geben Sie das neue Passwort ein, wenn die App danach fragt.",
        "Prüfen Sie den Speicher; die App synchronisiert nicht mehr, wenn weniger als 500 MB frei sind."]),
    ("de", "software"): ("Software lässt sich nicht installieren", [
        "Öffnen Sie das Softwarecenter und prüfen Sie, ob das Programm dort als verfügbar aufgelistet ist.",
        "Starten Sie das Softwarecenter als Administrator über das Kontextmenü neu und versuchen Sie es erneut.",
        "Stellen Sie sicher, dass mindestens 5 GB freier Speicherplatz auf dem Laufwerk C vorhanden sind.",
        "Schließen Sie alle geöffneten Programme und starten Sie die Installation noch einmal.",
        "Starten Sie den Rechner neu, wenn die Installation mit dem Fehlercode 1603 abbricht.",
        "Löschen Sie temporäre Dateien über die Datenträgerbereinigung und wiederholen Sie die Installation.",
        "Besteht der Fehler weiter, senden Sie uns den Fehlercode und den Namen des Programms."]),
}

# 5 relevant-ish cases per topic: three of the topic with decreasing length, two from other topics.
OTHERS = {"en": ["printer", "wifi", "email", "vpn"], "de": ["drucker", "email", "software", "vpn"]}


def case_pool(lang: str, topic: str, start_id: int) -> list[dict]:
    subject, steps = TOPICS[(lang, topic)]
    intro = "Thanks for reporting this. " if lang == "en" else "Danke für Ihre Meldung. "
    outro = " Please let us know if this solved it." if lang == "en" else " Bitte melden Sie sich, wenn das geholfen hat."
    detail = "\n\n" + ("Detailed steps:" if lang == "en" else "Schritte im Detail:") + "\n"
    numbered = lambda st: detail + "\n".join(f"{i}) {x}" for i, x in enumerate(st, 1))
    # Real resolutions are often long: top case ~1500 chars, second ~800, the rest short.
    answers = [intro + " ".join(steps) + numbered(steps) + outro,
               intro + " ".join(steps[1:6]) + numbered(steps[1:4]) + outro,
               intro + " ".join(steps[2:5]) + outro]
    subjects = [subject, subject + " (laptop)", subject + " (home office)"] if lang == "en" else \
        [subject, subject + " (Laptop)", subject + " (Homeoffice)"]
    for other in [o for o in OTHERS[lang] if o != topic][:2]:
        o_subject, o_steps = TOPICS[(lang, other)]
        answers.append(intro + " ".join(o_steps[:3]) + outro)
        subjects.append(o_subject)
    return [{"ticket_id": f"TKT-{start_id + i:05d}", "score": round(0.92 - i * 0.04, 2), "subject": subjects[i],
             "language": lang, "answer_snippet": answers[i]} for i in range(5)]


# ---------------------------------------------------------------- the 15 tickets

def tickets() -> list[dict]:
    t = [
        ("normal", "en", "vpn", "VPN disconnects", "Since this morning my VPN drops every 5 minutes on my laptop. I work from home on Wi-Fi. Thanks, Anna Meier (anna.meier@example.com)"),
        ("normal", "en", "password", "Locked out", "I cannot log in anymore, it says my account is locked. I changed my password yesterday. Can you help me get back in? Phone: +49 170 1234567"),
        ("normal", "en", "printer", "", "The printer on the 3rd floor shows offline for everybody in our team since the update. We tried printing several times."),
        ("normal", "en", "email", "Mail on iPhone", "My work email stopped syncing on my iPhone two days ago. New messages only show up when I open the web version."),
        ("normal", "en", "wifi", "Wi-Fi drops in meeting room", "In meeting room B the Wi-Fi disconnects every few minutes during video calls. Other rooms are fine."),
        ("normal", "de", "vpn", "VPN bricht ab", "Seit heute Morgen bricht mein VPN alle paar Minuten ab, besonders im WLAN zuhause. Ich arbeite im Homeoffice. Viele Grüße, Jonas Weber (jonas.weber@example.de)"),
        ("normal", "de", "passwort", "Konto gesperrt", "Ich kann mich nicht mehr anmelden, mein Konto ist laut Meldung gesperrt. Ich habe gestern mein Passwort geändert. Können Sie mir helfen?"),
        ("normal", "de", "drucker", "", "Der Drucker im dritten Stock wird seit dem Update für das ganze Team als offline angezeigt. Wir haben mehrfach versucht zu drucken."),
        ("normal", "de", "email", "Mail auf dem Handy", "Meine Firmen-E-Mail wird seit zwei Tagen auf meinem Handy nicht mehr synchronisiert. Neue Nachrichten sehe ich nur im Browser."),
        ("normal", "de", "software", "Installation schlägt fehl", "Ich möchte das Konstruktionsprogramm über das Softwarecenter installieren, aber die Installation bricht mit einem Fehler ab."),
    ]
    out = [{"group": g, "lang": l, "topic": tp, "subject": s, "body": b} for g, l, tp, s, b in t]
    adv = [json.loads(x) for x in (ROOT / "tests" / "adversarial.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    adv_map = {"adv-01": ("en", "invoice"), "adv-02": ("de", "vpn"), "adv-03": ("en", "invoice"),
               "adv-04": ("en", "password"), "adv-05": ("en", "printer")}
    for a in adv:
        lang, topic = adv_map[a["id"]]
        lang_of_text = "de" if a["id"] == "adv-02" else "en"
        out.append({"group": "adversarial", "id": a["id"], "lang": lang_of_text, "topic": topic,
                    "subject": a["subject"] or "", "body": a["body"]})
    for i, tk in enumerate(out):
        tk["text"] = (tk["subject"] or "").strip() + "\n" + tk["body"].strip()
        tk["hits"] = case_pool(tk["lang"], tk["topic"], 100 + i * 10)
        tk["name"] = tk.get("id") or f"{tk['lang']}-{tk['topic']}"
    return out


# ---------------------------------------------------------------- run + summarise

def pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def run(configs: dict, tks: list[dict], repeat: int = 1) -> list[dict]:
    for model in sorted({c["model"] for c in configs.values()}):
        print(f"warm-up {model}: {draft.warmup(model)}", flush=True)
    rows = []
    for i, tk in enumerate(tks * repeat, 1):
        for name, cfg in configs.items():
            t0 = time.perf_counter()
            out = draft.generate(tk["text"], tk["lang"], tk["hits"], model=cfg["model"], opts=cfg["opts"])
            ms = (time.perf_counter() - t0) * 1000
            post = gate.post(out, tk["hits"], tk["lang"])
            pre = gate.pre({"type": {"label": "Incident", "prob": 0.8}, "queue": {"label": "IT", "prob": 0.8},
                            "priority": {"label": "medium", "prob": 0.7}, "high_incident_prob": 0.1,
                            "severity_flags": []}, tk["hits"], tk["text"], tk["lang"])
            rows.append({
                "config": name, "ticket": tk["name"], "group": tk["group"], "lang": tk["lang"], "ms": round(ms),
                "pass": post["status"] == gate.AUTO, "post_codes": [r["code"] for r in post["reasons"]],
                "post_reasons": [gate.reason_text(r) for r in post["reasons"]], "pre_codes": [r["code"] for r in pre["reasons"]],
                "error": out.get("error"), "stop": out.get("stop_reason"),
                "words": len((out.get("reply") or "").split()), "reply": out.get("reply"),
                "cited": out.get("cited_ids"), "not_found": out.get("not_found"),
            })
        print(f"  ticket {i}/{len(tks) * repeat} done ({tk['name']})", flush=True)
    return rows


def summarise(rows: list[dict], configs: dict) -> list[dict]:
    table = []
    for name in configs:
        r = [x for x in rows if x["config"] == name]
        ms = [x["ms"] for x in r]
        codes = lambda c: sum(1 for x in r if c in x["post_codes"])
        normal = [x for x in r if x["group"] != "adversarial"]
        table.append({
            "config": name, "n": len(r), "p50_ms": round(pct(ms, .5)), "p95_ms": round(pct(ms, .95)),
            "mean_ms": round(statistics.mean(ms)), "max_ms": max(ms),
            "pass_all": f"{sum(x['pass'] for x in r)}/{len(r)}",
            "pass_normal": f"{sum(x['pass'] for x in normal)}/{len(normal)}",
            "bad_citation": codes("BAD_CITATION"), "lang_mismatch": codes("LANG_MISMATCH"),
            "unsupported_number": codes("UNSUPPORTED_NUMBER"), "not_found": codes("NOT_FOUND"),
            "errors": sum(1 for x in r if x["error"]),
            "max_tokens_hits": sum(1 for x in r if x["stop"] == "max_tokens"),
            "avg_words": round(statistics.mean(x["words"] for x in r if x["words"]) or 0) if any(x["words"] for x in r) else 0,
        })
    return table


def print_table(table: list[dict]) -> None:
    cols = ["config", "p50_ms", "p95_ms", "mean_ms", "max_ms", "pass_all", "pass_normal", "bad_citation",
            "lang_mismatch", "unsupported_number", "not_found", "errors", "max_tokens_hits", "avg_words"]
    widths = [max(len(c), *(len(str(t[c])) for t in table)) for c in cols]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for t in table:
        print("  ".join(str(t[c]).ljust(w) for c, w in zip(cols, widths)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="run only these config names")
    ap.add_argument("--extra", help='JSON: {"name": {"model": "...", "opts": {...}}}')
    ap.add_argument("--no-builtin", action="store_true", help="skip the built-in configs (use with --extra)")
    ap.add_argument("--repeat", type=int, default=1, help="run the 15 tickets this many times (more samples for p95)")
    ap.add_argument("--out", default="bench_draft.json")
    args = ap.parse_args()

    configs = {} if args.no_builtin else {k: v for k, v in CONFIGS.items() if not args.only or k in args.only}
    if args.extra:
        configs.update(json.loads(args.extra))
    tks = tickets()
    print(f"{len(tks)} tickets x {args.repeat} x {len(configs)} configs = {len(tks) * args.repeat * len(configs)} calls", flush=True)
    rows = run(configs, tks, args.repeat)
    table = summarise(rows, configs)

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.RESULTS_DIR / args.out
    out.write_text(json.dumps({"configs": configs, "table": table, "rows": rows}, ensure_ascii=False, indent=1))
    print()
    print_table(table)
    print(f"\nraw rows: {out}")


if __name__ == "__main__":
    main()
