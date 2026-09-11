# Human category and label review

Review training customer messages before filling the real company's taxonomy.
The existing 500-message `intent_review.csv` is unlabelled. A lightweight keyword
inspection found these provisional topics (overlapping matches, not predictions):

| Provisional topic | Matched sample rows | Example message IDs |
| --- | ---: | --- |
| Internet/connection/speed | 113 | 1854019, 1266628, 2114555 |
| Billing/payment/refund | 22 | 390902, 1974514, 1880770 |
| Television/channel/cable | 63 | 1490827, 1922695, 896236 |
| Technician/appointment | 15 | 2433111, 1389064, 2317119 |
| Account/login/password/cancellation | 15 | 1276227, 1765340, 1236981 |

These are suggestions to inspect, not approved labels or true class counts.
Patterns can overlap and miss synonyms. Review the remaining examples too,
resolve multi-issue and unclear cases, and write unambiguous category descriptions.
Do not infer labels solely from these keyword counts.

Use `intents.approved_taxonomy` entries with an `id` and `description`. After
review, mark categories requiring human support in `safety.risky_intents`, and
write baseline keyword rules using training data only. Keep review notes and
record any category revisions before touching golden annotations.

The training-label template contains 500 distinct training conversations;
complete the intent column for the subset you choose to label and save only
completed rows as `data/training_labels.csv`. The golden template contains 200
distinct evaluation conversations; finish all required fields and save as
`data/golden_set.csv`. Do not silently remove ambiguous golden examples to
improve scores. Resolve them through review and document annotation decisions.

Human reply-quality ratings are separate: they apply to the exact generated
drafts saved by evaluation, not merely to the original customer issue.
