# File walkthrough: `support_agent/agent/taxonomy.py`

This module checks approved category IDs, descriptions, risky-category references
and baseline keyword expressions. It does not invent or automatically approve
labels. The real agent refuses to run until a human has reviewed training
examples and filled `intents.approved_taxonomy` in the company YAML. Demo
categories live only in the explicitly synthetic demo configuration.
