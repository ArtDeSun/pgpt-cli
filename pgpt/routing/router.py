from __future__ import annotations

from pgpt.routing.classifier import classify_web_need
from pgpt.routing.rules import load_rule
from pgpt.routing.types import Complexity, RoutingDecision, Task


_TEMPLATE_TASK: dict[str, Task] = {
    "general": "general",
    "web-lookup": "general",
    "research-web": "research",
    "research": "research",
    "explain-code": "explain-code",
    "debug": "debug",
    "implement": "implement",
    "architecture": "architecture",
}

_TASK_COMPLEXITY: dict[Task, Complexity] = {
    "general": "simple",
    "explain-code": "standard",
    "debug": "standard",
    "implement": "standard",
    "architecture": "complex",
    "research": "complex",
}


def _matches(name: str, prompt: str) -> bool:
    return bool(load_rule(name).search(prompt))


def _task(
    prompt: str,
    *,
    symbol_hit: bool,
    project_evidence: bool,
    template_override: str | None,
) -> Task:
    if template_override in _TEMPLATE_TASK:
        return _TEMPLATE_TASK[template_override]
    if _matches("research", prompt):
        return "research"
    if _matches("debug", prompt):
        return "debug"
    if _matches("architecture", prompt):
        return "architecture"
    if _matches("implement", prompt):
        return "implement"
    if symbol_hit or _matches("explain-code", prompt):
        return "explain-code"
    if project_evidence:
        return "explain-code"
    return "general"


def resolve_route(
    prompt: str,
    *,
    project_name: str,
    web_override: str | None,
    project_override: bool | None,
    template_override: str | None,
    model_override: str | None,
    deep_override: bool | None,
    symbol_hit: bool,
) -> RoutingDecision:
    del project_name, model_override, deep_override

    explicit_web = _matches("explicit-web", prompt)
    explicit_project = _matches("explicit-project", prompt)
    current = _matches("current", prompt)
    writing = _matches("writing", prompt)

    project_evidence = bool(
        symbol_hit or explicit_project or project_override is True
    )
    task = _task(
        prompt,
        symbol_hit=symbol_hit,
        project_evidence=project_evidence,
        template_override=template_override,
    )

    web_need = "no"
    if (
        web_override is None
        and project_override is not True
        and not explicit_web
        and not project_evidence
        and not current
        and task == "general"
        and not writing
    ):
        web_need = classify_web_need(prompt)

    if web_override == "research":
        source = "web"
        reason = "explicit --web research"
    elif web_override in {"on", "lookup"}:
        source = "web"
        reason = "explicit --web lookup"
    elif project_override is True:
        source = "project"
        reason = "explicit project context"
    elif explicit_web:
        source = "web"
        reason = "explicit web request"
    elif project_evidence and project_override is not False:
        source = "project"
        reason = "project context"
    elif task == "research" and web_override != "off":
        source = "web"
        reason = "research requires web"
    elif current and web_override != "off":
        source = "web"
        reason = "current public information"
    elif web_need == "yes" and web_override != "off":
        source = "web"
        reason = "classifier: web needed"
    else:
        source = "none"
        reason = "local"

    if web_override == "off" and source == "web":
        source = "none"
        reason = "web disabled"

    if source == "project" and task == "general":
        task = "explain-code"

    web_mode = None
    if source == "web":
        web_mode = (
            "research"
            if web_override == "research" or task == "research"
            else "lookup"
        )

    if source == "project":
        freshness = "stable"
    elif current or web_need == "yes":
        freshness = "current"
    elif source == "web":
        freshness = "unknown"
    elif web_override == "off" and task == "general":
        freshness = "unknown"
    else:
        freshness = "stable"

    return RoutingDecision(
        source=source,  # type: ignore[arg-type]
        web_mode=web_mode,  # type: ignore[arg-type]
        task=task,
        freshness=freshness,  # type: ignore[arg-type]
        complexity=_TASK_COMPLEXITY[task],
        project_evidence=project_evidence,
        reason=reason,
    )
