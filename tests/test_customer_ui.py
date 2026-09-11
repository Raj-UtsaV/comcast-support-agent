"""Flask customer conversation and input boundary checks."""
from types import SimpleNamespace
from support_agent.shared.config import load_config
from support_agent.ui import customer
from support_agent.ui.web import create_app


def client():
    return create_app(config_path="configs/comcast.yaml").test_client()



def test_customer_errors_never_expose_internal_details(monkeypatch):
    def fail(*args):
        raise RuntimeError('private-key local/path/provider-details')
    monkeypatch.setattr(customer, 'answer', fail)
    result = client().post('/api/chat', json={'message': 'Help'})
    assert result.status_code == 503
    assert 'try again' in result.json['error']
    assert b'private-key' not in result.data


def test_history_order_reset_and_tampering(monkeypatch):
    seen = []
    def reply(config, messages, text):
        seen.append(([dict(m) for m in messages], text))
        return 'Next question'
    monkeypatch.setattr(customer, 'answer', reply)
    app = client()
    token = None
    for text in ['Internet is down', 'All devices', 'Blinking white']:
        response = app.post('/api/chat', json={'message': text, 'conversation': token})
        assert response.status_code == 200
        token = response.json['conversation']
    assert [len(history) for history, _ in seen] == [0, 2, 4]
    assert seen[2][0][2]['text'] == 'All devices'
    assert app.post('/api/chat', json={'message': 'Help', 'conversation': token + 'x'}).status_code == 400
    app.post('/api/chat', json={'message': 'New conversation'})
    assert seen[-1][0] == []


def test_input_limits_and_static_assets():
    app = client()
    for value in ['', 123, 'x' * 100000]:
        assert app.post('/api/chat', json={'message': value}).status_code == 400
    assert app.post('/api/chat', json=[]).status_code == 400
    assert app.get('/static/style.css').status_code == 200
    assert app.get('/static/app.js').status_code == 200
    assert app.get('/healthz').json == {'status': 'ok'}
    assert app.post('/api/analyse', json={}).status_code == 404



def test_conversation_works_across_workers(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test-shared-worker-key')
    seen = []
    def reply(config, messages, text):
        seen.append(len(messages))
        return 'A reply'
    monkeypatch.setattr(customer, 'answer', reply)
    first = client().post('/api/chat', json={'message': 'First'})
    second = client().post('/api/chat', json={'message': 'Followup', 'conversation': first.json['conversation']})
    assert second.status_code == 200 and seen == [0, 2]


def test_customer_page_has_official_support_route():
    page = create_app(config_path='configs/comcast.yaml').test_client().get('/')
    assert page.status_code == 200
    assert b'href="https://www.xfinity.com/support/contact-us"' in page.data
    assert b'Enter to send' in page.data
