"""Model-led chat uses history and verifies replies without scripted routing."""
from types import SimpleNamespace
import pytest
from support_agent.shared.config import load_config
from support_agent.shared.schemas import ReplyCheck
from support_agent.ui.conversation import ConversationReply, respond


def runtime(reply, safe=True):
    calls = []
    def generate(task, payload, schema, instructions):
        calls.append((task, payload))
        return reply if task == 'customer_conversation' else ReplyCheck(grounded=True, safe=safe, reason='checked')
    return SimpleNamespace(generator=SimpleNamespace(generate=generate),
                           retriever=SimpleNamespace(search=lambda *args: [])), calls


def test_model_controls_followup_without_evidence():
    config = load_config('configs/comcast.yaml')
    model, calls = runtime(ConversationReply(text='Does the connection fail on a wired device too?', next_step='continue'))
    history = [{'role': 'customer', 'text': 'Internet is down'}, {'role': 'agent', 'text': 'Have you restarted?'}]
    reply = respond(config, model, history, 'I already restarted but nothing happened')
    assert reply == 'Does the connection fail on a wired device too?'
    assert calls[0][1]['history'] == history
    assert calls[0][1]['evidence'] == []
    assert [c[0] for c in calls] == ['customer_conversation', 'verify_customer_conversation']


def test_model_handoff_includes_official_route():
    config = load_config('configs/comcast.yaml')
    model, _ = runtime(ConversationReply(text='A billing representative can review that charge.', next_step='provider_support'))
    assert 'https://www.xfinity.com/support/contact-us' in respond(config, model, [], 'Review this charge')


def test_unverified_response_is_not_shown():
    config = load_config('configs/comcast.yaml')
    model, _ = runtime(ConversationReply(text='An unverified claim', next_step='continue'), safe=False)
    with pytest.raises(RuntimeError):
        respond(config, model, [], 'Help')


def test_model_history_is_bounded_and_excludes_failed_turns():
    config = load_config('configs/comcast.yaml')
    config['runtime']['max_history_messages'] = 2
    model, calls = runtime(ConversationReply(text='Which devices are affected?', next_step='continue'))
    history = [
        {'role': 'customer', 'text': 'Old question'},
        {'role': 'agent', 'text': 'Old reply'},
        {'role': 'customer', 'text': 'Latest question'},
        {'role': 'agent', 'text': 'Latest reply'},
        {'role': 'agent', 'text': 'Temporary error', 'context': False},
    ]
    respond(config, model, history, 'Help')
    assert [m['text'] for m in calls[0][1]['history']] == ['Latest question', 'Latest reply']
    config['runtime']['max_history_messages'] = 0
    respond(config, model, history, 'Help')
    assert calls[2][1]['history'] == []
