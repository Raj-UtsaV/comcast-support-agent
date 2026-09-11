"""Streamlit interface for the configurable customer-support demonstration."""

import hashlib
import json

import streamlit as st

from support_agent.agent.runtime import create_agent
from support_agent.retrieval.index_state import source_state, storage_directory
from support_agent.shared.config import PROJECT_ROOT, load_config
from support_agent.shared.schemas import HistoryMessage, SupportRequest
from support_agent.ui.dashboard import evaluation_view, failure_view, load_report
from support_agent.ui.style import apply_style, empty_state, hero, reply_card


@st.cache_resource
def resources(config_json, revision):
    return create_agent(json.loads(config_json))


def main():
    st.set_page_config(page_title="Support Studio", page_icon="✦", layout="wide")
    apply_style()
    st.sidebar.markdown(
        '<div class="brand"><div class="brand-mark">S</div><div>'
        '<div class="brand-name">Support Studio</div>'
        '<div class="brand-sub">Customer experience</div></div></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("WORKSPACE")
    paths = sorted(
        path
        for path in (PROJECT_ROOT / "configs").glob("*.yaml")
        if path.name != "base.yaml"
    )
    selected = st.sidebar.selectbox(
        "Company", paths, format_func=lambda path: path.stem
    )
    if st.sidebar.button("Refresh workspace", use_container_width=True):
        resources.clear()
    try:
        config = load_config(selected)
    except ValueError as error:
        st.error(str(error))
        return
    st.sidebar.divider()
    st.sidebar.markdown("**Your support workflow**")
    st.sidebar.caption("1. Add a customer message")
    st.sidebar.caption("2. Review the suggested reply")
    st.sidebar.caption("3. Check evidence and handling")
    st.sidebar.divider()
    st.sidebar.caption(
        "Replies stay here for review. Account actions are handled by your team."
    )
    hero(config["company"]["display_name"], config["runtime"]["demo_mode"])
    if config["runtime"]["demo_mode"]:
        st.warning(
            "SYNTHETIC DEMO — scripted category, evidence and verification. No real model predictions or measured performance."
        )
    else:
        st.caption(
            "Drafts for review. This app never sends replies or performs account actions."
        )
    support, evaluation, failures = st.tabs(
        ["Support Agent", "Evaluation", "Failure Analysis"]
    )
    with support:
        compose, response = st.columns([1, 1.15], gap="large")
        with compose, st.container(border=True, key="composer"):
            st.markdown(
                '<div class="section-label">New conversation</div>',
                unsafe_allow_html=True,
            )
            st.subheader("What can we help with?")
            st.caption("Choose an example or paste a customer message to get started.")
            examples = {
                item["label"]: item["message"] for item in config["ui"]["example_messages"]
            }
            example = st.selectbox("Example message", ["Write my own message", *examples])
            message = st.text_area(
                "Customer message",
                height=190,
                placeholder="e.g. My internet keeps disconnecting, even after restarting the router…",
                value=examples.get(example, ""),
                key=f"message-{selected.stem}-{example}",
            )
            with st.expander("Optional conversation history"):
                history_text = st.text_area(
                    "History JSON",
                    value="[]",
                    help='List of {"role": "customer" or "agent", "text": "..."}.',
                )
            request_key = hashlib.sha256(
                json.dumps([str(selected), message, history_text]).encode()
            ).hexdigest()
            if st.button("Analyse", type="primary", use_container_width=True):
                try:
                    history = [
                        HistoryMessage.model_validate(item)
                        for item in json.loads(history_text)
                    ]
                    request = SupportRequest(
                        company_id=config["company"]["id"],
                        message=message,
                        conversation_history=history,
                    )
                    revision = "synthetic-demo"
                    if not config["runtime"]["demo_mode"]:
                        # Cache invalidates when either source data or published version changes.
                        revision = (
                            json.dumps(source_state(config), sort_keys=True)
                            + (storage_directory(config) / "current.json").read_text()
                        )
                    with st.spinner("Analysing the request..."):
                        result = resources(
                            json.dumps(config, sort_keys=True), revision
                        ).analyse(request)
                    st.session_state["support_result"] = result.model_dump()
                    st.session_state["support_request_key"] = request_key
                except (ValueError, OSError, RuntimeError, TypeError) as error:
                    st.session_state.pop("support_result", None)
                    st.error(str(error))
                    st.info(
                        "For a run without credentials or reviewed categories, select the explicit demo configuration in the sidebar."
                    )
        with response, st.container(border=True, key="response"):
            st.markdown(
                '<div class="section-label">Reply workspace</div>',
                unsafe_allow_html=True,
            )
            result = st.session_state.get("support_result")
            if (
                result
                and result["company_id"] == config["company"]["id"]
                and st.session_state.get("support_request_key") == request_key
            ):
                left, right = st.columns(2)
                left.metric("Request category", result["intent"] or "Unknown")
                right.metric(
                    "Model confidence (uncalibrated)", f"{result['intent_confidence']:.2f}"
                )
                if result["decision"] == "escalate":
                    st.warning("Escalate to human support")
                else:
                    st.success("Auto-handle candidate — no message has been sent")
                st.write(result["decision_reason"])
                st.subheader("Suggested reply")
                reply_card(result["draft_reply"])
                st.download_button(
                    "Download reply",
                    result["draft_reply"],
                    file_name="support-reply.txt",
                    mime="text/plain",
                )
                if result["reply_status"] == "safe_fallback":
                    st.caption(
                        "A configured fallback replaced an unavailable or unverified draft."
                    )
                if result["safety_flags"]:
                    st.write("Safety signals:", ", ".join(result["safety_flags"]))
                with st.expander("Historical evidence — resolution unverified"):
                    for match in result["retrieved_examples"]:
                        evidence = match["evidence"]
                        st.write(
                            evidence["evidence_id"],
                            "Similarity:",
                            round(match["similarity"], 3),
                        )
                        st.write("Customer:", evidence["customer_text"])
                        st.write("Historical reply:", evidence["reply_text"])
            else:
                empty_state(
                    "A considered reply starts here",
                    "Add a customer message and select Analyse. Your suggested reply, handling decision, and supporting evidence will appear here.",
                )
                st.divider()
                st.caption(
                    "Every draft includes a handling decision. Historical evidence "
                    "does not guarantee a successful resolution."
                )
    try:
        report, rows = load_report(config)
        with evaluation:
            evaluation_view(report)
        with failures:
            failure_view(rows, config)
    except (ValueError, OSError, KeyError) as error:
        st.error(f"Cannot load this company's evaluation artifacts: {error}")

    st.markdown(
        '<div class="workspace-footer">Support Studio · Draft, review, then decide.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
