# Comcast support assistant — submission report

## Problem and definition of good

Help customers understand internet/TV problems and obtain supported next steps,
while routing account actions, security issues, and exhausted troubleshooting to
a human. Good means relevant, helpful, grounded, respectful, and safe. A polite
but unhelpful handoff is not a successful resolution. Confidence is uncalibrated.
The assistant must not claim account changes or verify current outages, prices,
or policy from historical tweets.

The product includes customer chat with conversation context and a separate staff
dashboard. We did not build authentication, ticket creation, agent transfer,
account access, refunds, live outage checks, or production monitoring. This is
an independent demonstration, not an official Comcast channel. No custom model
is trained.

## Method, data, and evidence status

Groq-hosted GPT-OSS 120B classifies, drafts, and verifies structured replies.
Sentence Transformers `all-MiniLM-L6-v2` produces 384-dimensional embeddings;
FAISS retrieves training evidence. Rules and validation govern handling. Short
follow-ups include conversation context in chat calls and retrieval. Customer
chat can also offer bounded configured basic guidance. The evaluation harness
measures the underlying agent, not these UI-only guidance branches.

Source: Thought Vector, Customer Support on Twitter, version 10. Attribution and
terms are documented in `docs/dataset.md`. Chronological conversation grouping
avoids same-thread leakage; boundary-spanning groups are quarantined.

| Reproducible engineering measurement | Observed value |
| --- | ---: |
| Selected/normalized messages | 72,288 |
| Distinct selected conversations | 24,065 |
| Training / validation / evaluation messages | 49,950 / 9,589 / 9,881 |
| Quarantined messages | 2,868 |
| Indexed historical question–reply pairs | 22,978 |
| Held-out review sample | 200 distinct conversations |
| Completed human golden labels | 0 |

These are data-integrity counts, not response-quality scores. Fast replay verifies
selected records, split disjointness, evidence membership, vector shape, and
checksums. It does not reread the raw multi-company download. Automated test
results are in `submission/evidence/`; synthetic success is not real accuracy.

The author confirmed no completed human labels. The review set therefore
**does not yet satisfy the hand-labelled deliverable**. Seed-42 message shuffling
followed by conversation deduplication produced the sample; this favors longer
conversations and is not class-stratified. See the sampling/annotation protocol.

## Results versus two baselines

| Method | Classification | Reply/retrieval | Quality measurements |
| --- | --- | --- | --- |
| Trivial | Majority human-labelled training intent | Generic reply; always escalates | Not run |
| Simple | Training-reviewed keyword rules | TF-IDF historical reply; always escalates | Not run |
| Agent | GPT-OSS 120B | Embedding retrieval + draft/verification/rules | Not run |

Accuracy, macro-F1, per-category metrics, escalation precision/recall/F1,
Recall@1/3/5, fallback rate, auto-handle coverage, false-auto rate, and human-
verified safe coverage are implemented. No quality comparison is claimed:
human golden labels, training labels, and baseline keyword approval are absent.
The baselines' zero auto-handle coverage is a design property, not evidence of
useful support.

The judge scores relevance, helpfulness, groundedness, tone, and safety on
anchored 1–5 scales (`submission/JUDGE_RUBRIC.md`). Human ratings are bound to
exact reply checksums. Agreement includes paired counts, exact agreement,
unweighted Cohen's kappa, and Spearman correlation. **Judge–human agreement is
unavailable**: there is no judged golden run or independent human scoring.
A previous live provider smoke check returned HTTP 500; it is not benchmark data.

## Five priority failure modes with real examples

These are development priorities observed in real training examples, not a
frequency-ranked list of scored held-out model failures. Traceable IDs and
excerpts are in `submission/evidence/failure_examples.json`.

| Priority / message ID | Observed challenge | Hypothesis / next check |
| --- | --- | --- |
| 1 / 1989886 | “Curse of the shirtless gourd.” lacks actionable standalone context | Earlier turns or an out-of-scope policy may reduce forced classifications |
| 2 / 1820994 | Streaming performance, monthly charges, and threatened cancellation coexist | One intent loses secondary issues; adjudicate the primary intent and retain risk signals |
| 3 / 835513 | Claimed planned outage, no notification, and money-back request | Retrieval may repeat unverifiable current claims; separate advice and account decisions |
| 4 / 648739 | Processed text retains a street address; report excerpt additionally redacted | Regex masking misses addresses; add an audited masking challenge set |
| 5 / 1225999 | Customer already restarted repeatedly and unplugged equipment | Generic advice repeats failed steps; test history-aware next actions |

Engineering regressions also included escalation on “keeps disconnecting,”
assistant text triggering customer risk, and retrieval on “all devices” without
its topic. These were fixed and regression-tested. That does not establish
improved quality on the still-unlabelled golden set.

## What is misleading about my headline number?

22,978 pairs measure evidence availability, not relevance or correctness. Passing
tests demonstrates tested code paths, not customer outcomes. Neither substitutes
for a hand-labelled benchmark. A safety score can reward always handing off;
report helpfulness and coverage alongside false-auto and fallback rates. Null
metrics do not mean zero errors.

Incomplete relevance judgements and exposure to top-five candidates bias Recall.
Old tweets are not verified resolutions or current policy. Class imbalance,
multi-issue turns, and contextless messages distort accuracy. The single-turn
harness does not validate multi-turn customer chat or its configured guides.
The generator and judge can share biases; subset agreement is not universal
correctness. Constant ratings make some agreement measures undefined.

## Reproduction and one more week

`python3 scripts/reproduce_submission.py` verifies the engineering headline from
the bundle offline using only Python's standard library. Measured runtime is in
`submission/evidence/reproduction.json`. The target is under 15 minutes; cold
installation and a fresh live quality evaluation are outside the timed replay.
Full setup and evaluation instructions are in `submission/README.md`.

With another week: days 1–2, complete training/category review and independent
golden annotation; day 3, freeze settings and run all three methods with the
judge; day 4, blind human scoring and disagreement review; day 5, rank actual
held-out failures and audit multi-turn/privacy gaps; days 6–7, test targeted
fixes on development data, rerun the frozen benchmark, and publish immutable
predictions, agreement and quality results. Do not tune on held-out labels.
