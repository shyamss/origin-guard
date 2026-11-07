from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .model import TranscriptBlock


class TranscriptFormatError(ValueError):
    pass


def parse_jsonl_lines(lines: Iterable[str]) -> list[TranscriptBlock]:
    """Parse transcript JSONL while ignoring an explicit benchmark canary row.

    A canary row is ignored only when it has a ``canary`` field and no ``role``.
    Other malformed or empty rows fail closed instead of being silently skipped.
    """

    blocks: list[TranscriptBlock] = []
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TranscriptFormatError(
                f"line {line_number} is not valid JSON: {exc.msg}"
            ) from exc

        if "canary" in item and "role" not in item:
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"}:
            raise TranscriptFormatError(
                f"line {line_number} has unsupported role {role!r}"
            )
        if not isinstance(content, dict):
            raise TranscriptFormatError(
                f"line {line_number} content must be an object"
            )
        blocks.append(
            TranscriptBlock(
                index=len(blocks),
                role=role,
                content=content,
                cwd=item.get("cwd"),
            )
        )
    if not blocks:
        raise TranscriptFormatError("transcript has no message blocks")
    return blocks


def load_jsonl(path: Path) -> list[TranscriptBlock]:
    return parse_jsonl_lines(path.read_text(encoding="utf-8").splitlines())
