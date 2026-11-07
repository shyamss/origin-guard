from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ObjectOrigin(StrEnum):
    DIRECT_USER = "direct_user"
    AGENT_CLAIM = "agent_claim"
    AGENT_WRITTEN_CURRENT_SESSION = "agent_written_current_session"
    AGENT_WRITTEN_PRIOR_SESSION = "agent_written_prior_session"
    ENVIRONMENT_UNKNOWN = "environment_unknown"
    COMMAND_OUTPUT = "command_output"
    UNKNOWN = "unknown"


class Authority(StrEnum):
    USER_AUTHORIZATION = "user_authorization"
    UNTRUSTED_AGENT_CONTENT = "untrusted_agent_content"
    OBSERVATION_NOT_AUTHORIZATION = "observation_not_authorization"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TranscriptBlock:
    index: int
    role: str
    content: dict[str, Any]
    cwd: str | None = None

    @property
    def content_type(self) -> str:
        return str(self.content.get("type", "unknown"))


@dataclass
class ObjectState:
    object_id: str
    last_write_event_id: int
    last_write_session_id: str
    created_by_agent: bool = True


@dataclass(frozen=True)
class ProvenanceEvent:
    event_id: int
    session_id: str
    transcript_index: int
    actor: str
    operation: str
    objects: tuple[str, ...] = ()
    object_origins: tuple[str, ...] = ()
    authority: str = Authority.UNKNOWN
    depends_on: tuple[int, ...] = ()
    confidence: str = "structural"
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceState:
    objects: dict[str, ObjectState] = field(default_factory=dict)
    events: list[ProvenanceEvent] = field(default_factory=list)
    pending_tools: dict[str, int] = field(default_factory=dict)
    pending_tool_objects: dict[str, tuple[str, ...]] = field(default_factory=dict)
    pending_tool_origins: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def next_event_id(self) -> int:
        return len(self.events) + 1
