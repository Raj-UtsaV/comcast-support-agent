# test_models_ui.py

Provider tests replace only the LiteLLM boundary to check JSON validation,
configured routing, missing credentials and redacted exceptions. Streamlit's
AppTest loads the real website, selects its explicit demo and submits a message
with network calls blocked. This verifies UI wiring without presenting scripted
outputs as real model performance.

Package-command tests run data, retrieval, evaluation and annotation help in
subprocesses from another working directory. They verify the reorganized entry
points import successfully without runpy warnings.
