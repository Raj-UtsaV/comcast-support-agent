# File walkthrough: `support_agent/models/client.py`

`TextGenerator` defines structured generation. The factory constructs a LiteLLM
client from the configured provider, model, timeout and environment-variable
name. Keys remain in memory and are not included in outputs or error messages.
The client requests JSON, includes the Pydantic schema in its instructions and
validates the response locally. Partial, malformed or failed responses produce
an error; there is no implicit fake-model fallback. The selected provider/model
must support JSON-object responses. See [LiteLLM JSON mode](https://docs.litellm.ai/docs/completion/json_mode).

Classification, drafting and verification use the generator; evaluation judging
uses the independently configured judge. Real calls transmit masked task data
to that configured provider. Tests inject clients and make no API requests.
