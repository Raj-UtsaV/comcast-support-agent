# File walkthrough: `tests/test_index_store.py`

These tests run real data preparation, saved-file IO and FAISS search against
temporary synthetic conversations. They reuse `setup_project` from the
existing pipeline tests. The only substitute is an explicitly synthetic
encoder, whose identity is marked as test data and whose calls are counted.

The tests check matching search results after reload, no encoder use during
reload, explicit rebuilds, retained old versions, new golden exclusions, changed
prepared files/settings/code/dependencies, corruption checks, shape and company
validation, disabled pickle loading, failed-write recovery, generation-path
confinement and moving saved files to a different artifact directory. They also
check that a second builder respects an existing lock and that inputs changing
during encoding prevent publication.

`current_folder` locates the saved generation. `refresh_manifest` deliberately
updates checksums in corruption tests so those tests reach the deeper structural
validation instead of stopping at the checksum check.

Run from the project root:

```bash
.venv/bin/python -m pytest tests/test_index_store.py -q
```

Shared test settings block Python network calls. These checks do not measure
search relevance or support-agent quality.
