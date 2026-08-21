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

### Controls

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

An automatically chosen web route may degrade gracefully when offline and explicitly tells the model that live evidence was unavailable. A forced lookup/research or natural-language explicit web request instead returns a clear error if retrieval fails; it does not guess a current answer from local memory.

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

CI runs the suite on Python 3.11 and 3.13, validates browser JavaScript, and enforces the one-remote-branch rule. Coverage includes the 100+ routing policy dataset, NBA/current-year routing, smart history, model overrides, forced-web semantics, continuation behavior, server controls, knowledge-ingest safety, and browser controls.

The local-model routing acceptance suite is opt-in:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 python -m unittest tests.test_router_acceptance_local -v
```

See `docs/TESTING.md` for manual release scenarios.
