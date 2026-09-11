"""Shared company settings, safe YAML parsing and environment loading."""

from __future__ import annotations

import math
import os
import re
import unicodedata
from copy import deepcopy
from pathlib import Path

import yaml
from dotenv import load_dotenv

from support_agent.shared.text import PII_PATTERNS

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(ValueError):
    """Configuration is missing or invalid; safe to display to the user."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}

    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)

        if not isinstance(key, str) or key in result:
            raise ConfigError("YAML keys must be unique strings.")

        result[key] = loader.construct_object(value_node, deep=deep)

    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _unique_mapping,
)


def _merge(base: dict, overrides: dict) -> dict:
    result = deepcopy(base)

    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result


def _expand_environment(value):
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_expand_environment(item) for item in value]

    if isinstance(value, str):
        # Unset model placeholders remain unresolved until that model is used.
        return re.sub(
            r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
            lambda match: os.environ.get(match[1], match[0]),
            value,
        )

    return value


def load_config(config_path: str | Path, *, project_root: Path = PROJECT_ROOT) -> dict:
    """Merge base/company YAML; validate preparation settings, not API keys."""

    root = Path(project_root).resolve()
    selected = Path(config_path)

    if not selected.is_absolute():
        selected = root / selected

    try:
        with (root / "configs/base.yaml").open(encoding="utf-8") as stream:
            base = yaml.load(stream, Loader=_UniqueKeyLoader)

        with selected.open(encoding="utf-8") as stream:
            company = yaml.load(stream, Loader=_UniqueKeyLoader)

        if not isinstance(base, dict) or not isinstance(company, dict):
            raise ConfigError("Both configuration files must contain YAML mappings.")

        load_dotenv(root / ".env", override=False, interpolate=False)
        config = _expand_environment(_merge(base, company))

        if config["config_version"] != 1:
            raise ConfigError("Unsupported config_version.")

        company_id = config["company"]["id"]

        if not isinstance(company_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_-]*", company_id
        ):
            raise ConfigError(
                "company.id must be a lowercase ID without path separators."
            )

        for key in ("display_name", "instructions"):
            if (
                not isinstance(config["company"][key], str)
                or not config["company"][key].strip()
            ):
                raise ConfigError(f"company.{key} is required.")

        for key, value in config["paths"].items():
            if not isinstance(value, str) or not value.strip() or "${" in value:
                raise ConfigError(f"paths.{key} must be a resolved, nonempty path.")

            path = (root / value).resolve()

            if not path.is_relative_to(root) or path == root:
                raise ConfigError(f"paths.{key} must point inside the project.")

            config["paths"][key] = str(path)

        dataset = config["dataset"]

        if not isinstance(dataset["channel"], str) or not dataset["channel"]:
            raise ConfigError("dataset.channel is required.")

        accounts = dataset["company_author_ids"]

        if (
            not isinstance(accounts, list)
            or not accounts
            or any(not isinstance(item, str) or not item.strip() for item in accounts)
            or len(set(accounts)) != len(accounts)
        ):
            raise ConfigError(
                "dataset.company_author_ids must list unique account IDs."
            )

        for value, name in (
            (dataset["csv"]["chunk_size"], "chunk_size"),
            (config["intent_discovery"]["sample_size"], "sample_size"),
            (dataset["reply_quality"]["min_words"], "min_words"),
        ):
            if type(value) is not int or value < 1:
                raise ConfigError(f"{name} must be a positive integer.")

        if type(config["random_seed"]) is not int:
            raise ConfigError("random_seed must be an integer.")

        fractions = [
            config["splits"][f"{name}_fraction"]
            for name in ("train", "validation", "evaluation")
        ]

        if any(
            type(value) not in (int, float) or not 0 < value < 1 for value in fractions
        ) or not math.isclose(sum(fractions), 1.0):
            raise ConfigError("Split fractions must be positive and sum to one.")

        if (
            config["splits"]["strategy"] != "chronological"
            or config["splits"]["boundary_policy"]
            != "quarantine_spanning_conversations"
        ):
            raise ConfigError(
                "Only chronological splits with boundary quarantine are supported."
            )

        if not set(dataset["pii"]["mask_types"]).issubset(PII_PATTERNS):
            raise ConfigError("Unsupported sensitive-information mask type.")

        unicodedata.normalize(dataset["normalization"]["unicode_form"], "check")

        for pattern in dataset["reply_quality"]["reject_fullmatch_patterns"]:
            re.compile(pattern)

        return config
    except ConfigError:
        raise
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        yaml.YAMLError,
        re.error,
    ) as error:
        # Do not echo config contents: environment-expanded values may be private.
        raise ConfigError(
            f"Cannot load configuration ({type(error).__name__}); check required fields and YAML syntax."
        ) from None
