from __future__ import annotations

from pgpt.routing.classifier import (
    ClassifierDecision,
    classify_route_semantics,
    classify_web_mode,
)
from pgpt.routing.rules import load_rule
from pgpt.routing.types import RoutingDecision


def _matches(rule_name: str, prompt: str) -> bool:
    return bool(load_rule(rule_name).search(prompt))


def _explicit_web(prompt: str) -> bool:
    return _matches("explicit-web", prompt)


def _explicit_project(prompt: str) -> bool:
    return _matches("explicit-project", prompt)


def _current_external_hint(prompt: str) -> bool:
    return _matches("current-external", prompt) or _matches("live-lookup", prompt)


def _research_hint(prompt: str) -> bool:
    return _matches("research", prompt)


def _fast_semantics(prompt: str) -> ClassifierDecision | None:
    current = _current_external_hint(prompt)
    if _research_hint(prompt):
        return ClassifierDecision(
            task="research",
            freshness="current" if current else "unknown",
            complexity="complex",
        )
    if _matches("debug", prompt):
        return ClassifierDecision(
            task="debug",
            freshness="current" if current else "stable",
            complexity="standard",
        )
    if _matches("architecture", prompt):
        return ClassifierDecision(
            task="architecture",
            freshness="current" if current else "stable",
            complexity="complex",
        )
    if _matches("writing", prompt):
        return ClassifierDecision(
            task="general",
            freshness="stable",
            complexity="simple",
        )
    if current:
        return ClassifierDecision(
            task="general",
            freshness="current",
            complexity="simple",
        )
    return None


def _task_from_template(template: str) -> str | None:
    return {
        "general": "general",
        "web-lookup": "general",
        "research-web": "research",
        "research": "research",
        "explain-code": "explain-code",
        "debug": "debug",
        "implement": "implement",
        "architecture": "architecture",
    }.get(template)


def _normalize_task(
    *,
    prompt: str,
    task: str,
    source: str,
    web_mode: str | None,
    project_evidence: bool,
    symbol_hit: bool,
) -> str:
    if _matches("writing", prompt):
        return "general"
    if source == "web" and web_mode == "research" and _research_hint(prompt):
        return "research"
    if _matches("debug", prompt):
        return "debug"
    if _matches("architecture", prompt):
        return "architecture"
    if (
        source == "web"
        and web_mode == "lookup"
        and _matches("focused-web-navigation", prompt)
        and task in {"research", "architecture"}
    ):
        return "general"
    if (
        symbol_hit
        and source == "project"
        and task == "debug"
        and not _matches("debug", prompt)
    ):
        return "explain-code"
    if project_evidence and source == "project" and task == "general":
        return "explain-code"
    if source == "none" and task == "explain-code" and not _matches("code-object", prompt):
        return "general"
    return task


def _normalize_freshness(
    *,
    prompt: str,
    freshness: str,
    source: str,
    task: str,
    explicit_web: bool,
    project_evidence: bool,
) -> str:
    if _current_external_hint(prompt):
        return "current"
    if _matches("conversational-followup", prompt) or _matches("vague-context-reference", prompt):
        return "unknown"
    if project_evidence and source == "project":
        return "stable"
    if explicit_web:
        if _matches("focused-web-navigation", prompt) or task == "debug":
            return "unknown"
    if source == "none" and task in {
        "general",
        "explain-code",
        "debug",
        "implement",
        "architecture",
    }:
        return "unknown" if freshness == "unknown" else "stable"
    if _matches("writing", prompt):
        return "stable"
    return freshness


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

    semantic = _fast_semantics(prompt)
    if semantic is not None:
        semantic_reason = "deterministic fast semantic path"
    else:
        semantic = classify_route_semantics(prompt)
        semantic_reason = "semantic classifier"

    if semantic is None:
        task = "general"
        freshness = "unknown"
        complexity = "standard"
        semantic_reason = "semantic classifier unavailable"
    else:
        task = semantic.task
        freshness = semantic.freshness
        complexity = semantic.complexity

    explicit_web = _explicit_web(prompt)
    explicit_project = _explicit_project(prompt)
    strong_current = _current_external_hint(prompt)
    semantic_current = freshness == "current"
    research_requested = _research_hint(prompt)
    project_evidence = bool(
        symbol_hit
        or explicit_project
        or project_override is True
    )
    reasons = [semantic_reason]

    if web_override == "research":
        source = "web"
        reasons.append("explicit web research override")
    elif web_override in {"on", "lookup"}:
        source = "web"
        reasons.append("explicit web lookup override")
    elif project_override is True:
        source = "project"
        reasons.append("explicit project override")
    elif explicit_web:
        source = "web"
        reasons.append("explicit natural-language web request")
    elif project_evidence:
        source = "project"
        reasons.append("project evidence detected")
    elif (strong_current or semantic_current) and web_override != "off":
        source = "web"
        if strong_current:
            reasons.append("strong current external-information evidence")
        else:
            reasons.append("semantic classifier marked freshness as current")
    elif research_requested and task == "research" and web_override != "off":
        source = "web"
        reasons.append("multi-source research requires web retrieval")
    else:
        source = "none"
        reasons.append("no retrieval requirement established")

    if project_override is False and source == "project":
        source = "none"
        reasons.append("project retrieval disabled")
    if web_override == "off" and source == "web":
        source = "none"
        reasons.append("web retrieval disabled")

    web_mode: str | None = None
    if source == "web":
        if web_override == "research":
            web_mode = "research"
        elif web_override in {"on", "lookup"}:
            web_mode = "lookup"
        elif research_requested and task == "research":
            web_mode = "research"
        elif (
            _matches("live-lookup", prompt)
            or strong_current
            or (semantic_current and not research_requested)
        ):
            web_mode = "lookup"
        else:
            web_mode = classify_web_mode(prompt) or "lookup"
            if web_mode == "lookup":
                reasons.append("web mode defaulted to lookup")

    if template_override is not None:
        override_task = _task_from_template(template_override)
        if override_task is not None:
            task = override_task
            reasons.append("explicit template override")

    normalized_task = _normalize_task(
        prompt=prompt,
        task=task,
        source=source,
        web_mode=web_mode,
        project_evidence=project_evidence,
        symbol_hit=symbol_hit,
    )
    if normalized_task != task:
        task = normalized_task
        reasons.append("task normalized from strong request evidence")

    normalized_freshness = _normalize_freshness(
        prompt=prompt,
        freshness=freshness,
        source=source,
        task=task,
        explicit_web=explicit_web,
        project_evidence=project_evidence,
    )
    if normalized_freshness != freshness:
        freshness = normalized_freshness
        reasons.append("freshness normalized from strong request evidence")

    if (
        source == "web"
        and web_override is None
        and task != "research"
        and web_mode == "research"
        and not research_requested
    ):
        web_mode = "lookup"
        reasons.append("web mode normalized to focused lookup")

    if (
        symbol_hit
        and source == "project"
        and template_override is None
        and task == "general"
    ):
        task = "explain-code"
        reasons.append("exact project symbol promoted general task to explain-code")

    return RoutingDecision(
        source=source,
        web_mode=web_mode,  # type: ignore[arg-type]
        task=task,  # type: ignore[arg-type]
        freshness=freshness,  # type: ignore[arg-type]
        complexity=complexity,
        project_evidence=project_evidence,
        reason="; ".join(reasons),
    )
