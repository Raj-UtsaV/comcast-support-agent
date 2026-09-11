# File walkthrough: `support_agent/agent/runtime.py`

The real factory validates approved categories and model credentials, then loads
one generator, encoder and saved index. `SavedRetriever` rechecks source hashes
around each search so cached resources do not silently use newly reserved golden
examples. A lock protects encoder use in a shared UI resource. Reload the runtime
after changes; the application cache key includes config and saved-index state.

Only explicit `demo_mode: true` with demo settings selects scripted clients.
No model name, company logic or request category is embedded in this module.

`VectorStore` describes the model identity and company-scoped search contract.
Alternative backends can implement that interface and their persistence factory.
