# Golden Evaluation Set

I started from the seeded `support_agent.data.annotations golden` export: 200 distinct held-out Comcast conversations from the chronological evaluation split. I kept one customer message per conversation, read only the visible customer text, and assigned the closest approved intent. When the text needed account access, current outage status, a billing decision, a technician action, or was too vague to answer safely, I marked `should_escalate=true`.

Relevant evidence labels are deliberately sparse. I only attached historical training evidence IDs when the earlier customer problem was close enough to be useful as support-context, not merely because it shared words. `[]` means I did not find a close training example I would want the agent to rely on.

Golden size: 200 examples. Intent counts: {'television_service': 35, 'billing_payment': 25, 'account_access': 18, 'general_support': 75, 'internet_connection': 40, 'technician_appointment': 7}.
Training label sheet: 500 examples from the training split, used only for baselines. Intent counts: {'general_support': 196, 'television_service': 77, 'internet_connection': 107, 'account_access': 33, 'billing_payment': 72, 'technician_appointment': 15}.

The author-score file is a hand-check style review of the exact frozen replies. It is not a second independent annotator study; that limitation is called out in the report because it matters.
