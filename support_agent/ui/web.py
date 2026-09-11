"""Portable Flask interfaces for customer chat and staff review."""
import hashlib
import json
import os
import secrets

from flask import Flask, abort, jsonify, render_template, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from support_agent.shared.config import PROJECT_ROOT, load_config
from support_agent.shared.schemas import HistoryMessage, SupportRequest
from support_agent.ui import customer
from support_agent.ui.channels import support_channels
from support_agent.ui.dashboard import failure_rows, load_report


def create_app(staff=False, config_path=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=1024 * 1024,
                      SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32))
    signer = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='conversation')
    paths = {p.stem: p for p in (PROJECT_ROOT / 'configs').glob('*.yaml') if p.stem != 'base'}

    def configuration(name=None):
        if staff:
            name = name or 'comcast'
            if name not in paths:
                abort(400, 'Unknown company configuration')
            return load_config(paths[name])
        return load_config(config_path or os.environ.get('SUPPORT_CONFIG', 'configs/comcast.yaml'))

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    @app.get('/')
    def index():
        selected = request.args.get('company', 'comcast')
        try:
            config = configuration(selected)
            report, rows, report_error = None, [], None
            if staff:
                try:
                    report, rows = load_report(config)
                    rows = failure_rows(rows, config)
                except (ValueError, OSError, KeyError, TypeError):
                    report_error = 'Evaluation artifacts could not be loaded.'
            return render_template('staff.html' if staff else 'customer.html',
                                   config=config, companies=sorted(paths), selected=selected,
                                   report=report, failures=rows, report_error=report_error,
                                   support_channels=support_channels(config))
        except (ValueError, OSError):
            return 'Support is temporarily unavailable. Please try again later.', 503

    @app.post('/api/analyse' if staff else '/api/chat')
    def analyse():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='Send a JSON object.'), 400
        try:
            config = configuration(data.get('company'))
            message = data.get('message')
            if not isinstance(message, str) or not message.strip():
                return jsonify(error='Please enter a message.'), 400
            if len(message) > config['runtime']['max_message_characters']:
                return jsonify(error='The message is too long.'), 400
            if staff:
                history = data.get('history', [])
                if not isinstance(history, list):
                    raise ValueError('History must be a list')
                support_request = SupportRequest(company_id=config['company']['id'], message=message,
                    conversation_history=[HistoryMessage.model_validate(item) for item in history])
                revision = json.dumps(customer.source_state(config), sort_keys=True) + (customer.storage_directory(config) / 'current.json').read_text()
                result = customer.customer_runtime(json.dumps(config, sort_keys=True), revision).analyse(support_request)
                return jsonify(result=result.model_dump())
            scope = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
            messages = []
            token = data.get('conversation')
            if token:
                try:
                    state = signer.loads(token, max_age=86400)
                    if state['scope'] == scope:
                        messages = state['messages']
                except (BadSignature, TypeError, KeyError):
                    return jsonify(error='This conversation expired. Start a new conversation.'), 400
            reply = customer.answer(config, messages, message)
            messages.extend([{'role': 'customer', 'text': message}, {'role': 'agent', 'text': reply}])
            token = signer.dumps({'scope': scope, 'messages': messages[-100:]})
            return jsonify(reply=reply, conversation=token)
        except (ValueError, TypeError):
            return jsonify(error='Unable to process this request. Check your input and try again.'), 400
        except (OSError, RuntimeError):
            app.logger.exception('Support request failed')
            return jsonify(error='Sorry, I couldn’t process your message right now. Please try again later or contact your provider through your usual support channel.'), 503

    return app
