from __future__ import annotations

import re
from datetime import datetime

from pgpt.routing.classifier import classify_web_need
from pgpt.routing.rules import load_rule
from pgpt.routing.types import RoutingDecision, Task


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
_SYMBOL_INTENT = re.compile(r"\b(?:explain|review|analyze|find|where|modify|change|update|fix|add|implement|refactor)\b", re.I)
_CURRENT_QUESTION = re.compile(r"\b(?:who|what|when|where|which|winner|won|champion|result|released|version|price|status)\b", re.I)


def _matches(name: str, prompt: str) -> bool:
    return bool(load_rule(name).search(prompt))


def _current_year_question(prompt: str) -> bool:
    return str(datetime.now().year) in prompt and bool(_CURRENT_QUESTION.search(prompt))


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
    if _matches("implement", prompt) or (symbol_hit and _matches("change", prompt)):
        return "implement"
    if (symbol_hit and bool(_SYMBOL_INTENT.search(prompt))) or _matches("explain-code", prompt):
        return "explain-code"
    return "explain-code" if project_evidence else "general"


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
    del model_override, deep_override

    explicit_web = _matches("explicit-web", prompt)
    explicit_project = _matches("explicit-project", prompt)
    writing = _matches("writing", prompt)
    current = _matches("current", prompt) or (_current_year_question(prompt) and not writing)
    named_project = bool(project_name and project_name.casefold() in prompt.casefold())
    symbol_project = bool(symbol_hit and _SYMBOL_INTENT.search(prompt))
    project_evidence = bool(explicit_project or named_project or symbol_project or project_override is True)
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
        source, reason = "web", "explicit --web research"
    elif web_override in {"on", "lookup"}:
        source, reason = "web", "explicit --web lookup"
    elif project_override is True:
        source, reason = "project", "explicit project context"
    elif explicit_web:
        source, reason = "web", "explicit web request"
    elif project_evidence and project_override is not False:
        source, reason = "project", "project context"
    elif task == "research" and web_override != "off":
        source, reason = "web", "research requires web"
    elif current and not writing and web_override != "off":
        source, reason = "web", "current public information"
    elif web_need == "yes" and web_override != "off":
        source, reason = "web", "classifier: web needed"
    else:
        source, reason = "none", "local"

    if web_override == "off" and source == "web":
        source, reason = "none", "web disabled"

    if source == "project" and task == "general":
        task = "explain-code"

    web_mode = None
    if source == "web":
        web_mode = "research" if web_override == "research" or task == "research" else "lookup"

    if source == "project" or (writing and source == "none"):
        freshness = "stable"
    elif current or web_need == "yes":
        freshness = "current"
    elif source == "web" or (web_override == "off" and task == "general"):
        freshness = "unknown"
    else:
        freshness = "stable"

    return RoutingDecision(
        source=source,  # type: ignore[arg-type]
        web_mode=web_mode,  # type: ignore[arg-type]
        task=task,
        freshness=freshness,  # type: ignore[arg-type]
        project_evidence=project_evidence,
        reason=reason,
    )
