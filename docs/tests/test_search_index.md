# File walkthrough: `tests/test_search_index.py`

These tests use the installed FAISS library with small synthetic evidence
records and two-dimensional vectors whose cosine scores are known. They do not
load an embedding model or contact external services.

The `inputs` fixture supplies shared settings, four records, vectors and an
explicitly synthetic encoder identity. Two records share one conversation so
tests can catch incorrect filtering and deduplication. Small helpers build and
query the real index implementation.

Checks cover cosine ranking, inclusive thresholds, fewer-than-requested results,
empty results, deterministic equal-score ordering, distinct conversations,
intent filtering, company ownership, model compatibility, caller mutation,
duplicate IDs, invalid evidence, invalid vectors, invalid settings and an empty
index.

Run from the project root:

```bash
.venv/bin/python -m pytest tests/test_search_index.py -q
```

These tests verify search mechanics. They do not measure whether retrieved
historical replies correctly or safely answer real customer questions.
