from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Source = Literal["none", "project", "web"]
WebMode = Literal["lookup", "research"]
Task = Literal[
    "general",
    "explain-code",
    "debug",
    "implement",
    "architecture",
    "research",
]
Freshness = Literal["stable", "current", "unknown"]


@dataclass(frozen=True)
class RoutingDecision:
    source: Source
    web_mode: WebMode | None
    task: Task
    freshness: Freshness
    project_evidence: bool
    reason: str
