# Testing

Use the smallest useful test first. Run expensive Ollama/judge suites only after the cheap tests pass.

## 1. Offline checks

These need no Ollama, Brave, PrivateGPT, or external project files:

```bash
python -m json.tool config.json > /dev/null
python -m compileall -q pgpt tools tests
git diff --check
```

GitHub Actions runs the authoritative offline unittest list from `.github/workflows/ci.yml` on Python 3.11 and 3.13. Keep that workflow readable instead of duplicating the full list here.

## 2. Routing tests

Routing has two kinds of tests.

**Policy tests** (`tests/test_routes.py`) mock the one semantic decision and verify deterministic routing behavior. These run in CI.

**Local-model acceptance tests** use your actual Ollama router and run only in WSL:

```bash
python -m unittest \
  tests.test_router_dataset \
  tests.test_router_temporal_pairs \
  -v
```

`routing_gold.json` is the broad, human-curated routing set. `routing_temporal_pairs.json` focuses on current/moving facts versus fixed history or supplied context.

The router model only answers one question for ambiguous general prompts: does the answer require current public information?

Test another installed model without editing the repo:

```bash
PGPT_ROUTER_MODEL=gemma4:e4b \
  python -m unittest tests.test_router_temporal_pairs -v
```

Do not patch production regexes to satisfy one sentence. If a model repeatedly fails a class of cases, change the model or the general routing rule.

## 3. End-to-end quality

Run targeted cases first:

```bash
python -m tools.run_end_to_end_evals --case debug_local_01 --force
python -m tools.score_end_to_end_results \
  --model qwen3.5:9b \
  --case debug_local_01
```

Then run the full suite when the targeted cases are stable:

```bash
python -m tools.run_end_to_end_evals --fresh
python -m tools.score_end_to_end_results --model qwen3.5:9b
```

## 4. Judge calibration

```bash
python -m tools.calibrate_quality_judge --model qwen3.5:9b
```

Calibration checks the judge itself. Do not trust end-to-end quality scores if judge calibration is failing.

## 5. Reliability

Repeated runs are expensive. Use them near the end of a change:

```bash
python -m tools.run_reliability_evals \
  --runs 5 \
  --judge-model qwen3.5:9b \
  --fresh
```

## 6. Manual smoke test

```bash
pgpt status
pgpt validate "What is dependency injection?"
pgpt validate "What's the weather in Toronto?"
pgpt ask --web off "What is dependency injection?"
pgpt server
```

Then open `http://127.0.0.1:8765/` and check chat history, attachments, Markdown rendering, timers, links, and web-mode controls.

## Maintenance principle

Tests are documentation for the human maintainer. Prefer a small table of meaningful cases over large generated suites, and remove tests that duplicate another layer without adding confidence.
