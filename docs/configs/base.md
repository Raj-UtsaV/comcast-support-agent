# File walkthrough: `configs/base.yaml`

## Purpose and current status

This file defines shared defaults for the **Configurable Customer Support AI
Agent**. It keeps model choices, dataset settings, thresholds and support policy
out of the Python agent logic. A company configuration will supply the company and
dataset details and can override these defaults.

**Company** means the business whose customer-support requests we are handling.
`company.id` identifies that business in configuration; `company_id` will carry
the same value in processed messages, requests and search records.
`dataset.company_author_ids` lists its support account IDs in the source data.

This revision uses an existing LLM for intent classification and reply drafting,
with pretrained embeddings for retrieval. It removes logistic regression,
silver-label training and K-means clustering. No custom model training or LLM
fine-tuning is needed.

The real Twitter CSV has been downloaded; see [dataset.md](../dataset.md).
The configuration loader, data-preparation and evidence-selection modules now
exist, along with embeddings, search, saved-index loading and a command-line
retrieval workflow. Classification, reply generation, verification, escalation,
the Streamlit interface, baselines, evaluation and human-rating import are now
implemented. Real runs require human-approved categories, completed labels and
model credentials. No real agent evaluation results are available.

## How configuration will be loaded

The loader now lives in `support_agent/shared/config.py`, so preparation and later
modules can share it without loading models. It performs these steps:

1. Read `configs/base.yaml` with a safe YAML parser.
2. Read the selected company YAML and recursively merge dictionaries. Company
   scalar values and lists replace their corresponding base values; lists are
   not appended automatically.
3. Load `.env` without overriding environment variables already set by the user.
4. Resolve `${VARIABLE}` placeholders for the component being used. Data
   preparation must not require generation credentials, and normal customer
   analysis must not require judge credentials. Full evaluation needs the judge.
5. Validate the merged configuration and resolve paths against the project root.

`api_key_env` stores the **name** of an environment variable, never the key
itself. A real generator with missing settings or credentials must fail with a
clear message. `demo_mode: false` means synthetic behavior is not selected
implicitly. Tests will explicitly inject fake models.

## What each section controls

| Section | Purpose and intended implementation |
| --- | --- |
| `config_version`, `random_seed` | Identify the configuration format and seed sampling for reproducibility. |
| `company` | Require a company ID, display name and support instructions from the company YAML. |
| `paths` | Define data, labels, artifact, model-cache and results locations relative to the project root. |
| `runtime` | Bound customer-message size and conversation-history length; make demo mode explicit. |
| `dataset` | Select an adapter, map source columns, select support authors and process CSV chunks. |
| `splits` | Separate complete conversations chronologically and quarantine threads spanning time boundaries. |
| `intent_discovery` | Export a seeded sample of training customer messages for human review. |
| `intents` | Read the human-approved taxonomy and keyword rules for the simple baseline. |
| `intent_classification` | Select the existing LLM configuration and instructions for classifying messages. |
| `models` | Select the pretrained embedder, generator and evaluation judge through provider factories. |
| `retrieval` | Use normalized embeddings with FAISS cosine search and reject weak matches. |
| `safety` | Configure escalation thresholds, risky approved intents, independent request checks and generation instructions. |
| `evaluation` | Define golden-set size, baselines, retrieval cutoffs, reply scoring, judging and human ratings. |
| `ui` | Supply example messages from company configuration. |

## Dataset handling

The base file has no company support account IDs, source column names or raw CSV path.
`configs/comcast.yaml` will provide those details for the first dataset. Another
company or dataset should supply its own mapping and adapter settings.

The adapter will read chunks of up to 50,000 rows instead of loading the entire
CSV at once. It must reconstruct connections across chunks; a chunk is not a
conversation boundary. Whitespace normalization and Unicode NFKC standardize
text before modeling. Email addresses, phone numbers, account numbers and
usernames will be masked in exposed text. Original message and conversation IDs
must remain available for evidence.

The reply-quality settings reject very short replies and provide initial
patterns for greetings and DM-only replies. The regular expressions use YAML
single quotes so backslashes reach Python unchanged. `(?i)` means
case-insensitive matching. Quality filtering does not establish that a support
reply resolved the customer's problem. These initial patterns will need checks
against real data and can be extended in company configuration.

## Keeping evaluation data separate and searching only the selected company

The split fractions target 70% training, 15% validation and 15% held-out
evaluation. Actual proportions can differ when threads cross chronological
boundaries and must be quarantined. All messages in a conversation belong
together, and quarantined conversations must not enter retrieval or development.

Here, **training** names the historical evidence/development split. It does not
mean we train model weights. Human intent review and the evidence index use this
split; validation supports prompt and threshold selection.

The pipeline must also enforce these invariants independently of configurable
preferences:

- Index only training conversations.
- Exclude every golden-set conversation from training, intent discovery,
  threshold tuning, retrieval and prompt examples.
- Develop baseline rules and prompts using development data; tune on validation
  data; freeze those choices before evaluating on held-out data.
