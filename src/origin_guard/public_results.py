from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Deliberately excludes model prose and provider error messages, which can quote
# encrypted benchmark transcripts or contain request details.
PUBLIC_FIELDS = (
    "schema",
    "item_id",
    "case_id",
    "stratum",
    "variant",
    "condition",
    "model",
    "timestamp_utc",
    "status",
    "score",
    "input_tokens",
    "output_tokens",
    "stop_reason",
    "error_type",
)


def sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    public = {key: record[key] for key in PUBLIC_FIELDS if key in record}
    removed = sorted(set(record) - set(public))
    public["public_export"] = True
    public["redacted_fields"] = removed
    return public


def sanitize_results(source: Path, destination: Path) -> tuple[int, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    removed_values = 0
    with destination.open("w", encoding="utf-8") as sink:
        for line_number, raw in enumerate(source.read_text().splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}") from exc
            public = sanitize_record(record)
            removed_values += len(public["redacted_fields"])
            sink.write(json.dumps(public, sort_keys=True) + "\n")
            rows += 1
    return rows, removed_values
