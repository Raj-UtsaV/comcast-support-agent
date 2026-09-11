# File walkthrough: `configs/comcast.yaml`

## What this file does

This file supplies the settings for the first **company**, Comcast. It tells the
future data-processing code which CSV to read, which support account belongs to
the company and how to interpret the columns. It also supplies instructions for
drafting replies and clearly labelled example messages for the website.

The file is configuration, not executable processing code. Its mapping has been
checked against the downloaded CSV and used by the implemented data-preparation
module. See [the processing explanation](../data/preparation.md) for outputs. The agent
runtime has not been implemented yet.

## How it works with `base.yaml`

The planned loader combines shared defaults from `base.yaml` with the values
here. Dictionaries merge recursively; company values and lists replace matching
base values. For example:

- `company.id` changes from `null` to `comcast`.
- `paths.raw_csv` changes from `null` to `data/raw/twcs.csv`.
- `dataset.company_author_ids` becomes `[comcastcares]`.
- Shared model settings, chunk size, split fractions and safety checks remain
  inherited because this file does not replace them.

The numeric safety thresholds have not been tuned. This file inherits their
initial values rather than presenting company-specific thresholds as validated.
See [the shared configuration explanation](base.md) for their meaning.

## Company identity and source account

These two identifiers have different purposes:

| Setting | Value | Meaning |
| --- | --- | --- |
| `company.id` | `comcast` | Our project identifier, carried as `company_id` in processed records and requests. |
| `dataset.company_author_ids` | `[comcastcares]` | The actual support account ID to match in the source CSV's `author_id` column. |

The support account spelling was checked against the local dataset. The list
allows a company to have several support accounts later, without adding
company-specific conditions to Python.

The company instructions are choices for this applicationnstration. They are not
official Comcast policy. They ask for clear, evidence-based drafts and human
review when account access or an action would be needed. Shared safety
instructions from `base.yaml` must also be applied by the runtime.

## Input, output and source information

All paths are relative to the project root:

| Location | Purpose |
| --- | --- |
| `data/raw/twcs.csv` | Original downloaded CSV, containing multiple companies and their customers. |
| `data/processed/comcast/` | Destination for this company's cleaned conversations and splits. |
| `results/comcast/` | Destination for this company's evaluation outputs. |
| `artifacts/comcast/` | Future retrieval index, formed from the inherited artifact root plus `company.id`. |
| `data/golden_set.csv` | Inherited path for human annotations; every row must identify its company and conversation. |

The processing and results directories above are complete configured paths;
the implementation must not append the company ID to them a second time.
The artifact setting is a shared root, so the company ID is appended there.

The `source` section records Kaggle, the dataset reference, version 10 and the
original uploaded filename `twcs/twcs.csv`. The local file has been placed at
`data/raw/twcs.csv`. This information records where the input came from; normal
preparation reads the local file and does not download it again.

Download verification, record counts and the file checksum are documented in
[dataset.md](../dataset.md).

## Reading the CSV columns

An **adapter** is the code that converts a source dataset into our common
message format. `adapter: twitter_csv` selects the implementation that
understands Twitter reply connections. The column mapping keeps actual header
names out of company-specific Python logic.

| Adapter field | CSV column | How it will be used |
| --- | --- | --- |
| `message_id` | `tweet_id` | Preserve the source message ID. |
| `author_id` | `author_id` | Identify selected company support accounts. |
| `role` | `inbound` | Translate the source flag into `customer` or `agent`. |
| `timestamp` | `created_at` | Parse the timestamp for ordering and chronological splitting. |
| `text` | `text` | Read the message before cleaning and sensitive-information masking. |
| `reply_message_ids` | `response_tweet_id` | Read the comma-separated IDs of replies to this message. |
| `parent_message_id` | `in_response_to_tweet_id` | Read the ID of the message being answered. |

`role_values` maps `customer` to the source string `'True'` and `agent` to
`'False'`. The quotes are intentional: CSV readers return strings, while YAML
could otherwise turn these values into booleans. The adapter must reject
unexpected values rather than guess a role.

The timestamp format describes values such as
`Tue Oct 31 22:27:52 +0000 2017`. `%z` preserves the UTC offset; parsing must
produce timezone-aware timestamps. The source uses English weekday and month
abbreviations, so the parser must account for that rather than rely on an
arbitrary machine language setting. `reply_id_separator` identifies the comma
used between multiple reply IDs. Empty reply fields mean no recorded link.

The mapping also contains helper fields such as `author_id` and
`reply_message_ids`; these are not extra required fields in the final common
message format. The adapter will create `company_id` and `channel` from
configuration, construct `conversation_id` from message connections and add
appropriate metadata. IDs must remain strings, not floating-point numbers.

## Selecting complete conversations

The intended processing sequence is:

1. Find rows whose author is in `company_author_ids` and whose role is `agent`.
2. Follow both parent and reply IDs to locate connected customer messages and
   the selected company's other replies, including links across CSV chunks.
3. Exclude replies authored by other companies. An unselected support account
   must not be treated as a customer merely because its ID is different.
4. Reconstruct conversation groups before assigning chronological splits.
5. Clean text, retain evidence IDs and save only the selected company's records.

A reply existing in the data does not establish that it resolved an issue.
Quality filters and later reply verification still apply.

## Intent labels, safety and website examples

`approved_taxonomy`, `keyword_rules` and `risky_intents` remain empty until we
review the company's development conversations. A **taxonomy** here simply
means the approved list of request categories, with their descriptions.

The future data-preparation command should work with these empty lists. Real
agent execution must require approved categories, and the simple baseline
needs reviewed keyword rules. Existing generic risk checks remain inherited
even while `risky_intents` is empty. We have not discovered or approved any
company-specific intents at this stage.

The three website examples were written for demonstration. Their labels begin
with “Illustrative” so they cannot be mistaken for sampled dataset records.
They are neither intent labels nor golden evaluation examples, and they must
not be counted in evaluation results.

## Adding another company later

Create another company configuration with its ID, instructions, source account
IDs, column mapping and separate output paths. Reuse the same Python pipeline.
If a new dataset has a different conversation structure, it may need a new
adapter implementation; changing only header names does not.

Model providers remain configurable through the inherited model settings.
Company IDs on records and separate indexes must be checked in code as well
as described in configuration.

## Review checkpoint

The raw CSV remains original input. Data preparation now produces company
conversations using this configuration; approved categories, human golden labels
and agent evaluation metrics remain future work.
