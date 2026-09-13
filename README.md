# Configurable Customer Support AI Agent

A customer-support assistant using **Groq GPT-OSS 120B**, pretrained sentence
embeddings, and a local **FAISS vector index**. It provides a customer chat and
an independent staff dashboard for inspecting replies, evidence, and evaluation.
It does not access accounts, create tickets, or transfer customers to a human.

**Start here:** follow steps 1–7 below to go from a fresh GitHub clone to the
running apps. Commands use a Linux Bash terminal. Python 3.12 and `uv` are used
for installation; Git and `curl` are also required. Run each step only after the
previous one succeeds.

```text
Clone → install libraries → download raw data → configure Groq
      → prepare data + generate embeddings + build FAISS → verify → Flask
```

## 1. Clone the repository

```bash
git clone https://github.com/Raj-UtsaV/comcast-support-agent.git
cd comcast-support-agent
```

The repository is private, so your GitHub account needs access. The clone contains
source, configuration templates, tests, and documentation. It does **not** contain
`.env`, installed libraries, the raw dataset, model weights, or generated vectors.

## 2. Install Python and project libraries

With `uv` installed, run:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python --torch-backend cpu -r requirements.txt
uv pip check --python .venv/bin/python
```

The CPU option installs compatible CPU builds of PyTorch and torchvision.
All following commands explicitly use `.venv`, so activating it is optional.

## 3. Download the source dataset

Use the complete **Customer Support on Twitter** CSV, version 10, from
[Thought Vector on Kaggle](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter).
Place it at **`data/raw/twcs.csv`**. Do not substitute Kaggle's small `sample.csv`.
See [dataset provenance and terms](docs/dataset.md).

For a fresh clone, this downloads the pinned source ZIP and extracts the CSV:

```bash
mkdir -p data/raw .cache/dataset
curl --location --fail --show-error --retry 3 \
  --output .cache/dataset/twcs.zip \
  'https://www.kaggle.com/api/v1/datasets/download/thoughtvector/customer-support-on-twitter/twcs%2Ftwcs.csv?datasetVersionNumber=10'
.venv/bin/python -m zipfile -t .cache/dataset/twcs.zip
.venv/bin/python -m zipfile -e .cache/dataset/twcs.zip data/raw
sha256sum data/raw/twcs.csv
```

The expected CSV checksum is:

```text
cd297fcfa1bf6f99938be242e8e578980bc6d1b96adc8691abec9a39175b03c0
```

The CSV is approximately 493 MiB. If the download requires authentication or
returns an error, download version 10 through Kaggle and put the complete CSV at
the same path. Skip this step if you already have the verified file.

## 4. Configure Groq

Create your local settings file without overwriting an existing one:

```bash
test -f .env || cp .env.example .env
```

Open `.env` in your editor and fill in your Groq API key:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=groq/openai/gpt-oss-120b
LLM_API_KEY=YOUR_GROQ_API_KEY
```

The model/provider values are already in the template. `JUDGE_API_KEY` is needed
only for judged evaluation, not customer chat or vector building. Never commit
`.env`. Review company categories and rules in `configs/comcast.yaml`; the file
already contains starter internet, TV, billing, appointment, and account categories.
Human approval and training-reviewed keyword rules are needed before evaluation.

## 5. Generate processed data and the vector database — one command

```bash
.venv/bin/python -m support_agent setup --config configs/comcast.yaml
```

This command performs the pipeline in order:

1. Reads `data/raw/twcs.csv`, reconstructs company conversations, and writes
   chronological train/validation/evaluation splits under `data/processed/comcast/`.
2. Loads the pinned embedding model, downloading missing weights into
   `.cache/huggingface/` on first use.
3. Selects eligible training question–reply pairs and generates their vectors.
4. Saves and validates the FAISS index files under `artifacts/comcast/search/`.

The saved files include `vectors.npy`, `evidence.jsonl`, a generation manifest,
and `current.json`. **No separate vector database server is required.**
The recorded build contains **22,978 historical pairs with 384-dimensional
vectors**. These are pipeline counts, not answer-quality scores.

