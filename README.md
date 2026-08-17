# pgpt-cli

`pgpt-cli` is a local-first personal AI assistant for WSL development. It sits in front of local Ollama models and adds request routing, project-source retrieval, optional web research, persistent CLI chats, quality checks, reusable local skills, a small browser chat, and an OpenAI-compatible endpoint that can be used from VS Code.

The goal is a private ChatGPT-like development workflow where the orchestration layer is yours:

```text
VS Code / browser / terminal
            |
            v
      pgpt-cli interface
            |
            v
   semantic + rule routing
      /       |       \
     /        |        \
 local     project      web
 model     retrieval   retrieval
     \        |        /
      \       |       /
       context + prompt
              |
              v
         local Ollama
              |
              v
       verify / repair
              |
              v
            answer
```

## Current state

The repository now has a self-contained local assistant surface rather than being only an evaluation/CLI experiment:

```text
Foundation
  [done] routing and model selection
  [done] project source retrieval
  [done] Brave web lookup/research
  [done] streaming terminal responses and timing
  [done] deterministic verification/repair

Hardening
  [done] prompt ownership moved out of routing Python
  [done] model-selection regression coverage
  [done] end-to-end and reliability harnesses
  [done] criterion-isolated local quality judge
  [done] repository-owned historical project fixture
  [done] offline GitHub Actions gate

Local ChatGPT / IDE surface
  [done] persistent terminal chats
  [done] Markdown skill system
  [done] browser chat UI
  [done] OpenAI-compatible /v1/chat/completions endpoint
  [done] Continue/VS Code configuration example

Optional external integrations
  [kept] PrivateGPT sync / ingest / serve maintenance commands
  [kept] legacy vibemaster profile when that local project exists
```

The local HTTP service intentionally does **not** advertise tool-calling capability. Continue Chat is supported through the OpenAI-compatible endpoint; a future autonomous tool loop should be added only with explicit filesystem/process permissions rather than silently giving a local model unrestricted shell access.

## 1. WSL setup

From your WSL checkout:

```bash
cd ~/ai/pgpt-cli

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -e .
```

Check your local models:

```bash
ollama list
pgpt models
```

`config.json` contains task preferences rather than assuming one model can do every job. Install or change the configured models to match your hardware.

For Brave web retrieval, keep the real key outside the repository:

```bash
mkdir -p ~/.config/pgpt
cp secrets.env.example ~/.config/pgpt/secrets.env
chmod 600 ~/.config/pgpt/secrets.env
nano ~/.config/pgpt/secrets.env
```

The file should contain your local value:

```text
PGPT_BRAVE_API_KEY=...
```

## 2. Basic CLI workflow

Validate routing without generating an answer:

```bash
pgpt validate "What is dependency injection?"
```

Ask normally:

```bash
pgpt ask "What is dependency injection?"
```

Force a project:

```bash
pgpt ask \
  --project pgpt-cli \
  --context \
  "Explain how select_model works."
```

Use the repository-owned historical fixture:

```bash
pgpt ask \
  --project pgpt-cli-history \
  --context \
  "Explain how select_model works in the historical pgpt-cli project."
```

The historical profile points at `tests/fixtures/historical_pgpt`, which is a small source snapshot from commit `bc2343a14db511b4103afdf45e3fa8c81067e12c`. It gives project retrieval and evaluation a reproducible source that does not depend on private data outside the repository.

## 3. Persistent terminal chat

Create a chat:

```bash
pgpt chat-new "pgpt development"
pgpt chat
```

Useful commands inside chat:

```text
/web auto
/web off
/web lookup
/web research
/context auto
/context on
/context off
/deep auto
/deep on
/deep off
/skill code-review
/skill off
/exit
```

Chat JSON and runtime state are local-only and ignored by Git.

## 4. Local skills

Skills are Markdown system instructions. Built-in examples live under `skills/`; personal skills live outside the repository under `~/.config/pgpt/skills/`.

Create one:

```bash
pgpt skill-new my-review
nano ~/.config/pgpt/skills/my-review.md
pgpt skills
```

Use it for one request:

```bash
pgpt ask \
  --skill my-review \
  "Review the project retrieval implementation."
```

A personal skill with the same filename overrides the built-in version. This gives you a small, local skill-management layer without hard-coding natural-language behavior into Python.

## 5. Browser GUI and local API

Start the local service in WSL:

```bash
pgpt server
```

Defaults:

```text
Browser UI: http://127.0.0.1:8765/
API base:   http://127.0.0.1:8765/v1
Health:     http://127.0.0.1:8765/health
```

The browser UI supports project, web mode, deep mode, and skill selection. Conversation messages are kept in browser `localStorage` so a refresh does not immediately erase the local chat.

The server binds only to loopback by default. A non-loopback bind is refused unless `--allow-remote` is explicitly supplied. Browser CORS is limited to loopback origins.

OpenAI-compatible endpoints:

```text
GET  /v1/models
POST /v1/chat/completions
```

Example:

```bash
curl http://127.0.0.1:8765/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "pgpt-cli",
    "messages": [
      {"role": "user", "content": "Explain dependency injection."}
    ]
  }'
```

Optional pgpt controls can be supplied in a top-level `pgpt` object:

```json
{
  "pgpt": {
    "project": "pgpt-cli-history",
    "web": "off",
    "context": true,
    "deep": false,
    "skill": "code-review"
  }
}
```

