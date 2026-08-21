from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from pgpt.config import CONFIG, cfg_path, get_project
from pgpt.generation.ollama import list_models, stream_chat
from pgpt.output.stream import ResponseWriter
from pgpt.quality.repair import apply_deterministic_repairs, stream_repair
from pgpt.quality.verify import verify_answer
from pgpt.retrieval.project import build_context as build_project_context, has_symbol_hit
from pgpt.retrieval.web import (
    WebResult,
    brave_search,
    build_source_footer,
    build_web_context,
    connectivity_ok,
    fetch_sources,
)
from pgpt.routing.router import resolve_route
from pgpt.runtime.history import select_history
from pgpt.runtime.route import Route
from pgpt.runtime.status import StatusCallback, StatusReporter
from pgpt.runtime.timing import Timing

_OLLAMA_METRICS = ("load_duration", "prompt_eval_duration", "prompt_eval_count", "eval_duration", "eval_count", "total_duration")
_RUNTIME_MODELS = re.compile(r"\b(?:what|which|list|show|tell me)\b.{0,50}\b(?:ollama\s+)?models?\b|\bmodels?\b.{0,40}\b(?:installed|available|access)\b", re.IGNORECASE)
ChunkCallback = Callable[[str], None]
ReplaceCallback = Callable[[str], None]

@dataclass
class PipelineResult:
    route: Route
    response_path: Path
    answer: str
    timing: Timing

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:48] or "response"

