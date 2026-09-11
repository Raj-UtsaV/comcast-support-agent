# File walkthrough: `support_agent/data/evidence.py`

This file chooses historical customer questions and their support replies for
the later search step. Here, **evidence** means a traceable historical example.
It does not mean the reply solved the problem or describes a current policy.

## What it does

`collect_evidence(config)` returns two values: a list of customer/reply pairs
and a dictionary of selection counts. It reads the company and paths from
configuration. It does not download a model, train weights, call an API, or
write an index. The search module will consume these pairs in a later step.

```python
from support_agent.shared.config import load_config
from support_agent.data.evidence import collect_evidence

config = load_config("configs/comcast.yaml")

pairs, counts = collect_evidence(config)

print(counts)
```

Run this from the project root using the project's Python environment.

## How it is implemented

1. Read the preparation manifest and check its company and schema version.
2. Read each prepared split, checking record fields, company ownership and
   file counts against the manifest. Reject duplicate message IDs and any
   conversation appearing in more than one split. Training messages must
   precede the recorded validation boundary.
3. Re-read the human evaluation annotations. Entire reserved conversations
   are excluded even when annotations were added after data preparation.
   Supplied conversation and message IDs must match the prepared data.
4. Keep training replies that passed preparation's quality filter and still
   pass the current configured filter after masking again.
5. Follow explicit parent-message links backwards to the nearest customer
   message. Consecutive support replies can share that customer question.
   Every traversed link must stay in the same conversation and move backwards
   or remain at the same timestamp.
6. Return pairs with original IDs, masked text and selection counts.

Missing parents, agent-only cycles, cross-conversation parents, reversed
timestamps and branches without a reachable customer are skipped. The code
does not guess a question from the nearest row or a different branch of the
conversation. A reply linked only through the source's response-ID column can
belong to a prepared conversation but still be skipped here if its explicit
parent is missing. This sacrifices coverage to keep pair construction clear.

## Returned fields

| Field | Purpose |
| --- | --- |
| `evidence_id` | Company ID and source reply ID identify this historical reply. |
| `company_id`, `conversation_id` | Preserve company ownership and conversation grouping. |
| `customer_message_id`, `reply_message_id` | Trace the pair to prepared source messages. |
| `customer_text`, `reply_text` | Supply the masked question and historical response. |
| `timestamp` | Preserve the reply's original normalized timestamp. |
| `split` | Always `train`; other splits cannot supply evidence. |
| `intent` | `None` until request categories and annotations are approved. |
| `resolution_verified` | Always `False`; a historical reply is not proof of success. |

The summary counts every training agent reply exactly once: selected, excluded
by golden annotations, rejected for basic reply quality, or missing usable
customer context. An empty result remains empty; no examples are invented.

## Limits and responsibilities

The reply filter checks length and configured greeting/direct-message patterns.
It does not judge factual accuracy, safety, helpfulness or successful resolution.
The later agent must review historical examples before drafting an answer.
Masking is heuristic and has the limitations described in [text.md](../shared/text.md).

Each source reply produces at most one pair. Multiple replies in the same
conversation can produce multiple pairs. The [search index](../retrieval/search_index.md)
limits repeated conversations by returning one eligible reply per conversation.
No relevance scores are produced by evidence selection itself.

Memory holds training messages and identity maps for all prepared messages;
held-out message text is read for validation but not retained as evidence.
The implementation therefore scales with the selected company's data, not the
complete multi-company CSV. It is not an unlimited-memory streaming solution.

The prepared files should remain unchanged during selection. Count and identity
checks catch structural problems; they are not cryptographic tamper detection.
The [saved-index loader](../retrieval/index_store.md) now records source fingerprints and
checks for stale data or changed golden annotations before reuse. If preparation's quality
rules are relaxed, rerun preparation into a new output directory to reconsider
replies previously marked unusable.

The synthetic tests in `tests/test_evidence.py` exercise selection boundaries
and link handling without downloading models or contacting external services.

## Observed selection on the prepared Comcast data

The local check on September 10, 2026 selected **22,978 pairs across 16,842
conversations**. Of 23,076 training agent replies, 55 failed the basic quality
filter and 43 lacked usable linked customer context. No golden annotation file
was present, so no additional replies were excluded by annotations.

These are selection counts, not retrieval accuracy or agent performance.
No model, search index, approved intent labels or evaluation scores were
created in this step.
