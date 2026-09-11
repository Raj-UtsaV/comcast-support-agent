"""A bounded classify, retrieve, draft, verify and decide workflow."""

from copy import deepcopy

from support_agent.agent.safety import decision_flags, pattern_flags, validate_safety
from support_agent.agent.taxonomy import approved_categories
from support_agent.shared.config import ConfigError
from support_agent.shared.schemas import (
    Classification,
    ReplyCheck,
    ReplyDraft,
    SupportRequest,
    SupportResult,
)
from support_agent.shared.text import normalize_text


class SupportAgent:
    def __init__(self, config: dict, generator, retriever):
        self.config = deepcopy(config)
        self.categories = approved_categories(self.config)
        validate_safety(self.config)
        if config["intent_classification"]["model"] != "generator":
            raise ConfigError(
                "Intent classification currently uses the configured generator."
            )
        self.generator, self.retriever = generator, retriever

    def analyse(self, request: SupportRequest) -> SupportResult:
        config = self.config

        if request.company_id != config["company"]["id"]:
            raise ValueError("This request belongs to another company.")

        limit = config["runtime"]["max_message_characters"]
        history_limit = config["runtime"]["max_history_messages"]

        if (
            type(limit) is not int
            or limit < 1
            or type(history_limit) is not int
            or history_limit < 0
        ):
            raise ConfigError("Message/history limits must be valid integers.")

        if len(request.conversation_history) > history_limit:
            raise ValueError("Conversation history exceeds the configured limit.")

        flags, history = [], []
        texts = [request.message, *(item.text for item in request.conversation_history)]
        cleaned = []

        for position, text in enumerate(texts):
            if not text.strip() or len(text) > limit:
                raise ValueError(
                    "A message is blank or exceeds the configured character limit."
                )

            masked, sensitive = normalize_text(text, config)

            if not masked or len(masked) > limit:
                raise ValueError(
                    "A cleaned message is empty or exceeds the configured limit."
                )

            cleaned.append(masked)
            # Assistant suggestions are context, not new customer risk requests.
            if position == 0 or request.conversation_history[position - 1].role == "customer":
                flags.extend(pattern_flags(text, config["safety"]["request_patterns"]))

            if sensitive:
                flags.append("sensitive_information")

        for item, text in zip(request.conversation_history, cleaned[1:], strict=True):
            history.append({"role": item.role, "text": text})

        payload = {
            "message": cleaned[0],
            "history": history,
            "company_instructions": config["company"]["instructions"],
        }
        # Short answers such as "both devices" need the original issue and
        # the most recent question when looking up historical evidence.
        query = cleaned[0]
        if history:
            customers = [item["text"] for item in history if item["role"] == "customer"]
            context = list(dict.fromkeys([
                *(customers[:1]), *(customers[-1:]), history[-1]["text"],
            ]))
            budget = min(limit, 1500)
            current = cleaned[0][:budget // 2]
            remaining = max(0, budget - len(current) - 1)
            per_turn = remaining // max(1, len(context))
            query = "\n".join([current, *(text[:per_turn] for text in context)])[:budget]
        classification = Classification(
            intent=None, confidence=0.0, reason="Classification unavailable"
        )
        matches, cited = [], []
        reply = config["safety"]["fallback_reply"]
        reply_status = "safe_fallback"

        try:
            classification = Classification.model_validate(
                self.generator.generate(
                    "classify",
                    {**payload, "categories": self.categories},
                    Classification,
                    config["intent_classification"]["instructions"],
                )
            )

            if classification.intent is not None and classification.intent not in {
                entry["id"] for entry in self.categories
            }:
                raise ValueError("Model returned an unapproved category")
        except (ValueError, RuntimeError, TypeError):
            classification = Classification(
                intent=None, confidence=0.0, reason="Invalid classification"
            )
            flags.append("verification_failed")

        if "verification_failed" not in flags:
            # Retrieval/setup failures propagate; they must not masquerade as no matches.
            matches = self.retriever.search(query, classification.intent)

            if any(
                item["evidence"]["company_id"] != request.company_id for item in matches
            ):
                raise ValueError("Retrieved evidence belongs to another company.")

        if matches:
            try:
                draft = ReplyDraft.model_validate(
                    self.generator.generate(
                        "draft",
                        {**payload, "evidence": matches},
                        ReplyDraft,
                        config["safety"]["generation_instructions"],
                    )
                )
                known = {item["evidence"]["evidence_id"] for item in matches}
                if not draft.text.strip() or len(draft.text) > limit:
                    raise ValueError("Draft is empty or exceeds the message limit")
                draft_flags = pattern_flags(
                    draft.text, config["safety"]["reply_patterns"]
                )

                if not draft.evidence_ids or not set(draft.evidence_ids).issubset(
                    known
                ):
                    draft_flags.append("unsupported_claim")

                check = ReplyCheck.model_validate(
                    self.generator.generate(
                        "verify",
                        {**payload, "evidence": matches, "draft": draft.model_dump()},
                        ReplyCheck,
                        config["safety"]["verification_instructions"],
                    )
                )

                if not check.grounded:
                    draft_flags.append("unsupported_claim")

                if not check.safe:
                    draft_flags.append("verification_failed")

                flags.extend(draft_flags)

                if not draft_flags:
                    reply, _ = normalize_text(draft.text, config)
                    cited = list(dict.fromkeys(draft.evidence_ids))
                    reply_status = "generated"
            except (ValueError, RuntimeError, TypeError):
                flags.append("verification_failed")

        flags = decision_flags(config, classification, matches, flags)
        mandatory = {"verification_failed", "unsupported_claim", "risky_intent"}
        blocked = sorted(
            set(flags) & (set(config["safety"]["escalate_on"]) | mandatory)
        )

        if reply_status != "generated":
            blocked = sorted({*blocked, "verification_failed"})
            flags = sorted({*flags, "verification_failed"})

        return SupportResult(
            company_id=request.company_id,
            intent=classification.intent,
            intent_confidence=classification.confidence,
            draft_reply=reply,
            evidence_ids=cited,
            retrieved_examples=matches,
            decision="escalate" if blocked else "auto_handle",
            decision_reason="; ".join(name.replace("_", " ") for name in blocked)
            if blocked
            else "Configured checks passed; no account action was performed.",
            safety_flags=flags,
            reply_status=reply_status,
            demo=config["runtime"]["demo_mode"],
        )
