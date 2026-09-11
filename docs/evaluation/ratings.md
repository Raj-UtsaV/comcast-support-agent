# File walkthrough: `support_agent/evaluation/ratings.py`

This separate module imports human ratings for a saved evaluation run without
regenerating replies. Every row must match company, method, source message and
reply checksum. Duplicate or out-of-range ratings fail. It computes agreement
through `metrics.py`, fills safe auto-handle coverage only with sufficient human
safety ratings, and updates the report through a temporary file and atomic
replacement. Partial ratings remain visibly incomplete. `evaluation.py` exposes
it through the `rate` command.

Each import replaces the previous set of ratings. Missing safety ratings clear
previous safe-coverage values. Scoring uses the rubric saved with that run,
not potentially changed current configuration.
