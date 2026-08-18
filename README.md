# pgpt-cli

`pgpt-cli` is a local-first personal AI assistant for WSL development. It sits in front of local Ollama models and adds routing, project-source retrieval, optional Brave web lookup/research, persistent chats, reusable skills, response verification, a browser UI, and an OpenAI-compatible endpoint for VS Code clients.

```text
VS Code / browser / terminal
            |
            v
        pgpt-cli
            |
     routing + policy
      /      |      \
     /       |       \
 local    project     web
Ollama    source      Brave
     \       |       /
      \      |      /
       prompt + context
              |
              v
            Ollama
              |
              v
       verify / repair
              |
              v
            answer
```

## Quick mental model

```text
~/ai/pgpt-cli/
    application checkout
    Git-managed source, prompts, tests and built-in skills

~/.config/pgpt/skills/
    your personal skills
    normal place to create/edit skill Markdown
    outside the repository

~/ai/private-gpt/
    optional PrivateGPT checkout
    used only by pgpt sync/ingest/serve compatibility workflow

~/ai/private-gpt-data/
    optional PrivateGPT data/model home

pgpt server
    pgpt browser UI + OpenAI-compatible API

pgpt serve
    PrivateGPT compatibility server
```

Your current directory layout is already appropriate:

```text
~/ai/
├── pgpt-cli/
├── private-gpt/
├── private-gpt-data/
└── vibemaster-knowledge/
```

**You do not need to move or rename these directories.** The default `config.json` paths are designed for this arrangement.

## 1. Install / update in WSL

```bash
cd ~/ai/pgpt-cli
git pull

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

If `.venv` already exists, activate it and rerun the editable install after a pull.

Check the local services/models:

```bash
ollama list
pgpt status
pgpt models
```

## 2. Basic use

```bash
pgpt validate "What is dependency injection?"
pgpt ask "What is dependency injection?"
```

Project-grounded request:

```bash
pgpt ask \
  --project pgpt-cli \
  --context \
  "Explain how select_model works."
```

Reproducible historical project fixture:

```bash
pgpt ask \
  --project pgpt-cli-history \
  --context \
  "Explain how select_model works in the historical pgpt-cli project."
```

`pgpt-cli-history` points at `tests/fixtures/historical_pgpt/`, so project retrieval tests do not depend on your private external files.

## 3. Online vs offline chatbot usage

The `--web` control is the main switch:

```text
--web auto
    recommended default
    local/stable questions stay local
    current/live questions can use Brave when needed

--web off
    force local-only behavior
    no Brave search request is made

--web lookup
    force a focused web lookup

--web research
    force multi-source web research
```

Examples:

```bash
# Fully local even if Wi-Fi is available
pgpt ask --web off "Explain dependency injection."

# Automatic routing
pgpt ask --web auto "What's the weather in Toronto today?"

# Explicit live lookup
pgpt ask --web lookup "What's the weather in Toronto today?"

# Multi-source research
pgpt ask --web research \
  "Compare current AI privacy approaches from several independent sources."
