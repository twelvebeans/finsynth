# Agent Guide

Context for coding agents working on this Python project. Read this before making changes.

## General instructions

- When writing something intended for human consumption, (comment, commit message, reply to prompt) use as few words as possible. Pick every word meticulously to reduce the volume to a strict minimum.
- Keep function names short. Less than 30 characters.
- Make reading of the code easier. Add empty lines between logical blocks of code. Add a small, to the point, comment to explain _what_ the block does and _why_.
- Only touch blocks of code related to the feature you implement. Don't add or modify comments to a block of code if you did not create it or modify it.
- As much as possible try to minimize the number of changed lines when implementing a feature.

## Toolchain Overview

- Python version: pinned in `mise.toml`
- Toolchain is managed by [mise](https://mise.jdx.dev/): `mise.toml` selects Python
- Dependencies are managed by [uv](https://docs.astral.sh/uv/): `pyproject.toml` declares them, `uv.lock` pins exact versions
- If git commit fails - immideately stop and report.

## Commands

Tasks are defined in `mise.toml` and run with `mise run`.

```sh
mise run check    # full Definition of Done: ruff format --check -> ruff check -> mypy -> pytest -x
mise run test     # pytest -v -x
mise run lint     # ruff format --check src/ && ruff check src/ && uv run mypy src/
mise run fmt      # ruff format src/
mise run example  # python -m finsynth.cli
mise run install  # uv sync --all-extras
```

Raw commands, if mise isn't set up:

```sh
# Install deps
uv sync

# Run
uv run python -m <package>

# Test
uv run pytest                        # all tests
uv run pytest -x                     # stop on first failure
uv run pytest --tb=short             # compact tracebacks
uv run pytest tests/test_foo.py::test_name  # single test

# Format / lint / typecheck
uv run ruff format .       # format in place
uv run ruff format --check .  # check only (must print nothing)
uv run ruff check .        # lint
uv run mypy .              # type check
```

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) and [PEP 257](https://peps.python.org/pep-0257/).
- `ruff format` is the only mandatory formatter; run it before committing.
- Errors: raise with context — prefer specific exception types; never silence them with bare `except`.
- Exported symbols get docstrings; module names are short, lowercase, underscore-separated.
- Keep functions small; prefer early returns over deep nesting.
- Use type annotations throughout; `mypy` must pass.
- Tests live in `tests/` directory, run with `pytest`, parametrize table-driven cases.

## Conventions

- Run `uv sync --all-extras` after adding or removing dependencies; keep them minimal.
- Use `logging` with structured output (or `structlog` if already in the project).
- For commit messages use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
- Bumping Python: change the version in `mise.toml`, then run `mise lock` to refresh `mise.lock`. Never edit `mise.lock` by hand.
- Bumping deps: `uv add <pkg>` or `uv remove <pkg>`; never edit `uv.lock` by hand.

## Definition of Done

A change is complete when `mise run check` passes. That single task verifies all of:

1. `uv run ruff format --check -s src/` prints nothing
2. `uv run ruff check src/` passes
3. `uv run mypy src/` passes
4. `uv run pytest tests/ -x -v` passes
5. New behavior has tests; changed behavior updates existing tests
