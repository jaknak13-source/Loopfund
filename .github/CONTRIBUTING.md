# Contributing to loopfund

Thanks for your interest. loopfund is research/education software that runs in
dry mode only. It is not financial advice and makes no guarantee of returns.
Contributions must keep it that way.

## Development setup

You need Python 3.11 or newer. Node 18+ is optional (only for rebuilding the
dashboard frontend).

```bash
./start.sh          # macOS/Linux (start.bat on Windows)
```

On first run this creates a virtual environment in `.venv`, installs
dependencies, and starts the app. For live frontend development on macOS/Linux,
`./start.sh --dev` runs the backend plus the Vite dev server on
`http://localhost:5173`. The CLI commands are available as `./start.sh <cmd>`
(for example `./start.sh cycle`).

## Architecture

A continuous loop in `core/` schedules specialist agents in `agents/`. Each agent
produces findings, which are combined by evidence-weighted aggregation. A risk
agent can veto or haircut, and a decision agent makes one allocation decision per
interval against the dry-mode ledger in `execution/`. `NO_ACTION` is valid. A
learning store in `memory/` scores matured predictions and tracks an SPY
benchmark. All model calls go through one adapter layer in `models_adapter/` and
are serialized to one call at a time. House rules live in `docs/STRATEGY.md` and
are enforced in code.

Where things live:

- `agents/`: specialist agents and markdown briefings in `agents/briefings/`.
- `core/`: config, store, loop runner, app wiring, backups, sandbox.
- `models_adapter/`: model backends and the router.
- `quant/`: factors, valuation, backtest, regime detection.
- `tools/`: data sources and plugins.
- `memory/`: vector memory and the learning store.
- `execution/`: dry-mode ledger and risk governor.
- `schemas/`: pydantic models.
- `dashboard/`: FastAPI API and the React/Vite frontend.
- `mcp_server/`: Model Context Protocol server.
- `config/`: `settings.yaml`, `models.yaml`, `risk_limits.yaml`.

To add a model backend: implement the `complete` method in a new module under
`models_adapter/`, register it by name in `models_adapter/router.py`, and follow
the `<NAME>_API_KEY` and `<NAME>_BASE_URL` env-var pattern. To add an agent: add a
markdown briefing in `agents/briefings/`, no code required.

## Running tests

Keep the suite green. All new code should come with tests where it makes sense.

```bash
.venv/bin/python -m pytest
```

## Code style

- Python 3.11+ with type hints. Pydantic v2 for I/O models.
- ruff and mypy are configured in `pyproject.toml` (ruff line-length 100).

```bash
.venv/bin/ruff check .
.venv/bin/mypy .
```

- Keep changes surgical and match the style of the file you edit.
- No emojis or filler language in code, commits, or docs.

## Commit messages

Use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`,
`test:`. Keep the subject short and explain the *why* in the body when it is not
obvious.

## Pull requests

1. Fork and branch off the default branch. One concern per branch.
2. Make sure `pytest` passes and `ruff check .` is clean.
3. Describe what changed, why, and how you verified it.
4. Link any related issue.

## Dry-mode safety rules

These are non-negotiable for any contribution.

- Do not implement or enable live trading. The live gate in `core/app.py`
  (requires `mode=live` and `LOOPFUND_ALLOW_LIVE=1`) and the unimplemented
  execution adapter must stay in place.
- Never commit `.env`, API keys, tokens, or other secrets. `.env` is git-ignored;
  use `.env.example` with placeholder values for documentation.
- Do not weaken the prompt-injection fencing on untrusted web, news, or memory
  content.
- Keep model-authored code execution failing closed without an OS sandbox.
- Do not add profit claims, performance promises, or financial advice to code or
  docs.

## License

By contributing, you agree that your contributions are licensed under the
Apache-2.0 license that covers this project.