`stream: true` is accepted for OpenAI-client compatibility, but the current HTTP adapter emits the verified answer after the internal pipeline completes rather than exposing unverified draft tokens. Terminal generation still streams directly.

## 6. VS Code / Continue in WSL

The intended IDE path is:

```text
VS Code Remote - WSL
        |
        v
Continue chat model
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

Start `pgpt server` inside WSL, then merge `docs/continue-config.yaml` into your Continue configuration.

The example config deliberately points Continue at **pgpt**, not directly at Ollama. Going directly to Ollama would bypass pgpt's routing, project retrieval, web retrieval, skills, and quality layer.

See [docs/VS_CODE.md](docs/VS_CODE.md) for the focused setup.

## 7. Routing

Routing has two layers:

```text
user prompt
    |
    v
small semantic classifiers
    |
    +--> task
    +--> freshness
    +--> complexity telemetry
    |
    v
deterministic policy / explicit overrides
    |
    +--> local
    +--> project
    +--> web lookup
    +--> web research
```

The router decides meaning; `pgpt.runtime.route` then decides execution template and answer model. Explicit CLI overrides remain authoritative.

Important behavior:

- project evidence can activate project retrieval;
- strong current/external language can activate web retrieval;
- explicit multi-source research activates web research;
- `--web off` suppresses web retrieval;
- `--context` forces project retrieval;
- model selection uses ordered task preferences and only selects installed Ollama models.

## 8. Project retrieval

Project retrieval is intentionally source-grounded and bounded:

```text
prompt
  |
  +--> code-shaped identifier candidates
  |       |
  |       +--> ripgrep definition search
  |       +--> source window around best definition
  |
  +--> lexical fallback
          |
          +--> path/content scoring
          +--> bounded file context
```

Exact symbol definitions have priority. Broader architecture/review prompts fall back to lexical retrieval. If no useful file is found, the assistant receives a project manifest rather than invented source.

`pgpt-cli` uses the current repository as project source. `pgpt-cli-history` uses the tracked historical fixture. The `vibemaster` profile remains available for the original local project when its external path exists, but repository tests no longer depend on it.

## 9. Web retrieval

Brave Search is used only when routing selects web lookup/research or you explicitly request it.

```text
prompt
  |
  v
Brave search
  |
  +--> candidate results
  +--> bounded page fetches
  +--> source IDs [S1], [S2], ...
  |
  v
answer + source footer
```

When connectivity is unavailable, the runtime falls back rather than pretending live web evidence exists.

## 10. Quality and evaluation

There are three different quality layers:

```text
runtime verification
    |
    +--> deterministic checks
    +--> bounded deterministic repair
    +--> at most one semantic repair

end-to-end evaluation
    |
    +--> route contract
    +--> deterministic answer checks
    +--> semantic judge

reliability evaluation
    |
    +--> repeated generation
    +--> repeated judging
    +--> pass rates + latency statistics
```

The semantic evaluator now judges **one rubric criterion per local-model call**:

```text
required #1  --> boolean + reason
required #2  --> boolean + reason
...
forbidden #1 --> boolean + reason
forbidden #2 --> boolean + reason
                 |
                 v
         deterministic Python aggregation
```

This keeps criterion alignment out of one oversized judge response. Judge instructions live in Markdown prompt assets rather than Python.

See [docs/TESTING.md](docs/TESTING.md).

## 11. Automated CI

GitHub Actions runs an offline gate on Python 3.11 and 3.13. It does not require your Ollama models, Brave key, PrivateGPT checkout, or private project directory.

The gate covers syntax, packaging, model selection, mocked pipeline behavior, project-fixture integrity, skill management, HTTP integration, evaluation mechanics, and browser assets.

Model-dependent routing and quality evaluations remain local integration tests because GitHub-hosted runners do not have your Ollama environment.

## 12. PrivateGPT compatibility

The direct pgpt pipeline does not require PrivateGPT to answer ordinary or source-grounded project questions. The older maintenance commands are preserved for the local PrivateGPT/RAG workflow:

```bash
pgpt status
pgpt sync --project pgpt-cli
pgpt ingest --project pgpt-cli
pgpt serve
```

`pgpt serve` remains the legacy PrivateGPT server command. `pgpt server` is the new pgpt browser/OpenAI-compatible interface.

This separation lets you keep experimenting with PrivateGPT ingestion without making the everyday CLI/VS Code chat path depend on it.

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
├── skills/
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

## Local-only data

These should remain untracked:

```text
responses/
state/
local chats
evaluation result files
secrets.env
.env files
private keys
backups/
```

Before publishing changes, always review staged content for secrets.

## Design principles

1. **Local first.** Ordinary chat, project reasoning, skills, and orchestration should work against local models.
2. **Evidence before project claims.** Project-specific explanations should come from retrieved source.
3. **Explicit boundaries.** Routing, retrieval, model selection, generation, verification, storage, and UI are separate concerns.
4. **Natural-language behavior belongs in prompt assets.** Python owns mechanics and policy, not buried prompt prose.
5. **Small models need deterministic support.** Use schemas, rules, bounded retries, and tests instead of expecting one model call to do everything.
6. **Local does not mean unrestricted.** The browser/API binds to loopback by default, and autonomous shell/filesystem tool execution is not silently enabled.
