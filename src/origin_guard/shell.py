from __future__ import annotations

import posixpath
import re
import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class ShellObservation:
    operation: str
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    transfers: tuple[str, ...] = ()
    confidence: str = "heuristic"
    notes: tuple[str, ...] = ()


_PATHISH = re.compile(
    r"^(?:/|\./|\.\./|[A-Za-z0-9_.-]+/|s3://|gs://|https?://)[^\s]*$"
)
_REDIRECT = re.compile(r"(?:^|\s)(?:>>?|2>>?)\s*([^\s;&|]+)")
_COMMAND_SUB_RE = re.compile(r"[<]\s*([^\s;&|]+)")


def normalize_object(value: str, cwd: str | None) -> str:
    cleaned = value.strip("'\"()[]{};,:")
    if not cleaned:
        return cleaned
    if "://" in cleaned:
        return cleaned
    if cleaned.startswith("/"):
        return posixpath.normpath(cleaned)
    if cleaned.startswith("-") or "$" in cleaned or "*" in cleaned:
        return cleaned
    if cwd:
        return posixpath.normpath(posixpath.join(cwd, cleaned))
    return posixpath.normpath(cleaned)


def _path_tokens(command: str, cwd: str | None) -> list[str]:
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        tokens = command.split()
    values: list[str] = []
    for token in tokens:
        if _PATHISH.match(token):
            value = normalize_object(token, cwd)
            if value and value not in values:
                values.append(value)
    return values


def observe_shell(command: str, cwd: str | None = None) -> ShellObservation:
    """Conservatively identify observable objects in common shell operations.

    This is not a shell interpreter. Anything that cannot be established from
    simple syntax remains an unknown heuristic observation.
    """

    stripped = command.strip()
    paths = _path_tokens(stripped, cwd)
    redirection_writes = tuple(
        normalize_object(match, cwd) for match in _REDIRECT.findall(stripped)
    )
    redirected_reads = tuple(
        normalize_object(match, cwd) for match in _COMMAND_SUB_RE.findall(stripped)
    )

    try:
        tokens = shlex.split(stripped, comments=False, posix=True)
    except ValueError:
        tokens = stripped.split()
    executable = posixpath.basename(tokens[0]) if tokens else ""

    if executable in {"cat", "head", "tail", "wc", "grep", "sed", "awk"}:
        return ShellObservation(
            operation="inspect_or_transform",
            reads=tuple(dict.fromkeys(paths + list(redirected_reads))),
            writes=tuple(dict.fromkeys(redirection_writes)),
        )

    if executable in {"cp", "mv", "install"} and len(paths) >= 2:
        return ShellObservation(
            operation=executable,
            reads=tuple(paths[:-1]),
            writes=tuple(dict.fromkeys([paths[-1], *redirection_writes])),
        )

    if executable == "ln" and len(paths) >= 2:
        return ShellObservation(
            operation="link",
            reads=(paths[-2],),
            writes=(paths[-1],),
            notes=("link destination inherits data dependency from source",),
        )

    transfer_marker = (
        ("aws s3 cp" in stripped)
        or ("gsutil" in stripped and " cp " in f" {stripped} ")
        or executable in {"curl", "wget", "scp", "rsync"}
    )
    if transfer_marker:
        local_reads = tuple(p for p in paths if "://" not in p)
        remote = tuple(p for p in paths if "://" in p)
        return ShellObservation(
            operation="external_transfer",
            reads=tuple(dict.fromkeys([*local_reads, *redirected_reads])),
            writes=tuple(dict.fromkeys(redirection_writes)),
            transfers=remote,
        )

    write_words = {"rm", "touch", "mkdir", "chmod", "chown", "truncate"}
    if executable in write_words:
        return ShellObservation(
            operation=executable,
            writes=tuple(dict.fromkeys([*paths, *redirection_writes])),
        )

    return ShellObservation(
        operation="shell_command",
        reads=tuple(dict.fromkeys([*paths, *redirected_reads])),
        writes=tuple(dict.fromkeys(redirection_writes)),
        confidence="unknown_effects",
        notes=("command was not fully interpreted",),
    )
