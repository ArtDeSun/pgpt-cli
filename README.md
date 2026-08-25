# pgpt-cli

`pgpt-cli` is a local-first ChatGPT-style assistant for Linux and WSL2. Ollama generates answers, direct source retrieval handles registered code/project contexts, Brave supplies current public information and research, and PrivateGPT is an optional durable RAG/indexing layer.

The operating rule is: **Auto should normally work, but user context, PrivateGPT runtime state, browser chat history, and internal pgpt test projects must remain separate.**

## Quick start (Linux or WSL2)

The core browser and CLI require:

- Git.
- Python 3.11 or newer, including the `venv` module.
- [Ollama](https://ollama.com/download), running where this shell can reach `http://127.0.0.1:11434`.

PrivateGPT, `uv`, and Brave Search are optional. They are not required for local chat or direct retrieval from registered folders.

On Ubuntu or Debian, the base packages can be installed with:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv curl
curl -fsSL https://ollama.com/install.sh | sh
```

Use the equivalent packages on another Linux distribution. Confirm that `ollama list` works from the same shell in which pgpt will run. If the Ollama service is not started automatically, run `ollama serve` in a separate terminal.

### Fresh install

The default optional PrivateGPT paths use `$HOME/ai`, so this is the simplest layout. The pgpt-cli checkout itself can live elsewhere.

```bash
mkdir -p "$HOME/ai"
git clone https://github.com/ArtDeSun/pgpt-cli.git "$HOME/ai/pgpt-cli"
cd "$HOME/ai/pgpt-cli"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install the recommended local models:

```bash
ollama pull qwen3:1.7b
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
```

Verify the installation and start the browser/API:

```bash
pgpt status
pgpt models
pgpt server
```

Open `http://127.0.0.1:8765/`. `pgpt status` may report the optional PrivateGPT API and source as unavailable; that does not block normal pgpt use. Stop the browser server with `Ctrl+C`.

### Update an existing checkout

```bash
cd /path/to/pgpt-cli
git switch main
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e .

pgpt status
pgpt models
```

If `.venv` does not exist, create it with `python3 -m venv .venv` first. User contexts, chats, responses, personal skills, and secrets are not replaced by these commands.

### Non-default locations

The repository may be cloned anywhere. Relative `chats`, `responses`, and `state` paths resolve inside that checkout. Optional PrivateGPT defaults to `~/ai/private-gpt` for source and `~/ai/private-gpt-data` for generated state; change the corresponding values under `paths` in `config.json` if you intentionally use a different layout. User-owned paths use `~` or absolute paths, never a hard-coded username.

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

## Optional PrivateGPT source checkout

Keep `~/ai/private-gpt` as a clean source checkout rather than storing machine-specific model, web, project, or index state inside it. `pgpt-cli` supplies its PrivateGPT integration settings through environment variables and keeps generated state under `~/ai/private-gpt-data`.

For a first install, clone the current upstream source without adding machine-specific files to it:

```bash
mkdir -p "$HOME/ai"
git clone https://github.com/zylon-ai/private-gpt.git "$HOME/ai/private-gpt"
```

For an existing clean checkout, inspect it before updating:

```bash
git -C "$HOME/ai/private-gpt" status --short
git -C "$HOME/ai/private-gpt" pull --ff-only
```

Do not delete or overwrite a checkout with uncommitted work. Move it aside or preserve its changes before creating a clean replacement.

If `ArtDeSun/private-gpt` is intentionally kept synchronized with upstream, it can be used instead. The important requirement is that `~/ai/private-gpt` is a clean current checkout; do not copy machine-specific `settings-model.yaml`, `settings-web.yaml`, Qdrant data, or old `local_data` directories into it.

`pgpt-cli` deliberately does not use PrivateGPT's local source tree as a project registry and does not depend on PrivateGPT's built-in web search for normal pgpt web requests. Ollama and Brave remain controlled by pgpt itself.

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

## After a successful `pgpt ingest`

After a command such as `pgpt ingest --project test-notes` finishes, the indexed copy is ready. For the normal pgpt browser, run:

```bash
cd "$HOME/ai/pgpt-cli"
source .venv/bin/activate

pgpt status
pgpt models
pgpt server
```

Open `http://127.0.0.1:8765/`, then select **Settings → Project routing → Force project → test-notes**. Ask:

```text
Summarize the most distinctive facts in this project and cite the source filenames.
```

Expand **Run details** on the answer. It should report `test-notes` as the project and show retrieval/generation activity. The normal pgpt browser retrieves directly from the registered source folder; it does not need the PrivateGPT server or vector index.

To test the indexed copy separately, leave ingestion stopped and run this in another terminal:

```bash
cd "$HOME/ai/pgpt-cli"
source .venv/bin/activate
pgpt serve
```

Open `http://127.0.0.1:8080/ui`. In the Workbench, set the active document collection to `test-notes` when that setting is shown, enable **Documents** for the chat, and ask about a unique sentence from the notes. Stop this server with `Ctrl+C` before running another `pgpt ingest` or `pgpt knowledge-add` command. `pgpt server` on port 8765 may remain running.

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

## End-user browser acceptance checklist

Complete this checklist after installation or a release update. Unless a step says otherwise, keep `pgpt server` running and use `http://127.0.0.1:8765/`.

### 1. Prepare harmless test files

```bash
mkdir -p "$HOME/pgpt-ui-test/context"
printf 'Project codename: AURORA-731.\nOwner: local acceptance test.\n' \
  > "$HOME/pgpt-ui-test/context/facts.txt"
printf 'def ui_test_value():\n    return 731\n' \
  > "$HOME/pgpt-ui-test/context/example.py"
```

Use only small text/code attachments; the browser accepts multiple files smaller than 250 KiB each.

### 2. Startup and capability reporting

1. Open **Settings**.
2. Confirm **Ollama models** lists the same installed model IDs as `pgpt models`.
3. Confirm **Project context** accurately reports the current registry. If `test-notes` is already registered, confirm it is available when **Force project** is selected.
4. Confirm the context note shows `~/.config/pgpt/projects.json` as the registry and labels the PrivateGPT runtime as **not a context source**.
5. Confirm **Skills** reports the available skills. Brave may correctly show Offline until its optional API key is configured.

### 3. Add context folder UI

This test adds a persistent registry entry. First print the exact portable path to paste:

```bash
realpath "$HOME/pgpt-ui-test/context"
```

In **Settings → Add knowledge folder**, enter:

```text
Name: ui-smoke-context
Absolute folder path: paste the realpath output
Collection: ui-smoke-context
```

First click **Cancel** and confirm the dialog closes. Reopen it, enter a nonexistent absolute folder, and confirm **Add context** shows an error without closing the dialog. Then enter the valid values above, leave **Index in PrivateGPT after registering** unchecked, and click **Add context**. Confirm registration succeeds and `ui-smoke-context` appears under **Force project**. Ask with that project forced:

```text
What project codename and Python return value are recorded in this context? Cite both filenames.
```

The answer should contain `AURORA-731`, `731`, `facts.txt`, and `example.py`. The entry remains in `~/.config/pgpt/projects.json`; keep it as a reusable smoke-test context or remove that exact entry manually after testing.

To exercise the optional checkbox too, make sure `pgpt serve` is stopped, reopen the dialog with the same valid values, check **Index in PrivateGPT after registering**, and submit. With the optional PrivateGPT prerequisites installed, the status should progress from registration to indexing and finish with **Registered and indexed ui-smoke-context**.

### 4. Composer, streaming, Markdown, and Stop

Create a new chat and paste this prompt:

```text
Respond with an H2 heading, a three-item numbered list, one bold phrase, one inline-code token, one HTTPS Markdown link, and one fenced Python code block.
```

Confirm:

- `Shift+Enter` inserts a newline and `Enter` sends.
- The activity changes among Thinking, Retrieving, Analyzing, Working, or Reviewing as applicable.
- The answer streams incrementally and the Send button becomes Stop while work is active.
- The heading, list, bold text, inline code, link, and fenced block render as formatted content rather than raw Markdown.
- **Copy** on the code block places the code on the clipboard.
- **Run details** contains Execution, Source, Task, Model, Web, Project, Context, Length, Reason, timing, and status events where applicable.

Then send:

```text
Write a detailed 50-step guide to designing a local AI assistant. Number every step.
```

Click **Stop** while it is generating. Confirm generation stops, the button returns to Send, and a new prompt can still be submitted.

### 5. Follow-up actions

Under a completed answer, click **Explain more**, **Example**, and **Next step** one at a time. Each button should place its prompt in the composer; send at least one and confirm it becomes a normal follow-up answer.

### 6. Attachments

1. Click **＋** and select both `facts.txt` and `example.py` from `$HOME/pgpt-ui-test/context`.
2. Confirm both filename chips appear.
3. Click one chip to remove it, then attach that file again.
4. Send:

```text
From the attached files only, give the project codename, the function name, its return value, and the source filename for each fact.
```

The answer should report `AURORA-731`, `ui_test_value`, `731`, `facts.txt`, and `example.py`.

### 7. Chat management and persistence

1. Confirm the first prompt automatically replaced **New chat** with a title derived from the prompt.
2. Create a second chat, send `Reply only with SECOND CHAT`, and switch between both chats.
3. Search for part of a chat title and confirm the list filters.
4. Pin and unpin a chat; confirm it moves between **Pinned** and **Recents**.
5. Delete the expendable second chat and confirm the other chat remains.
6. Wait a few seconds, reload the browser, stop `pgpt server` with `Ctrl+C`, restart it, and reload again. Chats, messages, pins, and the active chat should remain.
7. Optionally confirm the disk state exists:

   ```bash
   test -s chats/browser-state.json \
     && echo 'browser history saved'
   ```

### 8. Export and saved responses

1. Click **Export chat** and confirm a readable `chat.md` downloads with user and assistant sections.
2. Open **Saved responses** using the `▤` button and click **Refresh**.
3. Open a generated response, confirm its Markdown renders, click **Download Markdown**, then use **Back**.

### 9. Project routing

Use a new chat for each case so earlier messages do not affect the result.

1. Set **Project routing = Off** and **Web = Off**, then ask:

   ```text
   What is dependency injection? Answer in two sentences.
   ```

   **Run details** should show no selected project and local web-off execution.

2. Set **Project routing = Auto**, then ask:

   ```text
   Using the registered ui-smoke-context project, report its codename and Python return value and cite the source filenames.
   ```

   The explicit registered name should select `ui-smoke-context`.

3. Set **Project routing = Force project**, select **ui-smoke-context**, and ask:

   ```text
   Find one exact, distinctive fact in this project, explain it briefly, and cite its source filename.
   ```

   The Project selector should be enabled only in Force mode, and **Run details** should report `ui-smoke-context`.

### 10. Model, task, context, length, skill, and reasoning controls

Select an installed model explicitly, set **Task = Explain code**, **Chat context = Off**, **Answer length = Short**, **Skill = Off**, and **Reasoning = Normal**. Send:

```text
Explain this expression in at most four bullets: sorted(items, key=lambda x: x.name)
```

Confirm the selected Model, Explain code task, Off context, and Short length appear in **Run details**, and the answer is short. Then:

1. Change **Answer length** to Long and request `Give a detailed architecture discussion of that sorting operation.` Confirm **Run details** shows Long and no internal continuation instructions appear.
2. Set **Chat context = Smart**, send `Remember this token: ORBIT-9462. Reply only with STORED.`, then ask `What token did I ask you to remember?` The reply should contain `ORBIT-9462`.
3. Set **Chat context = Off** and ask the token question again. The answer should not rely on earlier chat messages.
4. Set **Chat context = Full recent** and confirm a follow-up can use the recent conversation.
5. Select each available **Skill** once and send a prompt appropriate to its name; the request should complete using that skill. Return Skill to Off afterward.
6. Run one request with **Reasoning = Deep** and one with **Reasoning = Normal**. Both should complete, while the selected model/task/project overrides remain authoritative.

### 11. Brave web modes (optional)

Create `~/.config/pgpt/secrets.env` with your key and restrict its permissions:

```bash
mkdir -p "$HOME/.config/pgpt"
test -e "$HOME/.config/pgpt/secrets.env" \
  || install -m 600 secrets.env.example "$HOME/.config/pgpt/secrets.env"
nano "$HOME/.config/pgpt/secrets.env"
pgpt web-usage
```

Set `PGPT_BRAVE_API_KEY=...` in that file. In the UI:

1. Set **Web = Off** and ask `What is dependency injection?` Run details should stay local.
2. Set **Web = Force lookup** and ask `What is the latest stable Python release? Include source links.` Expect a current sourced answer and lookup metadata.
3. Set **Web = Force research** and ask `Compare the latest stable Python and Node.js releases using at least two sources, including release dates.` Expect a multi-source answer and research metadata.
4. Return **Web** to Auto and confirm the Brave badge/Capabilities card updates its usage count.

Without a valid key or connectivity, forced lookup/research must show a clear retrieval error rather than an unsourced current-information guess.

### 12. Optional PrivateGPT indexed-copy check

For a project already ingested through PrivateGPT (for example, `test-notes`), stop any ingestion process, start `pgpt serve`, and open `http://127.0.0.1:8080/ui`. Set the active document collection to that project when the setting is shown, enable **Documents** for the chat, and ask about a unique fact from the source. Confirm the answer is grounded in that collection. Stop `pgpt serve` before any later re-ingest.

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

pgpt resolves an untagged configured embedding model such as `mxbai-embed-large` to Ollama's exact installed ID, such as `mxbai-embed-large:latest`, before starting PrivateGPT.

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) if it is not already available, then install the required interpreter and embedding model:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
uv python install 3.11
ollama pull mxbai-embed-large
```

Open a new shell if the installer reports that `uv` was added to `PATH` but `uv --version` is not yet found.

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
