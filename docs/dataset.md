# Dataset download: `data/raw/twcs.csv`

## What this file is for

This is the original Customer Support on Twitter CSV. It contains customer
messages and company replies linked by tweet IDs. The project will use it to
reconstruct conversations, review possible intents, retrieve historical evidence
and build a held-out evaluation sample.

This step downloads and verifies real source data. It does not train a model,
generate intent labels, construct a retrieval index or produce evaluation scores.

## Source and download scope

- Publisher: Thought Vector on Kaggle.
- [Original dataset and attribution](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter).
- Dataset reference: `thoughtvector/customer-support-on-twitter`.
- Pinned version: `10`.
- Requested source file: `twcs/twcs.csv`.
- Local destination: `data/raw/twcs.csv`.
- Kaggle lists the license as **CC BY-NC-SA 4.0**; consult the original data card
  for its usage terms and attribution.

Only this dataset file was downloaded. The optional Banking77 dataset and
Kaggle's separate `sample.csv` were not downloaded.

Kaggle supplies a shared CSV containing multiple companies, not a separate
Comcast-only CSV. Selecting only rows authored by a company's support account would lose
the customer side of conversations. A later processing step will use the
configured company support account IDs and both reply-link columns to find connected
customer messages.

## How the download was implemented

1. Read Kaggle's public file listing to identify the required file and its
   advertised uncompressed size.
2. Read the dataset metadata to pin version 10.
3. Download that individual file over HTTPS with `curl`, following redirects,
   failing on HTTP errors and allowing bounded retries and timeouts.
4. Stage the response in a temporary directory. Kaggle returned a ZIP containing
   only `twcs.csv`.
5. Stream that ZIP member to a temporary CSV with Python's `zipfile` and
   `shutil` modules. Reading the complete member checks the archive CRC.
6. Compare the extracted size against Kaggle's listing, calculate a SHA-256
   fingerprint and parse the complete CSV with Python's `csv.DictReader`.
7. Move the verified CSV to `data/raw/twcs.csv`, refusing to overwrite an
   existing destination.

The download did not require installing the Kaggle client or using credentials.
The source file remains unchanged: no rows were filtered or rewritten.

## Verification results

These are observed dataset statistics, not agent performance metrics.

| Check | Result |
| --- | --- |
| Download response | HTTP 200 |
| ZIP members | Exactly one: `twcs.csv` |
| Compressed download | 176,765,850 bytes |
| Extracted CSV | 516,508,641 bytes, approximately 492.6 MiB |
| CSV data records, excluding header | 2,811,774 |
| Column count | 7 |
| Inbound customer records | 1,537,843 |
| Outbound support records | 1,273,931 |
| Distinct outbound author IDs | 108 |
| Outbound records authored by `comcastcares` | 33,031 |
| Full CSV parse | Passed; no missing or extra fields |
| `inbound` values | Every record contained `True` or `False` |

The 33,031 records are support tweets, **not** complete conversations or the
total size of the future sample for the selected company. Connected customer messages
will increase the selected message count; cleaning can subsequently remove rows.

SHA-256 of the extracted CSV:

```text
cd297fcfa1bf6f99938be242e8e578980bc6d1b96adc8691abec9a39175b03c0
```

This fingerprint records the bytes downloaded here. It is not a separately
published checksum from the dataset author.

## Understanding the source columns

| Column | Meaning and future use |
| --- | --- |
| `tweet_id` | Source message identifier; preserve it for links and evidence. |
| `author_id` | Customer or support author; match support accounts using company configuration. |
| `inbound` | `True` identifies inbound customer messages; `False` identifies support replies. |
| `created_at` | Source timestamp; parse it for ordering and chronological splits. |
| `text` | Original message text; normalize and mask sensitive information during processing. |
| `response_tweet_id` | Comma-separated IDs of replies to this message. |
| `in_response_to_tweet_id` | ID of the parent message, when provided. |

Tweets can contain embedded newlines. Counting physical lines with `wc -l`
would not reliably count CSV records; the verification used a CSV parser.

## Reproducing the download

The following command downloads the same single source file into a new
temporary directory. It does not overwrite the project's existing CSV.

```bash
dataset_ref='thoughtvector/customer-support-on-twitter'
dataset_file='twcs%2Ftwcs.csv'
dataset_version='10'
download_dir="$(mktemp -d /tmp/support-agent-dataset.XXXXXX)"

curl --location --fail --silent --show-error \
  --retry 3 --connect-timeout 20 --max-time 600 \
  --output "$download_dir/twcs.download" \
  "https://www.kaggle.com/api/v1/datasets/download/${dataset_ref}/${dataset_file}?datasetVersionNumber=${dataset_version}"

python3 -m zipfile -t "$download_dir/twcs.download"
python3 -m zipfile -e "$download_dir/twcs.download" "$download_dir"
sha256sum "$download_dir/twcs.csv"
```

Compare the extracted CSV's checksum with the fingerprint above. The current
project copy has already passed the additional schema and complete-record
checks described in this document.

## Keeping the implementation configurable

The dataset reference and source filename above identify this particular
download; they are not constants embedded in application logic. The Python
data pipeline is implemented in `support_agent/data/preparation.py`.

The upcoming company configuration will hold the source location, company author
IDs and column mapping. The data module will consume those settings rather than
contain conditions such as `if company == "comcast"`. It will process the CSV in
chunks, reconstruct complete conversations and preserve source IDs.

This source CSV is shared input. Normalized records must carry `company_id`, and
retrieval artifacts must be stored and checked separately for each company.

## What comes next

The shared settings in `configs/base.yaml` now reflect the agreed approach:
LLM intent classification with no custom classifier training, plus the required
LLM-judge evaluation. See [the configuration explanation](configs/base.md).

`configs/comcast.yaml` now defines the dataset adapter and company mapping.
Cleaning, thread reconstruction and development sampling have run; see
[the processing explanation](data/preparation.md). Golden annotations and agent evaluation
remain future work. The project's `.gitignore` excludes raw datasets and
generated indexes; no Git commit was made in the download step.
