"""Staff dashboard: gunicorn app:app."""
import os
from support_agent.ui.web import create_app

app = create_app(staff=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8001')))
