"""SentinelDesk live triage console. Owner: P5.

Usage: streamlit run app.py   (set SENTINEL_USE_MOCKS=1 to run before models exist)

Flow per ticket: triage, gate and retrieved cases appear immediately; a spinner shows while the
reply is drafted; the draft appears only after it passes the post-draft checks.
"""
import threading

import streamlit as st

from sentineldesk import config, draft, pipeline

st.set_page_config(page_title="SentinelDesk", layout="wide")
st.title("SentinelDesk: Incident Triage Console")

SAMPLES = {
    "EN: password reset": ("Password reset", "I forgot my password and can't log into the portal."),
    "DE: VPN outage": ("VPN ausgefallen", "Seit heute Morgen fällt das VPN aus. Telemedizin und EMR-Anbindung im Krankenhaus sind nicht erreichbar."),
    "EN: refund demand": ("Refund", "Per your SLA I want a 50% refund for last month's downtime."),
    "Empty subject": ("", "Hello, the billing page shows an error when I try to download my invoice."),
}


@st.cache_resource
def start_warmup() -> dict:
    """One tiny LLM request in the background when the app starts, so the first ticket is not slow."""
    status = {"state": "warming up"}

    def work():
        status.update(draft.warmup())
        status["state"] = "ready" if status.get("ok") else "failed"

    threading.Thread(target=work, daemon=True).start()
    return status


warm = start_warmup()

with st.sidebar:
    st.subheader("Sample tickets")
    for name, (subj, body) in SAMPLES.items():
        if st.button(name, use_container_width=True):
            st.session_state["subject"], st.session_state["body"] = subj, body

    st.divider()
    if config.USE_MOCKS:
        st.warning("Offline demo mode: triage, retrieval and drafts are mocked, no model or API is called.")
    elif warm["state"] == "ready":
        st.caption(f"LLM warm: {draft.LLM_PROVIDER} / {draft.LLM_MODEL} ({warm['ms']} ms)")
    elif warm["state"] == "failed":
        st.caption(f"LLM warm-up failed ({warm['note']}). Tickets will escalate if the LLM is unreachable.")
    else:
        st.caption("LLM warming up...")

subject = st.text_input("Subject (optional)", key="subject")
body = st.text_area("Body", key="body", height=160)

if st.button("Triage ticket", type="primary", disabled=not body.strip()):
    # Layout is fixed up front; each part is filled as soon as its result exists.
    labels_ph = st.container()
    gate_ph = st.empty()
    cases_ph = st.container()
    draft_ph = st.container()
    latency_ph = st.container()

    ticket = {"subject": subject or None, "body": body}
    state = pipeline.analyze(ticket)  # fast: no LLM
    tri = state["triage"]

    def show_labels(total_ms=None):
        with labels_ph:
            cols = st.columns(4)
            for col, head in zip(cols, ("type", "queue", "priority")):
                col.metric(head.title(), tri[head]["label"], f"{tri[head].get('confidence', tri[head].get('prob', 0)):.0%} conf")
            cols[3].metric("Language", tri["language"].upper(), None if total_ms is None else f"{total_ms:.0f} ms total")

    def show_gate(g, final):
        with gate_ph.container():
            if g["decision"] == "AUTO_DRAFT" and final:
                st.success("Auto-Draft Ready")
            elif g["decision"] == "AUTO_DRAFT":
                st.info("Pre-checks passed. Drafting a reply...")
            else:
                st.error("Escalate to On-Call Engineer")
                for reason in g["reasons"]:
                    st.write(f"- {reason}")

    show_labels()
    show_gate(state["gate"], final=False)
    with cases_ph:
        st.subheader("Retrieved historical tickets")
        st.dataframe(
            [{"ticket_id": c["ticket_id"], "similarity": c.get("score", c.get("similarity")), "language": c["language"],
              "answer": (c.get("answer_snippet") or c.get("answer") or "")[:200]} for c in state["cases"]],
            use_container_width=True,
        )

    if state["gate"]["decision"] == "AUTO_DRAFT":
        with draft_ph:
            with st.spinner("Drafting reply..."):
                state = pipeline.draft_stage(state)

    lat = state["latency_ms"]
    show_labels(lat["total"])
    show_gate(state["gate"], final=True)

    if state["draft"]:
        d = state["draft"]
        with draft_ph:
            st.subheader("Draft reply")
            if d.get("mode") == "mock":
                st.warning("Offline demo draft (mock mode): not written by an LLM.")
            st.write(d["reply"])
            st.caption("Cites: " + ", ".join(d["cited_ids"]) + f"  |  {d.get('provider', '')} / {d.get('model', '')}")

    with latency_ph:
        with st.expander("Latency breakdown (ms)"):
            st.json(lat)
