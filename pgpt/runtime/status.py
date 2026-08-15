from __future__ import annotations

import itertools
import sys
import threading
import time
from contextlib import contextmanager
from typing import Callable, Iterator


StatusCallback = Callable[[str, str, float, bool], None]


class StatusReporter:
    """
    Displays observable execution status.

    Examples:
        ⠹ Searching the web          1.2s
        ✓ Searching the web          1.4s

    This reports program activity, not model chain-of-thought.
    """

    _FRAMES = (
        "⠋",
        "⠙",
        "⠹",
        "⠸",
        "⠼",
        "⠴",
        "⠦",
        "⠧",
        "⠇",
        "⠏",
    )

    def __init__(
        self,
        on_update: StatusCallback | None = None,
    ) -> None:
        self.enabled = sys.stdout.isatty()
        self._on_update = on_update

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._label = ""
        self._started = 0.0

    def _notify(
        self,
        frame: str,
        label: str,
        elapsed: float,
        completed: bool,
    ) -> None:
        if self._on_update is not None:
            self._on_update(
                frame,
                label,
                elapsed,
                completed,
            )

    def _render_loop(self) -> None:
        frames = itertools.cycle(self._FRAMES)

        while not self._stop_event.wait(0.1):
            with self._lock:
                label = self._label
                started = self._started

            if not label:
                continue

            elapsed = time.monotonic() - started
            frame = next(frames)

            sys.stdout.write(
                f"\r{frame} {label:<28} {elapsed:>6.1f}s"
            )
            sys.stdout.flush()

            self._notify(
                frame,
                label,
                elapsed,
                False,
            )

    def start(
        self,
        label: str,
    ) -> None:
        self.stop(show_complete=False)

        with self._lock:
            self._label = label
            self._started = time.monotonic()

        self._stop_event.clear()

        self._notify(
            "…",
            label,
            0.0,
            False,
        )

        if self.enabled:
            self._thread = threading.Thread(
                target=self._render_loop,
                daemon=True,
            )
            self._thread.start()
        else:
            sys.stdout.write(
                f"… {label}\n"
            )
            sys.stdout.flush()

    def stop(
        self,
        *,
        show_complete: bool = True,
    ) -> float:
        with self._lock:
            label = self._label
            started = self._started

        if not label:
            return 0.0

        elapsed = time.monotonic() - started

        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=0.3)
            self._thread = None

        if self.enabled:
            sys.stdout.write(
                "\r" + (" " * 72) + "\r"
            )

        if show_complete:
            sys.stdout.write(
                f"✓ {label:<28} {elapsed:>6.1f}s\n"
            )
            sys.stdout.flush()

            self._notify(
                "✓",
                label,
                elapsed,
                True,
            )
        else:
            self._notify(
                "",
                label,
                elapsed,
                False,
            )

        with self._lock:
            self._label = ""
            self._started = 0.0

        return elapsed

    @contextmanager
    def phase(
        self,
        label: str,
    ) -> Iterator[None]:
        self.start(label)

        try:
            yield
        finally:
            self.stop()

    def complete_for_streaming(self) -> None:
        """
        Finish the waiting status immediately before the first
        generated token is printed.
        """
        self.stop(show_complete=True)

    def clear(self) -> None:
        self.stop(show_complete=False)