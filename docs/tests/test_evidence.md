# File walkthrough: `tests/test_evidence.py`

These tests create small, explicitly synthetic prepared conversations in a
temporary directory. They use the real configured text-cleaning and reply
quality defaults, but never read production customer messages or load a model.

The `message` helper makes a source record. The `prepared` fixture supplies
configuration, editable split records and a writer that creates JSONL files
and a matching preparation manifest. Tests change one condition at a time and
call the real `collect_evidence` function.

Checks cover traceable masked pairs, exclusion of every held-out split,
annotations added after preparation, invalid annotation identities, company
mixing, duplicate messages, overlapping conversations, training time boundaries,
manifest counts, broken or cyclic parent links, agent follow-ups and both
previous and current reply-quality rules.

Run from the project root:

```bash
.venv/bin/python -m pytest tests/test_evidence.py -q
```

These assertions verify selection behavior, not search relevance or agent
quality. Shared network blocking is documented in [conftest.md](conftest.md).
