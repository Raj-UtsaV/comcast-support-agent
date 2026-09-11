# File walkthrough: `support_agent/agent/demo.py`

Two scripted clients exercise the complete agent workflow using `demo.yaml`.
They make no network requests or vector searches. Every response is marked
`demo: true`, and the website displays a demo banner. The verifier's success and
similarity values are scripted; they must never be interpreted as measured
performance. Production factories never select these clients after a failure.
