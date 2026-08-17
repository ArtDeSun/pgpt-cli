# Testing pgpt-cli

pgpt-cli has two test layers because a local-model application cannot make every useful test hermetic.

## Offline CI gate

The GitHub Actions `ci` workflow runs without Ollama, Brave Search, PrivateGPT, or user project files. It validates:

- Python and JSON syntax;
- model-selection policy with injected available-model sets;
- the pipeline with mocked routing/model generation;
- path handling and self-contained historical project data;
- local skill discovery/override/creation;
- the browser/OpenAI-compatible HTTP surface;
- end-to-end scoring mechanics and prompt separation;
- evaluation project selection and evidence construction.

Run the same gate locally with the command listed in `.github/workflows/ci.yml` or individual `python -m unittest` modules.

## Local-model integration and evaluation

These tests intentionally require your WSL Ollama environment and are not part of GitHub-hosted CI:

```bash
python3 -m unittest \
  tests.test_routes \
  tests.test_router_dataset \
  tests.test_router_generated \
  tests.test_router_regressions \
  -v
```

Judge calibration:

```bash
python3 -m tools.calibrate_quality_judge \
  --model qwen3.5:9b
```

End-to-end generation and scoring:

```bash
python3 -m tools.run_end_to_end_evals --fresh
python3 -m tools.score_end_to_end_results \
  --model qwen3.5:9b
```

Reliability runs:

```bash
python3 -m tools.run_reliability_evals \
  --runs 5 \
  --judge-model qwen3.5:9b \
  --fresh
```

The project-grounded end-to-end case uses the repository-owned `pgpt-cli-history` snapshot, so it does not depend on the private `vibemaster` directory.

## Why judge criteria are isolated

Semantic quality judging evaluates one required or forbidden criterion per model call. Python then aggregates the booleans. This intentionally avoids asking a small local judge to keep many independent criterion decisions aligned in one large JSON response.

The natural-language judge instructions live in `prompts/quality/required-criterion.md` and `prompts/quality/forbidden-criterion.md`; Python owns only schemas, transport, validation, retries, and aggregation.
