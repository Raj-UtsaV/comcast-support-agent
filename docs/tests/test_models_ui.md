# Model and web tests

`tests/test_models_ui.py` tests provider routing, ordered history, missing
credentials, redacted errors and model request boundaries.
`tests/test_customer_ui.py` covers chat history, reset, tampered conversation
tokens, input limits, asset serving and customer-safe errors using Flask test clients.
Run `.venv/bin/python -m pytest -q`. Tests do not require network or credentials.
