# Testing

Use the cheapest test that can catch the problem. Run expensive Ollama/judge tests only after offline tests pass.

## 1. Offline tests

No Ollama, Brave, PrivateGPT, or external project is required:

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

GitHub Actions runs the same unittest discovery on Python 3.11 and 3.13. The real-model routing test is skipped there.

## 2. Real Ollama routing

`tests/test_router_dataset.py` is the single human-curated routing acceptance suite. It covers local, project, web, research, debugging, implementation, architecture, and moving-vs-fixed public facts.

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
  python -m unittest tests.test_router_dataset -v
```

Try another installed router without changing code:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
PGPT_ROUTER_MODEL=gemma4:e4b \
  python -m unittest tests.test_router_dataset -v
```

Do not add production regexes for one failing sentence. Fix a general rule or choose a better router model.

## 3. End-to-end quality

Start with one case:

```bash
python -m tools.run_end_to_end_evals --case debug_local_01 --force
python -m tools.score_end_to_end_results \
  --model qwen3.5:9b \
  --case debug_local_01
```

When targeted cases are stable:

```bash
python -m tools.run_end_to_end_evals --fresh
python -m tools.score_end_to_end_results --model qwen3.5:9b
```

## 4. Judge calibration

```bash
python -m tools.calibrate_quality_judge --model qwen3.5:9b
```

Do not trust semantic quality scores while judge calibration is failing.

## 5. Smoke test

```bash
pgpt status
pgpt validate "What is dependency injection?"
pgpt validate "What's the weather in Toronto?"
pgpt ask --web off "What is dependency injection?"
pgpt server
```

Then open `http://127.0.0.1:8765/` and check one chat, one attachment, links, Markdown rendering, and web-mode controls.

Tests are documentation for the human maintainer. Prefer a small set of distinct failure modes over many near-duplicate cases.
