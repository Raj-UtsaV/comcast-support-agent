# File walkthrough: `support_agent/shared/text.py`

This module contains reusable text operations:

- `normalize_text`: normalize Unicode, HTML escapes and whitespace; mask
  configured sensitive-information categories; return the detected categories.
- `useful_reply`: check the configured minimum length and patterns for
  greetings or replies that only ask the customer to send a direct message.
- `parse_timestamp`: convert configured source timestamps to UTC without
  changing the application's language setting.

The code was moved from `data.py` so both processing and live customer-message
handling can use the same cleaning behavior. It contains no company names or
model choices. Generic regular expressions describe text formats; company
settings select their use.

These are heuristics: unusual sensitive-information formats can be missed and
some number-like text can be overmasked. Passing the reply filter does not
prove the historical issue was resolved.