def response_path(prompt: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return cfg_path("responses_dir") / f"{stamp}-{_slug(prompt)}.md"

def _prompt_root() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"

def _load_prompt(template: str) -> str:
    root = _prompt_root()
    system = (root / "system.md").read_text(encoding="utf-8").strip()
    path = root / f"{template}.md"
    specific = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    return f"{system}\n\n{specific}".strip()

def _load_runtime_prompt(name: str, **values: str) -> str:
    text = (_prompt_root() / "runtime" / f"{name}.md").read_text(encoding="utf-8").strip()
    return text.format(**values) if values else text

def _system_prompt(route: Route, *, context: str, offline_web: bool, project_files: list[str], runtime_facts: str = "") -> str:
    parts = [_load_prompt(route.template)]
    if route.execution == "project":
        parts.append(_load_runtime_prompt("project-context"))
        if project_files:
            parts.append(_load_runtime_prompt("retrieved-files", files=", ".join(project_files)))
    if route.execution.startswith("web") and not offline_web:
        parts.append(_load_runtime_prompt("web-context"))
    if offline_web:
        parts.append(_load_runtime_prompt("offline-web"))
    if runtime_facts:
        parts.append(runtime_facts)
    if context:
        parts.append(_load_runtime_prompt("context", context=context))
    return "\n\n".join(parts)

def _runtime_facts(prompt: str) -> str:
    if not _RUNTIME_MODELS.search(prompt):
        return ""
    try:
        models = list_models()
    except Exception as exc:
        return f"Runtime fact: Ollama model listing failed: {exc}"
    if not models:
        return "Runtime fact: Ollama currently reports no installed models."
    return "Runtime fact: installed Ollama models are:\n" + "\n".join(f"- {name}" for name in models)

def _generate_once(*, route: Route, messages: list[dict[str, str]], on_text: ChunkCallback, max_tokens: int, num_ctx: int) -> dict:
    return stream_chat(model=route.model, messages=messages, on_text=on_text, max_tokens=max_tokens, num_ctx=num_ctx, temperature=float(CONFIG["defaults"].get("temperature", 0.1)))

def _merge_metrics(target: dict, extra: dict) -> None:
    for key in _OLLAMA_METRICS:
        first, second = target.get(key, 0) or 0, extra.get(key, 0) or 0
        if isinstance(first, (int, float)) and isinstance(second, (int, float)):
            target[key] = first + second

def _generation_settings(route: Route, answer_length: str | None) -> tuple[int, int]:
    performance = CONFIG["performance"]
    if answer_length and answer_length != "auto":
        try:
            max_tokens = int(performance["answer_lengths"][answer_length])
        except KeyError as exc:
            raise ValueError(f"Unknown answer length: {answer_length}") from exc
    else:
        max_tokens = int(performance["max_tokens_by_template"].get(route.template, 1000))
    coder_templates = set(CONFIG["models"].get("coder_templates", []))
    role = "deep" if route.deep else "coder" if route.template in coder_templates else "general"
    return max_tokens, int(performance["num_ctx_by_role"].get(role, 4096))

def _clean_continuation(text: str) -> str:
    instruction = _load_runtime_prompt("continue")
    cleaned = text.strip()
    if cleaned.casefold().startswith(instruction.casefold()):
        cleaned = cleaned[len(instruction):].lstrip(" :\n-")
    return re.sub(r"^\s*(?:continue(?:d|ing)?(?: the answer)?|continuation)\s*[:.-]?\s*", "", cleaned, count=1, flags=re.IGNORECASE)

def run(prompt: str, *, project_name: str | None = None, web_override: str | None = None, project_override: bool | None = None, template_override: str | None = None, model_override: str | None = None, deep_override: bool | None = None, history: list[dict[str, str]] | None = None, history_mode: str | None = None, answer_length: str | None = None, echo_route: bool = True, on_chunk: ChunkCallback | None = None, on_replace: ReplaceCallback | None = None, on_status: StatusCallback | None = None) -> PipelineResult:
    timing = Timing()
    project_name, _ = get_project(project_name)
    out = ResponseWriter(response_path(prompt), prompt=prompt)
    forced_web = web_override in {"on", "lookup", "research"}
    def status_update(frame: str, label: str, elapsed: float, completed: bool) -> None:
        out.update_status(frame, label, elapsed, completed)
        if on_status is not None:
            on_status(frame, label, elapsed, completed)
    status = StatusReporter(on_update=status_update)
    answer_parts: list[str] = []
    route: Route | None = None
    final: dict = {}
    web_results: list[WebResult] = []
    project_files: list[str] = []
    system = ""
    quality = None
    def emit(chunk: str) -> None:
        if not chunk:
            return
        answer_parts.append(chunk); out.write(chunk)
        if on_chunk is not None:
            on_chunk(chunk)
    def replace(answer: str) -> None:
        answer_parts[:] = [answer]; out.replace_answer(answer)
        if on_replace is not None:
            on_replace(answer)
    try:
        status.start("Routing request")
        try:
            with timing.phase("Routing"):
                symbol_hit = has_symbol_hit(prompt, project_name)
                decision = resolve_route(prompt, project_name=project_name, web_override=web_override, project_override=project_override, template_override=template_override, model_override=model_override, deep_override=deep_override, symbol_hit=symbol_hit)
                forced_web = forced_web or decision.reason == "explicit web request"
                route = Route.from_decision(decision, project_name=project_name, template_override=template_override, model_override=model_override, deep_override=deep_override)
        finally:
            status.stop()
        out.set_metadata(project=route.project or "off", model=route.model, template=route.template)
        if echo_route:
            print(f"[route] execution={route.execution}, template={route.template}, model={route.model}, deep={'on' if route.deep else 'off'}, project={route.project or 'off'}, reason={route.reason}")
        context = ""; offline_web = False
        if route.execution.startswith("web"):
            status.start("Checking connectivity")
            try:
                with timing.phase("Connectivity"):
                    online = connectivity_ok()
            finally:
                status.stop()
            if not online and forced_web:
                raise RuntimeError("Forced web search is unavailable. Check internet access and Brave configuration.")
            if online:
                is_research = route.execution == "web_research"; retrieval_error: str | None = None
                status.start("Searching the web")
                try:
                    with timing.phase("Retrieval"):
                        try:
                            web_results = brave_search(prompt, research=is_research)
                        except RuntimeError as exc:
                            retrieval_error = str(exc)
                finally:
                    status.stop()
                if retrieval_error and forced_web:
                    raise RuntimeError(f"Forced web search failed: {retrieval_error}")
                if not retrieval_error and forced_web and not web_results:
                    raise RuntimeError("Forced web search returned no results; refusing to guess from local knowledge.")
                if retrieval_error is None and web_results:
                    status.start("Fetching sources")
                    try:
                        with timing.phase("Source fetch"):
                            fetch_sources(web_results, research=is_research)
                    finally:
                        status.stop()
                    context = build_web_context(web_results, research=is_research)
                if retrieval_error:
                    print(f"[web] retrieval failed; using local fallback: {retrieval_error}"); offline_web = True; route.execution = "local"; route.project = None; web_results = []
            else:
                offline_web = True; route.execution = "local"; route.project = None; timing.phases.setdefault("Retrieval", 0.0); timing.phases.setdefault("Source fetch", 0.0)
        elif route.execution == "project":
            status.start("Retrieving project source")
            try:
                with timing.phase("Retrieval"):
                    context, project_files = build_project_context(prompt, project_name)
            finally:
                status.stop()
        else:
            timing.phases.setdefault("Retrieval", 0.0)
        status.start("Preparing context")
        try:
            with timing.phase("Analysis"):
                system = _system_prompt(route, context=context, offline_web=offline_web, project_files=project_files, runtime_facts=_runtime_facts(prompt))
                history_limit = int(CONFIG["history"].get("messages", 12)); mode = history_mode or str(CONFIG["history"].get("mode", "auto"))
                recent = select_history(prompt, history, mode=mode, limit=history_limit)
                messages = [{"role": "system", "content": system}, *recent, {"role": "user", "content": prompt}]
                max_tokens, num_ctx = _generation_settings(route, answer_length)
        finally:
            status.stop()
        waiting_for_first_token = True
        def on_text(chunk: str) -> None:
            nonlocal waiting_for_first_token
            if waiting_for_first_token:
                status.complete_for_streaming(); waiting_for_first_token = False
            emit(chunk)
        status.start("Waiting for first token")
        with timing.phase("Generation"):
            final = _generate_once(route=route, messages=messages, on_text=on_text, max_tokens=max_tokens, num_ctx=num_ctx)
            if waiting_for_first_token:
                status.stop(); waiting_for_first_token = False
            continuations = 0; maximum = int(CONFIG["performance"].get("max_continuations", 2))
            while final.get("done_reason") == "length" and continuations < maximum:
                continuations += 1; partial = "".join(answer_parts); continuation_parts: list[str] = []
                continuation = _generate_once(route=route, messages=[*messages, {"role": "assistant", "content": partial}, {"role": "user", "content": _load_runtime_prompt("continue")}], on_text=continuation_parts.append, max_tokens=max_tokens, num_ctx=num_ctx)
                _merge_metrics(final, continuation); final["done_reason"] = continuation.get("done_reason")
                cleaned = _clean_continuation("".join(continuation_parts))
                if cleaned:
                    if answer_parts and not answer_parts[-1].endswith(("\n", " ")):
                        emit("\n")
                    emit(cleaned)
        status.start("Verifying answer")
        try:
            with timing.phase("Verification"):
                quality = verify_answer(answer="".join(answer_parts), route=route, web_results=web_results, project_files=project_files, done_reason=final.get("done_reason"))
        finally:
            status.stop()
        if not quality.passed:
            current = "".join(answer_parts); status.start("Applying deterministic repair")
            try:
                with timing.phase("Repair"):
                    candidate, applied = apply_deterministic_repairs(answer=current, issues=quality.issues)
            finally:
                status.stop()
            if applied:
                status.start("Checking deterministic repair")
                try:
                    with timing.phase("Re-verification"):
                        candidate_quality = verify_answer(answer=candidate, route=route, web_results=web_results, project_files=project_files, done_reason=final.get("done_reason"))
                finally:
                    status.stop()
                if candidate.strip() and (candidate_quality.passed or len(candidate_quality.issues) < len(quality.issues)):
                    replace(candidate); quality = candidate_quality
        if not quality.passed:
            print("\n[quality] semantic repair required:")
            for issue in quality.issues: print(f"  - {issue}")
            repair_source = "".join(answer_parts); repair_parts: list[str] = []; waiting_for_repair_token = True; status.start("Repairing answer")
            def on_repair_text(chunk: str) -> None:
                nonlocal waiting_for_repair_token
                if waiting_for_repair_token:
                    status.complete_for_streaming(); waiting_for_repair_token = False; sys.stdout.write("\n"); sys.stdout.flush()
                repair_parts.append(chunk); sys.stdout.write(chunk); sys.stdout.flush()
            try:
                with timing.phase("Repair"):
                    repair_final = stream_repair(model=route.model, base_system=system, original_prompt=prompt, draft_answer=repair_source, issues=quality.issues, on_text=on_repair_text, max_tokens=max_tokens, num_ctx=num_ctx)
                    if waiting_for_repair_token:
                        status.stop(); waiting_for_repair_token = False
            finally:
                status.stop()
            _merge_metrics(final, repair_final); repaired = "".join(repair_parts); status.start("Checking repaired answer")
            try:
                with timing.phase("Re-verification"):
                    repaired_quality = verify_answer(answer=repaired, route=route, web_results=web_results, project_files=project_files, done_reason=repair_final.get("done_reason"))
            finally:
                status.stop()
            if repaired.strip() and (repaired_quality.passed or len(repaired_quality.issues) < len(quality.issues)):
                replace(repaired); quality = repaired_quality; final["done_reason"] = repair_final.get("done_reason")
        if not quality.passed:
            print("\n[quality] final response still has issues:")
            for issue in quality.issues: print(f"  - {issue}")
        if web_results:
            footer = build_source_footer(web_results)
            if footer: emit("\n\n" + footer)
        for key in _OLLAMA_METRICS:
            if key in final: timing.metrics[key] = final[key]
    finally:
        status.clear(); out.finish(timing)
    assert route is not None
    return PipelineResult(route=route, response_path=out.path, answer="".join(answer_parts), timing=timing)
