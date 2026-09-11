# File walkthrough: `support_agent/data/annotations.py`

The export command samples one customer message per conversation, using the
configured random seed. Golden sheets use only the held-out evaluation split;
training sheets exclude every currently reserved golden conversation. Exported
intent, escalation and evidence labels remain blank for human review. Existing
files are never overwritten. Spreadsheet formula prefixes are escaped in the
display-text column only.

Import resolves company/message/conversation IDs against source records, never
trusting editable CSV text. Golden evaluation requires the configured 150–250
distinct conversations, approved intent IDs, true/false escalation labels and a
JSON list of relevant training evidence IDs. `[]` means the annotator found no
relevant evidence; blank means unfinished. Evaluation checks referenced IDs.

Fill a training sheet for baseline majority labels; only its intent column is
required. Copy a completed golden sheet to `paths.golden_labels`, rebuild the
index, and freeze development choices before running evaluation. Do not use
golden labels to invent categories, prompts or keyword rules.
