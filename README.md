# pgpt-cli

`pgpt-cli` is a local-first ChatGPT-style assistant for WSL. Ollama generates answers, direct project-source retrieval handles code/project questions, Brave supplies current public information and research, and PrivateGPT is optional for durable RAG ingestion.

The operating rule is: **Auto should normally work, but the browser exposes authoritative manual overrides for every high-impact decision.**

## Recommended `~/ai` layout

```text
~/ai/
├── pgpt-cli/                 # this repository
├── private-gpt/              # PrivateGPT source
├── private-gpt-data/         # generated PrivateGPT state; do not ingest
│   ├── local_data/
│   ├── models/
│   └── tiktoken_cache/
└── knowledge/                # folders/snapshots intended as knowledge
    ├── pgpt-cli/
    └── vibemaster/

~/.config/pgpt/
├── projects.json             # projects added from the UI
├── secrets.env               # Brave key
└── skills/                   # personal skills
```

After pulling this release, you may migrate old knowledge snapshots:

```bash
mkdir -p ~/ai/knowledge
[ -d ~/ai/vibemaster-knowledge ] && [ ! -e ~/ai/knowledge/vibemaster ] && mv ~/ai/vibemaster-knowledge ~/ai/knowledge/vibemaster
[ -d ~/ai/pgpt-cli-knowledge ] && [ ! -e ~/ai/knowledge/pgpt-cli ] && mv ~/ai/pgpt-cli-knowledge ~/ai/knowledge/pgpt-cli
[ -d ~/ai/pgpt-cli-history-knowledge ] && [ ! -e ~/ai/knowledge/pgpt-cli-history ] && mv ~/ai/pgpt-cli-history-knowledge ~/ai/knowledge/pgpt-cli-history
```

Do **not** move or delete `~/ai/private-gpt-data`.

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

The main conversation now stays uncluttered. Open **Settings** only when you want to override Auto behavior. The drawer groups routing/context controls separately from capability status.

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

The **Capabilities** section shows the current Ollama models, Brave status/quota state, configured project sources, and skills. This borrows the useful part of a plugin-first UI—capabilities are visible as independent surfaces—without adding an agent framework or a dynamic plugin kernel.

### Run details

Each assistant response has a collapsed **Run details** inspector. It records the observable execution facts already produced by pgpt: route/source/task, selected model, web/project selection, context/length controls, status events, and timing.

It does **not** expose hidden chain-of-thought. The goal is operational traceability: you can see why a request used local/project/web and which model actually answered.

### Smart context

`Smart` is the default. It keeps relevant follow-ups but drops unrelated older topics. A project-code discussion therefore should not contaminate a later NBA/current-events question. `Full recent` deliberately sends recent history; `Off` starts clean except for an explicit skill.

This follows a simple memory principle: keep always-injected context small and retrieve/use older information only when relevant. pgpt does not require another memory service for ordinary chat.

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

If a previous run stored `monthly_limit: 0` and `monthly_remaining: 0`, you do **not** need to delete the state file after this fix; the corrected interpretation applies when the state is read.

An automatically chosen web route may degrade gracefully when offline and explicitly tells the model that live evidence was unavailable. A forced lookup/research or natural-language explicit web request instead returns a clear error if retrieval fails; it does not guess a current answer from local memory.

## Harness-inspired design choices

DeepSeek Harness is useful as a design reference, but `pgpt-cli` intentionally remains a simple local chat application rather than becoming an agent harness.

The adopted ideas are:

- **Capability boundaries:** model, web, project context, skills, sessions, and storage remain separate modules/configuration surfaces.
- **Provider-style settings:** the UI shows the active local model capability and Brave web capability independently instead of hiding them behind Auto.
- **Traceability:** observable routing, model selection, status events, and timing are inspectable per response.
- **Clean conversation surface:** advanced controls live in Settings instead of occupying the whole top of the chat.
- **Session-level choice:** manual model/web/project/context choices apply to the request without changing the routing architecture.

Not adopted: subagents, model-generated tool orchestration, creator mode, dynamic runtime plugin loading, or exposing private model reasoning.

## Long responses

Output budgets are larger than before. When Ollama ends with `done_reason=length`, pgpt can make bounded continuations and hides the internal continuation instruction. For large plans/analyses choose **Answer length → Long**. Use **Full recent** or **Deep** only when extra context is actually useful.

## Projects and PrivateGPT

Two separate mechanisms exist:

1. **Project-source retrieval** reads the selected source tree directly and is the normal fast code/project path.
2. **PrivateGPT ingestion** creates durable RAG data under `~/ai/private-gpt-data` for folders you explicitly add.

The browser's **Add knowledge folder** action accepts a readable local directory, project name, and optional collection. pgpt calls PrivateGPT's existing `scripts/ingest_folder.py` without shell interpolation and registers the project in `~/.config/pgpt/projects.json` only after successful ingestion. System roots and common credential directories are rejected.

Examples of valid source folders:

```text
/home/<you>/ai/knowledge/vibemaster
/home/<you>/dev/another-project
/mnt/c/Users/<you>/Documents/research-notes
```

Never use `private-gpt-data` itself as source knowledge.

PrivateGPT is optional for normal chat, direct project retrieval, Brave, and skills. It is required only for explicit ingestion/RAG maintenance.

```text
pgpt server   -> pgpt browser/API
pgpt serve    -> PrivateGPT server
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

## Tests

Offline release gate:

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

CI runs the suite on Python 3.11 and 3.13, validates browser JavaScript, and enforces the one-remote-branch rule. Coverage includes the 100+ routing policy dataset, NBA/current-year routing, smart history, model overrides, forced-web semantics, Brave unlimited-quota handling, continuation behavior, server controls, knowledge-ingest safety, run-details UI, and browser controls.

The local-model routing acceptance suite is opt-in:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 python -m unittest tests.test_router_acceptance_local -v
```

See `docs/TESTING.md` for manual release scenarios.
