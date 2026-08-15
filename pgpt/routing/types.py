from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Source = Literal[
    "none",
    "project",
    "web",
]

WebMode = Literal[
    "lookup",
    "research",
]

Task = Literal[
    "general",
    "explain-code",
    "debug",
    "implement",
    "architecture",
    "research",
]

Freshness = Literal[
    "stable",
    "current",
    "unknown",
]

Complexity = Literal[
    "simple",
    "standard",
    "complex",
]


@dataclass(frozen=True)
class RoutingDecision:
    source: Source
    web_mode: WebMode | None
    task: Task
    freshness: Freshness
    complexity: Complexity
    project_evidence: bool
    reason: str