# pgpt-cli

`pgpt-cli` is a local-first ChatGPT-style assistant for WSL. Ollama generates answers, direct project-source retrieval handles code/project questions, Brave supplies current public information and research, and PrivateGPT is an optional durable RAG layer.

The operating rule is: **Auto should normally work, but the browser exposes authoritative manual overrides for every high-impact decision.**

## Architecture

```text
Terminal: pgpt ask/chat          Browser: http://127.0.0.1:8765
            \                              /
             \                            /
              +------ pgpt-cli API ------+
                         |
               routing + context policy
                  /        |        \
                 /         |         \
        direct project    Brave      local skills/history
           source          web
                 \         |         /
                  \        |        /
                       Ollama
                         |
                  verify / repair
                         |
                       answer

Optional durable RAG path
-------------------------
local folder -> pgpt collection-aware ingest helper
             -> PrivateGPT IngestService
             -> ~/ai/private-gpt-data
```

PrivateGPT is **not** the normal pgpt answer-generation frontend. Normal chat, project-source retrieval, Brave, skills, routing, and verification remain pgpt-native.

## Existing `~/ai` layout

You do **not** need to reorganize your existing folders:

```text
~/ai/
├── pgpt-cli/                 # this repository
├── private-gpt/              # upstream PrivateGPT source checkout
├── private-gpt-data/         # generated PrivateGPT runtime/vector/env state
└── vibemaster-knowledge/     # current VibeMaster source/snapshot
```

`config.json` points the built-in `vibemaster` project at `~/ai/vibemaster-knowledge`.

For `pgpt-cli` itself, `pgpt sync --project pgpt-cli` may create this optional sanitized snapshot:

```text
~/ai/knowledge/pgpt-cli
```

That is additive. You do not need to move your repositories under `~/ai/knowledge`.

Personal pgpt state remains outside the repositories:

```text
~/.config/pgpt/
├── projects.json
├── secrets.env
└── skills/
```

Keep these boundaries:

```text
private-gpt/       upstream software/source code
private-gpt-data/  generated PrivateGPT runtime/vector/env state
pgpt-cli/          pgpt application source
vibemaster-knowledge/
                   current VibeMaster source/snapshot
```

Do not use `private-gpt-data` as an ingestion source.

## Pull and install pgpt-cli

```bash
cd ~/ai/pgpt-cli
git switch main
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e .

pgpt status
pgpt models
```

Recommended local answer/router models:

```bash
ollama pull qwen3:1.7b
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
```

Default roles:

```text
routing/classifier             qwen3:1.7b
general/research answers       llama3.2:3b when available
code/debug/implementation      qwen2.5-coder:3b when available
```

## Browser

Start pgpt:

```bash
pgpt server
```

Open:

```text
http://127.0.0.1:8765/
```

The browser includes multiple chats, pinned/recents/search, attachments, saved responses, Markdown/code rendering, streaming, execution status, stop-generation, follow-up actions, and route/model metadata.

### Settings

The main conversation stays uncluttered. Open **Settings** only when you want to override Auto behavior.

| Control | Options | Effect |
| --- | --- | --- |
| Project routing | Auto / Off / Force project | Prevent or force project retrieval. |
| Project | configured project | Chooses the project source. |
| Web | Auto / Off / Force lookup / Force research | Forced web never silently falls back to an ungrounded local guess. |
| Model | Auto / installed Ollama model | Explicit model always wins. |
| Task | Auto / General / Explain code / Debug / Implement / Architecture / Research | Overrides task/template routing. |
| Chat context | Smart / Full recent / Off | Controls conversation history. |
| Answer length | Auto / Short / Standard / Long | Controls output budget. |
| Skill | Off / selected skill | Applies a task instruction manual. |
| Reasoning | Auto / Deep / Normal | Controls the larger context mode. |

The **Capabilities** section shows current Ollama models, Brave status/quota state, configured project sources, and skills.

### Run details

Each assistant response has a collapsed **Run details** inspector containing observable execution facts: route/source/task, selected model, web/project selection, context/length controls, status events, and timing.

It does not expose hidden chain-of-thought.

### Smart context

`Smart` is the default. It preserves relevant follow-ups while dropping unrelated older topics. `Full recent` deliberately sends recent history; `Off` starts clean except for an explicitly selected skill.

## Routing and web behavior

With controls on Auto:

```text
stable/general question     -> local Ollama
project evidence/request    -> direct project-source retrieval
current public fact         -> Brave lookup
explicit web request        -> Brave lookup
multi-source research       -> Brave research
```

