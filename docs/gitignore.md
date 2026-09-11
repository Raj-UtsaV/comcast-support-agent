# File walkthrough: `.gitignore`

## What this file does

Git records project changes for version control. `.gitignore` tells Git which
untracked files to skip when you stage project files for a commit.

This project needs the downloaded CSV and generated search indexes locally,
but those large files do not belong in ordinary source-code commits. Local API
credentials, installed Python environments and temporary files should also
stay outside the repository history.

Adding these rules does not delete any local files or stop Python from reading
them. The downloaded `data/raw/twcs.csv` stays available for processing.

## What each group excludes

| Rule group | Examples | Reason |
| --- | --- | --- |
| Local credentials | `.env`, `.env.local`, `.streamlit/secrets.toml`, `kaggle.json` | These files may contain API keys or other local credentials. |
| Downloaded data | `data/raw/twcs.csv` | The original dataset is large and its source is documented separately. |
| Generated conversations | `data/processed/comcast/train.jsonl` | These files will be recreated by the data-processing command. |
| Search indexes | `artifacts/comcast/index.faiss` | These are generated for each company from its historical evidence. |
| Python environments | `.venv/`, `venv/` | Dependencies will be declared in `requirements.txt`, not committed as installed packages. |
| Compiled files and caches | `__pycache__/`, `.pytest_cache/`, `.cache/` | Python and development tools can recreate them. |
| Build outputs | `build/`, `dist/`, `*.egg-info/` | These are produced when packaging the project. |
| Editor and temporary files | `.vscode/`, `.idea/`, `*.log`, `*.tmp`, `*.part` | Local settings and temporary outputs are not project source files. |

The company name in the examples explains the current setup. The actual rules
ignore the shared parent directories, so adding another company's configuration
does not require changing `.gitignore`.

## How the patterns work

- A trailing slash matches a directory, including its contents. For example,
  `/artifacts/` covers all company index directories below it.
- A leading slash anchors a rule to this project's root. `/data/raw/` therefore
  identifies the dataset folder without excluding an unrelated nested folder
  with the same name in a future test fixture.
- `*` matches filename characters. `.env.*` covers files such as `.env.local`.
- `!` makes an exception. `!.env.example` allows a placeholder-only environment
  template even though other `.env.*` files are ignored.
- Slashless patterns such as `__pycache__/` also cover matching directories
  nested inside source and test folders.

## What remains available to commit

The rules intentionally leave these project deliverables trackable:

- Company configuration, Python source, tests and Markdown explanations.
- `.env.example`, which will contain placeholders rather than real keys.
- `data/golden_set.csv`, containing the required human annotations.
- Evaluation outputs such as `results/comcast/metrics.json`, prediction files,
  human ratings and failure-analysis examples.
- The README and decision log.

There is no blanket `*.csv` or `*.json` rule: those formats can contain the
evidence needed to assess the assignment. Any prepared sample or cached index
needed for the final reproduction workflow must be distributed deliberately;
ignored local files are not automatically included in a cloned repository.

An ignore rule applies to untracked files. It does not remove files already
committed to Git or detect secrets accidentally written into otherwise
trackable files. No Git repository or commit was created for the project in
this step.

## Verification and review checkpoint

The rules were checked with `git check-ignore` in a temporary repository using
representative paths. Downloaded data, search indexes and local credentials
were excluded, while configuration, the environment template, golden
annotations and evaluation results remained trackable. The temporary repository
was removed after the check.

This step adds only `.gitignore` and this explanation. The next file is
`requirements.txt`, with its own documentation, followed by another review pause.
