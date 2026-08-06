# Unit Test Layer — Container Validation Core

Fast, hermetic unit tests for the container-validation engine
(`utils/docker_utils.py` and `utils/execute_utils.py`). **No Docker daemon,
no network, no real container** — the whole suite runs in well under a second.

This is the *unit* layer of a two-layer strategy:

| Layer | Location | What it proves | Needs a container? |
|-------|----------|----------------|--------------------|
| **Unit** (this dir) | `tests/unit/` | The validator builds the right commands and takes the right branch, in isolation | No — the subprocess seam is mocked |
| **Functional/Integration** | `tests/*.robot` | The tool works end-to-end against a live container | Yes |

## The isolation seam

The only place this code touches the outside world is
`Utils.execute_commands()` — the wrapper around `subprocess.Popen`. Every unit
test replaces that single method with a mock (see `conftest.py::docker`), so the
`Docker` class's *logic* is tested deterministically:

```
Docker.query/ps/pull/run/teardown  ──►  Utils.execute_commands  ──►  subprocess
                                        └──────── mocked here ───────┘
```

`test_executor.py` then drops one layer lower and mocks `subprocess.Popen`
itself, proving the wrapper decodes stdout and surfaces the return code without
launching a shell.

## Techniques demonstrated

| Technique | Where |
|-----------|-------|
| Mock injection / dependency isolation | `conftest.py::docker` fixture, used by every test |
| Mock `.return_value` vs `.side_effect` sequencing | `TestPullContainer`, `TestRunContainer` (multi-call flows) |
| Exact command-string assertions | `TestQueryContainer`, `TestPsContainer`, `TestTeardownContainer` |
| `@pytest.mark.parametrize` | `test_parametrized_names_and_tags`, `test_image_ref.py::test_parse_variants` |
| `pytest.raises` (input validation) | `test_image_ref.py` (empty / malformed references) |
| `monkeypatch` of a module-level dependency | `test_executor.py::fake_popen` (patches `subprocess.Popen`, `sys.stdin`) |
| Boundary / edge cases | tests marked `edge` (unexpected return codes, bad references) |
| Regression pinning | tests marked `regression` (see bugs below) |
| Call-count / short-circuit assertions | "already pulled" / "already created" paths |
| Coverage gating | 100% line coverage on `ctf/engine/docker.py` |

## Bugs these tests found (and fixed)

Writing (and later running) the tests surfaced six real defects in the engine.
Each fix is commented in `ctf/engine/docker.py` and pinned by a
`@pytest.mark.regression` test.

1. **`pull_container` — dead branch + unbound `message`.** `if result == []`
   compared a *stripped string* to a list, so it was never true; and when the
   image name matched but the requested *tag* differed, every branch was
   skipped and `message` was returned unbound (`UnboundLocalError`). Fixed to
   short-circuit only when repository **and** tag are present, else pull.
   → `test_tag_mismatch_triggers_pull_not_unbound_message`

2. **`run_container` — unbound `message` on the already-created path.** The
   "already created" branch only logged, then returned an unset `message`.
   → `test_already_created_returns_message`

3. **Fabricated / broken image references.** The old code invented a
   `registry/name` reference (`--image mysql` → `docker pull mysql/mysql`, which
   does not exist) and `run_container` blew up with `IndexError` on any bare
   official image. Replaced with a proper `ImageRef` parser (`ctf/engine/image_ref.py`)
   that uses the reference verbatim — so `mysql`, `bitnami/mysql`, and
   `reg.io:5000/team/app:1.2` all work.
   → `test_pulls_when_image_absent`, `test_pulls_namespaced_image_verbatim`,
     `test_bare_official_image_runs_without_registry`, `test_image_ref.py`

4. **`teardown_container` — unbound `message` on an unexpected return code.**
   A code other than 0/1 fell through with no `message`. Now defaults to
   "Something else happened".
   → `test_unexpected_return_code_still_returns_message`

5. **`copy_file` — `AttributeError` on `self.workdir`.** The copy-out branch
   referenced an attribute that was never initialised. Now set in `__init__`.
   → `test_copy_out_of_container_uses_workdir`

6. **Registry port mistaken for a tag.** A naive `split(':')` would read the
   `5000` in `reg.io:5000/app` as a tag. `ImageRef` only treats a `:` in the
   final path segment as a tag separator.
   → `test_image_ref.py::test_parse_variants`

## Running

```bash
pip install -r requirements-dev.txt        # from repo root

# all unit tests
pytest

# with coverage on the engine + validators
pytest --cov=ctf --cov-report=term-missing

# a single marker
pytest -m mysql               # just the MySQLValidator tests
pytest -m regression
pytest -m "unit and not mysql"
```

`pytest.ini` (repo root) scopes collection to `tests/unit/`, runs with
`--strict-markers` (an unregistered marker fails the run), and registers the
`unit`, `docker_logic`, `mysql`, `edge` and `regression` markers.

> Note: `ctf/engine/executor.py` reports partial coverage — its unused
> `execute_workload()` helper and an unreachable dead-code loop are
> intentionally left untested rather than covered by artificial tests. The
> validator core (`docker_utils.py`) is at 100%.
