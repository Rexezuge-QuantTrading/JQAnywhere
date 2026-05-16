# AGENTS.md

## Setup And Commands

- Use a project virtualenv; the known-good local flow is `python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"`.
- Run formatting with `.venv/bin/ruff format .`.
- Run lint with `.venv/bin/ruff check .`; auto-fix with `.venv/bin/ruff check . --fix`.
- Run all tests with `.venv/bin/pytest`; run a focused test with `.venv/bin/pytest tests/test_runtime.py::test_simple_strategy_runs`.
- Run the example strategy through the installed CLI with `.venv/bin/jqanywhere run --config examples/jqanywhere.toml`.

## Formatting And Linting

- Ruff is the formatter and linter source of truth in `pyproject.toml`; no Black, isort, mypy, pre-commit, or CI config exists currently.
- Ruff targets `py313` with `line-length = 140`, double quotes, spaces, LF endings, and source roots `src`, `tests`, `examples`.
- Keep the configured per-file Ruff ignores for JoinQuant compatibility: examples may use `from jqdata import *`, `src/jqanywhere/jqcompat/api.py` re-exports wildcard API types, and `src/jqdata/__init__.py` intentionally re-exports compatibility globals.

## Git Commit Messages

- Use Conventional Commits with this subject format: `<TYPE>[optional scope]: <description>`.
- Write the type in uppercase, for example `FIX`, `FEAT`, `DOCS`, `STYLE`, `REFACTOR`, `TEST`, `BUILD`, `CHORE`, `CI`, or `PERF`.
- Write the optional scope in lowercase inside parentheses, for example `FEAT(runtime): Add Scheduled Job State`.
- Write the description as concise human-readable words with spaces, capitalizing the first letter of each word, for example `DOCS: Latest Agents Context Reflection`, `STYLE: Standardize Python Formatting`, or `FEAT: Bootstrap JQAnywhere v0.1 Framework`.
- When creating a commit from `main`, first switch to a new branch generated from the planned commit subject.
- Use lowercase slash-separated branch names: `type/description` when there is no scope, or `type/scope/description` when there is a scope.
- Convert the description to kebab-case for the branch, for example `docs/latest-agents-context-reflection`, `docs/agents/document-commit-standard`, or `feat/bootstrap/bootstrap-jqanywhere-v0.1-framework`.
- Use Markdown for optional commit bodies, separated from the subject by a blank line.
- Use optional footers after the body, separated by a blank line, following git trailer-style formatting.
- Use `FIX` for bug patches and `FEAT` for new features; other conventional types are allowed when they better communicate intent.
- Mark breaking API changes with `!` after the type or scope, or with a `BREAKING CHANGE: <description>` footer.

```text
<TYPE>[optional scope]: <description>

[optional body in Markdown]

[optional footer(s)]
```

## Architecture Notes

- This package is a compatibility runtime, not a strategy adapter: copied user strategies should keep JoinQuant style, especially `from jqdata import *`, `initialize(context)`, `run_daily(...)`, global `g`, and order functions.
- `src/jqdata` is the public compatibility package imported by strategies; most implementation lives under `src/jqanywhere`.
- Main local CLI entrypoint is `jqanywhere.cli:main`; Lambda entrypoint is `jqanywhere.runtime.lambda_handler.run`.
- Runtime construction is centralized in `src/jqanywhere/runtime/factory.py`; it currently selects memory vs DynamoDB state and console vs SNS notifier from config/env, while always using `EmptyMarketDataProvider` and `PaperBroker`.
- `RuntimeEngine.run()` loads the strategy file, requires `initialize(context)`, runs due scheduled jobs, persists `g`, sends logs, and always resets the runtime session token.

## Config And Deployment Gotchas

- `load_config()` reads `jqanywhere.toml` by default, or `JQANYWHERE_CONFIG`; example config lives at `examples/jqanywhere.toml`.
- Environment overrides include `JQANYWHERE_STRATEGY_PATH`, `JQANYWHERE_STRATEGY_ID`, `JQANYWHERE_INITIAL_CASH`, `JQANYWHERE_PERSISTENCE`, `JQANYWHERE_STATE_TABLE`, `JQANYWHERE_NOTIFIER`, and `AWS_ENDPOINT_URL`.
- `serverless.yml` defaults Lambda runtime to `python3.11` via `LAMBDA_RUNTIME`, even though Ruff targets `py313`; do not assume deploy runtime matches local lint target.
- Serverless packaging includes `src/**`, `examples/**`, and `jqanywhere.toml`, and excludes `tests/**` and `.venv/**`.

## Compatibility Constraints

- Unsupported JoinQuant APIs should fail explicitly with `NotImplementedError` rather than silently doing the wrong thing; tests already assert this for `get_fundamentals`.
- Live broker integration is intentionally a template extension point; see `src/jqanywhere/broker/template.py` before adding broker behavior.
