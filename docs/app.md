# Flask staff dashboard

`app.py` exposes a WSGI application built by `support_agent/ui/web.py`.
The dashboard accepts company selection, a message and optional JSON history,
and renders the category, confidence, draft, decision, safety signals and evidence.
Saved evaluation metrics and failure analysis appear below the reply workspace.
Editing the message or history clears the displayed draft. Replies can be downloaded.

HTML templates live in `support_agent/ui/templates`; CSS and JavaScript live in
`support_agent/ui/static`. User content is escaped by Jinja or rendered using
JavaScript textContent. The runtime has a bounded process-local LRU cache keyed
by configuration and index revision. Restart workers after changing credentials.

The customer app is a separate WSGI service (`customer_app:app`) and does not
expose staff routes. See [deployment](deployment.md) for commands and configuration.
