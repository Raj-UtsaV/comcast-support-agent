# Configurable Customer Support AI Agent

New to the codebase? Follow the [guided reading path](docs/reading-guide.md) for
the recommended file order, workflow diagrams, and how the modules connect.

## Submission and reproducible evidence

Start with [the submission guide](submission/README.md) and
[requirement status](submission/STATUS.md). From the provided source bundle,
`python3 scripts/reproduce_submission.py` verifies the engineering headline
offline using only Python's standard library: **72,288 processed messages,
24,065 conversations, and 22,978 indexed pairs**. See the recorded runtime in
`submission/evidence/reproduction.json`. These are data counts, not model-quality
scores. The 200-example review set is real but still unlabelled; human annotation,
baseline quality results and judge–human agreement remain explicitly pending.

A configurable Python support assistant that classifies a customer request,
retrieves historical evidence, drafts a reply and recommends auto-handling or
human escalation. No reply is sent and no account action is performed.

The first real dataset uses `comcastcares` conversations. Company identifiers,
categories, model choices, rules and thresholds live in YAML. No custom intent
model is trained: the agreed approach uses an existing LLM plus pretrained
embeddings. `company` consistently names the business being supported.

## What works now

- Chunked dataset preparation with company/conversation/time separation.
- Cached local embeddings and a saved index containing 22,978 historical pairs.
- Retrieval CLI; structured classification/drafting/verification; safety rules.
- Explicit offline synthetic demo and a three-tab Streamlit app.
- Two baselines, evaluation metrics, LLM judging and exact-reply human ratings.
- Blank real-data review sheets and offline tests. No headline quality scores
  have been fabricated; real evaluation awaits human labels and model credentials.

## Customer chat and staff workspace

For the new customer chat, run `.venv/bin/streamlit run customer_app.py`.
The existing `app.py` remains the staff workspace. See
[customer and staff startup instructions](docs/customer-app.md) to run both
interfaces, or to try the customer chat in explicit demo mode.

## Quick start: no keys or dataset required

Use Python 3.12. The current workspace already has a populated `.venv`.
For a fresh checkout with `uv` installed:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python --torch-backend cpu -r requirements.txt
```

From this project directory:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m support_agent check --config configs/demo.yaml
.venv/bin/python -m support_agent analyse --config configs/demo.yaml \
  --message "My connection stopped working."
.venv/bin/streamlit run app.py --server.address 127.0.0.1
```

Select **demo** in the website sidebar. It is visibly synthetic: classification,
evidence and verification are scripted and never stand in for model results.
An account-cancellation example demonstrates escalation. Demo mode cannot run
real-data evaluation.

## Architecture

```mermaid
flowchart LR
    A[Message and history] --> B[Validate and mask]
    B --> C[LLM category]
    C --> D[Company training evidence]
    D --> E[LLM draft with citations]
    E --> F[Rules and LLM verification]
    F --> G[Draft and handling decision]
```

| Folder inside `support_agent/` | Responsibility |
| --- | --- |
| `shared/` | Configuration, text cleaning and request/result schemas |
| `data/` | Preparation, conversations, splits, evidence and annotation exports |
| `embeddings/` | Pretrained text encoder and its provider interface |
| `retrieval/` | Search, saved indexes, fingerprints and retrieval commands |
| `models/` | Configurable LLM client |
| `agent/` | Support workflow, safety, categories, runtime and synthetic demo |
| `evaluation/` | Evaluation runner, baselines, metrics and human ratings |
| `ui/` | Evaluation and failure-analysis views used by root `app.py` |

The package root contains only `__init__.py` and the main CLI `__main__.py`.
Walkthroughs mirror these folders under `docs/`; test explanations live in
`docs/tests/`. See the [complete folder structure](docs/structure.md), including
module locations and command entry points.

## Real dataset and index

Obtain the Kaggle **Customer Support on Twitter** dataset and place its complete
CSV at `data/raw/twcs.csv`. See [download/provenance instructions](docs/dataset.md)
and the dataset's CC BY-NC-SA license terms. The current workspace already has
the downloaded CSV, prepared company data, model cache and saved index.

On a fresh data setup:

```bash
.venv/bin/python -m support_agent setup --config configs/comcast.yaml
```

This single command prepares missing data, downloads missing embedding weights,
builds the vector index, and verifies it. Later runs reuse existing data and a
valid index. Add `--rebuild` to regenerate the index from existing processed data.
See [the rebuild pipeline](docs/rebuild.md) for individual steps and prerequisites.

Preparation refuses to overwrite processed output. Choose a new
`paths.processed_dir` when preparing a changed version. Training means the
historical-development split, not training model weights. Validation is for
development/tuning; the held-out evaluation and golden sets stay separate.

For the first embedding-model download, run the snippet in
[embeddings.md](docs/embeddings/encoder.md). Then:

```bash
.venv/bin/python -m support_agent.retrieval build --config configs/comcast.yaml
.venv/bin/python -m support_agent.retrieval inspect --config configs/comcast.yaml
.venv/bin/python -m support_agent.retrieval search --config configs/comcast.yaml \
  --message "My internet keeps disconnecting."
```

Skip `build` when the saved index already exists. Use `build --rebuild` to
publish a new generation after input changes. Hash checks detect stale data,
golden annotations, embedding settings and relevant implementation changes.
Old generations remain available. Search never retrieves another company's
records and returns at most one reply per conversation.

## Activate the real support agent

1. Review `data/processed/comcast/intent_review.csv`. The
   [category-review guide](docs/category_review.md) lists provisional patterns
   found in that training sample; none is automatically approved.
2. Fill `intents.approved_taxonomy`, `intents.keyword_rules` and
   `safety.risky_intents` in `configs/comcast.yaml` after review.
