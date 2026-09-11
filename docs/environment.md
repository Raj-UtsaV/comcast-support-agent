# File walkthrough: `.env.example`

Environment variables are named settings supplied outside Python code. This
template lists the settings needed for real LLM calls and local model caching.
It contains no API keys and deliberately does not choose a paid provider or
model for you.

Copy `.env.example` to `.env` if `.env` does not already exist, then fill in the
values locally. `.env` is ignored by Git; the template remains trackable.
Do not overwrite an existing `.env` while repeating setup.

| Setting | Meaning |
| --- | --- |
| `LLM_PROVIDER` | Provider supported by the LLM client for classification and drafting. |
| `LLM_MODEL` | Model name accepted by that provider. |
| `LLM_API_KEY` | Credential for those calls. |
| `JUDGE_PROVIDER`, `JUDGE_MODEL`, `JUDGE_API_KEY` | Equivalent settings for the evaluation judge. |
| `HF_HOME` | Local folder for pretrained embedding-model downloads. |
| `HF_HUB_DISABLE_TELEMETRY` | Disables Hugging Face library telemetry. |
| `LITELLM_LOCAL_MODEL_COST_MAP` | Uses LiteLLM's bundled model metadata instead of downloading that metadata at import time. |

The shared YAML uses placeholders such as `${LLM_PROVIDER}` and names the key
variable with `api_key_env: LLM_API_KEY`. The loader must resolve settings only
when that component is used, never print API keys, and keep already-set process
environment variables in preference to `.env` values.

Data preparation can run with all six provider/model/key values empty. Real
classification and drafting require generator settings. Full evaluation also
requires judge settings. Missing required settings must produce a clear error,
not a silent fallback to a fake reply.

Tests inject fake models explicitly and must not call external APIs. Loading an
environment file does not itself make any LLM calls or upload customer messages.
