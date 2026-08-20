# pgpt-cli

`pgpt-cli` is a local-first ChatGPT-style assistant for WSL. Ollama generates answers; pgpt automatically chooses between local knowledge, configured project source, focused Brave lookup, and multi-source web research. It also provides persistent terminal chats, a browser UI, and an OpenAI-compatible endpoint for VS Code clients.

```text
terminal / browser / VS Code
             |
             v
          pgpt-cli
        /     |     \
     Ollama  project  Brave
```

The design goal is simple: ordinary questions stay fast and local, project questions use real source code, changing public facts use the web, and genuine research uses multiple sources. PrivateGPT remains optional compatibility/RAG tooling; normal chat does not depend on it.

## First pull / setup

The Python package itself has no third-party runtime dependencies. Prompt generation requires an Ollama server and at least one configured answer model.

```bash
cd ~/ai/pgpt-cli
git switch main
git pull --ff-only origin main

python3 -m venv .venv        # first setup only
source .venv/bin/activate
python -m pip install -e .

pgpt status
pgpt models
```

Default model preferences are in `config.json`. A practical baseline is:

```bash
ollama pull qwen3:1.7b
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
```

`pgpt status` is safe to run when services are stopped: it reports what is reachable instead of crashing. Keep Ollama, pgpt, and optional PrivateGPT bound to localhost unless you intentionally choose otherwise.

## Everyday use

```bash
pgpt ask "What is dependency injection?"
pgpt chat
pgpt server
```

Open the browser at `http://127.0.0.1:8765/`. The browser provides multiple chats, recents/pinning/search, Markdown and code rendering, copy controls, timestamps, attachments, saved-response browsing, follow-up suggestions, live execution status, and streamed answer text.

Project-aware examples:

```bash
pgpt ask --project pgpt-cli --context \
  "Explain how select_model works."

pgpt ask --project vibemaster --context \
  "Review the caching strategy in my application."
```

Normally you should not need to choose a route manually.

## Automatic routing

The default `--web auto` policy is:

```text
stable/general question     -> local Ollama
project evidence/request    -> direct project-source retrieval
current public fact         -> focused Brave lookup
explicit web request        -> focused Brave lookup
multi-source research       -> Brave research
```

High-confidence cases are deterministic. Only ambiguous general questions use one small Ollama decision: **does an accurate answer need current public information?** Explicit CLI overrides always win.

Manual controls remain available for debugging or deliberate overrides:

```text
--web auto       automatic
--web off        local-only
--web lookup     force focused lookup
--web research   force multi-source research
--context        force project source
--no-context     disable project source
```

Examples:

```bash
pgpt validate "What is dependency injection?"
pgpt validate "Who runs this organization?"
pgpt validate "Who ran this organization in 2010?"
pgpt validate "Look up this npm error on the web and explain the likely cause."
```

To try another installed router model without editing the repository:

```bash
PGPT_ROUTER_MODEL=gemma4:e4b pgpt validate "Who runs this organization?"
```

## Brave web access

Create the local secrets file outside Git:

```bash
mkdir -p ~/.config/pgpt
cp secrets.env.example ~/.config/pgpt/secrets.env
chmod 600 ~/.config/pgpt/secrets.env
```

Add `PGPT_BRAVE_API_KEY=...`, then check usage with:

```bash
pgpt web-usage
```

If the network or Brave retrieval is unavailable, an automatic web route falls back to local generation and is marked as offline rather than pretending current information was retrieved.

## Skills

```text
~/ai/pgpt-cli/skills/   built-in, Git-managed skills
~/.config/pgpt/skills/  personal skills
```

```bash
pgpt skill-new my-review
nano ~/.config/pgpt/skills/my-review.md
pgpt skills
pgpt ask --skill my-review "Review this design."
```

A personal skill overrides a built-in skill with the same name.

## VS Code / local API

Start:

```bash
pgpt server
```

The browser is at `http://127.0.0.1:8765/`; the OpenAI-compatible API is under `/v1`. See `docs/VS_CODE.md` and `docs/continue-config.yaml`.

`stream: true` chat completions emit answer chunks as they are generated. pgpt-specific SSE metadata also reports execution status and any verified answer replacement used by the browser.

## PrivateGPT is optional

Normal `ask`, `validate`, `chat`, `server`, browser/VS Code chat, direct project-source retrieval, Brave, and skills do **not** require PrivateGPT.

The optional compatibility/RAG maintenance commands are:

```bash
pgpt sync --project pgpt-cli
pgpt ingest --project pgpt-cli
pgpt serve
```

Remember:

```text
pgpt server   pgpt browser/API
pgpt serve    optional PrivateGPT server
```

## Test gates

Run the release-safe offline checks before pulling a change into your working setup:

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
pgpt --help > /dev/null
pgpt validate --web off "What is dependency injection?"
```

CI runs the offline suite on Python 3.11 and 3.13. It also checks the browser JavaScript, JSON datasets, CLI smoke commands, and the repository's single-branch policy.

Routing has two layers of coverage:

- `evals/routing_policy_cases.json`: 100+ deterministic policy cases run in normal CI.
- `evals/routing_gold.json`: human-curated real-Ollama acceptance cases, including moving-vs-fixed minimal pairs.

Run the real router locally:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
  python -m unittest tests.test_router_dataset -v
```

Response quality has separate end-to-end and judge suites because they intentionally exercise local models and, for web cases, live retrieval:

```bash
python -m tools.run_end_to_end_evals --fresh
python -m tools.score_end_to_end_results --model qwen3.5:9b
python -m tools.calibrate_quality_judge --model qwen3.5:9b
```

See `docs/TESTING.md` for the full workflow.

## Repository rule

`main` is the only intended branch. Do not create long-lived feature, repair, or experiment branches. Keep changes small, delete obsolete mechanisms instead of retaining parallel implementations, and keep secrets/runtime data out of Git.
