# pgpt-cli

`pgpt-cli` is a local-first ChatGPT-style assistant for WSL. Ollama generates answers, direct project-source retrieval handles code/project questions, Brave supplies current public information and research, and PrivateGPT is optional for durable RAG ingestion.

The operating rule is: **Auto should normally work, but the browser exposes authoritative manual overrides for every high-impact decision.**

## Where it fits

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

Optional RAG maintenance path
-----------------------------
local folder -> pgpt knowledge-add / pgpt ingest -> PrivateGPT -> private-gpt-data
```

PrivateGPT is **not** the normal answer-generation frontend in this design. It remains a separate optional service for explicit ingestion/RAG work.

## Your `~/ai` layout

You do **not** need to reorganize the existing top-level folders to use this release. This layout is valid:

```text
~/ai/
├── pgpt-cli/                 # this repository
├── private-gpt/              # upstream PrivateGPT source
├── private-gpt-data/         # generated PrivateGPT state; never ingest this as knowledge
└── vibemaster-knowledge/     # your current VibeMaster source/snapshot
```

`config.json` points the built-in `vibemaster` project at `~/ai/vibemaster-knowledge`, so direct project retrieval works from the layout above.

`pgpt sync --project pgpt-cli` may create `~/ai/knowledge/pgpt-cli` as a generated/sanitized snapshot for the optional PrivateGPT ingestion path. That is additive; you do not need to move your existing repositories into `~/ai/knowledge`.

Personal pgpt state stays outside the repositories:

```text
~/.config/pgpt/
├── projects.json             # folders added as user-managed projects
├── secrets.env               # Brave key
└── skills/                   # personal skills
```

Keep the boundaries clear:

```text
private-gpt/       software/source code
private-gpt-data/  generated vector/cache/runtime state
pgpt-cli/          pgpt application source
vibemaster-knowledge/
                   current VibeMaster source/snapshot
other folders      may be explicitly added as knowledge
```

Do **not** put your own knowledge files inside the `private-gpt` Git repository, and do not use `private-gpt-data` itself as an ingestion source.

## Pull and setup

```bash
cd ~/ai/pgpt-cli
git switch main
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e .

pgpt status
pgpt models
```

A practical model set is:

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

The small router remains a fallback, not the preferred normal answer model.

## Browser

```bash
pgpt server
```

Open `http://127.0.0.1:8765/`.

The browser includes multiple chats, pinned/recents/search, attachments, saved responses, Markdown/code rendering, streaming, execution status, stop-generation, follow-up actions, and route/model metadata.

### Settings and capabilities

The main conversation stays uncluttered. Open **Settings** only when you want to override Auto behavior. The drawer groups routing/context controls separately from capability status.

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

The **Capabilities** section shows the current Ollama models, Brave status/quota state, configured project sources, and skills. Capabilities are visible as independent surfaces without adding a dynamic plugin kernel.

### Run details

Each assistant response has a collapsed **Run details** inspector. It records observable execution facts already produced by pgpt: route/source/task, selected model, web/project selection, context/length controls, status events, and timing.

It does **not** expose hidden chain-of-thought. The goal is operational traceability: you can see why a request used local/project/web and which model actually answered.

### Smart context

`Smart` is the default. It keeps relevant follow-ups but drops unrelated older topics. A project-code discussion therefore should not contaminate a later current-events question. `Full recent` deliberately sends recent history; `Off` starts clean except for an explicit skill.

## PrivateGPT's own UI versus pgpt's UI

The current PrivateGPT source checkout has its own Workbench. Its runtime UI is intentionally implemented as one static file:

```text
~/ai/private-gpt/ui/index.html
```

When the PrivateGPT server is running with UI hosting enabled, that Workbench is normally served at:

```text
http://127.0.0.1:8080/ui
```

That UI is a PrivateGPT API demonstrator. It is separate from pgpt's everyday browser interface:

```text
http://127.0.0.1:8765/        pgpt browser + pgpt OpenAI-compatible API
http://127.0.0.1:8080/ui      PrivateGPT Workbench
```

The Markdown files under `private-gpt/ui/` are design/product/agent-maintenance notes; the actual UI code is in `ui/index.html`. pgpt does not copy, patch, or depend on PrivateGPT's UI files.

## Routing and web behavior

With controls on Auto:

```text
stable/general question     -> local Ollama
project evidence/request    -> direct project-source retrieval
current public fact         -> Brave lookup
explicit web request        -> Brave lookup
multi-source research       -> Brave research
```

High-confidence routing is deterministic; only ambiguous general freshness uses the small Ollama classifier. Current-year public-result questions are treated as current. A coincidental project symbol hit is not enough to hijack an unrelated public question.

Examples:

```bash
pgpt validate "What is dependency injection?"
pgpt validate "Who won the 2026 NBA championship?"
pgpt validate "Explain your own source code and routing."
pgpt validate "Look up this npm error on the web and explain the likely cause."
```

For Brave, create `~/.config/pgpt/secrets.env` containing:

```text
PGPT_BRAVE_API_KEY=...
```

Then check:

```bash
pgpt web-usage
```

### Brave quota behavior

Brave reports both short rate-limit windows and a monthly plan window. A Brave monthly limit of **`0` means unlimited**; pgpt therefore does not treat `limit=0, remaining=0` as an exhausted API plan.

`monthly_request_budget` in `config.json` is a separate pgpt safety budget. The default is 500 requests/month even when the Brave plan itself is unlimited. The browser badge shows that local safety budget and marks an unlimited Brave API plan as `API ∞`.

