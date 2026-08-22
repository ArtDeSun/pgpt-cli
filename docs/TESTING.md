# Testing pgpt-cli

## Offline release gate

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

CI runs this on Python 3.11 and 3.13, checks browser JavaScript, and requires exactly one remote branch named `main`.

The offline suite owns repository behavior that does not require your machine services: deterministic routing policy, route/runtime separation, direct project retrieval, historical fixtures, model selection with mocks, pipeline controls, verification rules, web quota/accounting, browser/API behavior, history, skills, response storage, and ingestion safety.

## Local-model routing acceptance

Requires Ollama and the configured router model:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
python -m unittest tests.test_router_acceptance_local -v
```

This intentionally tests the real small-model classifier rather than a mocked decision. It is opt-in so normal GitHub CI does not pretend to validate an Ollama daemon that is not present.

## Manual acceptance scenarios

1. **Current public result** — ask `Who won the 2026 NBA championship?`. Auto must choose web lookup. Force Lookup must either return a sourced web answer or a clear retrieval error; it must never silently guess locally.
2. **Stable local question** — ask `What is dependency injection?` with `--web off`. It should stay local and should not invoke PrivateGPT.
3. **Project retrieval** — ask `Explain how resolve_route works in pgpt-cli.` Confirm direct project-source retrieval names the real source file and does not require a vector index.
4. **Topic switch** — discuss pgpt source code, then ask an unrelated current-events question. Smart context should drop the old code topic.
5. **Follow-up context** — ask a stable question, then `Use the web for that.` Smart context should preserve the prior question.
6. **Model visibility** — compare `pgpt models` with the UI Model dropdown.
7. **Long response** — request a detailed plan with Answer length = Long. Internal continuation instructions must never appear in the visible answer.
8. **Manual routing** — force Project, Web, Model, Task, Context and Answer length individually and confirm route metadata reflects the choice.
9. **UI rendering** — verify hover/pressed/focus feedback, headings/lists/links/code render without visible Markdown syntax, streaming works, the activity indicator changes stages, and Send becomes Stop during generation.
10. **Arbitrary knowledge folder** — run `pgpt knowledge-add` on a harmless local directory. Confirm it appears as a project only after successful PrivateGPT ingestion. Confirm `/`, `.ssh`, `.gnupg`, and `.aws` are rejected.
11. **Zero-byte basename collision** — create `old/example.md` as zero bytes and `current/example.md` with content, then ingest the parent folder once. Confirm pgpt reports a temporary filtered staging tree and PrivateGPT still receives the valid `current/example.md`.
12. **PrivateGPT boundary** — confirm `pgpt server` works without PrivateGPT. When PrivateGPT is started separately with `pgpt serve`, its own Workbench is available at `http://127.0.0.1:8080/ui` if UI hosting is enabled.

## Real-service release checks

These cannot be truthfully certified by GitHub-hosted CI because they depend on your local NVIDIA/Ollama runtime, Brave credentials/quota, and PrivateGPT installation.

After pulling a release:

```bash
pgpt status
pgpt models
pgpt web-usage

pgpt validate --web off \
  "What is dependency injection?"

time pgpt ask --web auto \
  "Who won the 2026 NBA championship?"

time pgpt ask --project pgpt-cli \
  "Explain how resolve_route works in this project."
```

Then start the UI:

```bash
pgpt server
```

Open `http://127.0.0.1:8765/` and exercise a new chat, stop-generation, a project question, a web question, an attachment, a saved response, and Run details.

## End-to-end quality

When Ollama and Brave are configured, run the project evaluation commands in `tools/`. Review correctness, grounding, latency, route choice, model choice, and truncation together; unit routing accuracy alone is not enough.

For expensive judge calibration, prefer targeted known-difficult cases before running the entire set.
