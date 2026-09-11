# Project folder structure

The implementation is grouped by responsibility. Start with the
[guided reading path](reading-guide.md) for a recommended file order and workflows.
The package root contains the package marker, main entry point, and setup orchestrator.

```text
comcast-support-agent/
├── app.py                      # Staff Flask entry point
├── customer_app.py             # Customer Flask entry point
├── Dockerfile
├── Procfile
├── requirements.txt
├── README.md
├── configs/
├── data/                       # Dataset, processed records and review sheets
├── artifacts/                  # Saved company search indexes
├── results/                    # Evaluation outputs
├── support_agent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── setup.py
│   ├── shared/
│   │   ├── config.py
│   │   ├── schemas.py
│   │   └── text.py
│   ├── data/
│   │   ├── __main__.py
│   │   ├── preparation.py
│   │   ├── conversations.py
│   │   ├── splits.py
│   │   ├── evidence.py
│   │   └── annotations.py
│   ├── embeddings/
│   │   └── encoder.py
│   ├── retrieval/
│   │   ├── __main__.py
│   │   ├── service.py
│   │   ├── search_index.py
│   │   ├── index_state.py
│   │   └── index_store.py
│   ├── models/
│   │   └── client.py
│   ├── agent/
│   │   ├── workflow.py
│   │   ├── safety.py
│   │   ├── taxonomy.py
│   │   ├── runtime.py
│   ├── evaluation/
│   │   ├── __main__.py
│   │   ├── runner.py
│   │   ├── baselines.py
│   │   ├── metrics.py
│   │   └── ratings.py
│   └── ui/
│       ├── customer.py
│       ├── conversation.py      # Live chat prompt and model verification
│       ├── channels.py
│       ├── dashboard.py
│       ├── web.py
│       ├── templates/          # base.html, customer.html, staff.html
│       └── static/             # app.js, style.css
├── docs/                       # Mirrors the feature folders above
└── tests/
```

Each feature folder also has an `__init__.py` package marker, omitted from the
tree for readability. The markers in `shared`, `data`, `embeddings`, `retrieval`,
`models`, `agent`, `evaluation` and `ui` contain only descriptions. They do not
load models, read datasets, or make API calls.

## How the folders connect

`shared` supplies configuration, text cleaning and typed inputs/outputs.
`data` prepares conversations, selects evidence and exports annotation sheets.
`embeddings` converts text to vectors. `retrieval` owns search and persistence.
`models` supplies the configurable LLM client. `agent` combines these components
into the support workflow. `evaluation` compares the agent with baselines and
imports human ratings. `ui` implements model-led customer chat, Flask routes,
HTML/CSS styling, and evaluation views for `customer_app.py` and `app.py`.

The root `data/` directory stores files; `support_agent/data/` contains Python
code that processes them. Raw data, YAML company settings and model caches stay
outside the Python packages.

## Commands and imports

The package `__main__.py` files delegate to the relevant `main()` function:

| Command | Implementation |
| --- | --- |
| `python -m support_agent analyse` | Root `support_agent/__main__.py` |
| `python -m support_agent setup` | Root entry point delegates to `support_agent/setup.py` |
| `python -m support_agent.data prepare` | `data/preparation.py` |
| `python -m support_agent.retrieval search` | `retrieval/service.py` |
| `python -m support_agent.evaluation run` | `evaluation/runner.py` |
| `python -m support_agent.data.annotations golden` | `data/annotations.py` |

Add the required `--config` and other arguments shown in the [README](../README.md).
Annotation export now uses `support_agent.data.annotations`. Python imports use
explicit feature paths, for example:

```python
from support_agent.shared.config import load_config
from support_agent.embeddings.encoder import create_embedder
from support_agent.agent.runtime import create_agent
```

The previous flat implementation files have been moved, so update any personal
scripts that import the old module paths. Project imports, tests and documentation
use the new paths. For example, the encoder walkthrough now lives at
[embeddings/encoder.md](embeddings/encoder.md).
