# File walkthrough: `support_agent/shared/schemas.py`

Pydantic models define the request, permitted history roles, classification,
draft, verifier output and final support result. Extra fields and type coercion
are rejected. Confidence is bounded to zero through one. History cannot supply
system instructions. Judge score bounds depend on configuration and are checked
by evaluation code. These structures let the CLI, website and tests share one
contract without coupling their presentation code.
