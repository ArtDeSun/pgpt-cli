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
- generic time-scope classifier schema/mapping;
- deterministic fast routes only for explicit/high-confidence live surfaces;
- router-policy regressions with semantic decisions injected explicitly;
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

## Routing tests: policy vs language understanding

Routing has two different things to test, and they should not be confused.

The **offline router-policy tests** inject a semantic decision such as `current` or `stable`, then verify that execution policy maps it correctly to web/local/project behavior. These tests are deterministic and run in CI. They do not pretend to prove that your local Ollama router understands every English paraphrase.

The **local-model acceptance tests** exercise the actual router model. `routing_gold.json` covers the broad routing surface. `routing_temporal_pairs.json` covers moving vs fixed time scope across roles, releases, prices, policies, availability, relative dates, historical dates, concepts and supplied/project context.

The semantic router deliberately has a small contract:

```text
prompt
  -> task
  -> time_scope: moving | fixed | unknown

moving -> freshness=current
fixed  -> freshness=stable
```

Complexity is not asked of the language model. It is derived from the task and remains telemetry only.

Run the model-dependent suites in WSL:

```bash
python3 -m unittest \
  tests.test_router_dataset \
  tests.test_router_generated \
  tests.test_router_temporal_pairs \
  -v
```

Generated routing cases are exploratory diagnostics and can contain bad generated labels; inspect disagreements rather than changing production routing blindly to satisfy generated data.

### Compare router models before changing the default

The configured router is `qwen3.5:4b`. A temporary model can be selected without editing the repository by setting `PGPT_ROUTER_MODEL`.

To compare the configured router with the locally installed Gemma 4 E4B model on the same temporal acceptance set:

```bash
time python3 -m tools.benchmark_router_models \
  --model qwen3.5:4b \
  --model gemma4:e4b
```

The benchmark prints failures per model, total cases passed and elapsed time. It exits successfully only when at least one tested model passes the full temporal set.

For a one-off validation with a specific router model:

```bash
PGPT_ROUTER_MODEL=gemma4:e4b \
  pgpt validate "Who runs this organization?"
```

This makes router-model changes evidence-based instead of changing English rules to accommodate individual failed prompts.

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

Then check implicit temporal meaning with a minimal pair:

```bash
pgpt validate "Who runs this organization?"
pgpt validate "Who ran this organization in 2010?"
```

The first should be `current`/web lookup; the second should be `stable`/local. Neither behavior should depend on the organization name or a hard-coded job title.

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
