"""SentinelDesk live triage console. Owner: P5.

Usage: streamlit run app.py   (set SENTINEL_USE_MOCKS=1 to run before models exist)
"""
import streamlit as st

from sentineldesk import pipeline

st.set_page_config(page_title="SentinelDesk", layout="wide")
st.title("SentinelDesk: Incident Triage Console")

SAMPLES = {
    "EN: password reset": ("Password reset", "I forgot my password and can't log into the portal."),
    "DE: VPN outage": ("VPN ausgefallen", "Seit heute Morgen fällt das VPN aus. Telemedizin und EMR-Anbindung im Krankenhaus sind nicht erreichbar."),
    "EN: refund demand": ("Refund", "Per your SLA I want a 50% refund for last month's downtime."),
    "Empty subject": ("", "Hello, the billing page shows an error when I try to download my invoice."),
}

with st.sidebar:
    st.subheader("Sample tickets")
    for name, (subj, body) in SAMPLES.items():
        if st.button(name, use_container_width=True):
            st.session_state["subject"], st.session_state["body"] = subj, body

subject = st.text_input("Subject (optional)", key="subject")
body = st.text_area("Body", key="body", height=160)

if st.button("Triage ticket", type="primary", disabled=not body.strip()):
    with st.spinner("Triaging..."):
        result = pipeline.run({"subject": subject or None, "body": body})

    tri, gate = result["triage"], result["gate"]
    cols = st.columns(4)
    for col, head in zip(cols, ("type", "queue", "priority")):
        col.metric(head.title(), tri[head]["label"], f"{tri[head]['confidence']:.0%} conf")
    cols[3].metric("Language", tri["language"].upper(), f"{result['latency_ms']['total']:.0f} ms total")

    if gate["decision"] == "AUTO_DRAFT":
        st.success("Auto-Draft Ready")
    else:
        st.error("Escalate to On-Call Engineer")
        for reason in gate["reasons"]:
            st.write(f"- {reason}")

    st.subheader("Retrieved historical tickets")
    st.dataframe(
        [{"ticket_id": c["ticket_id"], "similarity": c["similarity"], "language": c["language"],
          "answer": c["answer"][:200]} for c in result["cases"]],
        use_container_width=True,
    )

    if result["draft"]:
        st.subheader("Draft reply")
        st.write(result["draft"]["reply"])
        st.caption("Cites: " + ", ".join(result["draft"]["cited_ticket_ids"]))

    with st.expander("Latency breakdown (ms)"):
        st.json(result["latency_ms"])
