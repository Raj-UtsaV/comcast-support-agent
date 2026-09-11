"""Customer conversation view using the existing configured support workflow."""

import argparse
import hashlib
import json
from html import escape

import streamlit as st

from support_agent.agent.runtime import create_agent
from support_agent.retrieval.index_state import source_state, storage_directory
from support_agent.shared.config import load_config
from support_agent.shared.schemas import HistoryMessage, SupportRequest
from support_agent.ui.troubleshooting import basic_guidance, is_handoff


@st.cache_resource
def customer_runtime(config_json, revision):
    return create_agent(json.loads(config_json))


def answer(config, messages, text):
    limit = config["runtime"]["max_history_messages"]
    history = [item for item in messages if item.get("context", True)]
    history = history[-limit:] if limit else []
    request = SupportRequest(
        company_id=config["company"]["id"],
        message=text,
        conversation_history=[
            HistoryMessage(role=item["role"], text=item["text"]) for item in history
        ],
    )
    revision = "synthetic-demo"
    if not config["runtime"]["demo_mode"]:
        revision = json.dumps(source_state(config), sort_keys=True) + (
            storage_directory(config) / "current.json"
        ).read_text()
    result = customer_runtime(json.dumps(config, sort_keys=True), revision).analyse(request)
    if (
        result.decision == "escalate"
        or result.reply_status == "safe_fallback"
        or is_handoff(result.draft_reply)
    ):
        hard_flags = {
            "risky_intent", "account_security", "account_access_or_action",
            "billing_refund_cancellation", "sensitive_information",
            "repeated_unresolved_problem",
        }
        guidance = None
        if not hard_flags.intersection(getattr(result, "safety_flags", [])):
            guidance = basic_guidance(config, messages, text)
        if guidance:
            return guidance
    if result.decision == "escalate" or result.reply_status == "safe_fallback":
        return (
            "This request needs a human support representative. Please contact your "
            "provider through your usual support channel for help. "
            "This chat cannot transfer you or make changes to your account."
        )
    return result.draft_reply


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/comcast.yaml")
    args, _ = parser.parse_known_args()
    st.set_page_config(page_title="Support · Let's talk", page_icon="✦", layout="centered")
    st.markdown(
        """<style>
        .stApp { background: #f5f8fa; }
        .block-container { max-width: 960px; padding-top: 2.5rem; }
        .customer-nav { display: flex; justify-content: space-between; gap: 16px;
          align-items: center; padding-bottom: 24px; border-bottom: 1px solid #dde6eb; }
        .customer-brand { font-size: 20px; font-weight: 750; color: #173a49; }
        .customer-badge { font-size: 12px; color: #497080; border: 1px solid #d0dfe6;
          border-radius: 30px; padding: 6px 12px; }
        .customer-hero { text-align: center; padding: 38px 16px 24px; }
        .customer-symbol { background: #dcf3ea; color: #087f8c; border-radius: 22px;
          display: grid; place-items: center; width: 70px; height: 70px;
          margin: 0 auto 20px; font-size: 32px; }
        .customer-hero h1 { color: #173a49; font-size: clamp(30px, 5vw, 46px);
          letter-spacing: -1.8px; padding: 0; margin: 0 0 14px; }
        .customer-hero p { color: #647986; line-height: 1.8; max-width: 520px; margin: auto; }
        .stButton button { border-radius: 14px; min-height: 46px; font-weight: 600; }
        [data-testid="stChatMessage"] { border: 1px solid #e0e9ed; border-radius: 18px;
          background: white; padding: 20px; margin-bottom: 12px; }
        [data-testid="stChatMessage"] p { line-height: 1.8; }
        [data-testid="stChatInput"] { border-radius: 18px; }
        .customer-note { color: #647986; font-size: 12px; text-align: center;
          line-height: 1.7; margin: 22px 0; }
        @media (max-width: 600px) {
          .block-container { padding: 1.5rem 1rem; }
          .customer-nav { flex-wrap: wrap; }
          .customer-hero { padding-top: 24px; }
        }
        </style>""",
        unsafe_allow_html=True,
    )
    try:
        config = load_config(args.config)
    except (ValueError, OSError):
        st.error("Support chat is temporarily unavailable. Please try again later.")
        return

    company = escape(config["company"]["display_name"])
    st.markdown(
        f'<div class="customer-nav"><span class="customer-brand">✦ {company} · Help</span>'
        '<span class="customer-badge">AI support assistant</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Independent support demonstration · No account access")
    if config["runtime"]["demo_mode"]:
        st.info("Demo conversation: replies are scripted examples.")

    scope = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if st.session_state.get("customer_scope") != scope:
        st.session_state["customer_messages"] = []
        st.session_state["customer_scope"] = scope
    messages = st.session_state["customer_messages"]

    if messages:
        heading, action = st.columns([3, 1])
        heading.subheader("Your conversation")
        if action.button("New conversation", use_container_width=True):
            st.session_state["customer_messages"] = []
            st.rerun()
    else:
        st.markdown(
            '<div class="customer-hero"><div class="customer-symbol">✦</div>'
            '<h1>A little help goes a long way.</h1>'
            '<p>Tell us what’s happening. We’ll help you explore the next steps, '
            'one message at a time.</p></div>',
            unsafe_allow_html=True,
        )

    prompt = None
    if not messages:
        topics = [
            ("Internet connection", "My internet connection stopped working. What can I try?"),
            ("A billing question", "I have an unexpected charge on my bill."),
            ("TV & channels", "Some of my TV channels are not working."),
        ]
        for column, (label, text) in zip(st.columns(3), topics, strict=True):
            if column.button(label, use_container_width=True):
                prompt = text
        st.markdown(
            '<div class="customer-note">Choose a topic above or describe your issue below.<br>'
            'Please leave out passwords, verification codes, and account numbers.</div>',
            unsafe_allow_html=True,
        )

    for item in messages:
        role = "user" if item["role"] == "customer" else "assistant"
        with st.chat_message(role):
            st.text(item["text"])

    typed = st.chat_input(
        "How can we help you today?",
        max_chars=config["runtime"]["max_message_characters"],
    )
    prompt = typed or prompt
    if prompt and prompt.strip():
        # Bound visible and retained history as well as the model request.
        with st.spinner("Thinking about your question…"):
            try:
                reply = answer(config, messages, prompt)
                context = True
            except (ValueError, OSError, RuntimeError, TypeError):
                reply = (
                    "Sorry, I couldn’t process your message right now. Please try again "
                    "later or contact your provider through your usual support channel."
                )
                context = False
        messages.extend([
            {"role": "customer", "text": prompt, "context": True},
            {"role": "agent", "text": reply, "context": context},
        ])
        st.session_state["customer_messages"] = messages[-100:]
        st.rerun()
