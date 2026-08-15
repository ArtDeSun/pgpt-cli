from __future__ import annotations

import html
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from pgpt.config import CONFIG, load_secrets
from pgpt.runtime.http import json_request


@dataclass
class WebResult:
    title: str
    url: str
    description: str
    extra_snippets: list[str]
    page_text: str = ""
    fetch_error: str | None = None


class _ReadableHTMLParser(HTMLParser):
    """
    Very small dependency-free HTML text extractor.

    Script/style/template/noscript content is ignored.
    """

    _SKIP_TAGS = {
        "script",
        "style",
        "template",
        "noscript",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
    }

    _BLOCK_TAGS = {
        "article",
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "main",
        "p",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True,
        )

        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        tag = tag.casefold()

        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return

        if (
            self._skip_depth == 0
            and tag in self._BLOCK_TAGS
        ):
            self.parts.append("\n")

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        tag = tag.casefold()

        if tag in self._SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if (
            self._skip_depth == 0
            and tag in self._BLOCK_TAGS
        ):
            self.parts.append("\n")

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def connectivity_ok() -> bool:
    host = CONFIG["web"].get(
        "connectivity_host",
        "api.search.brave.com",
    )

    port = int(
        CONFIG["web"].get(
            "connectivity_port",
            443,
        )
    )

    timeout = float(
        CONFIG["web"].get(
            "connectivity_timeout_seconds",
            0.7,
        )
    )

    try:
        with socket.create_connection(
            (host, port),
            timeout=timeout,
        ):
            return True

    except OSError:
        return False


def brave_search(
    query: str,
    *,
    research: bool = False,
) -> list[WebResult]:
    load_secrets()

    api_key = os.environ.get(
        "PGPT_BRAVE_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "PGPT_BRAVE_API_KEY is not set"
        )

    count = int(
        CONFIG["web"].get(
            (
                "research_results"
                if research
                else "lookup_results"
            ),
            8 if research else 3,
        )
    )

    params = {
        "q": query[:400],
        "count": str(count),
        "search_lang": CONFIG["web"].get(
            "search_lang",
            "en",
        ),
        "country": CONFIG["web"].get(
            "country",
            "CA",
        ),
    }

    if research:
        params["extra_snippets"] = "true"

    url = (
        "https://api.search.brave.com/"
        "res/v1/web/search?"
        + urllib.parse.urlencode(params)
    )

    data = json_request(
        "GET",
        url,
        headers={
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        },
        timeout=float(
            CONFIG["web"].get(
                "search_timeout_seconds",
                6,
            )
        ),
    )

    results: list[WebResult] = []

    for item in (
        ((data or {}).get("web") or {})
        .get("results", [])
    ):
        title = str(
            item.get("title") or ""
        ).strip()

        result_url = str(
            item.get("url") or ""
        ).strip()

        description = str(
            item.get("description") or ""
        ).strip()

        if not result_url:
            continue

        results.append(
            WebResult(
                title=title or result_url,
                url=result_url,
                description=description,
                extra_snippets=[
                    str(value).strip()
                    for value in item.get(
                        "extra_snippets",
                        [],
                    )
                    if str(value).strip()
                ],
            )
        )

    if not results:
        raise RuntimeError(
            "Brave returned no web results"
        )

    return results


def _clean_page_text(
    text: str,
) -> str:
    text = html.unescape(text)

    # Collapse horizontal whitespace.
    text = re.sub(
        r"[ \t\f\v]+",
        " ",
        text,
    )

    # Normalize blank lines.
    text = re.sub(
        r"\n[ \t]+",
        "\n",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    # Remove repeated spaces around newlines.
    lines = [
        line.strip()
        for line in text.splitlines()
    ]

    # Drop empty/navigation-like noise while keeping readable
    # paragraphs and short structured weather/table lines.
    cleaned: list[str] = []

    for line in lines:
        if not line:
            continue

        if len(line) == 1:
            continue

        cleaned.append(line)

    return "\n".join(cleaned)


def _extract_html_text(
    body: str,
) -> str:
    parser = _ReadableHTMLParser()

    try:
        parser.feed(body)
    except Exception:
        # HTMLParser is forgiving, but page extraction should
        # never crash the whole web request.
        return ""

    return _clean_page_text(
        "".join(parser.parts)
    )


def fetch_page(
    result: WebResult,
    *,
    max_chars: int,
) -> WebResult:
    """
    Fetch one search result.

    Failure is isolated to that source. Brave snippets remain
    available even when the webpage cannot be fetched.
    """

    request = urllib.request.Request(
        result.url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "Chrome/131 Safari/537.36"
            ),
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "text/plain;q=0.9,*/*;q=0.5"
            ),
            "Accept-Language": "en-CA,en;q=0.9",
        },
        method="GET",
    )

    timeout = float(
        CONFIG["web"].get(
            "fetch_timeout_seconds",
            5,
        )
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            content_type = (
                response.headers
                .get_content_type()
                .casefold()
            )

            raw = response.read(
                2 * 1024 * 1024
            )

            charset = (
                response.headers
                .get_content_charset()
                or "utf-8"
            )

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
    ) as exc:
        result.fetch_error = str(exc)
        return result

    try:
        body = raw.decode(
            charset,
            errors="replace",
        )
    except LookupError:
        body = raw.decode(
            "utf-8",
            errors="replace",
        )

    if (
        content_type == "text/html"
        or content_type
        == "application/xhtml+xml"
    ):
        text = _extract_html_text(
            body
        )

    elif content_type.startswith(
        "text/"
    ):
        text = _clean_page_text(
            body
        )

    else:
        result.fetch_error = (
            "Unsupported content type: "
            f"{content_type}"
        )
        return result

    if not text:
        result.fetch_error = (
            "No readable page text extracted"
        )
        return result

    result.page_text = text[:max_chars]

    return result


