# File walkthrough: `support_agent/retrieval/index_store.py`

This module saves selected evidence and its vectors, then reloads them without
running the embedding model over the historical dataset again. A saved version
is called a **generation**: a directory containing a complete matching set of
records, vectors and metadata.

You can now call this workflow through the [retrieval commands](service.md):
`python -m support_agent.retrieval build --config configs/comcast.yaml` or
`inspect` with the same configuration argument. Add `--rebuild` to intentionally
replace the current saved version.

The module reconstructs the lightweight FAISS `IndexFlatIP` structure from the
saved vectors. It does not deserialize a native FAISS binary or use Python
pickle. Model loading, evidence selection and search still live in their own
modules.

## Build, load and rebuild

From the project root, using `.venv/bin/python`:

```python
from support_agent.shared.config import load_config
from support_agent.retrieval.index_store import build_saved_index, load_saved_index

config = load_config("configs/comcast.yaml")

# First build: select evidence, use the cached model, encode and save.
index = build_saved_index(config)

# Later runs: load saved vectors; no encoder is constructed here.
index = load_saved_index(config)

# Deliberately replace the current version after relevant inputs change.
# index = build_saved_index(config, rebuild=True)
```

Normal builds refuse to replace an existing version. `rebuild=True` explicitly
publishes a new version and keeps the previous directory. A stale index is
reported as an error; the loader does not silently rebuild or substitute data.
For changed raw data or source-selection settings, prepare the data again first.

## Files and publication

Files live beneath `paths.artifacts_dir/{company_id}/search/`:

```text
search/
  current.json
  index-<generated ID>/
    evidence.jsonl
    vectors.npy
    manifest.json
```

- `evidence.jsonl` contains the selected historical pairs in vector-row order.
- `vectors.npy` contains the numerical vectors, saved with pickle disabled.
- `manifest.json` records company, model identity, row count, selection counts,
  build time, source fingerprints and checksums for the two data files.
- `current.json` identifies the published directory and its manifest checksum.

A build takes a directory lock to prevent competing builders, fingerprints its
inputs, selects evidence and constructs a validated in-memory index. It writes
a separate generation, rechecks the inputs, then atomically replaces the small
`current.json` pointer. Readers therefore see a complete old or new generation.
Handled failures remove the incomplete generation and leave the current pointer
unchanged. Old completed generations are not automatically deleted.

An abrupt process termination can leave an unreferenced generation or a
`.build-lock` directory. Confirm no builder is active before removing an
abandoned lock. Publication protects against partial application writes; it is
not a guarantee against every disk failure or power loss.

## Loading and stale-data checks

The loader reads the current pointer once and confines its generation path to
the company's directory. It checks the manifest checksum, company and schema,
then compares current source state with the saved state. See
[index_state.md](index_state.md) for the fingerprint contents.

Checks include changed prepared splits, added/removed/edited human evaluation
annotations, embedding configuration, relevant source code and dependency
versions. The record and vector file checksums are verified before parsing
their exact bytes. The loader disables pickle and reconstructs the search
object through its normal record, shape, company and vector validation.
NumPy's [`allow_pickle=False` option](https://numpy.org/doc/stable/reference/generated/numpy.load.html)
rejects stored object arrays rather than loading pickled Python objects.

Current search thresholds, result count and intent-filter settings apply when
loading; changing them does not require re-encoding. The loaded object still
requires a matching model identity when searching. An encoder is needed for a
new question, but not for loading the saved historical index.

## Limits

Fingerprints are checked before and after build/load. An already returned
in-memory index does not continuously monitor files: reload or rebuild after
changing inputs, and avoid modifying data during a running operation.
Checksums detect accidental corruption, not an attacker who controls both the
files and their checksums. Treat the artifact directory as local application
storage, not an upload endpoint for arbitrary files.

Each generation retains the full evidence and vector arrays. Builds and loads
hold these in memory; disk use grows when old versions are retained. No LLM
credentials, generated replies or evaluation scores are stored by this module.

## Verified in this step

On September 10, 2026, the real-data integration check saved 22,978 historical
pairs with 384-dimensional vectors. Reloading produced identical evidence and
scores for an illustrative connection-problem query, with five returned
conversations. The build and comparison ran with network connections blocked.

The full offline test suite passed 132 tests, including explicit checks that
reloading neither constructs nor calls an encoder. Lint and formatting checks
passed. These are storage/integration checks, not agent-quality measurements.
The first Comcast index has already been built; use `load_saved_index(config)`
for normal reuse instead of repeating the first-build example.
