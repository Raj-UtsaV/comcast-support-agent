# File walkthrough: `support_agent/embeddings/encoder.py`

An **embedding** is a numerical representation of text. The later search module
will compare these representations to find historical questions related to a
new customer message. This file converts text; it does not choose evidence,
search conversations, classify requests or draft replies.

## How it works

`create_embedder(config)` constructs the configured encoder. `TextEmbedder`
describes the small interface search will use: `encode`, `dimension` and
`identity`. A Python `Protocol` describes that interface without requiring
future providers to inherit from a particular implementation.

`SentenceTransformerEmbedder` validates its settings, loads the pretrained
model once and reuses it. The heavy model library is imported only when the
encoder is constructed. The first supported provider is
`sentence_transformers`; other values produce an error.

`encode(texts)` accepts a list or tuple of nonempty strings and preserves their
order. The library processes them in batches. The returned NumPy array has one
row per input and one column per model dimension. Its values use `float32`,
the numeric format intended for the later FAISS search index.

The code checks the array's size, rejects nonfinite numbers and zero vectors,
and makes each row have length one when normalization is enabled. An empty
list returns an empty array with the correct number of columns. A plain string
is rejected so it cannot accidentally be interpreted as individual characters.

## Settings and reproducibility

| YAML setting | Purpose |
| --- | --- |
| `models.embedding.provider` | Select the provider implementation. |
| `models.embedding.name` | Full public model repository ID. |
| `models.embedding.revision` | Immutable 40-character commit ID for model files. |
| `models.embedding.device` | Use `cpu`, `mps`, `cuda` or a numbered CUDA device. |
| `models.embedding.batch_size` | Number of inputs processed together by the model. |
| `models.embedding.normalize_embeddings` | Normalize output rows to length one. |
| `paths.model_cache` | Cache location resolved inside the project by `load_config`. |

CPU is the default for this project's installed environment. Other devices
require compatible hardware and libraries. Model names and dimensions are not
hardcoded in Python. Changing the model requires changing its revision too.
The model weights are used as downloaded; this module performs no training.

`identity` returns a separate dictionary containing the provider, repository,
revision, normalization setting, vector dimension, model sequence limit and
Sentence Transformers version. The future index must store this information
and reject an incompatible query encoder. Matching dimensions alone is not
enough to make two models compatible. This metadata is not a promise of
bit-for-bit equality across all hardware and dependency versions.

## First download and later local use

From the project root, using `.venv/bin/python`:

```python
from support_agent.shared.config import load_config
from support_agent.embeddings.encoder import create_embedder
from support_agent.shared.text import normalize_text

config = load_config("configs/comcast.yaml")

# Allow downloading the configured public model on the first setup run.
encoder = create_embedder(config, local_files_only=False)

message, _ = normalize_text("My internet keeps disconnecting.", config)
vectors = encoder.encode([message])

print(vectors.shape)
print(encoder.identity)
```

Later, use `create_embedder(config)`; it requests local files only by default.
If the selected revision is missing, loading fails with a setup error. There
is no substitute model or synthetic-vector fallback. Cached weights live in
the ignored project cache. `paths.model_cache` is passed directly to the model
loader, so the module does not depend on a shell-relative `HF_HOME` setting.

The loader uses the library's `revision`, `cache_folder` and `local_files_only`
options, disables custom repository code, and supplies no Hub authentication
token. See the [Sentence Transformers API](https://sbert.net/docs/package_reference/sentence_transformer/model.html).
This initial implementation supports public Hub repositories, not private
repositories or arbitrary local model directories.

## Limits and the next module

The default model is `sentence-transformers/all-MiniLM-L6-v2`. Its model card
describes 384-dimensional sentence vectors and truncation beyond 256 word
pieces; a word piece is a tokenizer unit and need not be a complete word.
See the [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).
The loaded model determines these limits; the Python code does not fix them.

This module does not clean or mask text itself. Callers must use `text.py`
before passing customer messages; `evidence.py` already masks historical pairs.
Encoding runs locally. Downloading model files does not upload input texts.
Long input can lose information through the model's normal truncation behavior.

Batching bounds model work per batch, but the returned array holds all requested
vectors. Very large corpora will need the index builder to request separate
chunks. Similar vectors do not prove that a reply is correct or safe.

The separate [search index](../retrieval/search_index.md) now indexes selected historical
customer questions and returns their associated replies in memory.
[index_store.py](../retrieval/index_store.md) saves and reloads its evidence and vectors.
No search index is created by the embedding module itself.

## Verified in this step

On September 10, 2026, the configured revision downloaded successfully and
encoded three illustrative sentences into a `(3, 384)` `float32` array. Output
rows had length one, and identical inputs produced matching vectors.

A fresh Python process then loaded the cached model and repeated these checks
with Hub offline mode enabled and Python socket connections blocked. The empty
input case returned shape `(0, 384)`. This is a model-loading and encoding check,
not a retrieval benchmark or agent evaluation. The full offline test suite
passed 69 tests; formatting and lint checks also passed.
