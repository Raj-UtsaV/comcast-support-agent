"""Training-only majority/keyword baselines and TF-IDF evidence retrieval."""

import re
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer


class Baselines:
    def __init__(self, config, records, training_labels):
        self.config, self.records = config, records
        counts = Counter(row["intent"] for row in training_labels)

        if not counts:
            raise ValueError(
                "The majority baseline requires human-labelled training examples."
            )

        self.majority = min(counts, key=lambda label: (-counts[label], label))
        self.vectorizer, self.matrix = None, None

        if records:
            self.vectorizer = TfidfVectorizer()
            self.matrix = self.vectorizer.fit_transform(
                [row["customer_text"] for row in records]
            )

    def analyse(self, method, message):
        matches = []
        intent = self.majority
        reply = self.config["evaluation"]["baseline_generic_reply"]

        if method == "simple":
            scores = {
                label: sum(bool(re.search(pattern, message)) for pattern in patterns)
                for label, patterns in self.config["intents"]["keyword_rules"].items()
            }
            best = max(scores.values(), default=0)
            winners = [
                label for label, score in scores.items() if score == best and best > 0
            ]
            intent = winners[0] if len(winners) == 1 else None

            if self.matrix is not None:
                similarities = (
                    (self.matrix @ self.vectorizer.transform([message]).T)
                    .toarray()
                    .ravel()
                )
                order = sorted(
                    range(len(similarities)),
                    key=lambda i: (-similarities[i], self.records[i]["evidence_id"]),
                )
                seen = set()

                for i in order:
                    if similarities[i] < self.config["retrieval"]["min_similarity"]:
                        break
                    row = self.records[i]
                    if row["conversation_id"] in seen:
                        continue
                    seen.add(row["conversation_id"])
                    matches.append(
                        {"evidence": row, "similarity": float(similarities[i])}
                    )
                    if len(matches) == self.config["retrieval"]["top_k"]:
                        break

                if matches:
                    reply = matches[0]["evidence"]["reply_text"]
        elif method != "trivial":
            raise ValueError("Unknown baseline")

        return {
            "company_id": self.config["company"]["id"],
            "intent": intent,
            "draft_reply": reply,
            "decision": "escalate",
            "decision_reason": "Baseline draft requires human review.",
            "evidence_ids": [matches[0]["evidence"]["evidence_id"]] if matches else [],
            "retrieved_examples": matches,
            "safety_flags": [],
            "reply_status": "baseline",
        }