Preparation and embedding run locally and do not require Groq credentials.
The first run can take time depending on downloads and CPU speed; a cold setup
is not guaranteed to finish within 15 minutes. Later runs reuse existing
processed data and a valid index. The command finishes with JSON containing
`"status": "ready"` and `"indexed_pairs"`.

## 6. Verify retrieval and live-agent setup

```bash
.venv/bin/python -m support_agent.retrieval inspect --config configs/comcast.yaml
.venv/bin/python -m support_agent.retrieval search --config configs/comcast.yaml \
  --message "My internet connection stopped working."
.venv/bin/python -m support_agent check --config configs/comcast.yaml
```

`inspect` validates the saved index. `search` tests local embedding/retrieval
without calling Groq; an empty match list is possible at the configured threshold.
For customer chat, `check` should show `categories`, `generator`, and `saved_index`
as `ready`. A missing judge key affects evaluation only. `check` validates local
configuration; it does not prove that Groq is reachable or that a key is accepted.

Optionally test a real model request before opening the website:

```bash
.venv/bin/python -m support_agent analyse --config configs/comcast.yaml \
  --message "My internet connection stopped working. What can I try?"
```

## 7. Start the Flask apps

Customer chat:

```bash
.venv/bin/python customer_app.py
```

Open **http://localhost:8000**. Follow-up messages remain in the current page;
refreshing the page or choosing New conversation starts again.

Staff dashboard, in a separate terminal:

```bash
.venv/bin/python app.py
```

Open **http://localhost:8001** and select **comcast** to inspect drafts, evidence,
and evaluation results. Stop with Ctrl+C; restart after changing credentials.
These commands use the development server. For hosting, use the production
commands and container in [deployment instructions](docs/deployment.md).

## Subsequent runs, rebuilds, and common errors

Normally, run only the Flask commands in step 7. Recreating vectors on every
app startup is unnecessary.

| Situation | Action |
| --- | --- |
| Processed data and/or index were deleted | Run the setup command in step 5 |
| Index is stale or you want to regenerate vectors | Run the command below with `--rebuild` |
| Raw data or preparation rules changed | Choose a new `paths.processed_dir` in company YAML, then run setup with `--rebuild` |
| Existing index but model cache was deleted | Use the model-download snippet below; ordinary setup can reuse an index without loading its encoder |
| `ModuleNotFoundError` | Repeat step 2 and launch with `.venv/bin/python customer_app.py` |
| Port is already in use | Stop the old app or choose another `PORT` environment variable |
| Groq request fails | Check the local key, provider availability, and rate limits; rebuilding vectors does not fix API errors |

```bash
.venv/bin/python -m support_agent setup --config configs/comcast.yaml --rebuild
```

Download missing model weights separately when reusing a saved index:

```bash
.venv/bin/python - <<'PY'
from support_agent.shared.config import load_config
from support_agent.embeddings.encoder import create_embedder
create_embedder(load_config("configs/comcast.yaml"), local_files_only=False)
PY
```

For the individual preparation/build commands, see [the rebuild guide](docs/rebuild.md).

## What results can be reproduced?

The fast, submitted benchmark is frozen in the repo and recomputes in a few
seconds once dependencies are installed:

```bash
.venv/bin/python -m support_agent.evaluation.offline --config configs/comcast.yaml
```

Headline result: **20.0% safe auto-handle coverage** on a 200-example golden set,
with **0 false auto-handles among 42 auto-handled cases**. The same command writes
`results/comcast/offline_report.json` and prints the core numbers:

| Method | Intent acc. | Intent macro-F1 | Escalation F1 | Auto-handle | Safe auto-handle | R@3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Agent | 0.870 | 0.943 | 0.974 | 0.210 | 0.200 | 0.941 |
| Trivial baseline | 0.375 | 0.091 | 0.857 | 0.000 | n/a | 0.000 |
| Simple baseline | 0.430 | 0.583 | 0.857 | 0.000 | n/a | 0.802 |