High-confidence routing is deterministic. Only ambiguous general freshness decisions use the small Ollama classifier. Current-year public-result questions are treated as current, and a coincidental project symbol hit is not enough to hijack an unrelated public question.

Examples:

```bash
pgpt validate "What is dependency injection?"
pgpt validate "Who won the 2026 NBA championship?"
pgpt validate "Explain your own source code and routing."
pgpt validate "Look up this npm error on the web and explain the likely cause."
```

For Brave, create:

```text
~/.config/pgpt/secrets.env
```

with:

```text
PGPT_BRAVE_API_KEY=...
```

Then check:

```bash
pgpt web-usage
```

A Brave monthly plan limit of `0` is treated as unlimited. `monthly_request_budget` in `config.json` is a separate pgpt-side safety budget.

An automatically chosen web route may degrade gracefully when offline and explicitly reports that live evidence was unavailable. A forced lookup/research or natural-language explicit web request instead returns a clear retrieval error rather than silently guessing a current answer locally.

## Projects and direct source retrieval

Normal project/code questions read the selected source tree directly. They do **not** require PrivateGPT or a vector index.

```bash
pgpt ask --project pgpt-cli \
  "Explain how resolve_route works."

pgpt ask --project vibemaster \
  "Explain the YouTube metadata handling in this project."
```

Direct retrieval excludes common generated/dependency directories, credentials directories, and symlink files. The built-in `pgpt-cli-history` fixture remains available to tests as a self-contained historical retrieval target.

## Optional PrivateGPT setup

The current upstream PrivateGPT checkout requires Python 3.11. pgpt therefore invokes PrivateGPT through `uv` with an explicit Python 3.11 and the upstream `core` extra.

Make sure `uv` is installed and Python 3.11 is available:

```bash
uv python install 3.11
```

PrivateGPT also needs an embedding-capable Ollama model for durable ingestion. A practical choice matching its current default 1024-dimensional vector configuration is:

```bash
ollama pull mxbai-embed-large
```

pgpt starts the current upstream PrivateGPT CLI approximately as:

```text
uv run --python 3.11 --extra core private-gpt serve --host 127.0.0.1
```

and points both PrivateGPT's LLM and embedding OpenAI-compatible endpoints at your local Ollama `/v1` endpoint.

### PrivateGPT runtime state

Current PrivateGPT and `uv` normally create local runtime/environment state around the project being run. pgpt redirects the relevant paths so generated state does not pollute `~/ai/private-gpt`.

pgpt redirects them under:

```text
~/ai/private-gpt-data/
├── venv/                     # uv environment for the PrivateGPT checkout
├── private_gpt/              # PrivateGPT local data
├── qdrant/                   # local Qdrant vector state
└── volumes/                  # local code-execution volume state
```

The upstream source checkout remains source code only.

## Add any knowledge folder

The browser's **Add knowledge folder** action and this CLI command use the same pgpt ingestion path:

```bash
pgpt knowledge-add /absolute/path/to/notes \
  --name notes \
  --collection notes
```

Optional basename ignores can be repeated:

```bash
pgpt knowledge-add /absolute/path/to/notes \
  --name notes \
  --ignore scratch.txt \
  --ignore generated.md
```

pgpt:

1. validates the project and collection names before starting an expensive ingestion job;
2. validates that the path is a readable directory;
3. rejects filesystem/home roots, PrivateGPT runtime data, and common credentials directories;
4. automatically excludes nested `.ssh`, `.gnupg`, `.aws`, `.env`, `.env.*`, `*.pem`, and `*.key` entries;
5. skips symlinks rather than following them into another tree;
6. runs a pgpt-owned collection-aware helper inside PrivateGPT's Python environment;
7. calls PrivateGPT's `IngestService` rather than modifying the upstream PrivateGPT checkout;
8. preserves the requested PrivateGPT collection name instead of relying on upstream `scripts/ingest_folder.py`'s hard-coded default collection;
9. stores path-aware artifact IDs so same-named files in different directories do not overwrite one another;
10. registers the project in `~/.config/pgpt/projects.json` only after successful ingestion;
11. propagates ingestion failures instead of reporting a false success.

### Local Qdrant sequencing

With the default file-backed Qdrant configuration, do **not** run `pgpt knowledge-add` or `pgpt ingest` concurrently with `pgpt serve`. Both processes can open the same local Qdrant state.

Use this sequence:

