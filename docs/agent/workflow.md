# File walkthrough: `support_agent/agent/workflow.py`

`SupportAgent` accepts injected generation and retrieval interfaces. It validates
company identity, history roles/count and message lengths, then masks all
message/history text before it reaches a model. Request risk detection runs on
the original text so masking does not hide risk signals.

The workflow is bounded: classify against approved IDs, retrieve, draft with
citations, verify, then decide. Invalid classifications do not reach drafting.
Missing evidence never yields an invented answer. Citations must identify
retrieved records; deterministic reply rules and a separate model-verification
call must pass. Invalid drafts become a clearly recorded safe fallback.

Setup/retrieval failures remain errors. Model-output failures produce an
escalation. No external action is executed. Auto-handle is a recommendation,
not an automatic send or a guarantee of correctness. The verifier can share
generator biases; evaluation must measure those correlated errors.
