# File walkthrough: `support_agent/ui/dashboard.py`

This module reads only the selected company's latest evaluation directory and
renders comparison metrics, per-category details, human/judge agreement and
failure rows. It verifies path containment and company ownership. No report
means an explicit unavailable state. Failure categories are derived from actual
saved predictions, annotations and verifier/judge flags, not fabricated examples.
