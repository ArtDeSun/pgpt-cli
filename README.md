# pgpt-cli

`pgpt-cli` is a local-first AI assistant for WSL. Ollama generates answers; pgpt can also read configured project source, use Brave for live public information, and expose a browser/OpenAI-compatible API for VS Code.

```text
terminal / browser / VS Code
             |
             v
          pgpt-cli
        /     |     \
     Ollama  project  Brave
```

The codebase is intentionally small enough for one human to understand and maintain end to end.

## Setup

Your current layout is correct. No directory changes are required.

```text
~/ai/
├── pgpt-cli/
├── private-gpt/       # optional
├── private-gpt-data/  # optional
└── vibemaster-knowledge/
```

Install or update:

```bash
cd ~/ai/pgpt-cli
git pull
source .venv/bin/activate
python -m pip install -e .
pgpt status
```

Create `.venv` first with `python3 -m venv .venv` if needed.

## Everyday use

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

`pgpt server` serves the browser UI at `http://127.0.0.1:8765/` and the OpenAI-compatible API at `/v1`.

## Online and offline

`--web` controls Brave retrieval:

```text
auto      use the web only when needed
off       never use the web
lookup    force one focused lookup
research  force multi-source research
```

Examples:

```bash
pgpt ask --web off "Explain dependency injection."
pgpt ask --web auto "What's the weather in Toronto?"
pgpt ask --web lookup "Has Python 3.14 been released?"
```

In `auto`, obvious live requests use deterministic rules. Ambiguous general questions use one small decision: **does an accurate answer need current public information?** There is no multi-stage semantic router.

To try another installed router model without editing the repo:

```bash
PGPT_ROUTER_MODEL=gemma4:e4b pgpt validate "Who runs this organization?"
```

If Wi-Fi is unavailable, use `--web off`. Failed online retrieval falls back to local generation and is reported as unavailable.

### Brave key and budget

```bash
mkdir -p ~/.config/pgpt
cp secrets.env.example ~/.config/pgpt/secrets.env
chmod 600 ~/.config/pgpt/secrets.env
```

Add `PGPT_BRAVE_API_KEY=...` to that file. Check usage with:

```bash
pgpt web-usage
```

`config.json` sets a 500-request monthly safety cap for pgpt. It does not define your Brave subscription limit.

## Skills

Keep the two skill locations distinct:

```text
~/ai/pgpt-cli/skills/   built-in, Git-managed skills
~/.config/pgpt/skills/  your personal skills
```

Normal skill work belongs in `~/.config/pgpt/skills/`:

```bash
pgpt skill-new my-review
nano ~/.config/pgpt/skills/my-review.md
pgpt skills
pgpt ask --skill my-review "Review this design."
```

A personal skill overrides a built-in skill with the same name.

## VS Code

Start `pgpt server`, then point a compatible client such as Continue at:

```text
http://127.0.0.1:8765/v1
```

See `docs/VS_CODE.md` and `docs/continue-config.yaml`.

## PrivateGPT is optional

Normal pgpt use does **not** require PrivateGPT. `ask`, `validate`, `chat`, `server`, browser/VS Code chat, direct project-source retrieval, Brave, and skills work without it.

PrivateGPT is only used by the optional compatibility/RAG maintenance path:

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

## Testing and ownership

Cheap offline tests run in GitHub Actions. Run them locally with:

```bash
python -m compileall -q pgpt tools tests
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

The real Ollama routing check is opt-in:

```bash
PGPT_RUN_LOCAL_MODEL_TESTS=1 \
  python -m unittest tests.test_router_dataset -v
```

See `docs/TESTING.md` for end-to-end and judge tests.

**Human ownership rule:** one human is responsible for this repository end to end. Keep changes small, review diffs, run the relevant tests, and delete obsolete mechanisms instead of keeping parallel versions. `main` is the only intended branch.
