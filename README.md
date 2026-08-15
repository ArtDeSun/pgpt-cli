# pgpt-cli v3

A modular local assistant over Ollama, with bounded local-project retrieval and direct Brave web search.

## Design

```text
prompt
  ↓
routing
  ↓
LOCAL | PROJECT | WEB_LOOKUP | WEB_RESEARCH
  ↓
bounded retrieval
  ↓
one final Ollama generation
  ↓
terminal + Markdown stream simultaneously
```

`pgpt ask` no longer depends on PrivateGPT's tool-agent loop. PrivateGPT remains available for your existing `serve` / `ingest` workflow, but ordinary answering uses direct Ollama generation, local source retrieval, and direct Brave search.

## Structure

```text
pgpt-cli/
├── pgpt.py
├── config.json
├── pgpt/
│   ├── cli.py
│   ├── config.py
│   ├── maintenance.py
│   ├── routing/router.py
│   ├── retrieval/project.py
│   ├── retrieval/web.py
│   ├── generation/ollama.py
│   ├── runtime/http.py
│   ├── runtime/pipeline.py
│   ├── runtime/timing.py
│   ├── output/stream.py
│   └── storage/chats.py
├── prompts/
├── chats/
├── responses/
├── state/
└── tests/
```

## Install

From the extracted v3 folder:

```bash
chmod +x install-v3.sh
./install-v3.sh
```

Your old `pgpt.py`, config, prompts, and package directory are backed up under `~/ai/pgpt-cli/backups/`.

Keep your alias:

```bash
alias pgpt='python3 ~/ai/pgpt-cli/pgpt.py'
```

## Brave key

Edit:

```bash
nano ~/.config/pgpt/secrets.env
```

and set:

```text
PGPT_BRAVE_API_KEY=your_key
```

The v3 web path calls Brave directly, so it does not use PrivateGPT's Brave retry loop. `settings-web.yaml` is still included for PrivateGPT compatibility and uses a non-zero `rate_limit`.

## Core commands

```bash
pgpt status
pgpt models
pgpt validate "What is dependency injection?"
pgpt ask "What is dependency injection?"
pgpt ask "Explain getYoutubeVideoMetadata in my project."
pgpt ask "What's Ottawa's weather today?"
pgpt ask "Research current AI privacy approaches and compare sources."
```

Project maintenance remains available:

```bash
pgpt sync
pgpt ingest
pgpt serve
python3 -m unittest discover -s tests -v
```

`pgpt ask` does not require `pgpt serve`.

## Interactive chat

```bash
pgpt chat-new "YouTube metadata"
pgpt chat
```

Inside chat:

```text
/web auto|on|off|research
/context auto|on|off
/deep auto|on|off
/new TITLE
/quit
```

## Timing

Terminal and Markdown use the same final timing layout:

```text
✓ Routing         0.1s
✓ Connectivity    0.1s
✓ Retrieval       1.4s
✓ Generation      6.8s
──────────────────────
  Total           8.4s

Model load        0.0s
Prompt eval       0.7s
Token generate    6.0s
Output tokens       182
Speed            30.3 tok/s
```

Generation is always the final timed phase. Ollama's final streaming chunk supplies the model-load, prompt-evaluation, token-count, and generation-duration metrics.

## Retrieval rules

For exact code identifiers, v3 searches the local repository first with `rg`. It does not ask a vector database to guess which file contains a named function.

For broader project questions, it selects a bounded set of local files lexically and instructs the model not to invent missing project evidence.

For web lookup, v3 performs one bounded Brave request. It does not let the model repeatedly invoke a failed search tool.

For web research, Brave returns more results and extra snippets, but generation still occurs only once.
