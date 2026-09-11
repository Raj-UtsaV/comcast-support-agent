# Rebuild the local data and vector index

## One-command setup

From the project directory, run:

```bash
.venv/bin/python -m support_agent setup --config configs/comcast.yaml
```

This prepares missing processed data, loads the embedding model (allowing a
download if needed), builds the vector index, and validates the saved files.
It requires the raw CSV, installed dependencies, and internet access if model
weights are missing. It does not need Groq credentials or run LLM evaluation.
Existing processed data is preserved. A valid existing index is reused without
loading the model. Invalid or stale indexes fail visibly; use `--rebuild` to
generate a new index from the existing processed data. To reprocess changed raw
data or preparation settings, choose a new `paths.processed_dir` first.

Launch the website separately with `.venv/bin/streamlit run app.py`.

## Individual pipeline steps

The cleanup removed `data/processed/comcast/` and `artifacts/comcast/`.
Source code, configurations, `.env`, the raw CSV, review templates, `.venv`,
and downloaded embedding weights were preserved.

Stop any running Streamlit process with Ctrl+C before rebuilding. Run these
commands in order; continue to the next step only when the previous one succeeds.

```bash
cd /mnt/sata/Hiver/comcast-support-agent
source .venv/bin/activate

# 1. Recreate conversation splits, manifest, and blank intent-review sheet.
python -m support_agent.data prepare --config configs/comcast.yaml

# 2. Encode historical evidence and save the vector index.
python -m support_agent.retrieval build --config configs/comcast.yaml

# 3. Validate the index and try a local search.
python -m support_agent.retrieval inspect --config configs/comcast.yaml
python -m support_agent.retrieval search --config configs/comcast.yaml \
  --message "My internet keeps disconnecting."

# 4. Check live-agent setup, then launch the website.
python -m support_agent check --config configs/comcast.yaml
streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501 and select **comcast**. Live replies require a Groq
API key in `.env` and reviewed categories in `configs/comcast.yaml`. The judge
key is needed only for evaluation. Preparation and index building run locally
without an LLM API key. Building the index encodes the corpus and may take time.

Preparation refuses to overwrite an existing processed directory. After the
first successful preparation, skip step 1 for later index-only rebuilds and
add `--rebuild` to step 2. A normal app restart does not need this pipeline.

## If the embedding weights are removed later

Run this before step 2; it permits downloading the configured public model:

```bash
python - <<'PY'
from support_agent.shared.config import load_config
from support_agent.embeddings.encoder import create_embedder

create_embedder(load_config("configs/comcast.yaml"), local_files_only=False)
PY
```

If the raw CSV is removed, follow [dataset.md](dataset.md) to obtain it again.
Human labels and review decisions cannot be regenerated automatically; keep
those files when doing future cleanups.
