from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Timing:
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None

    phases: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float | int] = field(default_factory=dict)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        start = time.monotonic()

        try:
            yield
        finally:
            elapsed = (
                time.monotonic()
                - start
            )

            self.phases[name] = (
                self.phases.get(
                    name,
                    0.0,
                )
                + elapsed
            )

    def stop(self) -> None:
        if self.finished is None:
            self.finished = (
                time.monotonic()
            )

    @property
    def total(self) -> float:
        end = (
            self.finished
            if self.finished is not None
            else time.monotonic()
        )

        return (
            end
            - self.started
        )

    def render(self) -> str:
        order = [
            "Routing",
            "Connectivity",
            "Retrieval",
            "Source fetch",
            "Analysis",
            "Generation",
            "Verification",
            "Repair",
            "Re-verification",
        ]

        lines: list[str] = []

        for name in order:
            if name in self.phases:
                lines.append(
                    f"✓ {name:<16} "
                    f"{self.phases[name]:>6.1f}s"
                )

        lines.append(
            "─" * 26
        )

        lines.append(
            f"  {'Total':<16} "
            f"{self.total:>6.1f}s"
        )

        if self.metrics:
            load_ns = int(
                self.metrics.get(
                    "load_duration",
                    0,
                )
            )

            prompt_ns = int(
                self.metrics.get(
                    "prompt_eval_duration",
                    0,
                )
            )

            eval_ns = int(
                self.metrics.get(
                    "eval_duration",
                    0,
                )
            )

            eval_count = int(
                self.metrics.get(
                    "eval_count",
                    0,
                )
            )

            speed = (
                eval_count
                / (eval_ns / 1e9)
                if eval_ns
                else 0.0
            )

            lines += [
                "",
                (
                    f"Model load         "
                    f"{load_ns / 1e9:>6.1f}s"
                ),
                (
                    f"Prompt eval        "
                    f"{prompt_ns / 1e9:>6.1f}s"
                ),
                (
                    f"Token generate     "
                    f"{eval_ns / 1e9:>6.1f}s"
                ),
                (
                    f"Output tokens      "
                    f"{eval_count:>6}"
                ),
                (
                    f"Speed              "
                    f"{speed:>6.1f} tok/s"
                ),
            ]

        return "\n".join(lines)