3. For a fresh setup, copy `.env.example` to `.env`. The template selects
   Groq-hosted GPT-OSS 120B: `LLM_PROVIDER=groq` and
   `LLM_MODEL=groq/openai/gpt-oss-120b`. Add your Groq API key as `LLM_API_KEY`
   in `.env`. The judge selects the same model; fill `JUDGE_API_KEY` (which may
   use the same key) only when running evaluation. The `groq/` prefix is
   [LiteLLM's provider routing](https://docs.litellm.ai/docs/providers/groq);
   Groq receives model ID `openai/gpt-oss-120b`, which supports the client's
   [JSON-object output](https://console.groq.com/docs/model/openai/gpt-oss-120b).
   Restart Streamlit after environment changes and select **comcast** in the
   sidebar to use the live model. **demo** continues to use scripted responses.
   Never commit keys.
4. Check readiness and analyse a message:

```bash
.venv/bin/python -m support_agent check --config configs/comcast.yaml
.venv/bin/python -m support_agent analyse --config configs/comcast.yaml \
  --message "My internet keeps disconnecting."
```

Both analysis and retrieval accept `--stdin` instead of `--message`, allowing
`--stdin < message.txt`. Input is bounded by YAML settings. Python callers may
construct `SupportRequest` with typed customer/agent history. No system-role
history is accepted. Real model calls send masked task text to your provider;
regex masking is not a guarantee of complete sensitive-data removal.

Missing setup is an error, never an implicit demo. Invalid or unsafe model
output produces a labelled safe fallback and escalation. Confidence and cosine
similarity are not calibrated probabilities of answer correctness.

## Human labels and evaluation

Two real-data review sheets are already provided:

- `data/golden_set_template.csv`: 200 distinct held-out conversations.
- `data/training_labels_template.csv`: 500 distinct training conversations.

For fresh alternative sheets, choose unused output paths:

```bash
.venv/bin/python -m support_agent.data.annotations golden --config configs/comcast.yaml \
  --output data/golden_review_new.csv
.venv/bin/python -m support_agent.data.annotations training --config configs/comcast.yaml \
  --output data/training_review_new.csv
```

Human reviewers fill approved intent IDs, `should_escalate` (`true`/`false`)
and `relevant_evidence_ids` (a JSON list of eligible training evidence IDs).
`[]` means no relevant evidence was found; blank means unfinished. Candidate
evidence IDs/text are available through retrieval and the saved `evidence.jsonl`.
Keep original company/conversation/message IDs unchanged.

Save completed golden rows as `data/golden_set.csv`. For the majority baseline,
save completed training rows as `data/training_labels.csv`; remove unlabelled
rows from that completed subset. Golden evaluation needs 150–250 distinct
conversations. Training labels need approved intents; their escalation/relevance
columns are not used. Do not silently exclude difficult golden examples.

Rebuild the index after activating golden annotations, then freeze prompts,
categories, rules and thresholds. Full evaluation:

```bash
.venv/bin/python -m support_agent.retrieval build --config configs/comcast.yaml --rebuild
.venv/bin/python -m support_agent.evaluation run --config configs/comcast.yaml \
  --training-labels data/training_labels.csv
```

The run saves `report.json`, `predictions.json` and `human_scores_template.csv`
under a new `results/comcast/evaluation-.../` directory. Complete independent
human scores for the exact saved drafts, then import without regenerating them:

```bash
.venv/bin/python -m support_agent.evaluation rate --config configs/comcast.yaml \
  --run results/comcast/evaluation-YOUR_RUN \
  --human-scores data/human_scores.csv
```

Replace `YOUR_RUN` with the directory printed by evaluation. The template carries
reply checksums, preventing ratings for a different draft from being reused.
Partial ratings remain visibly incomplete. `run --metrics-only` skips judging
explicitly and does not satisfy the full assignment evaluation.

Metrics cover intent accuracy/macro-F1/per-category results, Recall@k, escalation,
auto-handle/false-auto-handle rates, human-verified safe coverage, reply-quality
dimensions and judge/human agreement. See [metric definitions](docs/evaluation/metrics.md)
for denominators and unavailable values. Baselines use training majority/generic
reply and keyword classification/TF-IDF retrieval; both always escalate.

## Reproduction and extension

The offline test suite, scripted demo, cached-index inspection/search and loading
saved evaluation reports form the fast reproduction path. These do not require
re-encoding the corpus or rerunning paid judging. Full live evaluation of 200
messages makes many provider calls and can exceed 15 minutes; its runtime and
cost depend on your provider. No live quality results are currently claimed.

Another company supplies its own YAML, source account IDs, category taxonomy,
rules and instructions. Another CSV layout can reuse configurable column maps;
another dataset format implements the `data.conversations.ADAPTERS` reader contract
and preserves common message fields and split invariants.

An embedding provider implements `TextEmbedder` and is selected by its factory.
A text provider implements `TextGenerator`; the existing factory uses LiteLLM
provider routing. A replacement search provider preserves company/model checks,
ranked evidence, thresholds and conversation deduplication behind the search
factory; adapt persistence as required by that backend. Never weaken company
or golden-set exclusions for a provider change.

## Limits and delivery status

The software and offline demo are implemented. Real category approval, human
labels/ratings and configured live models are still required to claim measured
agent quality. Historical replies may be wrong, outdated or unresolved; model
verification and regex safety checks can miss errors. The UI has no production
authentication or account integrations. Exact in-memory search and repeated
freshness hashes suit this dataset, not unlimited-scale serving. Model weights
truncate long text according to their tokenizer limit.

See [report.md](report.md), [decision_log.md](decision_log.md) and the per-file
walkthroughs in `docs/`. The report explicitly separates observed pipeline counts
from unrun quality measurements.
