"""Explicitly scripted, synthetic demo clients; never a production fallback."""

from support_agent.shared.schemas import Classification, ReplyCheck, ReplyDraft


class DemoGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, task, payload, schema, instructions):
        if task == "classify":
            return Classification(
                intent=self.config["intents"]["approved_taxonomy"][0]["id"],
                confidence=self.config["demo"]["confidence"],
                reason="Scripted demo category",
            )

        if task == "draft":
            evidence = payload["evidence"][0]["evidence"]
            return ReplyDraft(
                text=evidence["reply_text"], evidence_ids=[evidence["evidence_id"]]
            )

        if task == "verify":
            return ReplyCheck(
                grounded=True, safe=True, reason="Scripted demo verification"
            )

        raise ValueError("Unsupported demo task")


class DemoRetriever:
    def __init__(self, config):
        self.config = config

    def search(self, message, intent=None):
        company = self.config["company"]["id"]
        return [
            {
                "similarity": self.config["demo"]["similarity"],
                "evidence": {
                    "company_id": company,
                    "conversation_id": "synthetic_conversation",
                    "evidence_id": f"{company}:synthetic_reply",
                    "split": "synthetic_demo",
                    "customer_text": self.config["demo"]["customer_text"],
                    "reply_text": self.config["demo"]["reply_text"],
                    "resolution_verified": False,
                },
            }
        ]
