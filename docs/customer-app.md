# Customer chat and staff workspace

The two interfaces share the same Python support workflow, `.env`, company
configuration, and saved index. The customer interface does not expose model
settings, evidence records, confidence scores, or evaluation tools.

From the project directory, prepare data and the vector index if needed:

```bash
.venv/bin/python -m support_agent setup --config configs/comcast.yaml
```

Run the customer app:

```bash
.venv/bin/streamlit run customer_app.py --server.address 127.0.0.1 --server.port 8501
```

In a second terminal, run the existing staff dashboard:

```bash
.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Open http://localhost:8501 for the customer chat and http://localhost:8502 for
the staff dashboard. Groq credentials remain in `.env`; category, safety and
model settings remain in `configs/comcast.yaml` and `configs/base.yaml`.
Restart both apps after changing credentials. There is no customer-side
configuration switch or admin link. These are separate local apps, not an
authentication system for a public deployment.

To try the customer interface without data, an index, or API keys:

```bash
.venv/bin/streamlit run customer_app.py --server.address 127.0.0.1 --server.port 8501 -- --config configs/demo.yaml
```

Demo mode is visibly labelled and uses scripted replies. The default customer
configuration is Comcast; another configuration can be selected with the same
`-- --config` argument at startup.

The customer can choose a starter topic, send follow-up messages, and reset
the conversation. The model receives at most the configured history limit;
the session retains at most 100 messages. Conversation history is local to the
browser session and is not added to the staff dashboard or saved as a ticket.
The configured provider receives masked task data when a live request runs.
Prior customer and assistant turns are sent as ordered chat messages for
classification, drafting, and verification. Retrieval includes bounded, masked
context from the original issue and recent turns, so short replies such as
"all devices" can retrieve evidence about the ongoing issue. Customer messages
remain available as context even when a provider request fails; temporary
error replies are excluded. A browser session reset still clears the chat.

Only replies passing the workflow's auto-handle checks are displayed as model
answers. For ordinary internet/TV questions, a fallback or handoff-only answer
can instead show a configured basic troubleshooting guide and a diagnostic
question. Each guide is offered at most once in the retained conversation.
Configured follow-up branches continue that guide for short answers such as
"all devices" and "blinking white", without repeating already-used questions.
These finite fallback branches do not replace unrestricted model conversation;
after their available questions are exhausted, the human-support route remains.
These are general guidance texts in `customer_support.troubleshooting` in
`configs/comcast.yaml`, not model predictions or historical evidence. The staff
dashboard and evaluation continue to report the underlying model's decision
and failures. The guides follow the basic connection/input checks documented
by [Xfinity Internet support](https://www.xfinity.com/support/articles/internet-connectivity-troubleshooting)
and [Xfinity TV support](https://www.xfinity.com/support/articles/troubleshoot-tv-no-picture-black-blue-screen).

Account/security requests, requests for a human, and explicitly failed prior
troubleshooting retain the human-support route. An intermittent symptom such
as "keeps disconnecting" alone no longer means troubleshooting has failed.
Assistant conversation history does not trigger customer request-risk rules.
No transfer or ticket is claimed or created. Setup and
provider failures receive a generic customer message; the staff dashboard's
existing diagnostics remain available. This is an independent demonstration,
not an official provider support channel.
