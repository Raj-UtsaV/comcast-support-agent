# File walkthrough: `support_agent/retrieval/index_state.py`

This small helper records what a saved index was built from. A **fingerprint**
is a SHA-256 hash of file contents or selected settings. Comparing fingerprints
lets the loader detect a changed input without encoding the dataset again.

`source_state(config)` fingerprints all five prepared splits, their preparation
manifest and the human evaluation annotation file. An absent annotation file
is recorded as `None`, so creating one later also makes the index stale.
Prepared source data must remain available when loading an index.

The state also includes a hash of dataset/split settings, company ID, model
name/revision/normalization, and search provider/metric. Source-code hashes
cover the configuration, cleaning, evidence, embedding, search and storage
modules. Installed numerical/model-library versions are recorded too. These
checks are deliberately conservative: even some harmless edits require rebuilds.

Absolute paths, batch size, device and cache location are excluded. The project
can therefore move without forcing re-encoding when its contents match.
Search result count, similarity cutoff and intent-filter settings can change
without rebuilding vectors. LLM credentials and prompts are not saved.
Dataset settings are stored only as a hash, not copied into the index manifest.

`check_encoder` compares the actual encoder's basic identity with configured
model settings. `storage_directory` builds a company-specific location under
`paths.artifacts_dir`. `file_hash` reads files in chunks through the standard
library, and `json_bytes` provides deterministic JSON serialization.

The helper checks prepared files; it does not reread the full raw CSV on every
load. After raw data or source-selection settings change, rerun preparation
before rebuilding the saved index. Hashes detect accidental changes, not a
malicious actor who can replace both data and its manifest.

Code paths are relative to the `support_agent` package root, for example
`embeddings/encoder.py` and `data/evidence.py`. This keeps fingerprints valid
across project-directory moves while still detecting edits inside feature
folders. A package reorganization changes those fingerprints and requires a
new saved-index generation.
