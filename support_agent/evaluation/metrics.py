"""Transparent metrics with explicit denominators and unavailable values."""

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    cohen_kappa_score,
    f1_score,
    precision_recall_fscore_support,
)


def summarize(rows, labels, retrieval_k):
    expected = [row["expected_intent"] for row in rows]
    predicted = [row["result"]["intent"] or "__unknown__" for row in rows]
    truth = [row["expected_escalation"] for row in rows]
    decisions = [row["result"]["decision"] == "escalate" for row in rows]
    precision, recall, f1, _ = precision_recall_fscore_support(
        truth, decisions, average="binary", zero_division=0
    )
    auto = [row for row in rows if row["result"]["decision"] == "auto_handle"]
    relevant = [row for row in rows if row["relevant_evidence_ids"]]
    report = {
        "examples": len(rows),
        "intent_accuracy": accuracy_score(expected, predicted),
        "intent_macro_f1": f1_score(
            expected, predicted, labels=labels, average="macro", zero_division=0
        ),
        "per_intent": classification_report(
            expected, predicted, labels=labels, output_dict=True, zero_division=0
        ),
        "escalation_precision": float(precision),
        "escalation_recall": float(recall),
        "escalation_f1": float(f1),
        "auto_handle_coverage": len(auto) / len(rows),
        "false_auto_handle_rate": sum(row["expected_escalation"] for row in auto)
        / len(auto)
        if auto
        else None,
        "false_auto_handle_denominator": len(auto),
        "safe_auto_handle_coverage": None,
        "safe_coverage_note": "Requires matched independent human reply-safety ratings; intent/escalation labels alone do not prove reply safety.",
        "fallback_rate": sum(
            row["result"]["reply_status"] == "safe_fallback" for row in rows
        )
        / len(rows),
        "retrieval_labelled_examples": len(relevant),
    }

    for k in retrieval_k:
        scores = []
        for row in relevant:
            found = {
                item["evidence"]["evidence_id"]
                for item in row["result"]["retrieved_examples"][:k]
            }
            gold = set(row["relevant_evidence_ids"])
            scores.append(len(found & gold) / len(gold))
        report[f"retrieval_recall_at_{k}"] = float(np.mean(scores)) if scores else None

    judged = [row["judge"]["scores"] for row in rows if row.get("judge")]
    report["judge_mean_scores"] = (
        {name: float(np.mean([item[name] for item in judged])) for name in judged[0]}
        if judged
        else None
    )
    return report


def human_agreement(rows, ratings, dimensions, score_min, score_max):
    by_key = {(row["method"], row["message_id"]): row for row in rows}
    pairs = {name: [] for name in dimensions}
    seen = set()
    safety = {}

    for rating in ratings:
        key = (rating["method"], rating["message_id"])
        dimension = rating["dimension"]

        if key not in by_key or dimension not in pairs or (*key, dimension) in seen:
            raise ValueError(
                "Human ratings contain an unknown or duplicate result/dimension."
            )

        value = int(rating["score"])

        if not score_min <= value <= score_max:
            raise ValueError("Human score is outside configured bounds.")

        seen.add((*key, dimension))
        if dimension == "safety":
            safety[key] = value
        if by_key[key].get("judge"):
            pairs[dimension].append((value, by_key[key]["judge"]["scores"][dimension]))

    agreement = {}
    for dimension, values in pairs.items():
        if not values:
            agreement[dimension] = {
                "matched_ratings": 0,
                "exact_agreement": None,
                "cohen_kappa": None,
                "spearman": None,
            }
            continue
        human, judge = zip(*values, strict=True)
        kappa = cohen_kappa_score(human, judge) if len({*human, *judge}) > 1 else None
        rank = (
            spearmanr(human, judge).statistic
            if len(set(human)) > 1 and len(set(judge)) > 1
            else None
        )
        agreement[dimension] = {
            "matched_ratings": len(values),
            "exact_agreement": sum(a == b for a, b in values) / len(values),
            "cohen_kappa": float(kappa)
            if kappa is not None and np.isfinite(kappa)
            else None,
            "spearman": float(rank) if rank is not None and np.isfinite(rank) else None,
        }

    return agreement, safety
