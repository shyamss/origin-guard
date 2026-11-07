from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .model import (
    Authority,
    ObjectOrigin,
    ObjectState,
    ProvenanceEvent,
    ProvenanceState,
    TranscriptBlock,
)
from .shell import normalize_object, observe_shell


class ProvenanceTracker:
    """Build provenance solely from observable transcript structure."""

    def __init__(self) -> None:
        self.state = ProvenanceState()

    def _origin_for(self, object_id: str, session_id: str) -> tuple[str, tuple[int, ...]]:
        item = self.state.objects.get(object_id)
        if item is None:
            return ObjectOrigin.ENVIRONMENT_UNKNOWN, ()
        if item.last_write_session_id == session_id:
            origin = ObjectOrigin.AGENT_WRITTEN_CURRENT_SESSION
        else:
            origin = ObjectOrigin.AGENT_WRITTEN_PRIOR_SESSION
        return origin, (item.last_write_event_id,)

    def _append(
        self,
        *,
        session_id: str,
        transcript_index: int,
        actor: str,
        operation: str,
        objects: Iterable[str] = (),
        origins: Iterable[str] = (),
        authority: str = Authority.UNKNOWN,
        depends_on: Iterable[int] = (),
        confidence: str = "structural",
        notes: Iterable[str] = (),
    ) -> ProvenanceEvent:
        event = ProvenanceEvent(
            event_id=self.state.next_event_id(),
            session_id=session_id,
            transcript_index=transcript_index,
            actor=actor,
            operation=operation,
            objects=tuple(objects),
            object_origins=tuple(origins),
            authority=authority,
            depends_on=tuple(sorted(set(depends_on))),
            confidence=confidence,
            notes=tuple(notes),
        )
        self.state.events.append(event)
        return event

    def _record_writes(self, event: ProvenanceEvent, paths: Iterable[str]) -> None:
        for path in paths:
            if not path or "$" in path or "*" in path:
                continue
            self.state.objects[path] = ObjectState(
                object_id=path,
                last_write_event_id=event.event_id,
                last_write_session_id=event.session_id,
            )

    def consume(self, session_id: str, blocks: Iterable[TranscriptBlock]) -> list[ProvenanceEvent]:
        start = len(self.state.events)
        for block in blocks:
            self._consume_block(session_id, block)
        return self.state.events[start:]

    def _consume_block(self, session_id: str, block: TranscriptBlock) -> None:
        kind = block.content_type

        if kind == "text":
            if block.role == "user":
                self._append(
                    session_id=session_id,
                    transcript_index=block.index,
                    actor="user",
                    operation="instruction",
                    origins=(ObjectOrigin.DIRECT_USER,),
                    authority=Authority.USER_AUTHORIZATION,
                )
            else:
                self._append(
                    session_id=session_id,
                    transcript_index=block.index,
                    actor="agent",
                    operation="claim",
                    origins=(ObjectOrigin.AGENT_CLAIM,),
                    authority=Authority.UNTRUSTED_AGENT_CONTENT,
                )
            return

        if kind == "thinking":
            self._append(
                session_id=session_id,
                transcript_index=block.index,
                actor="agent",
                operation="private_reasoning_record",
                origins=(ObjectOrigin.AGENT_CLAIM,),
                authority=Authority.UNTRUSTED_AGENT_CONTENT,
            )
            return

        if kind == "tool_use":
            self._consume_tool_use(session_id, block)
            return

        if kind == "tool_result":
            tool_id = str(block.content.get("tool_use_id", ""))
            dependency = self.state.pending_tools.get(tool_id)
            objects = self.state.pending_tool_objects.get(tool_id, ())
            origins = self.state.pending_tool_origins.get(
                tool_id, (ObjectOrigin.COMMAND_OUTPUT,)
            )
            self._append(
                session_id=session_id,
                transcript_index=block.index,
                actor="environment",
                operation="tool_result",
                objects=objects,
                origins=origins,
                authority=Authority.OBSERVATION_NOT_AUTHORIZATION,
                depends_on=(() if dependency is None else (dependency,)),
            )
            return

        self._append(
            session_id=session_id,
            transcript_index=block.index,
            actor=block.role,
            operation="unknown_content_block",
            origins=(ObjectOrigin.UNKNOWN,),
            authority=Authority.UNKNOWN,
            confidence="unknown",
        )

    def _consume_tool_use(self, session_id: str, block: TranscriptBlock) -> None:
        content = block.content
        tool_name = str(content.get("name", "unknown"))
        tool_id = str(content.get("id", ""))
        inputs = content.get("input")
        inputs = inputs if isinstance(inputs, dict) else {}

        if tool_name in {"Read", "Write", "Edit"}:
            raw_path = str(inputs.get("file_path", ""))
            object_id = normalize_object(raw_path, block.cwd)
            origin, deps = self._origin_for(object_id, session_id)
            operation = tool_name.lower()
            authority = (
                Authority.UNTRUSTED_AGENT_CONTENT
                if operation in {"write", "edit"}
                else Authority.OBSERVATION_NOT_AUTHORIZATION
            )
            event = self._append(
                session_id=session_id,
                transcript_index=block.index,
                actor="agent",
                operation=operation,
                objects=(object_id,),
                origins=(origin,),
                authority=authority,
                depends_on=deps,
            )
            if operation in {"write", "edit"}:
                self._record_writes(event, (object_id,))
            if tool_id:
                self.state.pending_tools[tool_id] = event.event_id
                self.state.pending_tool_objects[tool_id] = (object_id,)
                self.state.pending_tool_origins[tool_id] = (
                    self._origin_for(object_id, session_id)[0],
                )
            return

        if tool_name == "Bash":
            command = str(inputs.get("command", ""))
            observation = observe_shell(command, block.cwd)
            objects = tuple(dict.fromkeys([
                *observation.reads,
                *observation.writes,
                *observation.transfers,
            ]))
            origins: list[str] = []
            deps: list[int] = []
            for object_id in objects:
                origin, object_deps = self._origin_for(object_id, session_id)
                origins.append(origin)
                deps.extend(object_deps)
            event = self._append(
                session_id=session_id,
                transcript_index=block.index,
                actor="agent",
                operation=observation.operation,
                objects=objects,
                origins=origins,
                authority=Authority.UNTRUSTED_AGENT_CONTENT,
                depends_on=deps,
                confidence=observation.confidence,
                notes=observation.notes,
            )
            self._record_writes(event, observation.writes)
            if tool_id:
                self.state.pending_tools[tool_id] = event.event_id
                self.state.pending_tool_objects[tool_id] = objects
                self.state.pending_tool_origins[tool_id] = tuple(origins)
            return

        event = self._append(
            session_id=session_id,
            transcript_index=block.index,
            actor="agent",
            operation=f"tool:{tool_name}",
            authority=Authority.UNTRUSTED_AGENT_CONTENT,
            confidence="unknown_effects",
        )
        if tool_id:
            self.state.pending_tools[tool_id] = event.event_id


def event_object_origin(event: ProvenanceEvent, object_id: str) -> str | None:
    """Return the origin paired with ``object_id`` in an event."""

    try:
        index = event.objects.index(object_id)
    except ValueError:
        return None
    if index >= len(event.object_origins):
        return None
    return event.object_origins[index]
