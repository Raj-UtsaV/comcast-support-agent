# File walkthrough: `support_agent/evaluation/metrics.py`

Metrics include intent accuracy/macro-F1/per-category precision and recall,
escalation precision/recall/F1, retrieval Recall@k and auto-handle coverage.
Recall averages the fraction of annotated relevant evidence IDs returned and
excludes examples explicitly annotated with no relevant evidence. That denominator
is reported. False-auto-handle rate is required-escalation cases among auto-handled
cases; it is unavailable when none were auto-handled.

Safe auto-handle coverage remains unavailable until every auto-handled reply has
an independent human safety rating. Evaluation also requires correct intent and
no required escalation for a safe case. Judge means, exact human/judge agreement,
Cohen's kappa and Spearman correlation use matched ratings only. Constant ratings
produce unavailable kappa/correlation where undefined, not invented zeros.
The fallback rate is reported because safe template replacement can inflate
headline reply-safety numbers while hiding poor model drafts.
