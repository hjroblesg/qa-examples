# Architecture

This document explains how **container-test-framework** is put together: the
layers, the components in each, the design patterns they embody, and the testing
strategy. It's meant as a map for anyone reading or extending the code.

## Overview

The framework separates two concerns that a one-off container test script usually
tangles together:

- **Lifecycle** — pulling, running, and tearing down a container. This is
  *container-agnostic*: the same engine drives MySQL, an HTTP API, or anything
  else.
- **Correctness** — the target-specific checks that decide whether the thing
  inside the container is actually healthy and behaving. This lives in pluggable
  *validators*.

A small CLI exposes the engine, and two test layers prove the system at different
levels: fast hermetic unit tests, and Robot Framework functional suites that run
against real containers.

## Layers

```
         ┌──────────────────────────────────────────────────────────┐
         │  Validators (correctness)                                 │
         │  ContainerValidator (ABC) ── MySQLValidator, APIValidator │
         └───────────────┬──────────────────────────────────────────┘
                         │ uses (lifecycle)
         ┌───────────────▼───────────────┐        ┌───────────────────┐
         │  Engine                        │        │  CLI (ctf)        │
         │  Docker, RunOptions, ImageRef  │◄───────┤  python -m ctf    │
         │  config                        │  calls │  run/pull/rm ...  │
         └───────────────┬───────────────┘        └───────────────────┘
                         │ shells out through
         ┌───────────────▼───────────────┐
         │  CommandExecutor (I/O seam)    │  the single point that touches
         │  subprocess -> docker CLI      │  the outside world
         └────────────────────────────────┘
```

Everything above `CommandExecutor` is pure logic and is unit-tested with that one
seam mocked. That's what makes the unit layer fully hermetic — no Docker daemon,
no network.

## Components

### Engine (`src/ctf/engine/`)

| Module | Type | Responsibility |
|--------|------|----------------|
| `executor.py` | `CommandExecutor` | The only I/O boundary. Runs a shell command via `subprocess` and returns `(stdout, return_code)`. Everything else is mocked against this in unit tests. |
| `docker.py` | `Docker` | Container-agnostic Docker CLI wrapper: `query`, `ps`, `pull`, `run`, `copy`, `teardown`. Builds command strings and interprets results. Tracks `self.ok` (success of the last lifecycle command). |
| `image_ref.py` | `ImageRef` | Parses a Docker reference `[registry[:port]/][namespace/]repo[:tag][@digest]` into `repository` / `tag` / `reference` / `container_name`. Used *verbatim* for pull/run so official images (`mysql`), namespaced (`bitnami/mysql`), and private-registry refs all work. |
| `run_options.py` | `RunOptions` | Env vars, port mappings, and overridable `docker run` flags → a flag string. Lets the engine launch env-driven images like MySQL. |
| `config.py` | constants | Default `docker run` flags (`DOCKER_OPTNS`). |

### Validators (`src/ctf/validators/`)

| Module | Type | Responsibility |
|--------|------|----------------|
| `base.py` | `ContainerValidator` (ABC), `ValidationResult` | The contract every target implements, plus the `validate()` lifecycle template. `ValidationResult(name, passed, detail)` is the uniform outcome type. |
| `mysql.py` | `MySQLValidator`, `MySQLConfig` | Checks: connectivity/health, schema, CRUD, data integrity. DB client injected via `connection_factory` (defaults to lazily-imported `mysql.connector`). |
| `api.py` | `APIValidator`, `APIConfig` | Checks: health, status codes, JSON contract. HTTP client injected via `session_factory` (defaults to lazily-imported `requests`). Overrides `setup()` to publish the API port through `RunOptions`. |

### CLI (`src/ctf/cli.py`, `__main__.py`)

`python -m ctf --command <cmd> --image <ref> [--tag ...] [--env ...] [--publish
...] [--run-opts ...]`. Parses arguments, builds `RunOptions`, dispatches to the
engine, and maps `Docker.ok` to its exit code (`0` success, `1` on a failed
pull/run/remove) so CI and the Robot suites can detect failures.

## Design patterns

The patterns below are real in the code but *lightly* applied — appropriate for a
small framework. Each is here because a concrete need called for it, not for
decoration.

### Template Method — the validation lifecycle

`ContainerValidator.validate()` fixes the skeleton (`setup → checks → teardown`,
with teardown guaranteed via `finally`) and defers exactly one step, the abstract
`checks()`, to subclasses:

