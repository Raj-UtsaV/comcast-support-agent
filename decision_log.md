# Decision log

1. **Separate customer and staff interfaces.** Customer chat keeps model settings,
   evidence records, and evaluation tools out of the customer flow; both apps
   reuse the same configured workflow.
2. **Use existing models.** Follow the agreed LLM-classification/pretrained-
   embedding approach rather than training logistic regression on invented labels.
3. **Keep source adapters configurable.** Account IDs and column names live in
   YAML; the core pipeline has no Comcast branches.
4. **Group complete conversations before splitting.** This avoids leaking related
   replies across development and evaluation; boundary-spanning groups are held aside.
5. **Use SQLite for raw-source links.** Chunked reading avoids loading the entire
   multi-company CSV while retaining cross-chunk relationships.
6. **Retain unverified resolution.** A historical agent reply is evidence of what
   was said, not proof that a problem was solved.
7. **Index linked training questions only.** Explicit parent links provide traceable
   pairs; missing context is skipped rather than guessed.
8. **Pin the encoder revision.** Configured model identity and dependency/source
   fingerprints prevent mixing incompatible query vectors with stored records.
9. **Carry context into retrieval as well as the LLM.** Ordered chat turns alone
   did not help a search for “all devices”; bounded, masked issue context now
   accompanies short follow-up queries.
10. **Publish saved versions atomically.** Separate generations and a current pointer
    preserve the previous index after a failed rebuild; hashes reject stale inputs.
11. **Use a bounded support workflow.** Classification, retrieval, drafting and
    verification precede a decision; there is no free-running action loop.
12. **Make failures visible.** Missing setup is an error; failed/unsafe model drafts
    become explicitly labelled fallbacks with escalation. Demo selection is explicit.
13. **Compare two transparent baselines.** Training-majority/generic and keyword/
    TF-IDF drafts always escalate, exposing the coverage-versus-safety tradeoff.
14. **Bind human ratings to exact replies.** Company/method/message IDs and reply
    checksums prevent judging a regenerated answer with stale human ratings.
15. **Keep real results unavailable until measured.** Synthetic tests, preparation
    counts and demo outputs are never presented as evaluation performance.
