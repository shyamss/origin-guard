from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .provenance import ProvenanceTracker
from .transcript import TranscriptFormatError, load_jsonl


@dataclass(frozen=True)
class CoverageReport:
    files: int
    transcript_blocks: int
    provenance_events: int
    tool_events: int
    unknown_effect_events: int
    parse_errors: tuple[str, ...]

    @property
    def unknown_effect_rate(self) -> float:
        if self.tool_events == 0:
            return 0.0
        return self.unknown_effect_events / self.tool_events


def audit_sleight(root: Path) -> CoverageReport:
    """Audit structural coverage without reading any benchmark sidecar labels."""

    paths = sorted(
        path
        for name in ("transcript.jsonl", "benign.jsonl")
        for path in root.glob(f"*/*/{name}")
    )
    block_count = 0
    event_count = 0
    tool_events = 0
    unknown_effects = 0
    errors: list[str] = []

    for index, path in enumerate(paths, start=1):
        try:
            blocks = load_jsonl(path)
        except TranscriptFormatError as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
            continue
        tracker = ProvenanceTracker()
        events = tracker.consume(f"audit-{index}", blocks)
        block_count += len(blocks)
        event_count += len(events)
        for event in events:
            if event.actor == "agent" and (
                event.operation.startswith("tool:")
                or event.operation
                in {
                    "read",
                    "write",
                    "edit",
                    "shell_command",
                    "inspect_or_transform",
                    "external_transfer",
                    "cp",
                    "mv",
                    "install",
                    "link",
                    "rm",
                    "touch",
                    "mkdir",
                    "chmod",
                    "chown",
                    "truncate",
                }
            ):
                tool_events += 1
            if event.confidence in {"unknown", "unknown_effects"}:
                unknown_effects += 1

    return CoverageReport(
        files=len(paths),
        transcript_blocks=block_count,
        provenance_events=event_count,
        tool_events=tool_events,
        unknown_effect_events=unknown_effects,
        parse_errors=tuple(errors),
    )
