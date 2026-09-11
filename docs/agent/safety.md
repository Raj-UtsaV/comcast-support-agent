# File walkthrough: `support_agent/agent/safety.py`

Request and reply regex rules and the confidence threshold come from YAML.
Signals cover sensitive information, account/security/billing actions, repeated
problems, missing evidence and unknown/risky categories. Draft checks look for
prohibited claims and secret requests independently of the model verifier.
These are conservative heuristics, not a proof of safety. The agent always
escalates failed verification and risky categories even if optional escalation
settings are relaxed. A blocked draft is replaced by the configured safe
fallback, and the result records that replacement.
