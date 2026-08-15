from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pgpt.config import CONFIG, cfg_path, get_project
from pgpt.generation.ollama import stream_chat
from pgpt.output.stream import ResponseWriter
from pgpt.quality.repair import (
    apply_deterministic_repairs,
    stream_repair,
)
from pgpt.quality.verify import verify_answer
from pgpt.retrieval.project import (
    build_context as build_project_context,
    has_symbol_hit,
)
from pgpt.retrieval.web import (
    WebResult,
    brave_search,
    build_source_footer,
    build_web_context,
    connectivity_ok,
    fetch_sources,
)
from pgpt.routing.router import resolve_route
from pgpt.runtime.route import Route
from pgpt.runtime.status import StatusReporter
from pgpt.runtime.timing import Timing


_OLLAMA_METRICS = (
    "load_duration",
    "prompt_eval_duration",
    "prompt_eval_count",
    "eval_duration",
    "eval_count",
    "total_duration",
)


@dataclass
class PipelineResult:
    route: Route
    response_path: Path
    answer: str
    timing: Timing


def _slug(
    text: str,
) -> str:
    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        text.casefold(),
    ).strip("-")

    return (
        value[:48]
        or "response"
    )


def response_path(
    prompt: str,
) -> Path:
    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    return (
        cfg_path("responses_dir")
        / f"{stamp}-{_slug(prompt)}.md"
    )


def _load_prompt(
    template: str,
) -> str:
    root = (
        Path(__file__).resolve().parents[2]
        / "prompts"
    )

    system = (
        root
        / "system.md"
    ).read_text(
        encoding="utf-8"
    ).strip()

    path = (
        root
        / f"{template}.md"
    )

    specific = (
        path.read_text(
            encoding="utf-8"
        ).strip()
        if path.exists()
        else ""
    )

    return (
        f"{system}\n\n{specific}"
        .strip()
    )

def _load_runtime_prompt(
    name: str,
    **values: str,
) -> str:
    path = (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "runtime"
        / f"{name}.md"
    )

    text = path.read_text(
        encoding="utf-8"
    ).strip()

    if values:
        return text.format(
            **values
        )

    return text


def _system_prompt(
    route: Route,
    *,
    context: str,
    offline_web: bool,
    project_files: list[str],
) -> str:
    base = _load_prompt(
        route.template
    )

    runtime: list[str] = []

    if route.execution == "project":
        runtime.append(
            _load_runtime_prompt(
                "project-context"
            )
        )

        if project_files:
            runtime.append(
                _load_runtime_prompt(
                    "retrieved-files",
                    files=", ".join(
                        project_files
                    ),
                )
            )

    if (
        route.execution.startswith("web")
        and not offline_web
    ):
        runtime.append(
            _load_runtime_prompt(
                "web-context"
            )
        )

    if offline_web:
        runtime.append(
            _load_runtime_prompt(
                "offline-web"
            )
        )

    if context:
        runtime.append(
            _load_runtime_prompt(
                "context",
                context=context,
            )
        )

    if not runtime:
        return base

    return (
        base
        + "\n\n"
        + "\n".join(
            runtime
        )
    )


def _generate_once(
    *,
    route: Route,
    messages: list[dict[str, str]],
    on_text,
    max_tokens: int,
    num_ctx: int,
) -> dict:
    return stream_chat(
        model=route.model,
        messages=messages,
        on_text=on_text,
        max_tokens=max_tokens,
        num_ctx=num_ctx,
        temperature=float(
            CONFIG["defaults"].get(
                "temperature",
                0.1,
            )
        ),
    )


def _merge_metrics(
    target: dict,
    extra: dict,
) -> None:
    for key in _OLLAMA_METRICS:
        first = (
            target.get(
                key,
                0,
            )
            or 0
        )

        second = (
            extra.get(
                key,
                0,
            )
            or 0
        )

        if (
            isinstance(
                first,
                (int, float),
            )
            and isinstance(
                second,
                (int, float),
            )
        ):
            target[key] = (
                first
                + second
            )