The trivial baseline predicts the training-set majority intent and always sends a
generic escalation reply. The simple baseline uses reviewed keyword rules plus
TF-IDF evidence retrieval, then also escalates every case. The agent is the
configured classify/retrieve/draft/verify workflow represented by the frozen
replies in `data/frozen_predictions.jsonl`.

The judge rubric scores relevance, helpfulness, groundedness, tone and safety
from 1 to 5; the full wording lives in `configs/base.yaml`. Agreement was checked
against `data/human_reply_scores.csv`, an author-scored review of the exact saved
replies. Exact agreement was 0.955 relevance, 0.952 helpfulness, 0.970
groundedness, 0.915 tone and **0.940 safety**. Cohen's kappa for safety was
**0.901**. This is useful smoke, not a substitute for a second independent rater.

The larger setup path above still reproduces data preparation, vector building,
retrieval, and the apps. The recorded processing run selected **72,288 messages
across 24,065 conversations**, with **22,978 indexed pairs**.

Run the automated offline checks after dependency installation:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider
```

The offline tests verify engineering behavior, not customer-quality benchmarks.

New to the codebase? Follow the [guided reading path](docs/reading-guide.md) for
file order, workflow diagrams, and how the modules connect.

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
| `agent/` | Support workflow, safety, categories, runtime |
| `evaluation/` | Evaluation runner, baselines, metrics and human ratings |
| `ui/` | Customer chat, troubleshooting guides, staff styling, and evaluation views |

The package root contains `__init__.py`, the main CLI `__main__.py`, and `setup.py`.
Walkthroughs mirror these folders under `docs/`; test explanations live in
`docs/tests/`. See the [complete folder structure](docs/structure.md), including
module locations and command entry points.

## Submitted Evaluation Report

### Problem framing

For this brand, "good" means boringly careful Comcast support: understand the
issue, do not ask for secrets, do not claim account access, do not invent outage
status or policy, and only auto-handle when the answer can stay inside generic
troubleshooting. Billing, cancellation, appointment, account, current-status and
vague angry messages should go to a person.

I did not build account lookup, ticket creation, live outage checks, pricing or
policy tools, a transfer flow, fine-tuning, or a broad intent taxonomy. Those
would make the demo look stronger while also making the safety story worse. The
agent is a guarded reply drafter with evidence, not a Comcast operations system.

### Golden set

`data/golden_set.csv` has 200 hand-labelled examples from the held-out evaluation
split. The sampling note is in `data/golden_sampling_note.md`. I used the seeded
exporter, kept one customer message per conversation, then labelled intent,
escalation need and any close training evidence IDs. Intent mix:

| Intent | Examples |
| --- | ---: |
| general_support | 75 |
| internet_connection | 40 |
| television_service | 35 |
| billing_payment | 25 |
| account_access | 18 |
| technician_appointment | 7 |

`data/training_labels.csv` has 500 labelled training examples for the majority
and keyword baselines. Golden rows are never used as training evidence.

### Evaluation harness

Fast reproduction:

```bash
.venv/bin/python -m support_agent.evaluation.offline --config configs/comcast.yaml
```

Live model evaluation is still available, but it is not the sub-15-minute
headline path because it depends on provider calls:

```bash
.venv/bin/python -m support_agent.evaluation run --config configs/comcast.yaml \
  --training-labels data/training_labels.csv
.venv/bin/python -m support_agent.evaluation rate --config configs/comcast.yaml \
  --run results/comcast/evaluation-YOUR_RUN \
  --human-scores data/human_reply_scores.csv
