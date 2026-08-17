# VS Code / WSL integration

The recommended IDE topology keeps the orchestration layer inside WSL:

```text
VS Code Remote - WSL
        |
        v
Continue
        |
        v
pgpt local OpenAI-compatible endpoint
        |
        +--> routing
        +--> project retrieval
        +--> optional Brave web retrieval
        +--> skill instructions
        +--> local model selection
        +--> verification / repair
        |
        v
Ollama in the local WSL/Windows environment
```

## Start pgpt in WSL

Open the repository through VS Code's WSL remote environment, then use a WSL terminal:

```bash
cd ~/ai/pgpt-cli
source .venv/bin/activate
pgpt server
```

Default endpoints:

```text
Browser UI: http://127.0.0.1:8765/
API base:   http://127.0.0.1:8765/v1
Health:     http://127.0.0.1:8765/health
```

The service binds to loopback by default. Do not use `--allow-remote` unless you intentionally want another machine to reach the service and have separately considered authentication/network controls.

## Continue

The repository includes `docs/continue-config.yaml`. Merge that model entry into your Continue YAML configuration and reload Continue.

The model uses Continue's OpenAI-compatible provider path:

```yaml
models:
  - name: pgpt-cli
    provider: openai
    model: pgpt-cli
    apiBase: http://127.0.0.1:8765/v1
    apiKey: local
    useResponsesApi: false
    roles:
      - chat
```

The endpoint currently implements Chat Completions and does not advertise tool calling. Use it for Chat (and Continue's normal chat-model fallback behavior for edit/apply when appropriate), not Continue Agent mode.

Pointing Continue directly at Ollama is also possible, but that bypasses pgpt's routing, retrieval, skills, and verification layers.

## Browser GUI

Open `http://127.0.0.1:8765/` while the server is running. The browser UI supports:

- project selection;
- web auto/off/lookup/research;
- deep-mode override;
- local skills;
- persisted browser-tab chat history through localStorage;
- route/template/model metadata on generated answers.

## Local skills

Create personal skills without changing Git-tracked prompt files:

```bash
pgpt skill-new my-skill
nano ~/.config/pgpt/skills/my-skill.md
pgpt skills
```

Then select the skill in CLI chat, the browser GUI, or send a `pgpt.skill` option to `/v1/chat/completions`.
