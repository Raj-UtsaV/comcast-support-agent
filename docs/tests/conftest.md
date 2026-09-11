# File walkthrough: `tests/conftest.py`

Pytest automatically loads this file for the tests in this directory.
Its `offline` fixture runs before every test, blocks Python socket connections
and clears the configured LLM and judge environment variables for that test.
Pytest's `monkeypatch` restores those changes afterwards.

This shared setup previously lived in `test_pipeline.py`. Moving it here gives
the new evidence tests the same offline settings without duplicating code.
It guards normal Python network calls; it is not an operating-system sandbox.
