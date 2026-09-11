"""Provider-boundary validation and Streamlit's explicit demo interface."""

import os
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from support_agent.models.client import create_generator
from support_agent.shared.config import PROJECT_ROOT, ConfigError, load_config
from support_agent.shared.schemas import Classification


@pytest.mark.parametrize(
    ("module", "command"),
    [
        ("data", "prepare"),
        ("retrieval", "search"),
        ("evaluation", "run"),
        ("data.annotations", "golden"),
    ],
)
def test_package_commands_work_from_another_directory(module, command, tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", f"support_agent.{module}", command, "--help"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "--config" in result.stdout
    assert "RuntimeWarning" not in result.stderr


def configured(monkeypatch):
    config = load_config("configs/demo.yaml")
    config["models"]["generator"].update(provider="example", name="example/model")
    monkeypatch.setenv("LLM_API_KEY", "synthetic-secret")
    return config


def test_provider_schema_and_secret_redaction(monkeypatch):
    config = configured(monkeypatch)

    def complete(**kwargs):
        assert kwargs["custom_llm_provider"] == "example"
        assert kwargs["response_format"] == {"type": "json_object"}
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content='{"intent": null, "confidence": 0.2, "reason": "uncertain"}'
                    ),
                )
            ]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=complete))
    client = create_generator(config)
    assert client.generate("classify", {}, Classification, "Classify").intent is None

    def failure(**kwargs):
        raise ValueError("synthetic-secret private payload")

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=failure))
    with pytest.raises(RuntimeError) as error:
        client.generate("classify", {}, Classification, "Classify")
    assert "synthetic-secret" not in str(error.value)


def test_missing_credentials_fail_before_provider_import():
    config = load_config("configs/demo.yaml")
    config["models"]["generator"].update(provider="example", name="example/model")
    with pytest.raises(ConfigError, match="API-key"):
        create_generator(config)


def test_provider_receives_ordered_conversation_turns(monkeypatch):
    config = configured(monkeypatch)

    def complete(**kwargs):
        messages = kwargs["messages"]
        assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
        assert messages[1]["content"] == "My internet stopped working."
        assert messages[2]["content"] == "One device or all devices?"
        assert json.loads(messages[3]["content"])["data"]["message"] == "All devices"
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content='{"intent": null, "confidence": 0.2, "reason": "test"}'),
        )])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=complete))
    create_generator(config).generate("classify", {
        "message": "All devices",
        "history": [
            {"role": "customer", "text": "My internet stopped working."},
            {"role": "agent", "text": "One device or all devices?"},
        ],
    }, Classification, "Classify the ongoing issue")


def test_streamlit_demo_can_analyse_without_network_or_credentials():
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    app.sidebar.selectbox[0].select(PROJECT_ROOT / "configs/demo.yaml").run()
    app.text_area[0].set_value("My connection stopped working.")
    next(button for button in app.button if button.label == "Analyse").click().run()
    assert not app.exception
    assert any("SYNTHETIC DEMO" in warning.value for warning in app.warning)
    assert any("Auto-handle candidate" in success.value for success in app.success)
    app.text_area[0].set_value("A different customer question.").run()
    assert not app.success
