# Delivery artifacts

The current submission entry point is `submission/README.md`, with a requirement
audit in `submission/STATUS.md`. `comcast-support-agent-submission.zip` contains
the source and a frozen processed-data/current-index snapshot for fast offline
replay. `scripts/reproduce_submission.py` verifies the engineering counts using
the standard library; real quality results and human agreement remain pending.

`README.md` contains setup, demo, real-workflow, annotation, evaluation and
extension instructions. `report.md` is the concise report with observed data
counts, unavailable quality metrics, five failure hypotheses and the required
headline-number discussion. `decision_log.md` records 15 decisions made during
implementation.

`data/golden_set_template.csv` contains 200 real held-out customer examples;
`data/training_labels_template.csv` contains 500 real training examples.
They were exported by `annotations.py`, with no fabricated labels. The active
golden-label path is a different file so templates do not silently become
completed annotations or invalidate the existing saved index.