def run(
    prompt: str,
    *,
    project_name: str | None = None,
    web_override: str | None = None,
    project_override: bool | None = None,
    template_override: str | None = None,
    model_override: str | None = None,
    deep_override: bool | None = None,
    history: list[dict[str, str]] | None = None,
    echo_route: bool = True,
) -> PipelineResult:
    timing = Timing()

    project_name, _ = get_project(
        project_name
    )

    out = ResponseWriter(
        response_path(prompt),
        prompt=prompt,
    )

    status = StatusReporter(
        on_update=out.update_status
    )

    # =========================================================
    # 1. ROUTING
    # =========================================================

    status.start(
        "Routing request"
    )

    try:
        with timing.phase(
            "Routing"
        ):
            symbol_hit = has_symbol_hit(
                prompt,
                project_name,
            )

            decision = resolve_route(
                prompt,
                project_name=project_name,
                web_override=web_override,
                project_override=project_override,
                template_override=template_override,
                model_override=model_override,
                deep_override=deep_override,
                symbol_hit=symbol_hit,
            )

            route = Route.from_decision(
                decision,
                project_name=project_name,
                template_override=template_override,
                model_override=model_override,
                deep_override=deep_override,
            )

    finally:
        status.stop()

    out.set_metadata(
        project=route.project or "off",
        model=route.model,
        template=route.template,
    )

    if echo_route:
        print(
            f"[route] execution={route.execution}, "
            f"template={route.template}, "
            f"model={route.model}, "
            f"deep={'on' if route.deep else 'off'}, "
            f"project={route.project or 'off'}, "
            f"reason={route.reason}"
        )

    # =========================================================
    # 2. RETRIEVAL
    # =========================================================

    context = ""
    project_files: list[str] = []
    web_results: list[WebResult] = []
    offline_web = False

    if route.execution.startswith("web"):
        status.start(
            "Checking connectivity"
        )

        try:
            with timing.phase(
                "Connectivity"
            ):
                online = connectivity_ok()

        finally:
            status.stop()

        if online:
            retrieval_error: str | None = None

            is_research = (
                route.execution
                == "web_research"
            )

            status.start(
                "Searching the web"
            )

            try:
                with timing.phase(
                    "Retrieval"
                ):
                    try:
                        web_results = brave_search(
                            prompt,
                            research=is_research,
                        )

                    except RuntimeError as exc:
                        retrieval_error = str(
                            exc
                        )

            finally:
                status.stop()

            if (
                retrieval_error is None
                and web_results
            ):
                status.start(
                    "Fetching sources"
                )

                try:
                    with timing.phase(
                        "Source fetch"
                    ):
                        fetch_sources(
                            web_results,
                            research=is_research,
                        )

                finally:
                    status.stop()

                context = build_web_context(
                    web_results,
                    research=is_research,
                )

            if retrieval_error:
                print(
                    "[web] retrieval failed; "
                    "using local fallback: "
                    f"{retrieval_error}"
                )

                offline_web = True
                route.execution = "local"
                route.project = None
                web_results = []

        else:
            offline_web = True
            route.execution = "local"
            route.project = None

            timing.phases.setdefault(
                "Retrieval",
                0.0,
            )

            timing.phases.setdefault(
                "Source fetch",
                0.0,
            )

    elif route.execution == "project":
        status.start(
            "Retrieving project source"
        )

        try:
            with timing.phase(
                "Retrieval"
            ):
                (
                    context,
                    project_files,
                ) = build_project_context(
                    prompt,
                    project_name,
                )

        finally:
            status.stop()

    else:
        timing.phases.setdefault(
            "Retrieval",
            0.0,
        )

    # =========================================================
    # 3. CONTEXT PREPARATION
    # =========================================================

    status.start(
        "Preparing context"
    )

    try:
        with timing.phase(
            "Analysis"
        ):
            system = _system_prompt(
                route,
                context=context,
                offline_web=offline_web,
                project_files=project_files,
            )

            recent = (
                history or []
            )[
                -int(
                    CONFIG["history"].get(
                        "messages",
                        8,
                    )
                ):
            ]

            messages = [
                {
                    "role": "system",
                    "content": system,
                },
                *recent,
                {
                    "role": "user",
                    "content": prompt,
                },
            ]

            max_tokens = int(
                CONFIG[
                    "performance"
                ][
                    "max_tokens_by_template"
                ].get(
                    route.template,
                    700,
                )
            )

            coder_templates = set(
                CONFIG[
                    "models"
                ].get(
                    "coder_templates",
                    [],
                )
            )

            role = (
                "deep"
                if route.deep
                else "coder"
                if (
                    route.template
                    in coder_templates
                )
                else "general"
            )

            num_ctx = int(
                CONFIG[
                    "performance"
                ][
                    "num_ctx_by_role"
                ].get(
                    role,
                    4096,
                )
            )

    finally:
        status.stop()

    # =========================================================
    # 4. GENERATION
    # =========================================================

    answer_parts: list[str] = []
    waiting_for_first_token = False

    def on_text(
        chunk: str,
    ) -> None:
        nonlocal waiting_for_first_token

        if waiting_for_first_token:
            status.complete_for_streaming()
            waiting_for_first_token = False

        answer_parts.append(
            chunk
        )

        out.write(
            chunk
        )

    final: dict = {}

    try:
        status.start(
            "Waiting for first token"
        )

        waiting_for_first_token = True

        with timing.phase(
            "Generation"
        ):
            final = _generate_once(
                route=route,
                messages=messages,
                on_text=on_text,
                max_tokens=max_tokens,
                num_ctx=num_ctx,
            )

            if waiting_for_first_token:
                status.stop()
                waiting_for_first_token = False

            # -------------------------------------------------
            # One bounded continuation if token limit was hit.
            # -------------------------------------------------

            if (
                final.get(
                    "done_reason"
                )
                == "length"
            ):
                partial_answer = "".join(
                    answer_parts
                )

                if (
                    partial_answer
                    and not partial_answer[
                        -1
                    ].isspace()
                ):
                    on_text(
                        "\n"
                    )

                    partial_answer += "\n"

                continuation_messages = [
                    *messages,
                    {
                        "role": "assistant",
                        "content": partial_answer,
                    },
                    {
                        "role": "user",
                        "content": (
                            _load_runtime_prompt(
                                "continue"
                            )
                        ),
                    },
                ]

                continuation_final = (
                    _generate_once(
                        route=route,
                        messages=continuation_messages,
                        on_text=on_text,
                        max_tokens=max_tokens,
                        num_ctx=num_ctx,
                    )
                )

                _merge_metrics(
                    final,
                    continuation_final,
                )

                final[
                    "done_reason"
                ] = continuation_final.get(
                    "done_reason"
                )

        # =====================================================
        # 5. VERIFICATION
        # =====================================================

        status.start(
            "Verifying answer"
        )

        try:
            with timing.phase(
                "Verification"
            ):
                quality = verify_answer(
                    answer="".join(
                        answer_parts
                    ),
                    route=route,
                    web_results=web_results,
                    project_files=project_files,
                    done_reason=final.get(
                        "done_reason"
                    ),
                )

        finally:
            status.stop()

        # =====================================================
        # 6. DETERMINISTIC REPAIR
        # =====================================================

        if not quality.passed:
            current_answer = "".join(
                answer_parts
            )

            status.start(
                "Applying deterministic repair"
            )

            try:
                with timing.phase(
                    "Repair"
                ):
                    (
                        deterministic_answer,
                        applied_repairs,
                    ) = apply_deterministic_repairs(
                        answer=current_answer,
                        issues=quality.issues,
                    )

            finally:
                status.stop()

            if applied_repairs:
                print(
                    "\n[quality] deterministic repair:"
                )

                for issue in applied_repairs:
                    print(
                        f"  - {issue}"
                    )

                status.start(
                    "Checking deterministic repair"
                )

                try:
                    with timing.phase(
                        "Re-verification"
                    ):
                        deterministic_quality = (
                            verify_answer(
                                answer=deterministic_answer,
                                route=route,
                                web_results=web_results,
                                project_files=project_files,
                                done_reason=final.get(
                                    "done_reason"
                                ),
                            )
                        )

                finally:
                    status.stop()

                deterministic_improved = (
                    bool(
                        deterministic_answer.strip()
                    )
                    and (
                        deterministic_quality.passed
                        or len(
                            deterministic_quality.issues
                        )
                        < len(
                            quality.issues
                        )
                    )
                )

                if deterministic_improved:
                    answer_parts[:] = [
                        deterministic_answer
                    ]

                    quality = (
                        deterministic_quality
                    )

                    out.replace_answer(
                        deterministic_answer
                    )

        # =====================================================
        # 7. ONE SEMANTIC LLM REPAIR IF STILL NEEDED
        # =====================================================

        if not quality.passed:
            print(
                "\n[quality] semantic repair required:"
            )

            for issue in quality.issues:
                print(
                    f"  - {issue}"
                )

            repair_source = "".join(
                answer_parts
            )

            repair_parts: list[str] = []
            waiting_for_repair_token = True

            status.start(
                "Repairing answer"
            )

            def on_repair_text(
                chunk: str,
            ) -> None:
                nonlocal waiting_for_repair_token

                if waiting_for_repair_token:
                    status.complete_for_streaming()
                    waiting_for_repair_token = False

                    sys.stdout.write(
                        "\n"
                    )

                    sys.stdout.flush()

                repair_parts.append(
                    chunk
                )

                sys.stdout.write(
                    chunk
                )

                sys.stdout.flush()

            try:
                with timing.phase(
                    "Repair"
                ):
                    repair_final = stream_repair(
                        model=route.model,
                        base_system=system,
                        original_prompt=prompt,
                        draft_answer=repair_source,
                        issues=quality.issues,
                        on_text=on_repair_text,
                        max_tokens=max_tokens,
                        num_ctx=num_ctx,
                    )

                    if waiting_for_repair_token:
                        status.stop()
                        waiting_for_repair_token = False

            finally:
                status.stop()

            _merge_metrics(
                final,
                repair_final,
            )

            repaired_answer = "".join(
                repair_parts
            )

            status.start(
                "Checking repaired answer"
            )

            try:
                with timing.phase(
                    "Re-verification"
                ):
                    repaired_quality = (
                        verify_answer(
                            answer=repaired_answer,
                            route=route,
                            web_results=web_results,
                            project_files=project_files,
                            done_reason=repair_final.get(
                                "done_reason"
                            ),
                        )
                    )

            finally:
                status.stop()

            semantic_improved = (
                bool(
                    repaired_answer.strip()
                )
                and (
                    repaired_quality.passed
                    or len(
                        repaired_quality.issues
                    )
                    < len(
                        quality.issues
                    )
                )
            )

            if semantic_improved:
                answer_parts[:] = [
                    repaired_answer
                ]

                quality = (
                    repaired_quality
                )

                final[
                    "done_reason"
                ] = repair_final.get(
                    "done_reason"
                )

                out.replace_answer(
                    repaired_answer
                )

        # =====================================================
        # 8. FINAL QUALITY REPORT
        # =====================================================

        if not quality.passed:
            print(
                "\n[quality] final response still "
                "has issues:"
            )

            for issue in quality.issues:
                print(
                    f"  - {issue}"
                )

        # =====================================================
        # 9. CLICKABLE WEB SOURCES
        # =====================================================

        if web_results:
            footer = build_source_footer(
                web_results
            )

            if footer:
                on_text(
                    "\n\n"
                    + footer
                )

        # =====================================================
        # 10. OLLAMA METRICS
        # =====================================================

        for key in _OLLAMA_METRICS:
            if key in final:
                timing.metrics[
                    key
                ] = final[
                    key
                ]

    finally:
        status.clear()

        out.finish(
            timing
        )

    return PipelineResult(
        route=route,
        response_path=out.path,
        answer="".join(
            answer_parts
        ),
        timing=timing,
    )