```

Inside `pgpt chat`:

```text
/web auto
/web off
/web lookup
/web research
```

The browser UI has the same `auto`, `off · local-only`, `lookup`, and `research` choices.

### What happens without Wi-Fi?

With `auto`, pgpt checks connectivity only when the selected route actually needs the web. If Brave cannot be reached, the pipeline falls back to local generation and explicitly marks the web context as unavailable rather than pretending it has live data.

For predictable offline use, select `off`:

```bash
pgpt ask --web off "your prompt"
```

### Fast live lookups

Common live surfaces such as weather, time, opening hours, current scores, prices/rates, and transport status use a deterministic fast routing path. Focused web lookup uses Brave snippets without fetching full result pages by default; deeper page fetching remains reserved for research. This avoids spending several local-model routing passes and several page downloads on a simple question such as today's weather.

## 4. Brave API key and usage budget

Keep the real key outside the repository:

```bash
mkdir -p ~/.config/pgpt
cp secrets.env.example ~/.config/pgpt/secrets.env
chmod 600 ~/.config/pgpt/secrets.env
nano ~/.config/pgpt/secrets.env
```

Add:

```text
PGPT_BRAVE_API_KEY=your_real_key
```

`config.json` contains a local safety budget:

```json
"monthly_request_budget": 500
```

This is a **pgpt safety cap**, not a claim about the quota of your Brave subscription. Change it if your plan differs.

Inspect usage:

```bash
pgpt web-usage
```

The browser UI also shows a Brave usage badge. pgpt stores its local count in:

```text
state/brave_usage.json
```

That file is runtime state and should remain untracked. When Brave returns rate-limit headers, pgpt also records the API-reported monthly limit/remaining values and uses the stricter effective count. A search is blocked when the configured safety budget is exhausted or the API reports no remaining monthly requests.

## 5. Persistent terminal chat

```bash
pgpt chat-new "pgpt development"
pgpt chat
```

Useful commands:

```text
/web auto|on|off|lookup|research
/context auto|on|off
/deep auto|on|off
/skill NAME
/skill off
/new TITLE
/exit
```

Terminal chats are stored locally and are ignored by Git.

## 6. Skills: built-in vs personal

There are two intentionally separate skill locations:

| Location | Purpose | Normal owner | Git-managed? |
|---|---|---|---|
| `~/ai/pgpt-cli/skills/` | Built-in skills shipped with pgpt-cli | Application development | Yes |
| `~/.config/pgpt/skills/` | Your personal/local skills | You | No |

For normal skill management, use:

```bash
pgpt skill-new my-review
nano ~/.config/pgpt/skills/my-review.md
pgpt skills
```

Use a skill:

```bash
pgpt ask --skill my-review "Review this architecture."
```

If the same skill name exists in both locations, the personal file under `~/.config/pgpt/skills/` overrides the built-in version.

Only edit `~/ai/pgpt-cli/skills/` when you intentionally want to change a built-in skill and commit that change to pgpt-cli.

## 7. Browser GUI

Start:

```bash
pgpt server
```

Open:

```text
http://127.0.0.1:8765/
```

The browser UI provides:

- multiple chats with **Recents**, **Pinned**, search and delete;
- per-message time stamps and date separators;
- a visible elapsed timer while a prompt is running;
- project, web mode, skill and deep-mode controls;
- rendered Markdown headings/lists/inline code/code blocks rather than exposing raw `##` or backtick syntax;
- clickable web links and copy buttons for source-code blocks;
- follow-up suggestion chips after responses;
- text/code file attachment and attachment download;
- chat export;
- browsing, rendering and downloading Markdown files from `responses/`;
- Brave usage/online status.

Text/code attachment limits are intentionally bounded (250 KB per file, 750 KB total per request). The current endpoint is text-only; binary images/PDFs are not silently passed to a non-multimodal Ollama model.

Saved response Markdown also includes a creation timestamp and a clickable **Rendered view** URL so it can be opened through the browser renderer.

### Local API

```text
GET  /health
GET  /api/meta
GET  /api/web-usage
GET  /api/responses
GET  /api/responses/<name>
GET  /api/responses/<name>/download
GET  /v1/models
POST /v1/chat/completions
```

The server binds to loopback by default. A non-loopback bind is refused unless `--allow-remote` is explicitly supplied.

## 8. VS Code / Continue in WSL

```text
VS Code Remote - WSL
        |
        v
Continue
        |
        v
http://127.0.0.1:8765/v1
        |
        v
pgpt routing / retrieval / skills / verification
        |
        v
local Ollama models
```

Start `pgpt server` in WSL, then merge `docs/continue-config.yaml` into Continue's configuration. See [docs/VS_CODE.md](docs/VS_CODE.md).

Point Continue at **pgpt**, not directly at Ollama, if you want pgpt's routing, project retrieval, optional web retrieval, skills and quality layer.

## 9. What requires PrivateGPT?

### PrivateGPT is **not required** for the normal pgpt experience

These paths use pgpt directly and do not require the `~/ai/private-gpt` process:

```text
pgpt ask
pgpt validate
pgpt chat
pgpt server
browser UI
VS Code / Continue -> pgpt /v1
project source retrieval from configured source_dir
Brave web lookup/research
skills
runtime verification/repair
```

Normal project retrieval reads the configured source tree directly. For example, `--project pgpt-cli` reads the current pgpt-cli checkout; `--project pgpt-cli-history` reads the tracked historical fixture.

### PrivateGPT **is used only for the compatibility / RAG maintenance workflow**

The following commands depend on your separate PrivateGPT checkout/data directories:

```text
pgpt sync
pgpt ingest
pgpt serve
```

Flow:

```text
project source
    |
    | pgpt sync
    v
project knowledge directory
    |
    | pgpt ingest
    v
PrivateGPT local data/index
    |
    | pgpt serve
    v
PrivateGPT API on 127.0.0.1:8080
```

Manage it with your current directory structure:

