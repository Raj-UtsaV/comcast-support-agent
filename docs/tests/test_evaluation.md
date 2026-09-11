# test_evaluation.py

Tests prepare real synthetic CSV fixtures, add explicitly synthetic human labels
and inject a scripted generator/retriever/judge. They verify all three methods,
metric denominators, unavailable safe coverage before human scoring, matching
reply checksums, constant-rating agreement, metrics-only status, rejection of
demo evaluation, blank review exports and training/held-out separation.
These temporary scores are test assertions, not project performance results.
