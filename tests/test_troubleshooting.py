"""Basic customer guidance stays bounded and respects account-risk rules."""

from types import SimpleNamespace

import pytest

from support_agent.shared.config import load_config
from support_agent.ui import customer
from support_agent.ui.troubleshooting import basic_guidance


def test_first_connection_question_gets_checks_without_model_evidence(monkeypatch):
    config = load_config("configs/comcast.yaml")
    config["runtime"]["demo_mode"] = True
    result = SimpleNamespace(
        decision="escalate", reply_status="safe_fallback", draft_reply="Contact support.",
        safety_flags=["verification_failed", "unknown_intent", "missing_evidence"],
    )
    monkeypatch.setattr(customer, "customer_runtime", lambda *args: SimpleNamespace(analyse=lambda request: result))
    reply = customer.answer(config, [], "My internet keeps disconnecting.")
    assert "securely connected" in reply and "every device" in reply
    assert "contact" not in reply.lower()
    history = [{"role": "agent", "text": reply}]
    assert "human support" in customer.answer(config, history, "My internet keeps disconnecting.")


@pytest.mark.parametrize("message", [
    "My internet was disconnected for an unpaid bill.",
    "Cancel my internet account.",
    "My internet is still not working; I already tried those steps.",
    "I want a human to help with my internet.",
])
def test_guidance_does_not_override_account_actions_or_repeat_failed_steps(message):
    config = load_config("configs/comcast.yaml")
    assert basic_guidance(config, [], message) is None


def test_tv_guidance_and_customer_history():
    config = load_config("configs/comcast.yaml")
    assert "TV input" in basic_guidance(config, [], "My TV has no picture.")
    history = [{"role": "customer", "text": "I already tried checking the cables."}]
    assert basic_guidance(config, history, "My internet is down.") is None


def test_short_followups_continue_the_active_guide_and_topic_changes_work():
    config = load_config("configs/comcast.yaml")
    first = basic_guidance(config, [], "My internet keeps disconnecting.")
    messages = [
        {"role": "customer", "text": "My internet keeps disconnecting."},
        {"role": "agent", "text": first},
    ]
    second = basic_guidance(config, messages, "All devices")
    assert "steady or blinking" in second
    messages += [{"role": "customer", "text": "All devices"}, {"role": "agent", "text": second}]
    third = basic_guidance(config, messages, "Blinking white")
    assert "model name" in third
    messages += [{"role": "customer", "text": "Blinking white"}, {"role": "agent", "text": third}]
    assert basic_guidance(config, messages, "Blinking white") is None
    assert "TV input" in basic_guidance(config, messages, "My TV has no picture.")