```bash
# Check Ollama, pgpt API and PrivateGPT reachability
pgpt status

# Copy a configured project's files into its knowledge directory
pgpt sync --project pgpt-cli

# Run PrivateGPT's ingestion script against that knowledge directory
pgpt ingest --project pgpt-cli

# Optional watched ingestion
pgpt ingest --project pgpt-cli --watch

# Start the PrivateGPT compatibility server
pgpt serve
```

The defaults expect:

```text
~/ai/private-gpt/       PrivateGPT source checkout
~/ai/private-gpt-data/  PGPT_HOME / PrivateGPT data
```

Those paths match your current setup, so **no directory restructuring is necessary**.

Do not confuse:

```text
pgpt server   -> pgpt browser + OpenAI-compatible API (normal workflow)
pgpt serve    -> PrivateGPT compatibility server (optional RAG workflow)
```

## 10. Routing and latency

Routing intentionally separates semantic meaning from execution policy:

```text
prompt
  |
  +--> high-confidence deterministic fast path
  |       live lookups / research / debug / architecture / writing
  |
  +--> one local semantic classifier when still ambiguous
          task + time_scope
          moving | fixed | unknown
  |
  v
policy + explicit overrides
  |
  +--> local
  +--> project
  +--> web lookup
  +--> web research
```

The semantic model is deliberately not asked to score complexity. Complexity is derived from the classified task and is telemetry only. Common explicit live lookups still skip the classifier entirely.

The router model can be temporarily overridden without changing `config.json`:

```bash
PGPT_ROUTER_MODEL=gemma4:e4b \
  pgpt validate "your prompt"
```

Use `python3 -m tools.benchmark_router_models` to compare installed router models against the same temporal acceptance set before changing the configured default.

## 11. Project retrieval

```text
prompt
  |
  +--> symbol candidates
  |       -> ripgrep definition search
  |       -> bounded source window
  |
  +--> lexical fallback
          -> path/content scoring
          -> bounded source context
```

Exact symbols have priority. If no useful source is found, pgpt uses a project manifest rather than inventing files.

Configured project profiles:

```text
--project pgpt-cli
    current checkout

--project pgpt-cli-history
    tracked historical test fixture

--project vibemaster
    optional external project when its configured path exists
```

## 12. Response quality and follow-ups

Runtime answers pass through deterministic verification and bounded repair. Substantive answers are instructed to end with a small `Next ideas` section containing useful follow-up questions/tasks. The browser renders those suggestions as clickable chips.

The end-to-end semantic judge evaluates one rubric criterion at a time. Required criteria use a `satisfied` boolean; forbidden criteria use a `violated` boolean. This prevents the polarity confusion that can occur when a generic `passed` field is used for both meanings.

## 13. Testing

GitHub Actions runs an offline gate on Python 3.11 and 3.13. It covers:

- packaging/configuration syntax;
- model selection;
- mocked pipeline behavior;
- routing decision vs runtime-route boundaries;
- fast live lookup routing;
- project fixture/retrieval behavior;
- skills;
- HTTP API and CORS;
- Brave usage-budget bookkeeping and HTTP hooks;
- semantic scorer polarity/retries;
- response Markdown metadata;
- browser UI contracts and JavaScript syntax;
- prompt ownership/separation.

Generated routing cases are exploratory diagnostics, not trusted gold labels. Authoritative regressions should be deliberate, high-value cases.

See [docs/TESTING.md](docs/TESTING.md) for exact commands.

Model/GPU/Brave/PrivateGPT-dependent integration tests must still be run on your WSL machine because GitHub-hosted CI does not have your Ollama models, API key, or PrivateGPT installation.

## Repository map

```text
pgpt-cli/
├── pgpt/
│   ├── cli.py
│   ├── config.py
│   ├── server.py
│   ├── skills.py
│   ├── generation/
│   ├── models/
│   ├── output/
│   ├── quality/
│   ├── retrieval/
│   ├── routing/
│   ├── runtime/
│   └── storage/
├── prompts/
├── skills/                       # built-in, Git-managed skills
├── web/
├── docs/
├── tests/
│   └── fixtures/historical_pgpt/
├── evals/
├── tools/
├── .github/workflows/ci.yml
├── config.json
└── pyproject.toml
```

Personal skills deliberately live outside this tree:

```text
~/.config/pgpt/skills/
```

## Local-only data

Keep these untracked:

```text
responses/
state/
chats/
evaluation result files
secrets.env
.env files
private keys
backups/
```

Before publishing changes, review staged content for secrets.