```

Metrics cover intent accuracy/macro-F1, per-intent precision and recall,
escalation precision/recall/F1, auto-handle coverage, false-auto-handle rate,
safe auto-handle coverage, retrieval Recall@1/3/5, judge score means and
judge/author agreement. Reply hashes prevent scores from being reused on a
different draft.

### Failure analysis

Top five failure modes from the frozen agent run:

1. Vague complaint becomes fallback. Example `2897024`: a joke/movie-review tweet
   got `intent=None`, which is safe but useless. Hypothesis: the catch-all intent
   needs clearer handling for off-topic text and sarcasm.
2. Feature complaint mixed with cancellation pressure. Example `2864344`: scheduled
   recordings plus "cancel subscription" was predicted as billing instead of
   account access. Hypothesis: cancellation terms dominate the support issue.
3. Service installation and technician language gets muddled. Example `586530`:
   "new phone lines" and "come for the cable" was labelled TV but predicted
   general support and escalated. Hypothesis: the taxonomy is too narrow for
   multi-product field-work complaints.
4. Short follow-ups lose context. Example `2844856`: "Sent" fell to fallback.
   Hypothesis: the frozen benchmark evaluates single messages, while the live
   workflow can use conversation history.
5. Generic service anger is classified but not helped. Example `530199`: "your
   internet service is garbage" became general support instead of internet. The
   safe reply is acceptable, but it asks for context the customer probably expects
   Comcast to already have. Hypothesis: anger words overpower product words.

### What is misleading about my headline number?

The 20.0% headline is **safe auto-handle coverage**, not total answer quality.
It rewards caution. Always escalating can look safe on escalation recall, which
is why the baselines have 0 safe auto-handle coverage even though their
escalation F1 is decent. The golden set is only 200 Twitter-era Comcast examples,
and `general_support` is large because many tweets are short, sarcastic or
missing prior context. The judge agreement is against author ratings of frozen
replies, not a blinded multi-rater study. Finally, frozen predictions reproduce
the submission quickly; live LLM results can move with model/provider behavior.

### One more week

- Add a second human annotator and adjudicate disagreements.
- Split `general_support` into off-topic, short-follow-up and broad complaint.
- Evaluate full conversation threads, not just one selected customer message.
- Add an outage/status tool boundary so the agent can say when it cannot know.
- Tune retrieval labels with a reviewer UI instead of sparse CSV notes.
- Run a fresh live-model evaluation and compare it against the frozen submission.

### Decision log

- Used Twitter support data because it has real messy customer language.
- Kept chronological splits to avoid future replies leaking into training.
- Added `general_support` because forcing every vague tweet into billing/internet
  made the labels worse.
- Treated billing, account, appointment and vague messages as human-review cases.
- Chose safe auto-handle coverage as the headline because Comcast-risk answers
  should value restraint over volume.
- Kept two baselines: majority/generic and keyword/TF-IDF. They are dull, useful
  reference points.
- Froze submitted predictions so reviewers can reproduce numbers quickly.
- Kept live LLM evaluation separate because provider calls are slow and mutable.
- Used reply hashes before importing scores so ratings attach to exact text.
- Labelled evidence sparsely; bad evidence is worse than no evidence.
- Scored tone separately from safety because polite unsafe replies are still bad.
- Did not build account actions or ticketing because the demo has no authority
  to perform them.
- Preferred config rules over training a classifier; the dataset is small for
  this taxonomy.
- Made the README the report to keep the repo easy to review.

## Human labels and fresh evaluation

The completed sheets are:

- `data/golden_set.csv`: 200 distinct held-out conversations.
- `data/training_labels.csv`: 500 distinct training conversations.
- `data/human_reply_scores.csv`: author ratings for the exact frozen replies.

For fresh alternative review sheets, choose unused output paths:

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

## Reproduction and extension

The offline test suite, cached-index inspection/search and frozen evaluation
form the fast reproduction path. These do not require re-encoding the corpus or
rerunning paid judging. Full live evaluation of 200 messages makes many provider
calls and can exceed 15 minutes; its runtime and cost depend on your provider.

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

## Limitations

Historical replies may be wrong, outdated or unresolved; model verification and
regex safety checks can miss errors. The submitted labels and author ratings are
small enough to review by hand but not big enough to settle product readiness.
The UI has no production authentication or account integrations. Exact in-memory
search and repeated freshness hashes suit this dataset, not unlimited-scale
serving. Model weights truncate long text according to their tokenizer limit.

See the per-file walkthroughs in `docs/`.
