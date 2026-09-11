# File walkthrough: `support_agent/retrieval/service.py`

This module connects configuration, message cleaning, saved-index loading,
embedding and historical search. It supplies a reusable `retrieve` function and
three command-line commands. It does not classify messages, write a customer
reply or decide whether a request should be handled automatically.

## Commands

Run these from the project root. The Comcast index already exists, so start
with inspection or search:

```bash
.venv/bin/python -m support_agent.retrieval inspect --config configs/comcast.yaml

.venv/bin/python -m support_agent.retrieval search \
  --config configs/comcast.yaml \
  --message "My internet keeps disconnecting."
```

For a first build or an intentional rebuild:

```bash
.venv/bin/python -m support_agent.retrieval build --config configs/comcast.yaml

.venv/bin/python -m support_agent.retrieval build \
  --config configs/comcast.yaml --rebuild
```

Build uses the already cached model. Missing weights require the first-download
setup described in [embeddings.md](../embeddings/encoder.md); commands do not download a
different model or replace missing real data automatically. Rebuild preserves
older saved generations as described in [index_store.md](index_store.md).

To read a message from a file or another process, use standard input:

```bash
.venv/bin/python -m support_agent.retrieval search \
  --config configs/comcast.yaml --stdin < message.txt
```

`message.txt` is your input file, not a provided project artifact. Standard input
keeps its contents out of command arguments. The reader accepts at most the
configured character limit plus one character to detect oversized input.

Use exactly one of `--message` and `--stdin`. `--intent` accepts an existing
approved category ID; leave it out while the company taxonomy is still empty.
Search thresholds and result count come from YAML, not command-line defaults.

## How one search works

`retrieve(config, message, intent=None, embedder=None)` performs these steps:

1. Validate the configured character limit and reject blank or oversized input.
2. Normalize and mask text using `text.py`, retaining detected sensitive-data
   categories. Recheck length because normalization can expand some characters.
3. Check an explicitly supplied intent against approved company category IDs.
4. Reload and validate the saved index, including source/annotation fingerprints.
5. If the index has records and any required intent is present, obtain the
   cached encoder and compare its full identity with the saved index.
6. Encode only the cleaned incoming message and search historical evidence.
7. Return the masked query, detected categories, retrieval status and matches.

The embedding model's token limit remains separate from the configurable input
character limit. Passing the character check does not guarantee that a long
message fits entirely inside the model's token window.

The optional `embedder` argument lets tests or a future application reuse an
already loaded encoder. It does not bypass model-identity checks. Each call
still reloads the saved index so it checks current fingerprints. Loading and
hashing the saved data adds work per request; a later application can add a
careful cache while preserving these checks.

## Output

Successful commands print one JSON document to standard output. Library progress
is directed to standard error, so command output can be redirected to a JSON
file. The module itself does not save customer queries or search results.

Inspection reports company ID, indexed pair count and embedding identity
without loading an encoder. Search returns:

| Field | Meaning |
| --- | --- |
| `company_id` | Company selected through its configuration file. |
| `query.text` | Cleaned, masked customer message. |
| `query.sensitive_information` | Sensitive-data categories detected during masking. |
| `intent` | Supplied approved category, or `null`; no category is inferred here. |
| `status` | `matches_found`, `no_matches` or `missing_intent`. |
| `matches` | Historical evidence and cosine similarity scores. |

`missing_intent` means intent filtering is enabled but no intent was supplied.
`no_matches` means no eligible evidence was returned, including an empty index.
These statuses describe retrieval only. They are not safety decisions or proof
that the historical reply is suitable to send to a customer.

Missing/stale indexes, incompatible models and invalid inputs produce a readable
error on standard error and exit code 1. Invalid command syntax uses argparse's
exit code 2. A completed command returns 0 even if search finds no matches.
Masking retains the heuristic limitations described in [text.md](../shared/text.md).

The company configuration is chosen by the local caller. This command is a
development interface, not an authenticated multi-company service.

## Verification

The full offline suite passes 157 tests, including 25 tests of this module.
The tests exercise the real saved-index and search implementation with an
explicitly synthetic encoder. They do not fabricate relevance scores or agent
evaluation results.
