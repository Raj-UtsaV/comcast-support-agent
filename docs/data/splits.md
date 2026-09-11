# File walkthrough: `support_agent/data/splits.py`

This module keeps development conversations separate from evaluation data.

`golden_conversations` reads company/conversation IDs reserved by the human
evaluation annotations. During preparation, it also verifies their message and
conversation identities against reconstructed source groups. Evidence selection
reuses this check against prepared message identities. A missing annotation
file reserves no conversations; malformed annotations produce an error.

`split_conversations` derives time boundaries from configured fractions and
assigns whole conversations to training, validation or evaluation. Conversations
crossing a boundary are held aside in `quarantine`; golden conversations are
reserved separately. Empty resulting development/evaluation splits are errors.

The functions were extracted from `data.py` so evidence selection can share the
golden-data exclusion rule. Training means the historical evidence/development
split in this project; these functions do not train a model.