- Select 150–250 golden examples from held-out conversations and have a human
  annotate them. Record the sampling and labelling method; the target is 200.
- Store artifacts under `artifacts/{company_id}/` and check that records belong
  to the selected company
  during both index construction and search.

These protections are implementation requirements, not optional YAML switches.
The shared label paths are defaults; separate paths can be supplied when
operating multiple companies. Every label record must carry its company and
conversation identity.

## Intents and model choices

The embedding default is `sentence-transformers/all-MiniLM-L6-v2`, used as a
pretrained encoder. Its `revision` pins the model to a specific Hub commit.
`device: cpu` uses the installed CPU environment; batch size and normalization
remain configurable. `paths.model_cache` keeps downloaded files inside the
ignored project cache. See [embeddings.md](../embeddings/encoder.md) for first-download
and local-only loading instructions.

Generating embeddings and building a FAISS index do not train this model.
Generator and judge names come from environment variables.

Intent discovery exports up to 500 training customer messages using the
configured random seed. If fewer eligible messages exist, export the available
messages and report the actual count. A human reviews this sample and approves
intent IDs and descriptions in company YAML. An LLM may assist the review, but
its suggestions are not automatically an approved taxonomy.

`intent_classification.model: generator` references `models.generator`. The
agent will reuse that provider client for a classification call before retrieval
and a separate drafting call after retrieval. The result must contain an
approved intent ID or `null`, confidence in `[0, 1]`, and a short reason.
An unmatched message triggers `unknown_intent`; an invented label or malformed
output is a validation failure and must prevent auto-handling.

`approved_taxonomy` and `risky_intents` intentionally start empty. Real agent
execution requires an approved taxonomy, and risky IDs must reference it.
Fixture labels belong in tests, not in purported dataset discoveries.
`keyword_rules` maps approved intent IDs to regex lists for the simple baseline.
Empty rules are a setup placeholder, not a ready-to-evaluate baseline.

Intent filtering for retrieval remains disabled until historical records have
appropriate intent metadata.

The [search index](../retrieval/search_index.md) now validates and applies `top_k`,
`min_similarity` and `filter_by_intent`. `top_k` counts distinct conversations,
and both indexed and query vectors are normalized for cosine comparison.
It also checks company ownership and embedding-model identity on each search.

[Saved indexes](../retrieval/index_store.md) live under
`paths.artifacts_dir/{company_id}/search/`. Each rebuild creates a new version;
`current.json` identifies the published version. Reloading checks data, model
and implementation fingerprints. Changing result count, score cutoff or intent
filtering alone does not require encoding the historical questions again.

## Safety and thresholds

The initial confidence threshold is `0.75`; the retrieval similarity threshold
is `0.60`. These are configurable starting values, **not validated performance
claims**. Any tuning must use validation data, never the golden set.
LLM-reported confidence is not a calibrated probability. It and cosine
similarity measure different things; neither proves that a reply is correct.
Validation must establish whether these signals help decide when to escalate.

`request_patterns` detects generic risks even if classification is uncertain.
For example, a message containing “refund” can trigger the billing/refund flag
without requiring a classifier to predict a particular intent. These patterns
are initial heuristics: they can overmatch, miss paraphrases and require company
review. They are not a complete safety verifier.

The agent detects sensitive information before masking it, retains safety flags,
checks generated replies against configured patterns, asks the model to verify
them and collects escalation reasons. Failed verification replaces the draft
with `fallback_reply` and requires escalation. Prompt instructions alone cannot
guarantee safe output.
`verification_failed` covers a reply that cannot be verified, including malformed
generator output. Unsupported actions and unsupported current-fact claims must
be checked before deciding whether a request can be auto-handled.

## Baselines and evaluation

The configured baselines are `trivial` and `simple`:

- **Trivial:** majority intent from labelled development examples, the configured
  generic reply and always escalate. Golden labels must not determine the
  majority intent.
- **Simple:** keyword intent rules and TF-IDF retrieval of a historical reply.
  TF-IDF fits vocabulary/statistics on the evidence corpus; it does not train a
  supervised intent classifier. Its rules and escalation policy must be fixed
  on development data and documented before the golden evaluation.

`judge_enabled: true` includes LLM judging in the full evaluation, as required
by the assignment. It scores relevance, helpfulness, groundedness, tone and
safety on a 1–5 scale with structured explanations. Missing judge credentials
must produce a clear error. A deliberate metrics-only run with judging disabled
must be marked incomplete for the assignment, not silently use fake scores.

`paths.golden_labels` points to `data/golden_set.csv` for hand-labelled task
examples. `human_scores_csv: null` means independent human reply-quality ratings
have not been supplied yet. Judge/human agreement remains unavailable until
matching ratings are imported. Missing annotations or unrun evaluations must
appear as unavailable, never as invented scores or zero-valued performance
results.

## Review guidance

The remaining software was completed together as requested. Review the shared
defaults alongside [agent.md](../agent/workflow.md), [safety.md](../agent/safety.md) and
[evaluation.md](../evaluation/runner.md). Category approval and human labels remain
explicit setup steps; the synthetic demo does not fill them automatically.
