# app.py

The website has Support Agent, Evaluation and Failure Analysis tabs. It reads
company settings from YAML, accepts a message and optional typed history, then
shows the category, draft, decision, reasons and historical evidence. It never
sends messages or performs external account actions. The demo has a persistent
synthetic-data banner.

`st.cache_resource` reuses the generator, encoder and index across interactions.
The cache key includes configuration, source fingerprints and the current saved
generation; cached retrieval also checks freshness around searches. See
[Streamlit resource caching](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource).
Restart after changing environment credentials. Requests/results live only in
the browser session state unless you explicitly export evaluation artifacts.
This is a local demonstration, not an authenticated production service.

The displayed result is associated with the submitted company, message and
history. Editing those inputs hides the old answer until Analyse is run again.
