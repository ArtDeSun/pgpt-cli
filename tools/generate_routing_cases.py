from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from pgpt.generation.ollama import ollama_url
from pgpt.runtime.http import json_request


ROOT = Path(__file__).resolve().parents[1]

SCENARIOS_PATH = (
    ROOT
    / "evals"
    / "routing_scenarios.json"
)

OUTPUT_PATH = (
    ROOT
    / "evals"
    / "routing_generated.json"
)


# Start with one reasonably capable, reasonably fast model.
#
# We are testing the router, not benchmarking prompt generators.
GENERATOR_MODEL = "llama3.2:3b"


# One generated prompt per selected domain keeps the first
# synthetic suite fast and easy to inspect.
PROMPTS_PER_DOMAIN = 2


# One retry only for malformed model output.
MAX_ATTEMPTS = 2


PROMPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
        }
    },
    "required": [
        "prompt",
    ],
    "additionalProperties": False,
}


def _routing_prompt(
    name: str,
) -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "prompts"
        / "routing"
        / f"{name}.md"
    )

    return path.read_text(
        encoding="utf-8"
    ).strip()


def _load_json(
    path: Path,
) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def _save_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")


def _choose(
    values: list[dict],
) -> dict:
    return random.choice(
        values
    )


def _scenario_instruction(
    *,
    domain: str,
    source: dict,
    task: dict,
    freshness: dict,
    complexity: dict,
) -> str:
    web_mode = source.get(
        "web_mode"
    )

    return _routing_prompt(
        "generate-case-request"
    ).format(
        domain=domain,
        source=source["source"],
        source_description=source["description"],
        web_mode=web_mode,
        task=task["task"],
        task_description=task["description"],
        freshness=freshness["freshness"],
        freshness_description=freshness["description"],
        complexity=complexity["complexity"],
        complexity_description=complexity["description"],
    )


def _generate_one(
    instruction: str,
) -> str | None:
    payload = {
        "model": GENERATOR_MODEL,
        "messages": [
            {
                {
                    "role": "system",
                    "content": _routing_prompt(
                        "generate-case-system"
                    ),
                },
            },
            {
                "role": "user",
                "content": instruction,
            },
        ],
        "stream": False,
        "think": False,
        "format": PROMPT_SCHEMA,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.65,
            "num_ctx": 1536,
            "num_predict": 140,
        },
    }

    response = json_request(
        "POST",
        ollama_url(
            "/api/chat"
        ),
        payload=payload,
        timeout=120,
    )

    if not isinstance(
        response,
        dict,
    ):
        return None

    message = response.get(
        "message"
    )

    if not isinstance(
        message,
        dict,
    ):
        return None

    content = str(
        message.get(
            "content"
        )
        or ""
    ).strip()

    if not content:
        return None

    try:
        data = json.loads(
            content
        )
    except json.JSONDecodeError:
        return None

    prompt = data.get(
        "prompt"
    )

    if not isinstance(
        prompt,
        str,
    ):
        return None

    prompt = prompt.strip()

    if not prompt:
        return None

    return prompt


def _looks_valid(
    prompt: str,
) -> bool:
    """
    Reject only obvious malformed generator output.

    Do not try to semantically re-classify the prompt here.
    The generated evaluation runner will reveal semantic
    disagreements later.
    """

    lowered = prompt.casefold()

    if len(prompt) < 12:
        return False

    if len(prompt) > 1200:
        return False

    forbidden = (
        "assistant router",
        "routing properties",
        "routing labels",
        "classifier",
        "evaluation dataset",
        "generate exactly",
        "generate one realistic",
        "<your answer>",
        "required routing",
    )

    if any(
        value in lowered
        for value in forbidden
    ):
        return False

    if (
        prompt.startswith("{")
        or prompt.startswith("[")
    ):
        return False

    return True


def _make_case(
    *,
    case_id: str,
    prompt: str,
    domain: str,
    source: dict,
    task: dict,
    freshness: dict,
    complexity: dict,
) -> dict:
    return {
        "id": case_id,
        "prompt": prompt,
        "generator_model": (
            GENERATOR_MODEL
        ),
        "domain": domain,
        "expect": {
            "source": source[
                "source"
            ],
            "web_mode": source.get(
                "web_mode"
            ),
            "task": task[
                "task"
            ],
            "freshness": freshness[
                "freshness"
            ],
            "complexity": complexity[
                "complexity"
            ],
        },
    }


def main() -> None:
    # Fixed seed makes scenario selection reproducible.
    random.seed(
        42
    )

    data = _load_json(
        SCENARIOS_PATH
    )

    domains = data[
        "domains"
    ]

    sources = data[
        "source_scenarios"
    ]

    tasks = data[
        "task_scenarios"
    ]

    freshness_values = data[
        "freshness_scenarios"
    ]

    complexity_values = data[
        "complexity_scenarios"
    ]

    generated: list[dict] = []

    malformed = 0

    started = time.monotonic()

    for domain_index, domain in enumerate(
        domains,
        start=1,
    ):
        print()
        print(
            "=" * 72
        )

        print(
            f"DOMAIN {domain_index}/{len(domains)}: "
            f"{domain}"
        )

        for prompt_index in range(
            1,
            PROMPTS_PER_DOMAIN + 1,
        ):
            source = _choose(
                sources
            )

            task = _choose(
                tasks
            )

            freshness = _choose(
                freshness_values
            )

            complexity = _choose(
                complexity_values
            )

            print(
                f"  case {prompt_index}: "
                f"source={source['source']} "
                f"web_mode={source.get('web_mode')} "
                f"task={task['task']} "
                f"freshness={freshness['freshness']} "
                f"complexity={complexity['complexity']}"
            )

            instruction = (
                _scenario_instruction(
                    domain=domain,
                    source=source,
                    task=task,
                    freshness=freshness,
                    complexity=complexity,
                )
            )

            accepted_prompt = None

            for attempt in range(
                1,
                MAX_ATTEMPTS + 1,
            ):
                try:
                    candidate = _generate_one(
                        instruction
                    )

                except Exception as exc:
                    print(
                        f"    attempt {attempt}: "
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

                    continue

                if (
                    candidate is None
                    or not _looks_valid(
                        candidate
                    )
                ):
                    malformed += 1

                    print(
                        f"    attempt {attempt}: "
                        "malformed"
                    )

                    continue

                accepted_prompt = candidate

                break

            if accepted_prompt is None:
                print(
                    "    skipped"
                )

                continue

            case_id = (
                f"generated_"
                f"{domain_index:03d}_"
                f"{prompt_index:02d}"
            )

            generated.append(
                _make_case(
                    case_id=case_id,
                    prompt=accepted_prompt,
                    domain=domain,
                    source=source,
                    task=task,
                    freshness=freshness,
                    complexity=complexity,
                )
            )

            # Save after every successful case.
            #
            # If generation is interrupted, completed work remains.
            _save_json(
                OUTPUT_PATH,
                generated,
            )

            print(
                "    accepted:",
                accepted_prompt,
            )

    elapsed = (
        time.monotonic()
        - started
    )

    _save_json(
        OUTPUT_PATH,
        generated,
    )

    print()
    print(
        "=" * 72
    )

    print(
        "Generated:",
        len(generated),
    )

    print(
        "Malformed attempts:",
        malformed,
    )

    print(
        f"Elapsed: {elapsed:.1f}s"
    )

    if generated:
        print(
            "Average per accepted case:",
            f"{elapsed / len(generated):.1f}s",
        )

    print(
        "Saved:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()