# Testing pgpt-cli

## Offline release gate

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

CI runs this on Python 3.11 and 3.13, checks browser JavaScript, and requires exactly one remote branch named `main`.

## Local-model routing acceptance

Requires Ollama and the configured router model:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 python -m unittest tests.test_router_acceptance_local -v
```

## Manual acceptance scenarios

1. **Current NBA result** — ask `Who won the 2026 NBA championship?`. Auto must choose web lookup. Force Lookup must either return a sourced web answer or a clear retrieval error; it must never silently guess locally.
2. **Topic switch** — discuss pgpt source code, then ask an unrelated NBA/current-events question. Smart context should drop the old code topic.
3. **Follow-up context** — ask a stable question, then `Use the web for that.` Smart context should preserve the prior question.
4. **Model visibility** — ask which Ollama models are available and compare with `pgpt models`. The UI Model dropdown should also list installed models.
5. **Long response** — request a detailed music-business model with Answer length = Long. Internal continuation instructions must never appear in the visible answer.
6. **Manual routing** — force Project, Web, Model, Task, Context and Answer length individually and confirm route metadata reflects the choice.
7. **UI rendering** — verify hover/pressed/focus feedback, headings/lists/links/code render without visible Markdown syntax, streaming works, and Send becomes Stop during generation.
8. **Knowledge ingestion** — Add knowledge folder using a harmless local directory. Confirm it appears in Project after successful PrivateGPT ingestion. Confirm `/`, `.ssh`, `.gnupg`, and `.aws` are rejected.

## End-to-end quality

When Ollama and Brave are configured, run the project evaluation commands documented in `tools/`. Review correctness, grounding, latency, route choice, model choice, and truncation together; unit routing accuracy alone is not enough.
