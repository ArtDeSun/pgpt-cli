# pgpt-cli

`pgpt-cli` is a local-first AI assistant for WSL. It uses Ollama for generation, can read configured project source, can use Brave for current public information, and exposes a browser UI plus an OpenAI-compatible endpoint for VS Code clients.

```text
terminal / browser / VS Code
             |
             v
          pgpt-cli
        /     |     \
     local  project  web
     Ollama  source  Brave
```

The codebase is intentionally small enough for one human to understand and maintain end to end.

## Directory layout

Your current layout is correct; no restructuring is required.

```text
~/ai/
├── pgpt-cli/          # this repository
├── private-gpt/       # optional PrivateGPT checkout
├── private-gpt-data/  # optional PrivateGPT data
└── vibemaster-knowledge/
```

Skills have two separate locations:

```text
~/ai/pgpt-cli/skills/       built-in, Git-managed skills
~/.config/pgpt/skills/      your personal skills
```

Use `~/.config/pgpt/skills/` for normal personal skill work.

## Install or update

```bash
cd ~/ai/pgpt-cli
git pull
source .venv/bin/activate
python -m pip install -e .

pgpt status
pgpt models
```

Create `.venv` first with `python3 -m venv .venv` if it does not exist.

## Core commands

```bash
pgpt validate "What is dependency injection?"
pgpt ask "What is dependency injection?"
pgpt chat
pgpt server
```

Project-grounded request:

```bash
pgpt ask --project pgpt-cli --context \
  "Explain how select_model works."
```

The browser UI is served at:

```text
http://127.0.0.1:8765/
```

## Online and offline use

`--web` controls public web retrieval:

```text
--web auto      decide automatically
--web off       never use Brave
--web lookup    force one focused lookup
--web research  force multi-source research
```

Examples:

```bash
pgpt ask --web off "Explain dependency injection."
pgpt ask --web auto "What's the weather in Toronto?"
pgpt ask --web lookup "Has Python 3.14 been released?"
```

In `auto` mode, obvious live requests such as weather, current time, prices, scores, or explicit `latest/current` wording skip the router model. Ambiguous ordinary questions use one small decision: **does an accurate answer require current public information?** There is no second web-mode classifier.

The default router is `qwen3.5:9b`. To test another installed Ollama model without editing the repo:

```bash
PGPT_ROUTER_MODEL=gemma4:e4b \
  pgpt validate "Who runs this organization?"
```

If Wi-Fi is unavailable, use `--web off` for predictable local-only behavior. In `auto`, a failed web connection falls back to local generation and is reported as unavailable rather than pretending live data was retrieved.

## Brave API and request budget

Store the key outside Git:

```bash
mkdir -p ~/.config/pgpt
cp secrets.env.example ~/.config/pgpt/secrets.env
chmod 600 ~/.config/pgpt/secrets.env
```

Then add:

```text
PGPT_BRAVE_API_KEY=your_key
```

Check the local/API-derived usage state with:

```bash
pgpt web-usage
```

`config.json` currently caps pgpt at 500 Brave requests per month. This is a local safety limit, not a statement about your Brave subscription.

## Skills

```bash
pgpt skill-new my-review
nano ~/.config/pgpt/skills/my-review.md
pgpt skills
pgpt ask --skill my-review "Review this design."
```

Personal skills override built-in skills with the same name. Only edit `~/ai/pgpt-cli/skills/` when changing a built-in skill for the repository.

## VS Code

Start:

```bash
pgpt server
```

Then point a compatible VS Code client such as Continue at:

```text
http://127.0.0.1:8765/v1
```

See `docs/VS_CODE.md` and `docs/continue-config.yaml`.

Point the client at pgpt rather than Ollama directly when you want pgpt routing, project retrieval, Brave lookup, skills, and verification.

## PrivateGPT: optional compatibility workflow

Normal pgpt use does **not** require PrivateGPT.

These work without the PrivateGPT server:

```text
pgpt ask
pgpt validate
pgpt chat
pgpt server
browser / VS Code API
project source retrieval
Brave lookup/research
skills
```

PrivateGPT is only used by the optional maintenance/compatibility commands:

```bash
pgpt sync --project pgpt-cli
pgpt ingest --project pgpt-cli
pgpt serve
```

Remember:

```text
pgpt server   pgpt browser + OpenAI-compatible API
pgpt serve    optional PrivateGPT server
```

## Routing design

Routing has three simple layers:

```text
1. explicit user overrides and obvious high-confidence rules
2. project evidence, when present
3. one web-need classifier for ambiguous general questions
```

Task type is derived from clear request signals (`debug`, `implement`, `architecture`, `research`, code explanation). Web research is selected only for research tasks; other web requests use focused lookup.

The goal is correctness with the fewest model calls, not perfect linguistic classification of every sentence.

## Testing

Offline CI covers deterministic code, routing policy, project retrieval, server behavior, Brave usage accounting, prompts, skills, and UI contracts.

Run the human-curated local Ollama routing checks in WSL:

```bash
python -m unittest \
  tests.test_router_dataset \
  tests.test_router_temporal_pairs \
  -v
```

For the rest of the test workflow, see `docs/TESTING.md`.

## Human maintenance rule

One human owns this repository end to end. Before keeping a change:

```bash
git diff --check
git status
python -m compileall -q pgpt tools tests
```

Then run the smallest relevant tests first, followed by the full offline suite before release.

Keep runtime data, secrets, responses, chats, and local evaluation output out of Git. Prefer deleting obsolete code/tests over keeping parallel mechanisms “just in case.”

Repository policy: `main` is the only intended long-lived branch.
