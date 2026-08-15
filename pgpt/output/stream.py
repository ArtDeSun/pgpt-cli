from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import TextIO

from pgpt.runtime.timing import Timing


class ResponseWriter:
    def __init__(
        self,
        path: Path,
        *,
        prompt: str,
        project: str = "pending",
        model: str = "pending",
        template: str = "pending",
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path = path
        self.prompt = prompt
        self.project = project
        self.model = model
        self.template = template

        self._lock = threading.Lock()

        self._completed_stages: list[
            tuple[str, float]
        ] = []

        self._current_stage: tuple[
            str,
            str,
            float,
        ] | None = None

        self._streaming_started = False
        self._file: TextIO | None = None
        self._answer_parts: list[str] = []

        self._rewrite_prefix()

    def _execution_markdown(self) -> str:
        lines = [
            "## Execution",
            "",
        ]

        for label, elapsed in self._completed_stages:
            lines.append(
                f"- ✓ {label} · {elapsed:.1f}s"
            )

        if self._current_stage is not None:
            frame, label, elapsed = self._current_stage

            lines.append(
                f"- {frame} {label} · {elapsed:.1f}s"
            )

        if (
            not self._completed_stages
            and self._current_stage is None
        ):
            lines.append(
                "- … Starting · 0.0s"
            )

        return "\n".join(lines)

    def _prefix(self) -> str:
        return (
            "# pgpt Response\n\n"
            f"> **Project:** `{self.project}`  \n"
            f"> **Model:** `{self.model}`  \n"
            f"> **Template:** `{self.template}`\n\n"
            f"{self._execution_markdown()}\n\n"
            "## You\n\n"
            f"{self.prompt}\n\n"
            "## Assistant\n\n"
        )

    def _rewrite_prefix(self) -> None:
        if self._streaming_started:
            return

        with self.path.open(
            "w",
            encoding="utf-8",
        ) as file:
            file.write(
                self._prefix()
            )
            file.flush()

    def set_metadata(
        self,
        *,
        project: str,
        model: str,
        template: str,
    ) -> None:
        with self._lock:
            self.project = project
            self.model = model
            self.template = template

            self._rewrite_prefix()

    def update_status(
        self,
        frame: str,
        label: str,
        elapsed: float,
        completed: bool,
    ) -> None:
        with self._lock:
            if completed:
                self._current_stage = None

                if not any(
                    existing_label == label
                    for existing_label, _
                    in self._completed_stages
                ):
                    self._completed_stages.append(
                        (
                            label,
                            elapsed,
                        )
                    )

            elif frame:
                self._current_stage = (
                    frame,
                    label,
                    elapsed,
                )

            else:
                self._current_stage = None

            # Before streaming begins, status changes are
            # immediately reflected in the Markdown file.
            #
            # After streaming begins, they are still recorded
            # and are written into the canonical file when the
            # answer is replaced or finished.
            self._rewrite_prefix()

    def _start_streaming(self) -> None:
        if self._streaming_started:
            return

        self._current_stage = None
        self._rewrite_prefix()

        self._file = self.path.open(
            "a",
            encoding="utf-8",
            buffering=1,
        )

        self._streaming_started = True

    def write(
        self,
        chunk: str,
    ) -> None:
        if not chunk:
            return

        with self._lock:
            self._start_streaming()

            self._answer_parts.append(
                chunk
            )

            sys.stdout.write(chunk)
            sys.stdout.flush()

            assert self._file is not None

            self._file.write(chunk)
            self._file.flush()

    def replace_answer(
        self,
        answer: str,
    ) -> None:
        """
        Replace the streamed draft with a repaired canonical
        answer in the Markdown file.

        This does not print the answer again to the terminal;
        repair streaming is handled by the pipeline.
        """

        with self._lock:
            if self._file is not None:
                self._file.flush()
                self._file.close()
                self._file = None

            self._answer_parts = [
                answer
            ]

            self._current_stage = None

            with self.path.open(
                "w",
                encoding="utf-8",
            ) as file:
                file.write(
                    self._prefix()
                )

                file.write(answer)
                file.flush()

            self._file = self.path.open(
                "a",
                encoding="utf-8",
                buffering=1,
            )

            self._streaming_started = True

    def finish(
        self,
        timing: Timing,
    ) -> None:
        timing.stop()

        with self._lock:
            self._current_stage = None

            if self._file is not None:
                self._file.flush()
                self._file.close()
                self._file = None

            block = timing.render()

            # Rewrite the final Markdown once so its Execution
            # section contains every completed stage, including
            # stages that occurred after streaming began.
            with self.path.open(
                "w",
                encoding="utf-8",
            ) as file:
                file.write(
                    self._prefix()
                )

                file.write(
                    "".join(
                        self._answer_parts
                    )
                )

                file.write(
                    "\n\n"
                    "## Timing\n\n"
                    "```text\n"
                    f"{block}\n"
                    "```\n"
                )

                file.flush()

        sys.stdout.write(
            f"\n\n{block}\n"
        )
        sys.stdout.flush()