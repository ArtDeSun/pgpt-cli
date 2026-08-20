# Testing

Use the cheapest test that can catch the problem. Offline CI must be green before running expensive Ollama, Brave, or judge suites.

## 1. Offline release gate

No Ollama, Brave, PrivateGPT, or external project is required:

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
pgpt --help > /dev/null
pgpt validate --web off "What is dependency injection?"
```

GitHub Actions runs this surface on Python 3.11 and 3.13, validates JSON datasets and browser JavaScript, and checks that `main` is the only remote branch.

`evals/routing_policy_cases.json` is the scalable offline routing contract. It contains 100+ cases spanning general, writing, current facts, moving-vs-fixed pairs, explicit web, research, project, debug, implementation, architecture, symbol routing, and overrides. Cases declare the semantic web decision when one is required, so CI tests production policy without needing Ollama.

## 2. Real Ollama routing acceptance

`tests/test_router_dataset.py` uses `evals/routing_gold.json` with the actual router model. This is deliberately opt-in because it requires your local Ollama server.

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
  python -m unittest tests.test_router_dataset -v
```

Try another installed router without editing code:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
PGPT_ROUTER_MODEL=gemma4:e4b \
  python -m unittest tests.test_router_dataset -v
```

Treat a repeated class of failures as a routing-policy or router-model problem. Do not add a one-sentence regex solely to satisfy one example.

## 3. End-to-end response quality

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

These cases check both the selected route/model/template and answer content. Web cases need Brave; project cases use repository-contained fixtures where possible.

## 4. Judge calibration

```bash
python -m tools.calibrate_quality_judge --model qwen3.5:9b
```

Do not trust semantic quality scores while judge calibration is failing.

## 5. Browser/API smoke test

```bash
pgpt status
pgpt models
pgpt server
```

Open `http://127.0.0.1:8765/` and verify:

- create/switch/search/pin/delete chats;
- streamed answer text and live execution status;
- Markdown, links, code blocks, and copy control;
- one text/code attachment;
- saved-response browsing/download;
- web auto/off/lookup/research controls.

For the OpenAI-compatible API, verify both normal and `stream: true` chat completions.

## Release checklist

- `main` is the only branch.
- Offline CI passes on Python 3.11 and 3.13.
- No skipped offline test hides a required dependency.
- Real-router acceptance is run after routing/model changes.
- Targeted end-to-end quality cases pass after prompt/model/retrieval changes.
- README setup commands match the current CLI.
- Local services bind to loopback by default.
- No secrets, responses, chats, state, or model data are committed.
