# File walkthrough: `support_agent/evaluation/runner.py`

Evaluation validates completed held-out golden labels, labelled training data
and eligible relevance IDs before running the frozen agent and both baselines.
The judge receives message, draft and evidence, not gold intent/escalation labels.
All configured score dimensions and bounds are required. Metrics-only mode is
explicitly incomplete for the assignment, which requires judging and human
agreement.

Each run saves predictions, a report and a human-rating template in a separate
results directory. `latest.json` changes only after those files are written.
Human ratings include company/method/message IDs and the exact reply checksum.
Use the `rate` command to import ratings without rerunning generation. Unknown,
duplicate or mismatched ratings are rejected. Reports stay incomplete until all
required human scores and judge outputs exist. These files are local experiment
artifacts, not authenticated uploads.

Evaluate actual displayed replies, including safe fallbacks, and inspect the
reported fallback rate alongside safety scores. Evaluation does not tune prompts,
thresholds or categories on the golden set. The initial workflow evaluates
individual held-out customer turns with empty history; it is not a claim about
full multi-turn performance.

Reports record source fingerprints, the training-label checksum, configuration
digest, public model identifiers and workflow-code hashes. Rating dimensions,
bounds and the safety cutoff are saved with the run so later YAML edits cannot
change how its human ratings are interpreted.

Workflow provenance discovers Python files recursively from the package root,
using relative paths as keys. It includes every feature folder, not just the
evaluation runner's own directory.
