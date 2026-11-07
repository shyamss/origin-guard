from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .monitor import EvaluationItem, parse_score


def load_api_key(path: Path) -> str:
    raw = path.read_text().strip()
    if not raw:
        raise ValueError("API key file is empty")
    if "=" in raw:
        name, value = raw.split("=", 1)
        if name.strip() != "ANTHROPIC_API_KEY":
            raise ValueError("key file assignment must use ANTHROPIC_API_KEY")
        raw = value.strip().strip("'\"")
    if not raw:
        raise ValueError("API key is empty")
    return raw


def completed_item_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("status") == "ok":
            completed.add(str(item["item_id"]))
    return completed


def run_items(
    items: Iterable[EvaluationItem],
    *,
    api_key: str,
    model: str,
    results_path: Path,
    max_output_tokens: int,
) -> tuple[int, int]:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("install the 'api' optional dependency") from exc

    client = Anthropic(api_key=api_key)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    done = completed_item_ids(results_path)
    succeeded = 0
    failed = 0

    with results_path.open("a", encoding="utf-8") as sink:
        for item in items:
            if item.item_id in done:
                continue
            record = {
                "schema": "origin-guard/monitor-result/v1",
                "item_id": item.item_id,
                "case_id": item.case_id,
                "stratum": item.stratum,
                "variant": item.variant,
                "condition": item.condition,
                "model": model,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=max_output_tokens,
                    system=item.system_prompt,
                    messages=[{"role": "user", "content": item.user_message}],
                )
                text = "\n".join(
                    block.text for block in response.content
                    if getattr(block, "type", None) == "text"
                )
                record.update({
                    "response": text,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "stop_reason": response.stop_reason,
                })
                record["score"] = parse_score(text)
                record["status"] = "ok"
                succeeded += 1
            except Exception as exc:  # record provider and parse failures
                record.update(
                    {
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                failed += 1
            sink.write(json.dumps(record, sort_keys=True) + "\n")
            sink.flush()
            print(f"{record['status']} {item.item_id}")
    return succeeded, failed
