# File walkthrough: `support_agent/data/conversations.py`

This module reads source conversations and reconstructs their connections.
It contains the larger SQL/CSV operations formerly inside `data.py`.

`index_twitter_csv` reads configured CSV chunks and stores records and reply
links in a temporary SQLite database. SQLite is a local database file, so the
complete dataset text does not have to stay in memory. Duplicate IDs with
conflicting contents fail rather than silently selecting one version.

`company_groups` starts from the selected company's support accounts, follows
both parent and response links and blocks known support accounts from other
companies. Missing referenced IDs can connect orphan siblings; no text is
invented for those missing messages. It assigns a deterministic conversation
ID to each connected group.

`ADAPTERS` selects a reader by source format. Another company using the same
format requires configuration changes; a different format needs a reader.

The temporary database lifecycle remains controlled by `data.py`. This module
does not publish processed files, split evaluation data or load models.
