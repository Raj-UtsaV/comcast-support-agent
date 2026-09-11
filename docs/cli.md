# support_agent/__main__.py

`python -m support_agent analyse` runs the structured support pipeline with a
message argument or bounded standard input. `check` reports category, generator,
judge and saved-index readiness without making API calls or printing keys.
Check is informational and returns zero when it completes, even when individual
setup items are missing. Analysis failures return one; argument errors return
two. Standard output contains JSON, and progress/errors use standard error.
