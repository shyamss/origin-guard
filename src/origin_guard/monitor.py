from __future__ import annotations

import json
import hashlib
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .provenance import ProvenanceTracker
from .render import render_json
from .transcript import load_jsonl


CONDITIONS = (
    "base",
    "state_prompt",
    "provenance",
    "neutral_provenance",
    "policy_only",
    "placebo",
)
_SCORE = re.compile(r"<score>\s*(\d{1,3}(?:\.\d+)?)\s*</score>", re.I)


@dataclass(frozen=True)
class EvaluationItem:
    item_id: str
    case_id: str
    stratum: str
    variant: str
    condition: str
    system_prompt: str
    user_message: str

    @property
    def estimated_input_tokens(self) -> int:
        return math.ceil((len(self.system_prompt) + len(self.user_message)) / 4)


def _transcript_text(path: Path) -> str:
    blocks = load_jsonl(path)
    return "\n".join(
        json.dumps(
            {"role": block.role, "content": block.content, "cwd": block.cwd},
            sort_keys=True,
        )
        for block in blocks
    )


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if data.get("schema") != "origin-guard/case-manifest/v1":
        raise ValueError("unsupported case manifest schema")
    return list(data["cases"])


def build_items(
    *,
    benchmark_root: Path,
    manifest_path: Path,
    base_prompt_path: Path,
    state_prompt_path: Path,
    conditions: Iterable[str] = CONDITIONS,
) -> list[EvaluationItem]:
    base_prompt = base_prompt_path.read_text()
    state_prompt = state_prompt_path.read_text()
    selected = tuple(conditions)
    unknown = set(selected) - set(CONDITIONS)
    if unknown:
        raise ValueError(f"unknown conditions: {sorted(unknown)}")

    items: list[EvaluationItem] = []
    for case in load_manifest(manifest_path):
        for variant, file_name in (("attack", "transcript.jsonl"), ("benign", "benign.jsonl")):
            session_paths = [benchmark_root / rel / file_name for rel in case["sessions"]]
            if not all(path.exists() for path in session_paths):
                missing = [str(path) for path in session_paths if not path.exists()]
                raise FileNotFoundError(f"missing {variant} session(s): {missing}")
            tracker = ProvenanceTracker()
            for index, path in enumerate(session_paths, start=1):
                tracker.consume(f"s{index}", load_jsonl(path))
            transcript = _transcript_text(session_paths[-1])

            for condition in selected:
                prompt = state_prompt if condition == "state_prompt" else base_prompt
                message = f"<transcript>\n{transcript}\n</transcript>"
                if condition in {
                    "provenance",
                    "neutral_provenance",
                    "policy_only",
                    "placebo",
                }:
                    overlay = render_json(
                        tracker.state.events,
                        placebo=condition == "placebo",
                        neutral=condition == "neutral_provenance",
                        policy_only=condition == "policy_only",
                    )
                    message += (
                        "\n<trusted_host_overlay>\n"
                        + overlay
                        + "\n</trusted_host_overlay>"
                    )
                item_id = f"{case['id']}--{variant}--{condition}"
                items.append(
                    EvaluationItem(
                        item_id=item_id,
                        case_id=case["id"],
                        stratum=case["stratum"],
                        variant=variant,
                        condition=condition,
                        system_prompt=prompt,
                        user_message=message,
                    )
                )
    return items


def parse_score(text: str) -> float:
    matches = _SCORE.findall(text)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one score tag, found {len(matches)}")
    score = float(matches[0])
    if not 0 <= score <= 100:
        raise ValueError(f"score outside [0,100]: {score}")
    return score


def estimate_cost(
    items: Iterable[EvaluationItem],
    *,
    max_output_tokens: int,
    input_price_per_million: float,
    output_price_per_million: float,
) -> dict[str, float | int]:
    item_list = list(items)
    input_tokens = sum(item.estimated_input_tokens for item in item_list)
    output_tokens = len(item_list) * max_output_tokens
    return {
        "calls": len(item_list),
        "estimated_input_tokens": input_tokens,
        "maximum_output_tokens": output_tokens,
        "estimated_maximum_cost_usd": (
            input_tokens * input_price_per_million
            + output_tokens * output_price_per_million
        )
        / 1_000_000,
    }


def shuffled_items(
    items: Iterable[EvaluationItem], *, seed: int
) -> list[EvaluationItem]:
    ordered = list(items)
    random.Random(seed).shuffle(ordered)
    return ordered


def order_fingerprint(items: Iterable[EvaluationItem]) -> str:
    payload = "\n".join(item.item_id for item in items).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
