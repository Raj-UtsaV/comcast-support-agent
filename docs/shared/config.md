# File walkthrough: `support_agent/shared/config.py`

This module owns shared configuration loading. It was extracted from `data.py`
so data preparation, retrieval and the future agent can use the same settings
without importing processing code or loading models.

`load_config` reads shared and company YAML, rejects duplicate keys, merges
dictionaries, replaces overridden lists and loads `.env` without replacing
existing environment values. It checks company IDs, project-relative paths,
source settings and split fractions. Missing model environment values stay
unresolved until the corresponding model is needed.

`ConfigError` provides readable configuration failures without printing
environment-expanded values that might contain credentials. `PROJECT_ROOT`
keeps relative paths independent of the shell's current directory.

The extraction preserves the existing behavior and command-line usage. Its
regression tests live in `tests/test_pipeline.py`.
