# Add a development structure health check

This ExecPlan is a living document maintained under `.agent/PLANS.md`.

## Purpose / Big Picture

Contributors can run one command to confirm that the repository contains the development orchestration files and directories required by its operating policy. This task also exercises the Medium workflow with separate implementation and validation workers under Sol coordination.

## Progress

- [x] (2026-10-01 03:18Z) Inspected the repository, read its policies, verified Orca readiness, and defined acceptance criteria before implementation.
- [x] (2026-10-01 03:19Z) Dispatched separate Luna implementation and test workers through Orca Run `run_4640117878fb`.
- [x] (2026-10-01 03:26Z) Reviewed the two worker files in the shared worktree and ran final validation on that integrated state.
- [x] (2026-10-01 03:27Z) Recorded evidence and made the Sol PASS gate decision; move this plan to completed.

## Surprises & Discoveries

- The repository currently contains planning documents and no application or test framework. `python --version` returned Python 3.12.7 in the current worktree.
- An unrelated untracked `.agents/` directory was present at intake. Leave it untouched.

## Decision Log

- Decision: Implement a Python standard library CLI at `scripts/check_development_structure.py` with an optional `--root` directory argument. Date / decision maker: 2026-10-01 / Sol. Rationale: The repository has no language toolchain or test framework; Python is available, and root injection enables behavior-based temporary fixture tests without changing the real repository.
- Decision: Use separate Orca Luna workers in the current worktree, with production script ownership and test file ownership separated. Date / decision maker: 2026-10-01 / Sol. Rationale: The files do not overlap, and final validation will run on the integrated worktree.

## Outcomes & Retrospective

Delivered a read-only health-check CLI and separate behavior-based tests. AC-1 through AC-5 are satisfied by the evidence below. No product code changed. The independent workers exercised a real Orca Run with distinct task ownership, accepted completion messages, and terminal accounting. The implementation terminal was retained by Orca with reason `user_takeover`; the test terminal was released. No follow-up work is required for this task.

## Context and Orientation

`AGENTS.md`, `.agent/PLANS.md`, and `docs/development/orchestration.md` define repository development policy. `docs/exec-plans/active/` and `docs/exec-plans/completed/` hold living and finished plans. The current repository has these paths, with `.gitkeep` in both plan directories. There is no existing check script or test suite. The health check concerns path existence and type only, not document contents.

## Scope and Non-Goals

Add `scripts/check_development_structure.py` and a focused test file under `tests/`. The test worker may add test-only fixtures under `tests/` if needed. Do not change `src/`, the required policy documents, unrelated files, or the untracked `.agents/` directory. Do not add dependencies or a general purpose project scaffold.

## Acceptance Criteria

- AC-1: Running `python scripts/check_development_structure.py` from any current directory checks the script's repository and exits 0 when all five required paths exist with the right types. It prints a concise success result.
- AC-2: The check requires regular files at `AGENTS.md`, `.agent/PLANS.md`, and `docs/development/orchestration.md`, and directories at `docs/exec-plans/active/` and `docs/exec-plans/completed/`. Extra paths do not affect the result.
- AC-3: When any required path is missing or has the wrong type, the check exits nonzero and identifies every offending path with the expected type. It does not create or repair paths.
- AC-4: `--root <directory>` checks that directory with the same rules, enabling isolated validation.
- AC-5: Tests derived from AC-1 through AC-4 pass on the integrated state, the real repository health check passes, and no file under `src/` changes.

## Task Graph and Ownership

Sol owns this plan, criteria, integration, final evidence, and final gate. The Luna implementation worker owns only `scripts/check_development_structure.py` and focused smoke evidence. A separate Luna test worker owns only `tests/test_development_structure.py` and test-only fixtures, derives cases from AC-1 through AC-4, and reports validation commands. The two workers may proceed concurrently because their file ownership does not overlap. Sol runs final validation after both outputs are present.

## Plan of Work

The script resolves its default repository root from its own location, not the process current directory. It checks the three file paths with `Path.is_file()` and the two directory paths with `Path.is_dir()`. It accepts `--root` through `argparse`. It reports every failed item and returns a nonzero code for a failed check. It must be read-only. The test worker uses temporary roots and subprocess execution to observe exit status and output for complete, missing, wrong-type, and alternate-root cases. The tests also verify the real repository command from another current directory.

## Concrete Steps

From the repository root, run `python scripts/check_development_structure.py` and `python -m unittest discover -s tests -p "test_development_structure.py" -v`. Sol will inspect `git diff --stat`, `git diff -- scripts tests`, and `git status --short` before gating. Running the script again is safe because it only reads paths. Temporary fixture directories are managed by the tests.

## Validation and Acceptance

The test worker must cover valid and invalid roots, all five path/type requirements, and the alternate root option. Sol will run the test command and the real repository check after integration, recording command, working directory, exit code, concise result, and covered criteria here. A clean `src/` diff covers AC-5's scope constraint.

Final integrated evidence, working directory `C:\Users\user\orca\workspaces\EasyResearch\EasyResearch`:

- `python -B -m unittest discover -s tests -p test_development_structure.py -v` exited 0, six tests passed. Covers AC-1 through AC-4, including all five missing and wrong-type variants, all-errors reporting, extra paths, alternate root, execution from another current directory, and read-only behavior.
- `python -B scripts/check_development_structure.py` exited 0 and printed `Development structure check passed (5 required paths).` Covers AC-1 and AC-2 against the real repository.
- After moving this plan to `docs/exec-plans/completed/`, `python -B scripts/check_development_structure.py` again exited 0 with the same five-path pass result. `Test-Path` confirmed the completed plan exists and the active copy does not.
- `git diff -- src/` exited 0 with no output. `git status --short --untracked-files=all` showed only the pre-existing `.agents/skills/.gitkeep`, this plan, the script, and the test file after generated cache cleanup. Covers AC-5's scope constraint.
- Sol reviewed both new files. The implementation uses `Path(__file__).resolve().parent.parent` for the default root, `is_file()` and `is_dir()` for the required types, collects every failure, and returns 1 without mutations. The tests exercise CLI exit status and output via subprocess and temporary fixture roots.

## Idempotence and Recovery

The check is read-only. A failed test can be rerun without cleanup beyond test-managed temporary directories. Worker changes to distinct files can be reviewed independently; Sol will route implementation defects to the implementation worker and test defects to the test worker.

## Interfaces and Dependencies

Python 3.12 standard library is the only runtime dependency observed in this workspace. The CLI exit code is the automation interface: 0 means all required paths have the expected type; nonzero means at least one path is invalid. `--root` accepts a filesystem directory for isolated checks.

## Artifacts and Notes

Orca Run `run_4640117878fb`; implementation Task `task_f7a0cb33cd59`, Dispatch `ctx_374ae3f8b619`; test Task `task_71fd5a0adcc2`, Dispatch `ctx_a4a47090dd38`. Both launch receipts reported effective `gpt-6-luna` at `xhigh`, ready state, and observed turn start.

Both workers sent accepted `worker_done` messages with `succeeded` outcomes and only their assigned file in `filesModified`. Orca released the test terminal and retained the implementation terminal with reason `user_takeover`; `worker-list --run run_4640117878fb --terminal-state reclaimable --json` returned zero reclaimable terminals. Sol gate: **PASS** on 2026-10-01.

## Revision Note

Initial plan written before implementation on 2026-10-01.
