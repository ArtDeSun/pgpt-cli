from __future__ import annotations

from dataclasses import dataclass

from pgpt.models.selector import select_model
from pgpt.routing.types import RoutingDecision


MODEL_TASK = {
    "web-lookup": "general",
    "research-web": "research",
}


@dataclass
class Route:
    """Concrete runtime plan."""

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
        selection = select_model(
            MODEL_TASK.get(template, decision.task),
            model_override=model_override,
        )

        return cls(
            decision=decision,
            execution=execution,
            template=template,
            model=selection.model,
            deep=bool(deep_override),
            project=project_name if decision.source == "project" else None,
            reason=(
                f"{decision.reason}; execution={execution}; "
                f"template={template}; {selection.reason}"
            ),
        )


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
    return "web-lookup" if decision.task == "general" else decision.task
