# File walkthrough: `tests/test_retrieval.py`

These tests reuse the synthetic prepared-project and test-encoder fixture from
`test_index_store.py`. The `ready` fixture builds a real saved FAISS-compatible
index, then points CLI configuration/model construction at that temporary setup.
No downloaded model or real customer data is needed.

The tests verify masking before query encoding and output, message-size limits,
Unicode expansion, blank inputs, approved category IDs, missing filtered intents,
unmatched categories, model-identity checks and stale-index rejection before
query-model loading.

CLI checks cover JSON output, model-free inspection, standard-input messages,
bounded input reads, progress on standard error, explicit rebuilds and invalid
argument combinations. Captured output is parsed as JSON instead of just checking
that the command returned successfully.

Run from the project root:

```bash
.venv/bin/python -m pytest tests/test_retrieval.py -q
```

These checks cover retrieval and its command-line interface, not classification,
reply quality or escalation decisions.
