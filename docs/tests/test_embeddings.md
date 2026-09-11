# File walkthrough: `tests/test_embeddings.py`

These offline tests replace the third-party model loader with a small synthetic
model inside the test process. No model weights are downloaded by pytest, and
synthetic vectors are never used by the application as a fallback.

The `provider` fixture reads shared embedding defaults, points its cache at a
temporary directory and installs the fake loader using `monkeypatch`. Tests
inspect the encoder's behavior and simulate broken model outputs.

Checks cover local-only loading, explicit download mode, configurable model
identity and device, batch size, ordered output, normalization, output numeric
format, empty inputs, invalid inputs, zero/nonfinite/wrong-sized vectors,
caller mutation and missing-cache failures.

Run from the project root:

```bash
.venv/bin/python -m pytest tests/test_embeddings.py -q
```

These are interface and validation checks, not semantic-relevance measurements.
The real pretrained model is checked separately with illustrative sentences;
that setup check does not produce agent evaluation scores.
