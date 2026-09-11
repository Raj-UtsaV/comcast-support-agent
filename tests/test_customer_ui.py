"""Customer chat behavior without provider calls or customer data."""

from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from support_agent.shared.config import PROJECT_ROOT, load_config
from support_agent.ui import customer


def customer_app(monkeypatch):
    config = load_config("configs/demo.yaml")
    monkeypatch.setattr(customer, "load_config", lambda path: config)
    customer.customer_runtime.clear()
    return AppTest.from_file(str(PROJECT_ROOT / "customer_app.py"), default_timeout=20).run()


def test_customer_chat_topics_followup_and_reset(monkeypatch):
    app = customer_app(monkeypatch)
    assert not app.exception
    assert not app.sidebar.selectbox and not app.tabs
    next(b for b in app.button if b.label == "Internet connection").click().run()
    assert not app.exception
    assert len(app.chat_message) == 2
    assert "securely connected" in app.chat_message[1].text[0].value
    app.chat_input[0].set_value("Please cancel my account.").run()
    assert not app.exception
    assert len(app.chat_message) == 4
    assert "cannot transfer you" in app.chat_message[-1].text[0].value
    next(b for b in app.button if b.label == "New conversation").click().run()
    assert not app.chat_message


def test_customer_setup_errors_never_expose_internal_details(monkeypatch):
    app = customer_app(monkeypatch)

    def fail(*args):
        raise RuntimeError("private-key local/path/provider-details")

    monkeypatch.setattr(customer, "answer", fail)
    app.chat_input[0].set_value("Can you help?").run()
    assert not app.exception
    reply = app.chat_message[-1].text[0].value
    assert "try again" in reply
    assert "private-key" not in reply and "provider-details" not in reply


def test_sequential_customer_messages_reach_backend_in_order(monkeypatch):
    app = customer_app(monkeypatch)
    seen = []

    def reply(config, messages, text):
        seen.append(([dict(item) for item in messages], text))
        return "Which devices are affected?" if not messages else "What lights do you see?"

    monkeypatch.setattr(customer, "answer", reply)
    app.chat_input[0].set_value("Internet is down").run()
    app.chat_input[0].set_value("All devices").run()
    app.chat_input[0].set_value("Blinking white").run()
    assert not app.exception
    assert [len(history) for history, _ in seen] == [0, 2, 4]
    assert [item["text"] for item in seen[2][0]] == [
        "Internet is down", "Which devices are affected?",
        "All devices", "What lights do you see?",
    ]


def test_customer_history_is_bounded_and_escalated_draft_is_not_shown(monkeypatch):
    config = load_config("configs/demo.yaml")
    config["runtime"]["max_history_messages"] = 2
    captured = []

    def analyse(request):
        captured.append(request)
        return SimpleNamespace(
            decision="escalate", reply_status="generated", draft_reply="Internal draft"
        )

    monkeypatch.setattr(
        customer, "customer_runtime", lambda *args: SimpleNamespace(analyse=analyse)
    )
    messages = [
        {"role": "customer", "text": "Old question"},
        {"role": "agent", "text": "Old answer"},
        {"role": "customer", "text": "Latest question"},
        {"role": "agent", "text": "Latest answer"},
        {"role": "agent", "text": "Temporary error", "context": False},
    ]
    reply = customer.answer(config, messages, "Help")
    assert "Internal draft" not in reply
    assert [item.text for item in captured[0].conversation_history] == [
        "Latest question", "Latest answer"
    ]
    config["runtime"]["max_history_messages"] = 0
    customer.answer(config, messages, "Help")
    assert captured[-1].conversation_history == []
