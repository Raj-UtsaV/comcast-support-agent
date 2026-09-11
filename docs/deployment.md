# Deploy with Python or Docker

The customer and staff interfaces use Flask, server-rendered HTML, CSS and plain
JavaScript. Deploy to a host with a Python WSGI runtime or Docker support.
Static-only hosting cannot run the Python backend.

Install `requirements.txt` with Python 3.12. Set environment variables in the
provider's settings (use `.env.example` for model configuration). Set `SECRET_KEY`
to a long random secret, identical across all workers and replicas. Generate one
with `python -c "import secrets; print(secrets.token_hex(32))"`.
Set `SUPPORT_CONFIG` to your company YAML; the default is `configs/comcast.yaml`.
Model credentials and a prepared index are required.

Customer start command (also supplied in `Procfile`):

```bash
gunicorn customer_app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 180
```

Deploy staff tools as a separate service, with access restricted through your
hosting provider or reverse proxy; the application does not implement login:

```bash
gunicorn app:app --bind 0.0.0.0:${PORT:-8001} --workers 1 --threads 4 --timeout 180
```

Both services expose `GET /healthz` for process health checks. It does not check
model credentials or index readiness. Serve public traffic through HTTPS.

Build the container:

```bash
docker build -t support-chat .
```

Pass `SECRET_KEY` and model credentials as environment variables when running the container. The image excludes secrets,
raw data, generated artifacts, and model caches. For live deployment, run the
README setup pipeline and provision the processed data, index and embedding
cache on the host at the paths in company configuration; mount those directories
into the container. The model cache defaults to `/app/.cache/huggingface`.
Provision artifacts during deployment rather than rebuilding on every request.
Allocate memory/disk for PyTorch, the embedding model and index. Each additional
worker loads its own runtime, so begin with one worker and scale after measuring.

Conversation history is signed, expires after 24 hours, and is held in page
memory. Refresh or New conversation clears it. Signing prevents modification;
it is not encryption. No shared database is needed. Without an explicit
`SECRET_KEY`, restarting or switching workers invalidates conversation tokens.
