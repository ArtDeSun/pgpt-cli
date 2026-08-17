# Testing pgpt-cli

pgpt-cli has an offline production gate plus explicit local-model acceptance tests. The split is intentional: GitHub-hosted runners cannot reproduce your WSL GPU, Ollama model set, Brave subscription, or PrivateGPT installation.

## Offline CI gate

`.github/workflows/ci.yml` runs on Python 3.11 and 3.13 without Ollama, Brave, PrivateGPT, or external project files.

It validates:

- Python/JSON/package syntax;
- browser JavaScript syntax;
- model selection with injected model availability;
- mocked pipeline behavior;
- routing decision vs runtime-route boundaries;
- deterministic fast routes for weather/time/live lookup surfaces;
- path/config handling;
- the repository-owned historical project fixture;
- source retrieval snapshots;
- built-in and personal skill behavior;
- HTTP/CORS/chat-completion behavior;
- saved response listing/read/download;
- Brave safety-budget state, header parsing and HTTP hooks;
- semantic judge required/forbidden polarity and malformed-JSON retry;
- response Markdown metadata/rendered-view links;
- browser UI contracts for multiple chats, files, Markdown rendering, timers and usage controls;
- prompt ownership: natural-language judge/router instructions live in Markdown assets rather than Python.

Run the complete offline gate by copying the unittest module list from `.github/workflows/ci.yml`.

## Routing datasets

There are deliberately different levels of trust.

`routing_gold.json` and regression tests are curated expectations. Generated routing cases are broad exploratory diagnostics and can contain bad generated labels; disagreements should be inspected rather than blindly changing production routing to satisfy them.

The model-dependent dataset/report commands include:

```bash
python3 -m unittest \
  tests.test_router_dataset \
  tests.test_router_generated \
  tests.test_router_regressions \
  -v
```

These may call your local router model and therefore are not part of GitHub-hosted CI.

## Local WSL acceptance

After pulling a release candidate:

```bash
cd ~/ai/pgpt-cli
source .venv/bin/activate
python -m pip install -e .

pgpt status
pgpt models
pgpt web-usage
```

Check a stable local prompt:

```bash
time pgpt ask --web off \
  "What is dependency injection?"
```

Check the fast live lookup surface:

```bash
time pgpt ask --web auto \
  "What's the weather in Toronto today?"
```

The second request should route to focused web lookup without running the ambiguous semantic classifier and without fetching full result pages. Network speed, Ollama cold starts, and Brave latency will still affect wall-clock time.

Check browser/API:

```bash
pgpt server
```

Then open `http://127.0.0.1:8765/` and verify chats, attachments, timer, rendered Markdown, response browsing, usage badge, and web-mode switching.

## Judge calibration

The semantic judge evaluates each required/forbidden criterion independently. Required judgments return `satisfied`; forbidden judgments return `violated`. This avoids the previous ambiguity of using a generic `passed` field for opposite meanings.

Start with targeted cases while iterating:

```bash
python3 -m tools.calibrate_quality_judge \
  --model qwen3.5:9b \
  --case project_grounded_bad_subtle_cleanup_02 \
  --case project_grounded_bad_mixed_accuracy_03
```

Then run the full suite:

```bash
time python3 -m tools.calibrate_quality_judge \
  --model qwen3.5:9b
```

Criterion output is capped to a tiny structured boolean response, so the judge does not spend hundreds of tokens generating prose reasons or truncate a long JSON reason string.

## End-to-end evaluation

```bash
time python3 -m tools.run_end_to_end_evals --fresh

time python3 -m tools.score_end_to_end_results \
  --model qwen3.5:9b
```

The project-grounded case uses `pgpt-cli-history`, not the inaccessible external `vibemaster` directory.

## Reliability

Run repeated generation only after targeted correctness is stable:

```bash
time python3 -m tools.run_reliability_evals \
  --runs 5 \
  --judge-model qwen3.5:9b \
  --fresh
```

Reliability runs are intentionally expensive. Use targeted cases first rather than spending GPU time rerunning a large suite after every small change.

## Brave usage tests vs real account usage

Offline tests simulate Brave headers and local state. They do not consume API requests. Real successful Brave calls update `state/brave_usage.json`, and `pgpt web-usage` reports the local/API-derived snapshot.

The configured `monthly_request_budget` is a local safety ceiling. It is independent from, and should be set at or below, whatever quota your actual Brave plan provides.
