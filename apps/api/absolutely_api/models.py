from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"


@dataclass(slots=True)
class CommandEvent:
    command: str
    cwd: str
    timestamp_start: datetime
    timestamp_end: datetime
    duration_ms: int
    exit_code: int
    shell: str
    host: str
    session_id: str
    stdout: str | None = None
    stderr: str | None = None
    actor_type: ActorType = ActorType.HUMAN
    actor_name: str | None = None
    agent_session_id: str = ""
    repository_name: str | None = None
    repository_root: str | None = None
    git_branch: str | None = None
    git_commit_hash: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SessionRecord:
    session_key: str
    host: str
    shell: str
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None = None
    session_type: str = "terminal"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RepositoryRecord:
    root_path: str
    host: str
    name: str
    first_seen_at: datetime
    last_seen_at: datetime
    branch: str | None = None
    current_commit_hash: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentRecord:
    actor_type: ActorType
    actor_name: str
    host: str
    first_seen_at: datetime
    last_seen_at: datetime
    agent_session_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommitRecord:
    repository_id: str
    commit_hash: str
    message: str
    authored_at: datetime
    committed_at: datetime
    session_record_id: str | None = None
    author_name: str | None = None
    diff_summary: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FileChangeRecord:
    repository_id: str
    commit_id: str | None
    path: str
    change_type: str
    lines_added: int = 0
    lines_removed: int = 0
    old_path: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingRecord:
    entity_type: str
    entity_id: str
    model_name: str
    vector: list[float]
    dimensions: int
    created_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DailySummaryRecord:
    summary_date: str
    host: str
    worked_ms: int
    commands_count: int
    commits_count: int
    repositories: list[str] = field(default_factory=list)
    top_tools: list[str] = field(default_factory=list)
    summary_text: str = ""
    mistake_text: str | None = None
    created_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

