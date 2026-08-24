# pgpt-cli

`pgpt-cli` is a local-first ChatGPT-style assistant for WSL. Ollama generates answers, direct source retrieval handles registered code/project contexts, Brave supplies current public information and research, and PrivateGPT is an optional durable RAG/indexing layer.

The operating rule is: **Auto should normally work, but user context, PrivateGPT runtime state, browser chat history, and internal pgpt test projects must remain separate.**

## Architecture

```text
Terminal: pgpt ask/chat          Browser: http://127.0.0.1:8765
            \                              /
             +--------- pgpt-cli ---------+
                         |
                 routing + context
                   /       |       \
                  /        |        \
      registered source   Brave    skills/history
             folders       web
                  \        |        /
                       Ollama
                         |
                  verify / repair
                         |
                       answer

Optional durable indexing
-------------------------
registered source folder
        -> pgpt PrivateGPT ingest helper
        -> PrivateGPT IngestService
        -> ~/ai/private-gpt-data
```

PrivateGPT runtime directories are **not** project/context directories and are never scanned to populate the project selector.

## Filesystem boundaries

A normal WSL layout is:

```text
~/ai/
├── pgpt-cli/                 # this repository
├── private-gpt/              # clean upstream PrivateGPT source checkout
└── private-gpt-data/         # generated PrivateGPT runtime/vector/env state
```

User-selectable contexts live wherever you choose. Their authoritative registry is:

```text
~/.config/pgpt/projects.json
```

Personal pgpt configuration is:

```text
~/.config/pgpt/
├── projects.json             # authoritative user context registry
├── secrets.env
└── skills/
```

Browser/session data and generated responses are local runtime files under the pgpt-cli checkout:

```text
~/ai/pgpt-cli/
├── chats/
│   └── browser-state.json    # browser chat list, messages, pins, active chat
├── responses/
│   └── *.md                  # generated response artifacts
└── state/                    # small CLI/runtime state
```

`chats/`, `responses/`, and `state/` are gitignored. Pulling new code does not overwrite them.

PrivateGPT-generated state is kept under:

```text
~/ai/private-gpt-data/
├── venv/
├── private_gpt/
├── qdrant/
└── volumes/
```

`private-gpt-data` is disposable generated state. If it is deleted, pgpt recreates the runtime directories automatically the next time PrivateGPT indexing or serving is used. Deleting it removes existing PrivateGPT indexes, but it does **not** remove registered context folders from `~/.config/pgpt/projects.json` or browser chats from `~/ai/pgpt-cli/chats/browser-state.json`.

An older installation may also contain:

```text
~/ai/private-gpt-data/local_data/private_gpt/
```

That is legacy runtime/index state. pgpt reports it when present but ignores it for context discovery. Do not use either `private-gpt-data/private_gpt` or `private-gpt-data/local_data/private_gpt` as context sources.

## PrivateGPT source checkout

Keep `~/ai/private-gpt` as a clean source checkout rather than storing machine-specific model, web, project, or index state inside it. `pgpt-cli` supplies its PrivateGPT integration settings through environment variables and keeps generated state under `~/ai/private-gpt-data`.

The recommended canonical source is upstream:

```bash
cd ~/ai
rm -rf private-gpt
git clone https://github.com/zylon-ai/private-gpt.git private-gpt
```

If `ArtDeSun/private-gpt` is intentionally kept synchronized with upstream, it can be used instead. The important requirement is that `~/ai/private-gpt` is a clean current checkout; do not copy machine-specific `settings-model.yaml`, `settings-web.yaml`, Qdrant data, or old `local_data` directories into it.

`pgpt-cli` deliberately does not use PrivateGPT's local source tree as a project registry and does not depend on PrivateGPT's built-in web search for normal pgpt web requests. Ollama and Brave remain controlled by pgpt itself.

## Pull and install

```bash
cd ~/ai/pgpt-cli
git switch main
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e .

pgpt status
pgpt models
```

Recommended local models:

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

## Register context folders

Direct project retrieval does not require PrivateGPT. Register a real source folder with:

```bash
pgpt context-add /absolute/path/to/project \
  --name my-project
```

This writes the context entry to `~/.config/pgpt/projects.json`. The source folder remains in place; pgpt does not copy it into `private-gpt-data`.

Example registry:

```json
{
  "my-project": {
    "source_dir": "/home/user/ai/my-project",
    "knowledge_dir": "/home/user/ai/my-project",
    "collection": "my-project",
    "sync_excludes": [],
    "ingest_ignored": [],
    "sync_required": false,
    "user_managed": true
  }
}
```

The browser **Project** selector contains only entries from this user registry. Internal `pgpt-cli` fixtures and PrivateGPT storage directories do not appear there.

## Auto project routing

Auto is neutral. An unspecified request no longer silently defaults to the `pgpt-cli` repository.

Automatic context selection considers only registered user contexts and requires an unambiguous match:

```text
explicit registered context name   -> that context
unique matching code symbol         -> that context
"my project" + exactly one context -> that context
ambiguous/no match                  -> no project context
```

For a manual override:

```bash
pgpt ask --project my-project --context \
  "Explain how renderCard works."
```

In the browser, **Force project** makes the selected project authoritative. Auto and Off do not treat the visible dropdown value as an implicit project choice.

Validate routing without generating an answer:

```bash
pgpt validate --web off "What is dependency injection?"
pgpt validate --web off "Explain renderCard in my project."
```

