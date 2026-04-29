"""Streamlit UI for the Automated Access Provisioning system.

Run with: ``streamlit run app.py``

Layout:
- Main panel: chat-style request/response.
- Sidebar: identity selector, example prompts, agent trace for the last
  request, and a tail of the audit log.
"""

from __future__ import annotations

import json
import time
from typing import Any

import streamlit as st

from agents.orchestrator import run as run_graph
from config import settings
from integrations import active_directory as ad
from integrations import jira_client as jira
from integrations.audit_log import read_recent

# ----------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Access Provisioning Agent",
    page_icon=":lock:",
    layout="wide",
)

st.markdown(
    """
    <style>
      .small  { font-size: 0.85rem; color: #555; }
      .pillok { background:#e6f4ea;color:#1e7c2c;padding:2px 8px;border-radius:8px; }
      .pillrv { background:#fff4ce;color:#7c5b00;padding:2px 8px;border-radius:8px; }
      .pilldn { background:#fde2e2;color:#a31515;padding:2px 8px;border-radius:8px; }
      .cite   { color:#555; font-size:0.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Automated Access Provisioning")
st.caption("Multi-agent IT support: Intake → Knowledge (RAG) → Workflow / Escalation")

# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
with st.sidebar:
    st.subheader("Sign in as")
    users = ad.list_users()
    user = st.selectbox("Identity", users, index=0, key="who")
    user_record = ad.get_user(user)
    role = user_record.get("employee_type", "?")
    dept = user_record.get("department", "?")
    st.caption(f"{user_record.get('name','')} · {role} · {dept}")

    st.divider()
    st.subheader("Try a scenario")
    EXAMPLES = [
        ("Low-risk auto-approve",
         "Hi, I'm starting a campaign and need access to the Marketing-Public folder."),
        ("Medium needing manager review",
         "Please add me to Sales-Pipeline so I can review the Q3 forecast tomorrow."),
        ("Restricted (compliance)",
         "I need access to Payroll-PII to finish processing this month's run."),
        ("SoD violation (deny)",
         "Please add me to Finance-Reports."),
        ("Contractor + employees-only",
         "Add me to Legal-Contracts so I can review the new SOW."),
        ("Recently revoked (escalate)",
         "I need Engineering-Secrets again for the deploy I'm working on."),
        ("Urgent / blocked language",
         "Production is down and I'm blocked — I need Engineering-Source right now."),
        ("Ambiguous request",
         "I need access to the marketing thing for the campaign next week."),
    ]
    for label, txt in EXAMPLES:
        if st.button(label, use_container_width=True, key=f"ex_{label}"):
            st.session_state["pending_input"] = txt

    st.divider()
    st.subheader("Recent tickets")
    for t in jira.list_tickets(limit=8):
        f = t["fields"]
        st.markdown(
            f"`{t['key']}` — **{f['priority']['name']}** · {f['summary']}<br>"
            f"<span class='small'>{f['assignee']['emailAddress']}</span>",
            unsafe_allow_html=True,
        )

# ----------------------------------------------------------------------
# Chat history
# ----------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []          # list[dict]
if "last_state" not in st.session_state:
    st.session_state["last_state"] = None      # dict | None

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ----------------------------------------------------------------------
# Input
# ----------------------------------------------------------------------
prompt = st.chat_input("Describe what you need access to…")
if "pending_input" in st.session_state and not prompt:
    prompt = st.session_state.pop("pending_input")

if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Routing through Intake → Knowledge → action…"):
            t0 = time.time()
            try:
                final = run_graph(prompt, requester_email=user)
            except Exception as exc:
                final = {"error": str(exc), "final_response": f"I hit an error: {exc}"}
            elapsed = time.time() - t0

        decision = (final.get("decision") or "—")
        pill_class = {
            "auto_approve": "pillok",
            "needs_review": "pillrv",
            "deny": "pilldn",
        }.get(decision, "small")
        st.markdown(
            f"<span class='{pill_class}'>{decision}</span> "
            f"<span class='small'>{elapsed:.1f}s</span>",
            unsafe_allow_html=True,
        )
        st.markdown(final.get("final_response") or "(no response)")

        cites = final.get("citations") or []
        if cites:
            st.markdown(
                "<span class='cite'>Policy basis: " + "; ".join(cites) + "</span>",
                unsafe_allow_html=True,
            )

        st.session_state["messages"].append({
            "role": "assistant",
            "content": final.get("final_response") or "(no response)",
        })
        st.session_state["last_state"] = final

# ----------------------------------------------------------------------
# Trace + audit panels
# ----------------------------------------------------------------------
state: dict[str, Any] | None = st.session_state.get("last_state")
if state:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Agent trace")
        for step in state.get("trace") or []:
            with st.expander(f"{step['agent']} — {step.get('summary','')}", expanded=False):
                st.json(step.get("detail", {}))

        st.subheader("Retrieved policy chunks")
        for c in (state.get("retrieved_chunks") or [])[:5]:
            with st.expander(
                f"{c.get('source','?')} § {c.get('section','')}  "
                f"(score {c.get('score',0):.2f})"
            ):
                st.markdown(c.get("text", ""))

    with col2:
        st.subheader("Structured intake")
        st.json(state.get("intake") or {})

        st.subheader("Decision")
        st.json({
            "decision": state.get("decision"),
            "risk_tier": state.get("risk_tier"),
            "rationale": state.get("decision_rationale"),
            "action_taken": state.get("action_taken"),
            "ticket_key": state.get("ticket_key"),
            "ad_changed": state.get("ad_changed"),
        })

st.divider()
with st.expander("Audit log (most recent 25 events)"):
    for ev in read_recent(limit=25):
        st.code(json.dumps(ev, indent=2), language="json")