```text
1. Stop pgpt serve if it is running.
2. Run pgpt knowledge-add ... or pgpt ingest ...
3. Wait for ingestion to finish.
4. Start pgpt serve when you want the PrivateGPT Workbench/API.
```

The normal pgpt browser server (`pgpt server`) is independent and does not create this Qdrant conflict.

### Zero-byte source cleanup

PrivateGPT ignore rules are basename-oriented. A naive workaround for empty files can therefore hide a valid file elsewhere with the same basename.

For example:

```text
source/
├── old/example.md        0 bytes
└── current/example.md    valid content
```

For one-shot ingestion, pgpt detects this collision and builds a temporary filtered staging tree containing the valid file but not the zero-byte path. The original source tree is not modified, and the staging tree is deleted afterward.

When there is no basename collision, pgpt keeps the faster direct-ingestion path and adds the empty basenames to the ignore set.

`--watch` cannot use a temporary snapshot because later source changes would not be mirrored into it. In the rare watched-ingestion collision case, pgpt prints an explicit warning and retains basename filtering.

## Existing project sync / ingestion

The project-oriented maintenance commands remain:

```bash
# create/update optional sanitized pgpt-cli snapshot
pgpt sync --project pgpt-cli

# ingest it into its configured PrivateGPT collection
pgpt ingest --project pgpt-cli

# VibeMaster already points directly at its source/snapshot
pgpt sync --project vibemaster
pgpt ingest --project vibemaster

# optional watched ingestion
pgpt ingest --project pgpt-cli --watch
```

For `vibemaster`, sync is intentionally a no-op because its source and knowledge directory are already the same configured folder.

```text
pgpt server   -> pgpt browser/API; normal everyday workflow
pgpt serve    -> PrivateGPT server; optional RAG/compatibility workflow
```

## PrivateGPT's own UI

PrivateGPT has its own Workbench, separate from the pgpt browser.

When `pgpt serve` is running and upstream UI hosting is enabled:

```text
http://127.0.0.1:8080/ui      PrivateGPT Workbench
http://127.0.0.1:8765/        pgpt browser
```

The Workbench is an upstream PrivateGPT API demonstrator. pgpt does not patch or depend on its HTML.

## Skills

```text
~/ai/pgpt-cli/skills/   built-in Git-managed skills
~/.config/pgpt/skills/  personal skills
```

```bash
pgpt skill-new music-business
pgpt skills
pgpt ask --skill music-business "Evaluate this plan."
```

Skills are intentionally plain files with a small, inspectable contract. The repository does not grant the model unrestricted filesystem/process tools.

## Harness-inspired design choices

Adopted ideas:

- capability boundaries between model, web, project context, skills, sessions, and storage;
- provider-style settings rather than hiding everything behind Auto;
- per-response routing/model/status/timing traceability;
- advanced controls in Settings rather than cluttering the chat surface;
- explicit session-level model/web/project/context overrides;
- a clear future boundary for process/filesystem tools instead of implicit unrestricted agent access.

Not adopted today: subagents, unrestricted model-generated tool orchestration, dynamic runtime plugin loading, or exposure of private model reasoning.

## Long responses

When Ollama stops because of the output-length budget, pgpt can issue bounded continuations while hiding its internal continuation instruction. For large plans and analyses, choose **Answer length → Long**. Use **Full recent** or **Deep** only when additional context is useful.

## VS Code / WSL

`pgpt server` exposes an OpenAI-compatible endpoint:

```text
http://127.0.0.1:8765/v1
```

See:

```text
docs/continue-config.yaml
docs/VS_CODE.md
```

Intended path:

```text
VS Code Remote WSL
        |
     Continue
        |
http://127.0.0.1:8765/v1
        |
     pgpt-cli
        |
routing + direct project retrieval + Brave + skills + verification
        |
      Ollama
```

## Tests

Offline release gate:

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

CI runs on Python 3.11 and 3.13, validates browser JavaScript, and enforces the one-remote-branch rule.

Coverage includes the routing policy dataset, current-year routing, smart history, model overrides, forced-web semantics, Brave quota handling, continuation behavior, project retrieval safety, knowledge-ingest safety, zero-byte basename collisions, PrivateGPT runtime-path isolation, collection-aware ingestion, path-aware artifact IDs, ingestion failure propagation, run-details UI, and browser controls.

The real local-router acceptance suite is opt-in because GitHub-hosted CI has no Ollama daemon:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
python -m unittest tests.test_router_acceptance_local -v
```

See `docs/TESTING.md` for hardware/service-dependent release checks.
