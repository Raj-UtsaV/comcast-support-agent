# File walkthrough: `requirements.txt`

This file lists the Python packages used by the project. Each `==` specifies
the exact version of a directly used package. This avoids silently switching
those packages on the next installation. Indirect dependencies are still
resolved by the installer; this is not a complete dependency lockfile.

## Package purposes

| Package | Why it is included |
| --- | --- |
| PyYAML | Read company and shared configuration safely. |
| python-dotenv | Load local environment settings without replacing existing environment variables. |
| Pydantic | Validate structured requests, model outputs and evaluation scores. |
| NumPy | Work with numerical embedding vectors. |
| SciPy | Calculate rank correlation for judge/human comparisons. |
| scikit-learn | TF-IDF baseline, classification metrics and Cohen's kappa agreement metric. It is not used to train an intent classifier. |
| PyTorch | Run the pretrained embedding model on the CPU. |
| torchvision | Supply the image transforms imported by Transformers, including the ZoeDepth image processor; installed from the PyTorch CPU index. |
| Sentence Transformers | Turn messages into embeddings: numerical representations used for similarity search. |
| FAISS CPU | Search those vectors without requiring a GPU or database service. |
| LiteLLM | Provide a common calling interface for supported LLM providers. The selected provider and model remain in configuration. |
| Flask | Serve the HTML/CSS customer chat and staff dashboard. |
| pytest | Run tests using synthetic data and fake models, without paid API calls. |

The data pipeline uses Python's built-in CSV and SQLite modules. SQLite is a
small database stored in a local file; it lets preparation follow message links
without keeping the complete Twitter CSV in memory. No database server is
required.

## Installation

Run from the project root using Python 3.12. With `uv`, a Python environment and
package installer:

```bash
uv venv --python 3.12 --seed .venv
uv pip install --python .venv/bin/python --torch-backend cpu -r requirements.txt
uv pip check --python .venv/bin/python
```

On this workstation, the Python download and package caches are kept inside
the project using `UV_PYTHON_INSTALL_DIR=.cache/python` and
`UV_CACHE_DIR=.cache/uv`. The `.venv` environment is also local and ignored by
Git. These choices do not replace the workstation's system Python.

For an existing Python 3.12 installation, the equivalent pip workflow is:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

The CPU selection avoids downloading GPU runtime packages for this application.
Commands above use Linux/macOS executable paths; Windows environments use
`.venv\Scripts\python.exe`. Only the local Linux installation is being checked
during this implementation step.

Installing these packages does not download model weights or run evaluation.
The pretrained embedding weights will be cached when retrieval is implemented.
LLM API credentials are needed only when the real model client is used.

## References

- [Sentence Transformers installation and usage](https://www.sbert.net/docs/installation.html).
- [PyTorch installation](https://pytorch.org/get-started/locally/).
- [LiteLLM structured outputs](https://docs.litellm.ai/docs/completion/json_mode).
- [uv Python installation](https://docs.astral.sh/uv/guides/install-python/).
- Exact package releases are published on [PyPI](https://pypi.org/).

## Verified installation

The dependencies installed successfully in the local Linux environment using
Python 3.12.14 and PyTorch 2.14.0+cpu. `pip check` reported no broken
requirements. All 12 directly listed packages imported successfully with
network connections disabled. No embedding weights were downloaded and no LLM
requests were made. The data-preparation command and its tests also ran in this
environment.
