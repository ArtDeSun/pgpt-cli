from __future__ import annotations

from dataclasses import dataclass

from pgpt.models.selector import select_model
from pgpt.routing.types import RoutingDecision


_TASK_TEMPLATES = {
    "general",
    "research",
    "explain-code",
    "debug",
    "implement",
    "architecture",
}


@dataclass
class Route:
    """Concrete runtime plan built from a routing decision."""

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
        execution = _execution(decision)
        template = template_override or _template(decision)
        model_task = _model_task(template, decision.task)
        selection = select_model(model_task, model_override=model_override)

        return cls(
            decision=decision,
            execution=execution,
            template=template,
            model=selection.model,
            deep=bool(deep_override),
            project=project_name if decision.source == "project" else None,
            reason="; ".join(
                (
                    decision.reason,
                    f"execution={execution}",
                    f"template={template}",
                    selection.reason,
                )
            ),
        )


def _model_task(template: str, fallback: str) -> str:
    if template == "web-lookup":
        return "general"
    if template == "research-web":
        return "research"
    return template if template in _TASK_TEMPLATES else fallback


def _execution(decision: RoutingDecision) -> str:
    if decision.source == "project":
        return "project"
    if decision.source == "web":
        return "web_research" if decision.web_mode == "research" else "web_lookup"
    return "local"


def _template(decision: RoutingDecision) -> str:
    if decision.source != "web":
        return decision.task
    if decision.web_mode == "research":
        return "research-web"
    if decision.task in {"debug", "architecture", "explain-code", "implement"}:
        return decision.task
    return "web-lookup"
