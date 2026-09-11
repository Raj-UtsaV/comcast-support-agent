# File walkthrough: `support_agent/data/preparation.py`

This module turns the shared Twitter CSV into cleaned conversations for the
configured company. It separates complete conversations by time and exports
customer messages for reviewing request categories. It runs locally without
an LLM, API keys or model training.

## Run it

From the project root:

```bash
.venv/bin/python -m support_agent.data prepare --config configs/comcast.yaml
```

Missing real data produces an error with its expected location; synthetic data
is never substituted. Existing processed output is not overwritten. To prepare
another version, choose a new `paths.processed_dir` in company configuration.

## Smaller modules and responsibilities

The original 805-line file has been separated into focused modules. `data.py`
now coordinates preparation and output; it imports helpers from:

- [config.py](../shared/config.md): company settings and environment loading.
- [text.py](../shared/text.md): cleaning, masking and timestamp parsing.
- [conversations.py](conversations.md): CSV reading and conversation connections.
- [splits.py](splits.md): chronological splits and golden exclusions.

The command and processed message format remain the same.

| Function | What it does |
| --- | --- |
| `load_config` | Safely reads and merges base/company YAML, loads `.env`, validates preparation settings and resolves paths. |
| `normalize_text` | Normalizes text, masks sensitive information and returns detected categories. |
| `useful_reply` | Checks the configured minimum length and greeting/DM-only filters. |
| `index_twitter_csv` | Reads CSV chunks and stores source messages and connections in temporary SQLite tables. |
| `company_groups` | Follows message connections for the selected company and groups conversations. |
| `golden_conversations` | Identifies complete conversations reserved by existing human evaluation annotations. |
| `split_conversations` | Assigns complete conversations to chronological ranges or holds them aside. |
| `prepare_data` | Coordinates processing and publishes normalized files and a preparation summary. |
| `main` | Provides the command-line entry point and readable errors. |

The loader lives in `config.py` so modules can share it without loading models
or importing the entire data-preparation workflow.

Dictionary settings merge recursively; company lists replace shared lists.
Duplicate YAML keys, unsafe company IDs, paths outside the project and invalid
split fractions are rejected. Existing environment values take precedence over
`.env`. Unset model placeholders remain unresolved until a model is used.
The later model factory must validate provider/model credentials itself.

## Following conversations across chunks

SQLite is a local file-based database requiring no server. The temporary
database stores source IDs, parent IDs and response connections. It lets the
reader follow links across chunks rather than treating a chunk as a complete
conversation.

The search starts from configured company support accounts and follows both
reply-link columns. Customer roles come from the configured source flags.
Other companies' support accounts are blocked: they cannot become evidence or
connecting points in this company's conversations.

Missing referenced IDs can connect orphan sibling messages. These IDs provide
connections only; no missing message text is invented. Empty messages are
removed after grouping so known connections remain intact.

Each connected group receives its lexicographically smallest source ID as its
`conversation_id`. This is a deterministic grouping rule, not a claim that the
ID belongs to the first message chronologically. It can refer to a missing
source message. Changing source connections can change conversation IDs, so
existing golden annotations that no longer match cause an error.

Duplicate source IDs with identical contents are removed. Conflicting contents
for the same ID cause failure. Repeated text with different IDs is retained:
it may be a customer reporting the same unresolved problem.

`ADAPTERS` selects a source-format reader by its configured name. An adapter
simply means code that interprets a dataset format. Another Twitter company
needs different configuration; another dataset structure needs another adapter.
No company name, embedding model or intent label is embedded in this module.

## Normalized records and masking

Each JSONL record has these fields. JSONL means one JSON object per line:

```text
company_id, conversation_id, message_id, parent_message_id,
timestamp, role, text, channel, metadata
```

Timestamps become UTC values, and roles become `customer` or `agent`. The
timestamp parser handles the source's English month/day abbreviations without
changing the application's process-wide language setting.

Email addresses, phone-like numbers, labelled account numbers and usernames
are replaced by markers such as `[EMAIL]` and `[PHONE]`. Existing source masks
`__email__` and `__phone__` are recognized too. Detection categories are retained
in metadata for later safety decisions. Patterns are generic text-format rules;
selected categories and reply-quality settings come from YAML.

Metadata also records whether a reply passes the basic quality filter and
whether a parent is missing or belongs to another company. Successful
resolution is always marked unverified. Low-quality replies remain in
conversation history, marked unusable as retrieval evidence; the retrieval
selection module now enforces this distinction; see [evidence.md](evidence.md).

Masking is heuristic: some number-like text can be overmasked and unusual
formats can be missed. An identifier flag does not prove the text is secret.
These output markers are not a guarantee of complete sensitive-data removal.

## Separating development and evaluation

The boundaries come from ordered conversation end times and the configured
fractions, using midpoints between adjacent end times. Each full conversation
span determines its assignment:

- **Training:** all messages precede the validation boundary. This supplies
  historical evidence and development examples; no model weights are trained.
- **Validation:** all messages fall between the boundaries.
- **Evaluation:** all messages fall after the evaluation boundary.
- **Quarantine:** the conversation crosses a boundary and is held aside.
- **Golden:** an existing hand-labelled evaluation file reserves this complete
  conversation, excluding it from other splits and development examples.

The development/evaluation time ranges do not overlap. Small or highly
overlapping datasets can leave a split empty; that produces an error rather
than silently changing the rules.

Golden annotations require `company_id` and `conversation_id`; if `message_id`
is provided, its conversation is checked too. Golden examples should be drawn
from held-out conversations. The exclusion guard also protects an earlier
conversation if it is annotated, but that does not validate its sampling method.
When no annotation file exists, preparation records that fact and invents none.

The evidence selector rechecks golden exclusions, including annotations added
after this preparation run. A later persisted search index must also reject
stale evidence when annotations change.

## Output and observed first run

The real CSV produced 72,288 messages across 24,065 company conversations:

| Output | Messages | Conversations |
| --- | ---: | ---: |
| `train.jsonl` | 49,950 | 16,845 |
| `validation.jsonl` | 9,589 | 3,517 |
| `evaluation.jsonl` | 9,881 | 3,519 |
| `quarantine.jsonl` | 2,868 | 184 |
| `golden.jsonl` | 0 | 0 |

Files are under `data/processed/comcast/`. Also produced:

- `intent_review.csv`: 500 seeded training customer messages with blank
  `proposed_intent` and `review_notes` columns. Spreadsheet formula prefixes are
  escaped in this export only; normalized JSONL text is not changed by that step.
- `manifest.json`: source checksum, local configuration fingerprint, counts,
  time boundaries and `evaluation_status: not_run`.

These are observed preparation counts, **not agent performance metrics**.
No golden annotations, intent categories or evaluation scores have been created.
The configuration fingerprint includes resolved local paths, and no API keys
are saved in the manifest.

## Memory, temporary files and review

The complete CSV is not loaded into memory. The temporary database stores the
source lookup on disk; memory holds a CSV chunk and the selected company's
connected messages. Memory therefore grows with the selected company's size.
This is not an unbounded streaming solution for arbitrarily large companies.

Temporary database files can contain unmasked source text. They live under the
ignored processed-data parent and are removed after success or handled errors.
An abrupt process termination can leave a `.prepare-*` directory. Normalized
outputs are published only after the complete preparation succeeds.

The code uses multiline expressions and blank lines between logical steps for
readability. Review company selection, missing-link handling, masking and time
separation before continuing to retrieval and agent behavior.