An automatically chosen web route may degrade gracefully when offline and explicitly tells the model that live evidence was unavailable. A forced lookup/research or natural-language explicit web request instead returns a clear error if retrieval fails; it does not guess a current answer from local memory.

## Projects and direct source retrieval

Normal code/project questions read the selected source tree directly. They do **not** require PrivateGPT or a vector index.

```bash
pgpt ask --project pgpt-cli \
  "Explain how resolve_route works."

pgpt ask --project vibemaster \
  "Explain the YouTube metadata handling in this project."
```

The built-in historical fixture remains available to tests as `pgpt-cli-history`. It gives the repository a self-contained project-retrieval target without depending on your private machine data.

## Add any knowledge folder

For durable RAG ingestion, PrivateGPT must be installed in `~/ai/private-gpt` and its configured dependencies must be available.

The browser's **Add knowledge folder** action and the CLI command below use the same safe ingestion path:

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

1. validates the project name before launching an expensive ingestion job;
2. validates that the path is a readable directory;
3. rejects filesystem/home roots, PrivateGPT runtime data, and common credentials directories;
4. automatically excludes nested `.ssh`, `.gnupg`, `.aws`, `.env`, `.env.*`, `*.pem`, and `*.key` entries from the ingestion set;
5. invokes PrivateGPT's existing `scripts/ingest_folder.py` without shell interpolation;
6. never copies the folder into the `private-gpt` Git repository;
7. registers the project in `~/.config/pgpt/projects.json` only after successful ingestion.

### Zero-byte source cleanup

PrivateGPT's `--ignored` argument is basename-based. A naive zero-byte workaround can therefore drop a valid file when an empty file elsewhere has the same basename.

pgpt now handles that collision safely for one-shot ingestion:

```text
source/
├── old/example.md        0 bytes
└── current/example.md    valid content
```

Instead of ignoring every `example.md`, pgpt builds a temporary filtered staging tree, removes only the zero-byte path from that temporary copy, ingests the valid file, then deletes the staging tree. The original source directory is never modified.

When there is no basename collision, pgpt keeps the faster direct-ingestion path and simply adds the zero-byte basenames to PrivateGPT's ignore list.

`--watch` cannot use a temporary snapshot because later source changes would not be mirrored into it. In the rare case where watched ingestion sees a zero-byte basename collision, pgpt prints an explicit warning and retains PrivateGPT's basename behavior.

## Existing project sync / ingestion

The older project-oriented maintenance commands remain:

```bash
# create/update the optional sanitized pgpt-cli snapshot
pgpt sync --project pgpt-cli

# ingest that project through PrivateGPT
pgpt ingest --project pgpt-cli

# direct VibeMaster folder: sync is intentionally a no-op
pgpt sync --project vibemaster
pgpt ingest --project vibemaster

# optional watched ingestion
pgpt ingest --project pgpt-cli --watch
```

PrivateGPT is optional for normal chat, direct project retrieval, Brave, and skills. It is required only for explicit ingestion/RAG maintenance.

```text
pgpt server   -> pgpt browser/API, normal everyday workflow
pgpt serve    -> PrivateGPT server, optional RAG/compatibility workflow
```

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

Skills are intentionally plain files with a small, inspectable contract. The repository does not yet grant a model unrestricted filesystem/process tools.

## Harness-inspired design choices

Agent harnesses are useful design references, but `pgpt-cli` intentionally remains a simple local chat application rather than pretending to be an unrestricted autonomous coding agent.

Adopted ideas:

- **Capability boundaries:** model, web, project context, skills, sessions, and storage remain separate modules/configuration surfaces.
- **Provider-style settings:** the UI shows local model and Brave capabilities independently instead of hiding everything behind Auto.
- **Traceability:** observable routing, model selection, status events, and timing are inspectable per response.
- **Clean conversation surface:** advanced controls live in Settings.
- **Session-level choice:** manual model/web/project/context choices apply to the request without changing the routing architecture.
- **Tool boundary for future agents:** an eventual process/filesystem tool layer can be added behind explicit permission controls instead of being implicit in normal chat.

Not adopted today: subagents, model-generated unrestricted tool orchestration, dynamic runtime plugin loading, or exposing private model reasoning.

## Long responses

Output budgets are larger than before. When Ollama ends with `done_reason=length`, pgpt can make bounded continuations and hides the internal continuation instruction. For large plans/analyses choose **Answer length → Long**. Use **Full recent** or **Deep** only when extra context is actually useful.

## VS Code / WSL

`pgpt server` exposes an OpenAI-compatible endpoint:

```text
http://127.0.0.1:8765/v1
```

Use the example Continue configuration in:

```text
docs/continue-config.yaml
```

and the focused setup notes in:

```text
docs/VS_CODE.md
```

The intended path is:

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

CI runs the suite on Python 3.11 and 3.13, validates browser JavaScript, and enforces the one-remote-branch rule. Coverage includes the 100+ routing policy dataset, current-year routing, smart history, model overrides, forced-web semantics, Brave unlimited-quota handling, continuation behavior, project retrieval, knowledge-ingest safety, zero-byte basename-collision handling, run-details UI, and browser controls.

The real local-router acceptance suite is opt-in because GitHub CI has no Ollama daemon:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
python -m unittest tests.test_router_acceptance_local -v
```

See `docs/TESTING.md` for manual release scenarios and the hardware/service-dependent acceptance checks.
