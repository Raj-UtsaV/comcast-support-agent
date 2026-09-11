"""Read company evaluation artifacts and render evaluation/failure views."""

import json
from pathlib import Path

import streamlit as st

from support_agent.ui.style import empty_state


def load_report(config):
    root = Path(config["paths"]["results_dir"]).resolve()
    pointer = root / "latest.json"
    if not pointer.exists():
        return None, []
    name = json.loads(pointer.read_text())["run"]
    folder = (root / name).resolve()
    if folder.parent != root:
        raise ValueError("Evaluation path is outside this company's results directory.")
    report = json.loads((folder / "report.json").read_text())
    rows = json.loads((folder / "predictions.json").read_text())
    if report["company_id"] != config["company"]["id"] or any(
        row["company_id"] != config["company"]["id"] for row in rows
    ):
        raise ValueError("Evaluation results belong to another company.")
    return report, rows


def evaluation_view(report):
    st.subheader("Measure the quality of your support")
    st.caption("Compare methods, review coverage, and inspect human-rated results.")
    if report is None:
        with st.container(border=True):
            empty_state(
                "Your results belong here",
                "No real evaluation has been run. Complete the human review sheets and run evaluation to see measured results.",
                "◎",
            )
        return
    st.write("Evaluation status:", report["status"])
    fields = [
        "intent_accuracy",
        "intent_macro_f1",
        "auto_handle_coverage",
        "false_auto_handle_rate",
        "safe_auto_handle_coverage",
        "fallback_rate",
    ]
    st.dataframe(
        [
            {"method": method, **{key: scores.get(key) for key in fields}}
            for method, scores in report["methods"].items()
        ],
        hide_index=True,
    )
    for method, scores in report["methods"].items():
        with st.expander(f"{method}: all metrics and per-category results"):
            st.json(scores)
    st.write("Human / judge agreement")
    if report["human_agreement"] is None:
        st.info("Independent human ratings have not been imported.")
    else:
        st.json(report["human_agreement"])


def failure_view(rows, config):
    st.subheader("Find opportunities to improve")
    st.caption("Inspect category errors, retrieval gaps, and drafts that need attention.")
    if not rows:
        with st.container(border=True):
            empty_state(
                "Turn evaluation into insight",
                "Run evaluation to inspect requests that need attention. This view will show observed failures from your saved results.",
                "⌕",
            )
        return
    failures = []
    for row in rows:
        result = row["result"]
        reasons = []
        if result["intent"] != row["expected_intent"]:
            reasons.append("incorrect category")
        found = {
            item["evidence"]["evidence_id"] for item in result["retrieved_examples"]
        }
        if row["relevant_evidence_ids"] and not found.intersection(
            row["relevant_evidence_ids"]
        ):
            reasons.append("poor retrieval")
        if set(result["safety_flags"]) & {"unsupported_claim", "verification_failed"}:
            reasons.append("blocked or unverified draft")
        if (
            row.get("judge")
            and row["judge"]["scores"].get("safety", 0)
            < config["evaluation"]["safety_pass_score"]
        ):
            reasons.append("low judge safety score")
        if (
            row["method"] == "agent"
            and result["intent_confidence"] < config["safety"]["min_intent_confidence"]
        ):
            reasons.append("low confidence")
        if reasons:
            failures.append(
                {
                    "method": row["method"],
                    "message_id": row["message_id"],
                    "message": row["message"],
                    "expected": row["expected_intent"],
                    "predicted": result["intent"],
                    "reasons": "; ".join(reasons),
                }
            )
    st.dataframe(failures, hide_index=True)
