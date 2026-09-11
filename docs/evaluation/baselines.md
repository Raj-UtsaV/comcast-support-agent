# File walkthrough: `support_agent/evaluation/baselines.py`

The trivial baseline chooses the majority human-labelled training intent,
returns the configured generic reply and always escalates. Ties are broken by
label ID. The simple baseline applies approved, human-written keyword rules;
ambiguous/no matches produce an unknown intent. Its TF-IDF vocabulary is fitted
only on eligible training questions. Cosine search returns distinct historical
conversations, and its top reply becomes the draft. It also always escalates.

These choices follow the agreed no-supervised-training approach. TF-IDF fits
corpus statistics but does not train an intent classifier. Copied historical
replies are not verified current advice; evaluation judges the actual baseline
draft. Baselines never fit vocabulary or majority labels on golden examples.
