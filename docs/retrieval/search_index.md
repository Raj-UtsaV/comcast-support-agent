# File walkthrough: `support_agent/retrieval/search_index.py`

A **search index** holds numerical vectors and connects each one to a historical
customer question and support reply. This module compares a new question's
vector with those stored vectors and returns matching evidence.

It takes already selected evidence from `evidence.py` and vectors produced by
`embeddings.py`. It does not load models, read datasets, save files or draft an
answer. Keeping these responsibilities separate makes the search implementation
replaceable without changing data preparation or model loading.

The [retrieval workflow](service.md) now connects these components through
`python -m support_agent.retrieval search`. It validates and masks incoming
messages before querying this index.

## How it is implemented

`create_search_index(config, records, vectors, embedding_identity=...)` builds a
`FaissSearchIndex`. Vector row `i` must represent `records[i]["customer_text"]`.
The caller is responsible for this alignment; numerical vectors alone cannot
prove which text produced them.

The constructor checks company ownership, the training-split marker, required
record fields and unique evidence IDs. Historical resolution must remain
unverified. It copies records and model metadata so subsequent changes to a
caller's dictionaries cannot change the index.

Both stored vectors and query vectors are converted to contiguous `float32`
arrays and normalized to length one. Wrong dimensions, zero vectors and
nonfinite values are rejected. Input arrays are copied before normalization.

FAISS `IndexFlatIP` compares every stored vector using the inner product. For
normalized stored and query vectors, that comparison is cosine similarity.
Higher scores indicate closer vector directions. This follows the
[FAISS cosine-search guidance](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances).
The index does not train or change model weights.

## Search behavior

Each search requires a company ID and the query encoder's complete identity.
A different company or model identity produces an error, even if the query's
number of dimensions happens to match. This is a local consistency check; the
eventual app must separately authenticate users and determine their company.

Search then:

1. Scores every record and orders candidates by descending similarity.
2. Uses the evidence ID to break exactly equal score ties consistently.
3. Rejects scores below the configured minimum; equality is accepted.
4. Applies the optional intent filter.
5. Keeps the highest-ranked eligible reply from each conversation.
6. Stops after `top_k` distinct conversations or returns fewer when insufficient
   eligible matches exist.

All candidates are considered before filtering and deduplication. Simply asking
FAISS for five rows could miss a valid sixth row when the first five come from
one conversation. This implementation avoids that behavior.

`intent` means the approved request-category ID. Filtering is disabled by
default because historical records have no approved intent annotations yet.
When enabled, a missing query intent returns no matches; an unknown label also
matches nothing. The module does not invent categories or annotate evidence.

The result is a list of dictionaries containing `evidence` and `similarity`.
Each evidence dictionary is a separate copy. Scores are clipped to `[-1, 1]`
to remove tiny floating-point overshoots; they are not probabilities of a
correct answer. An empty index returns an empty list for a valid query.

## Configuration

| Setting | Meaning |
| --- | --- |
| `company.id` | Company that owns every record in this index. |
| `retrieval.provider` | Currently supports `faiss`. |
| `retrieval.similarity` | Currently supports `cosine`. |
| `retrieval.top_k` | Maximum number of distinct conversations returned. |
| `retrieval.min_similarity` | Inclusive similarity cutoff between -1 and 1. |
| `retrieval.filter_by_intent` | Whether evidence must match the supplied intent ID. |

Settings are copied at construction. Create a new index object to apply changed
settings. Search always normalizes its vectors because cosine similarity
requires that behavior, even if embedding output normalization was disabled.

## Connect the existing modules

From the project root, using `.venv/bin/python`:

```python
from support_agent.shared.config import load_config
from support_agent.embeddings.encoder import create_embedder
from support_agent.data.evidence import collect_evidence
from support_agent.retrieval.search_index import create_search_index
from support_agent.shared.text import normalize_text

config = load_config("configs/comcast.yaml")
pairs, counts = collect_evidence(config)
encoder = create_embedder(config)

vectors = encoder.encode([pair["customer_text"] for pair in pairs])
index = create_search_index(
    config, pairs, vectors, embedding_identity=encoder.identity,
)

message, _ = normalize_text("My internet keeps disconnecting.", config)
matches = index.search(
    encoder.encode([message]),
    company_id=config["company"]["id"],
    embedding_identity=encoder.identity,
)

print(index.size, len(matches))
```

This example encodes all selected historical questions each time it runs.
For reuse across runs, [index_store.py](index_store.md) now saves the evidence
and vectors and reloads the index without re-encoding those questions.

## Limits and next responsibilities

This is an exact, in-memory CPU index. Storage grows with the number of vectors,
their dimensions and evidence text. Every query scans all vectors and sorts
the candidates, so it is not intended for arbitrarily large collections.
The separate provider boundary allows a more selective index later without
merging model or dataset logic into this file.

The index validates supplied training markers but does not independently reopen
source splits or human evaluation annotations. Use `collect_evidence` to enforce
those exclusions. After annotations change, reselect evidence and rebuild;
this in-memory object does not monitor files for changes. The saved-index
loader now checks source fingerprints and annotation changes before reuse.

The module preserves historical text and unverified resolution. Similarity does
not establish current policy, answer correctness or safety. Those checks belong
to the later support-agent pipeline.

## Verified in this step

On September 10, 2026, an offline integration check selected and encoded all
22,978 eligible historical pairs with the cached 384-dimensional model, then
built this in-memory index. One existing historical question and one
illustrative connection-problem query each returned five distinct conversations
above the configured `0.60` cutoff. The existing-question probe's best score
also exceeded `0.999`, checking that encoding and record lookup connect properly.

Python socket connections were blocked and the model loader used offline mode.
The full test suite passed 105 tests; lint and formatting checks passed too.
These checks establish module integration and search mechanics, not retrieval
accuracy or support-answer quality. No index file or evaluation scores were
saved in this step.
