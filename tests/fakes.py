"""Test doubles for offline workflow regression tests; not application components."""

from support_agent.shared.schemas import Classification, ReplyCheck, ReplyDraft


class FakeGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, task, payload, schema, instructions):
        if task == "classify":
            return Classification(
                intent=self.config["intents"]["approved_taxonomy"][0]["id"],
                confidence=0.9,
                reason="Scripted test category",
            )

        if task == "draft":
            evidence = payload["evidence"][0]["evidence"]
            return ReplyDraft(
                text=evidence["reply_text"], evidence_ids=[evidence["evidence_id"]]
            )

        if task == "verify":
            return ReplyCheck(
                grounded=True, safe=True, reason="Scripted test verification"
            )

        raise ValueError("Unsupported test task")


class FakeRetriever:
    def __init__(self, config):
        self.config = config

    def search(self, message, intent=None):
        company = self.config["company"]["id"]
        return [
            {
                "similarity": 0.9,
                "evidence": {
                    "company_id": company,
                    "conversation_id": "synthetic_conversation",
                    "evidence_id": f"{company}:synthetic_reply",
                    "split": "synthetic_test",
                    "customer_text": "My connection stopped working.",
                    "reply_text": "Please check that the cable is securely connected.",
                    "resolution_verified": False,
                },
            }
        ]
