"""Shared test settings: network access and real model credentials are disabled."""

import socket

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Tests must not make network calls")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)

    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_API_KEY",
        "JUDGE_PROVIDER",
        "JUDGE_MODEL",
        "JUDGE_API_KEY",
    ):
        monkeypatch.setenv(name, "")
