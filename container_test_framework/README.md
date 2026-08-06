# container-test-framework

A small, **container-agnostic** framework for validating containers — built from
scratch to demonstrate real unit-, functional- and integration-testing practice.

The idea: one engine drives container *lifecycle* (pull / run / copy / teardown),
and pluggable **validators** own the target-specific *correctness* checks. The
same core is meant to serve a MySQL validator today, a REST API validator next,
and a deep-learning benchmark validator later — without changing the engine.

## Design

```
                 ┌─────────────────────────────────────────────┐
                 │                 validators/                 │
                 │  ContainerValidator (ABC)  ── mysql / api / │
                 │        │  reuse            dl (planned)     │
                 └────────┼────────────────────────────────────┘
                          │ uses
                 ┌────────▼─────────┐
                 │   engine/        │   Docker: query/pull/run/copy/teardown
                 │   Docker         │        │
                 │   CommandExecutor│◄───────┘ single I/O seam (mocked in unit tests)
                 └────────┬─────────┘
                          │ shells out to
                     `docker` CLI
```

Two test layers prove different things:

| Layer | Location | Proves | Container? |
|-------|----------|--------|-----------|
| **Unit** | `tests/unit/` | The engine builds the right commands and branches correctly, in isolation | No — the executor seam is mocked |
| **Functional / integration** | `tests/*.robot` (and `tests/integration/`, planned) | It works end-to-end against a live container | Yes |

## Layout

```
container-test-framework/
├── src/ctf/
│   ├── engine/
│   │   ├── docker.py        # container-agnostic Docker CLI wrapper
│   │   ├── executor.py      # the single shell-execution seam
│   │   └── config.py        # docker run options
│   ├── validators/
│   │   ├── base.py          # ContainerValidator ABC + ValidationResult
│   │   └── mysql.py         # MySQLValidator: health/schema/CRUD/integrity
│   ├── cli.py               # `python -m ctf` front-end
│   └── __main__.py
├── tests/
│   ├── unit/                # mocked, hermetic unit tests (see its README)
│   └── *.robot              # Robot Framework functional layer
├── pyproject.toml           # packaging + `ctf` console script
├── pytest.ini               # unit-test config
├── requirements.txt         # runtime (Robot layer)
└── requirements-dev.txt     # test toolchain
```

## Quickstart

```bash
# install dev toolchain
pip install -r requirements-dev.txt

# run the unit suite (fast, no Docker needed)
pytest

# with coverage on the engine
pytest --cov=ctf.engine --cov-report=term-missing

# run the CLI against a real image (needs Docker)
python -m ctf --command run_container --image acme/mysql --tag 8.0
```

## CLI usage

The engine is driven through `python -m ctf` (or the installed `ctf` console
script). Every invocation needs a `--command` and an `--image`; `--tag` defaults
to `latest`.

```
python -m ctf --command <command> --image <image> [--tag <tag>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--command` | yes | — | One of the commands in the table below |
| `--image` | yes | — | Any Docker image reference: `mysql`, `mysql:8.0`, `bitnami/mysql`, or `reg.io:5000/team/app:1.2`. Used verbatim for pull/run |
| `--tag` | no | `latest` | Image tag. A tag written into `--image` (e.g. `mysql:8.0`) takes precedence over this |
| `--test` | no | — | *(reserved)* test labels to run — wired up with the validator suites |
| `--exclude` | no | — | *(reserved)* test labels to skip |

### Commands

| `--command` | What it does | Example |
|-------------|--------------|---------|
| `query_container` | Check whether the **image** exists locally (`docker images` + grep) | `python -m ctf --command query_container --image mysql --tag 8.0` |
| `pull_container` | Pull the image if it isn't already present locally | `python -m ctf --command pull_container --image mysql --tag 8.0` |
| `ps_container` | Check whether a **container instance** exists (`docker ps -a`) | `python -m ctf --command ps_container --image mysql --tag 8.0` |
| `run_container` | Start the container | `python -m ctf --command run_container --image mysql --tag 8.0` |
| `rm_container` | Stop and remove the container | `python -m ctf --command rm_container --image mysql --tag 8.0` |

### Image references & container naming

`--image` is treated as a real Docker reference and used **verbatim** for
`docker pull` / `docker run` — the framework never fabricates a registry:

| `--image` | Pulled/run as | Container name |
|-----------|---------------|----------------|
| `mysql` (`--tag 8.0`) | `mysql:8.0` | `mysql-8.0` |
| `mysql:8.0` | `mysql:8.0` | `mysql-8.0` |
| `bitnami/mysql:8.0` | `bitnami/mysql:8.0` | `mysql-8.0` |
| `reg.io:5000/team/app:1.2` | `reg.io:5000/team/app:1.2` | `app-1.2` |

The container name (used for `run --name`, `ps`, `rm`) is the last path segment
plus the tag. A registry port (the `:5000` above) is never mistaken for a tag.

### Notes

- **Return codes.** The CLI exits `0` on success and `1` on error (including bad
  arguments or an engine exception). Running with no arguments prints help and
  exits `1`.
- **Help.** `python -m ctf --help` lists all arguments and valid commands.

### Typical flow

```bash
# pull, run, verify it's up, then tear it down
python -m ctf --command pull_container --image mysql --tag 8.0
python -m ctf --command run_container  --image mysql --tag 8.0
python -m ctf --command ps_container   --image mysql --tag 8.0
python -m ctf --command rm_container   --image mysql --tag 8.0
```

## Status & roadmap

- [x] Container-agnostic engine (`Docker` + `CommandExecutor`)
- [x] Hermetic unit layer — 26 tests, 100% line coverage on `engine/docker.py`
      (found & fixed 5 real defects; see `tests/unit/README.md`)
- [x] `ContainerValidator` ABC so targets plug into a shared lifecycle
- [x] **MySQL validator** — health, schema, CRUD, data-integrity checks
      + mocked unit tests (DB client injected; 98% coverage)
- [ ] MySQL **integration** layer — `testcontainers` MySQL, run against a live DB
- [ ] REST API validator — mocked unit tests + live contract/endpoint tests
- [ ] DL benchmark validator — threshold-based, deterministic asserts (stretch)
- [ ] CI workflow (lint + unit on push; integration on demand) and coverage gate

## Why it's a framework, not a script

The `ContainerValidator` abstract base class is the hinge: a new target implements
`checks()` and reuses the engine's pull/run/teardown lifecycle. Adding MySQL or an
API target requires no change to the engine or the unit harness — only a new
validator subclass and its tests.