The validation JSON includes `selected_project` so the source choice is visible.

## Browser

Start the pgpt browser/API:

```bash
pgpt server
```

Open:

```text
http://127.0.0.1:8765/
```

The browser includes multiple chats, pinned/recents/search, attachments, saved responses, Markdown/code rendering, streaming, execution status, stop-generation, follow-up actions, and route/model metadata.

### Persistent chat history

Browser history is disk-backed. The UI still keeps a browser-local cache for responsiveness, but `pgpt server` synchronizes the complete chat state to:

```text
~/ai/pgpt-cli/chats/browser-state.json
```

On startup, the server-backed state is restored into the UI. If this release finds older browser-local history but no disk state yet, that history is migrated to the disk-backed state automatically. Closing/reopening the browser or restarting `pgpt server` therefore should not erase chats.

The Markdown files in `responses/` are answer artifacts; they are **not** the authoritative chat/session history. The complete browser conversation list is `chats/browser-state.json`.

### Settings

| Control | Options | Effect |
| --- | --- | --- |
| Project routing | Auto / Off / Force project | Auto may select one registered context; Off prevents project retrieval; Force uses the selected context. |
| Project | registered user context | User registry only; internal/runtime folders are excluded. |
| Web | Auto / Off / Force lookup / Force research | Forced web never silently falls back to an ungrounded current-information guess. |
| Model | Auto / installed Ollama model | Explicit model wins. |
| Task | Auto / General / Explain code / Debug / Implement / Architecture / Research | Overrides task/template routing. |
| Chat context | Smart / Full recent / Off | Controls conversation history supplied to the model. |
| Answer length | Auto / Short / Standard / Long | Controls output budget. |
| Skill | Off / selected skill | Applies a task instruction manual. |
| Reasoning | Auto / Deep / Normal | Controls the larger context mode. |

The API metadata also reports the authoritative registry path, PrivateGPT runtime root, registered source paths, source existence, and any detected legacy PrivateGPT runtime tree.

### Run details

Each assistant response has a collapsed **Run details** inspector containing observable execution facts: route/source/task, selected model, web/project selection, status events, and timing. It does not expose hidden chain-of-thought.

## Routing and web behavior

With controls on Auto:

```text
stable/general question       -> local Ollama
unambiguous project evidence  -> direct registered-source retrieval
current public fact           -> Brave lookup
explicit web request          -> Brave lookup
multi-source research         -> Brave research
```

For Brave, create `~/.config/pgpt/secrets.env` with:

```text
PGPT_BRAVE_API_KEY=...
```

Then check:

```bash
pgpt web-usage
```

A forced lookup/research or natural-language explicit web request returns a retrieval error instead of silently guessing when live retrieval is unavailable.

## Optional PrivateGPT indexing

PrivateGPT is optional for normal source-aware chat. Use it when you specifically want durable RAG/indexed knowledge.

Current PrivateGPT requires Python 3.11. pgpt invokes the source checkout through `uv` with Python 3.11 and the upstream `core` extra. The integration supports PrivateGPT's current `get_injector()` API while retaining compatibility with older `get_global_injector()` checkouts.

```bash
uv python install 3.11
ollama pull mxbai-embed-large
```

Register and index a folder through PrivateGPT with:

```bash
pgpt knowledge-add /absolute/path/to/notes \
  --name notes \
  --collection notes
```

`knowledge-add` validates the folder, rejects system/home/runtime/credential roots, protects sensitive files, skips generated dependency/build/cache directories and nested `private-gpt-data`, uses a collection-aware pgpt helper, preserves path-aware artifact IDs, and registers the user context only after successful ingestion.

For direct retrieval without indexing, use `context-add` instead.

If `private-gpt-data` was deleted while contexts remain registered, recreate only the indexes you actually need:

```bash
pgpt ingest --project my-project
```

Do not recreate old runtime folders manually.

### Local Qdrant sequencing

With the default file-backed Qdrant configuration, do not run `pgpt knowledge-add` or `pgpt ingest` concurrently with `pgpt serve`.

```text
1. Stop pgpt serve if it is running.
2. Run pgpt knowledge-add ... or pgpt ingest ...
3. Wait for ingestion to finish.
4. Start pgpt serve when you need PrivateGPT.
```

The normal browser server, `pgpt server`, is independent from this Qdrant conflict.

```text
pgpt server   -> pgpt browser/API; normal workflow
pgpt serve    -> PrivateGPT server; optional RAG/compatibility workflow
```

## Existing internal projects

The repository keeps hidden internal project entries for pgpt maintenance/evaluation, including `pgpt-cli` and the historical test fixture. They remain available when explicitly requested by development tooling, but they are not user-selectable browser contexts and are not candidates for Auto user-project selection.

For example, repository development can still explicitly run:

```bash
pgpt ask --project pgpt-cli --context \
  "Explain resolve_route."
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

## VS Code / WSL

`pgpt server` exposes an OpenAI-compatible endpoint:

```text
http://127.0.0.1:8765/v1
```

See `docs/continue-config.yaml` and `docs/VS_CODE.md`.

## Tests

Offline release gate:

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

CI runs on Python 3.11 and 3.13, validates both browser JavaScript files, enforces the one-remote-branch rule, and runs the full offline unit suite.

The real local-router acceptance suite remains opt-in because GitHub-hosted CI has no Ollama daemon:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
python -m unittest tests.test_router_acceptance_local -v
```

See `docs/TESTING.md` for hardware/service-dependent release checks.
