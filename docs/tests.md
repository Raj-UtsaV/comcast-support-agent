# File walkthrough: `tests/test_pipeline.py`

The current tests cover data preparation using small synthetic conversations
defined inside the test file. They do not contain copied real customer text.

Run from the project root:

```bash
.venv/bin/python -m pytest -q tests/test_pipeline.py
```

Each test creates a temporary project, source CSV and company configuration.
The company is named `example`, showing that processing does not depend on
Comcast. One test renames all source columns to check configurable mapping.
One-row CSV chunks force replies and customer messages into different chunks.

Checks cover configuration merging, environment precedence, invalid YAML and
paths, company separation, duplicate IDs, empty messages, masking, reply quality,
missing parents, response-only links, cycles, golden-set exclusion, chronological
separation, missing input and existing output. Network connections are disabled
in every test by the shared [conftest.py](tests/conftest.md) fixture, and
temporary fixtures are cleaned up automatically.

The first run passed all 20 preparation tests. These checks verify processing
behavior, not headline agent performance. The full offline suite now also
covers retrieval, classification, generation, escalation and evaluation.

Historical-pair selection now has separate tests documented in
[test_evidence.md](tests/test_evidence.md). Run `.venv/bin/python -m pytest -q`
to check both preparation and evidence selection.

The embedding wrapper has separate offline tests documented in
[test_embeddings.md](tests/test_embeddings.md). The full pytest command also
includes these checks without loading or downloading a real model.

The [search-index tests](tests/test_search_index.md) use real FAISS with
synthetic vectors to verify ranking, thresholds, conversation deduplication,
company ownership and model compatibility. They are included in the same
offline pytest command.

[Saved-index tests](tests/test_index_store.md) verify round-trip search results,
stale-data rejection, corruption checks, explicit rebuilds, retained previous
versions and failed-write recovery. Reload tests also check that no encoder is
constructed or called.

The [retrieval API and CLI tests](tests/test_retrieval.md) verify message masking,
input limits, approved intent IDs, JSON output, standard input and command errors.
They reuse saved synthetic evidence and are part of the same offline suite.

The [agent tests](tests/test_agent.md) cover classification failures, unsafe
drafts, evidence checks, masking and escalation. The
[provider/UI tests](tests/test_models_ui.md) check model routing, sanitized
errors and actual Streamlit demo interactions. The
[evaluation tests](tests/test_evaluation.md) exercise both baselines, saved
reports, review exports and exact-reply human-rating imports. All model results
in tests are injected fixtures, not measured customer-support performance.