def fetch_sources(
    results: list[WebResult],
    *,
    research: bool,
) -> list[WebResult]:
    """
    Fetch a bounded number of top Brave results.

    The rest remain search-snippet-only sources.
    """

    if research:
        page_count = int(
            CONFIG["web"].get(
                "research_fetch_pages",
                4,
            )
        )

        max_chars = int(
            CONFIG["web"].get(
                "research_page_chars",
                6000,
            )
        )

    else:
        page_count = int(
            CONFIG["web"].get(
                "lookup_fetch_pages",
                2,
            )
        )

        max_chars = int(
            CONFIG["web"].get(
                "lookup_page_chars",
                3500,
            )
        )

    for result in results[:page_count]:
        fetch_page(
            result,
            max_chars=max_chars,
        )

    return results


def _truncate_text(
    text: str,
    max_chars: int,
) -> str:
    if len(text) <= max_chars:
        return text

    if max_chars <= 1:
        return text[:max_chars]

    candidate = (
        text[:max_chars - 1]
        .rsplit(" ", 1)[0]
        .rstrip()
    )

    if not candidate:
        candidate = text[
            :max_chars - 1
        ].rstrip()

    return candidate + "…"


def _source_context(
    result: WebResult,
    *,
    source_id: str,
    research: bool,
    page_chars: int,
) -> str:
    block = [
        f"[{source_id}]",
        f"Title: {result.title}",
        f"URL: {result.url}",
    ]

    if result.description:
        block.append(
            "Search snippet: "
            + result.description
        )

    if research:
        for snippet in (
            result.extra_snippets[:2]
        ):
            block.append(
                "Additional search snippet: "
                + snippet
            )

    if (
        result.page_text
        and page_chars > 0
    ):
        block += [
            "",
            "Retrieved page excerpt:",
            _truncate_text(
                result.page_text,
                page_chars,
            ),
        ]

    elif result.fetch_error:
        block += [
            "",
            (
                "Page fetch unavailable; "
                "use search snippet only."
            ),
        ]

    return "\n".join(block)


def build_web_context(
    results: list[WebResult],
    *,
    research: bool = False,
) -> str:
    if not results:
        return ""

    total_chars = int(
        CONFIG["web"].get(
            (
                "research_context_chars"
                if research
                else "lookup_context_chars"
            ),
            9000 if research else 6000,
        )
    )

    page_chars = int(
        CONFIG["web"].get(
            (
                "research_context_page_chars"
                if research
                else "lookup_context_page_chars"
            ),
            900 if research else 1500,
        )
    )

    # ---------------------------------------------------------
    # Pass 1: reserve space for EVERY source.
    #
    # Do not add page excerpts yet. This prevents early fetched
    # pages from consuming the context before later sources such
    # as S6 are represented.
    # ---------------------------------------------------------

    blocks = [
        _source_context(
            result,
            source_id=f"S{index}",
            research=research,
            page_chars=0,
        )
        for index, result in enumerate(
            results,
            1,
        )
    ]

    base_context = "\n\n".join(
        blocks
    )

    # If snippets alone exceed the entire budget, compact each
    # source fairly rather than dropping later sources.
    if len(base_context) >= total_chars:
        separator_chars = (
            2 * (len(results) - 1)
        )

        per_source = max(
            120,
            (
                total_chars
                - separator_chars
            )
            // len(results),
        )

        compact_blocks: list[str] = []

        for index, result in enumerate(
            results,
            1,
        ):
            source_id = f"S{index}"

            block = _source_context(
                result,
                source_id=source_id,
                research=False,
                page_chars=0,
            )

            marker = f"[{source_id}]"

            available = max(
                0,
                per_source
                - len(marker)
                - 1,
            )

            body = block[
                len(marker) + 1:
            ]

            compact_blocks.append(
                marker
                + "\n"
                + _truncate_text(
                    body,
                    available,
                )
            )

        return "\n\n".join(
            compact_blocks
        )[:total_chars]

    # ---------------------------------------------------------
    # Pass 2: use only the REMAINING budget for page excerpts.
    # ---------------------------------------------------------

    used_chars = len(
        base_context
    )

    for index, result in enumerate(
        results
    ):
        if (
            not result.page_text
            or page_chars <= 0
        ):
            continue

        remaining = (
            total_chars
            - used_chars
        )

        label = (
            "\n\n"
            "Retrieved page excerpt:\n"
        )

        # Don't add a useless tiny fragment.
        if remaining <= len(label) + 40:
            break

        excerpt_limit = min(
            page_chars,
            remaining - len(label),
        )

        excerpt = _truncate_text(
            result.page_text,
            excerpt_limit,
        )

        addition = (
            label
            + excerpt
        )

        blocks[index] += addition
        used_chars += len(
            addition
        )

    context = "\n\n".join(
        blocks
    )

    return context[:total_chars]


def build_source_footer(
    results: list[WebResult],
) -> str:
    if not results:
        return ""

    lines = [
        "### Sources",
        "",
    ]

    for index, result in enumerate(
        results,
        1,
    ):
        source_id = f"S{index}"

        title = (
            result.title
            .replace("[", "\\[")
            .replace("]", "\\]")
        )

        lines.append(
            f"- [{source_id} — {title}]"
            f"({result.url})"
        )

    return "\n".join(lines)