```python
def validate(self, teardown=True):
    self.setup()                 # framework: pull + run via the engine
    try:
        return self.checks()     # subclass: target-specific assertions
    finally:
        if teardown:
            self.teardown()      # framework: clean up
```

This inversion — the base class calls into your code, not the other way round —
is what makes this a *framework* rather than a library or script.

### Strategy — interchangeable validators

Each `ContainerValidator` subclass is a swappable strategy for "how to validate
this target." `MySQLValidator` and `APIValidator` implement the same interface
with completely different internals (SQL vs. HTTP), and callers treat them
uniformly.

### Dependency Injection / Dependency Inversion — testable seams

High-level policy depends on abstractions, not concretions:

- `Docker` talks to a `CommandExecutor`, mocked in unit tests.
- `MySQLValidator` takes a `connection_factory`; `APIValidator` takes a
  `session_factory`. Both default to the real driver (imported lazily) but are
  replaced with mocks in unit tests — so the suite runs without a database,
  without a server, and without those drivers installed.

### Factory — deferred client creation

`connection_factory` / `session_factory` are small factory callables: the *what*
(a DB connection / HTTP session) is decoupled from the *how* (real driver vs.
mock, created only on first use).

### Value Object — structured results

`ValidationResult` is an immutable data holder giving every check a uniform
`(name, passed, detail)` shape, so reporting and pass/fail aggregation are written
once and work for all validators.

### Parser + Value Object — image references

`ImageRef` turns the messy Docker reference grammar into a clean object with
`reference` and `container_name` properties, so the engine never does ad-hoc
string surgery (and never mistakes a registry `:port` for a tag).

### Layered / ports-and-adapters

Validators (policy) sit on the engine (mechanism), which sits on the
`CommandExecutor` adapter to the outside world. The single seam is what keeps the
unit layer hermetic.

**One-line summary:** Template Method fixes the validation lifecycle, Strategy
makes each target a pluggable validator, and dependency injection at the I/O
boundaries makes every layer unit-testable in isolation.

## Testing strategy

Two layers prove different things.

| | Unit (`tests/unit/`) | Functional (`tests/*.robot`) |
|-|----------------------|------------------------------|
| What it proves | Logic: commands built, branches taken, results interpreted | End-to-end behaviour against a real container |
| Isolation | Every external seam mocked | Real MySQL / go-httpbin via Docker |
| Needs Docker? | No | Yes |
| Runner | pytest | Robot Framework |
| Speed | milliseconds | seconds |

**Unit layer.** pytest, scoped to `tests/unit/` by `pytest.ini`, run with
`--strict-markers`. Markers: `unit`, `docker_logic`, `mysql`, `api`, `edge`,
`regression`. The engine (`docker.py`, `image_ref.py`, `run_options.py`) and both
validators sit at or near 100% line coverage.

**Functional layer.** Robot Framework suites (`tests/mysql_tests.robot`,
`tests/rest_api_tests.robot`) with reusable keywords in `tests/resources/`. These
bring the container up and down **through the `ctf` engine itself** (`python -m
ctf --command run_container/rm_container ...`), so running a suite is also a real
end-to-end exercise of the engine against Docker. They are opt-in — a plain
`pytest` run never touches them.

## Adding a new validator

The `ContainerValidator` ABC is the extension point. To add a target (say Redis):

1. Subclass `ContainerValidator` in `src/ctf/validators/redis.py`; add a
   `RedisConfig` and an injectable client factory.
2. Implement `checks()` returning a list of `ValidationResult`. Optionally
   override `setup()` if the container needs specific `RunOptions` (ports/env).
3. Export it from `validators/__init__.py`.
4. Add mocked unit tests under `tests/unit/` (register a marker if desired) with
   the client factory mocked.
5. Optionally add a Robot functional suite that drives lifecycle through the CLI.

No change to the engine, the base class, or existing tests is required — that's
the Open/Closed principle in practice.

## Known limitations & future work

- **`ps_container` doesn't check the return code.** If the Docker daemon is
  down/absent, its error text can be read as "a container exists," so
  `run_container` may short-circuit to "already created." Hardening `ps` to treat
  a non-zero `docker ps` as an error is a clean follow-up.
- **CI.** A GitHub Actions workflow (unit job + Docker-enabled functional job) is
  planned but not yet added.
- **Shell quoting.** Command strings are assembled for `bash -c`; env values are
  shell-escaped, but the engine assumes otherwise well-formed image/tag inputs.
