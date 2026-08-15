from __future__ import annotations

from dataclasses import dataclass

from pgpt.models.selector import select_model
from pgpt.routing.types import RoutingDecision


_TASK_TEMPLATE = {
    "general": "general",
    "research": "research",
    "explain-code": "explain-code",
    "debug": "debug",
    "implement": "implement",
    "architecture": "architecture",
}


_TEMPLATE_TASK = {
    "general": "general",
    "web-lookup": "general",
    "research": "research",
    "research-web": "research",
    "explain-code": "explain-code",
    "debug": "debug",
    "implement": "implement",
    "architecture": "architecture",
}


@dataclass
class Route:
    """
    Runtime execution plan.

    RoutingDecision describes what the request means.

    Route describes how the runtime will execute that
    already-classified request.
    """

    decision: RoutingDecision
    execution: str
    template: str
    model: str
    deep: bool
    project: str | None
    reason: str

    @classmethod
    def from_decision(
        cls,
        decision: RoutingDecision,
        *,
        project_name: str,
        template_override: str | None,
        model_override: str | None,
        deep_override: bool | None,
    ) -> "Route":
        execution = _execution_from_decision(
            decision
        )

        template = _template_from_decision(
            decision
        )

        if template_override is not None:
            template = template_override

        selection_task = _TEMPLATE_TASK.get(
            template,
            decision.task,
        )

        selection = select_model(
            selection_task,
            model_override=model_override,
        )

        # Complexity is currently telemetry only.
        # Automatic deep escalation remains disabled until
        # we have evidence that it improves end-to-end quality.
        deep = (
            bool(deep_override)
            if deep_override is not None
            else False
        )

        project = (
            project_name
            if decision.source == "project"
            else None
        )

        reason_parts = [
            decision.reason,
            (
                f"execution={execution}"
            ),
            (
                f"template={template}"
            ),
            selection.reason,
        ]

        if (
            decision.complexity
            == "complex"
            and deep_override is None
        ):
            reason_parts.append(
                "complexity=complex is telemetry only"
            )

        return cls(
            decision=decision,
            execution=execution,
            template=template,
            model=selection.model,
            deep=deep,
            project=project,
            reason="; ".join(
                part
                for part in reason_parts
                if part
            ),
        )


def _execution_from_decision(
    decision: RoutingDecision,
) -> str:
    if decision.source == "project":
        return "project"

    if decision.source == "web":
        if decision.web_mode == "research":
            return "web_research"

        return "web_lookup"

    return "local"


def _template_from_decision(
    decision: RoutingDecision,
) -> str:
    if decision.source == "web":
        if decision.web_mode == "research":
            return "research-web"

        # Preserve task-specific behavior for web debugging,
        # architecture, and code explanation.
        if decision.task in {
            "debug",
            "architecture",
            "explain-code",
            "implement",
        }:
            return decision.task

        return "web-lookup"

    return _TASK_TEMPLATE.get(
        decision.task,
        "general",
    )
