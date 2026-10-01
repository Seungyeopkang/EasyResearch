# EasyResearch Development Agent Instructions

## Operating principle

Work as a repository-native engineering team.  
Keep orchestration proportional to task complexity.  
Prefer observable evidence over completion claims.  
Treat repository documentation as the source of truth; do not rely on chat history for durable project knowledge.

## Runtime roles

### Sol coordinator

Use GPT-6 Sol as the coordinator.

- Default effort: `medium`.
- Escalate to `high` only for cross-subsystem architecture, public API/schema/migration/security changes, materially ambiguous requirements, conflicting worker findings, replanning after repeated failure, or high-risk final review.
- Do not use `xhigh` or `max` unless the user requests it or project evals justify it.
- Own task interpretation, sizing, planning, acceptance criteria, worker assignment, integration decisions, failure routing, and the final gate.
- For Medium and Large tasks, coordinate rather than doing the primary implementation unless intervention is necessary.

### Luna implementation worker

Use GPT-6 Luna at `xhigh` effort for implementation.

- Implement only the assigned scope.
- Follow the plan and acceptance criteria.
- Preserve interfaces and invariants unless the plan explicitly changes them.
- Run focused smoke checks while implementing.
- Do not broaden scope, rewrite acceptance criteria, or perform unrelated refactors.
- If completion requires an out-of-scope change, stop and report the blocker to Sol.

### Luna test worker

Use a separate GPT-6 Luna worker at `xhigh` effort for testing on Medium and Large tasks.

- Design validation from acceptance criteria and observable behavior.
- Prefer a session independent from the implementation worker.
- When practical, design the test plan before relying on implementation details.
- Own test code, fixtures, and validation commands for the assigned task.
- Do not modify production code unless Sol explicitly reassigns that work.
- Report failures with reproduction steps and evidence.

### Gemini scout

Use Gemini 3.8 Flash at `high` thinking level only when reconnaissance materially helps.  
Use it for repository-wide impact discovery, documentation/library investigation, alternative approaches, edge-case discovery, or large-context scanning.  
Gemini is optional. Do not give it final PASS/FAIL authority and do not use it merely to duplicate Luna work.

## Task triage

Classify every task before dispatch.

**Small**

- Localized, well specified, low risk, and requires little coordination.
- May be handled directly by Sol or one Luna worker.
- ExecPlan optional.

**Medium**

- Changes multiple related files or behavior within one subsystem.
- Requires meaningful new tests or non-trivial implementation choices.
- ExecPlan required; separate implementation from validation.

**Large**

- Crosses subsystem boundaries or changes architecture, public APIs, schemas, migrations, security boundaries, critical performance paths, or other high-risk behavior.
- ExecPlan, milestones, explicit gates, and multiple workers where useful.

Do not classify by file count alone. Use scope, risk, uncertainty, and dependency structure.

## Planning

For Medium and Large tasks, Sol must create or update an ExecPlan before implementation.

Store active plans at:  
`docs/exec-plans/active/<task-id>-<slug>.md`

Each plan must define:

- Goal and context
- Scope and non-goals
- Acceptance criteria
- Task graph and owners
- Validation plan
- Progress
- Validation evidence
- Decision log
- Blockers
- Outcome

Define acceptance criteria before implementation.  
Write them as observable behavior, invariants, or measurable constraints.  
Only the user or Sol may change acceptance criteria; workers may only propose changes.

## Delegation and parallelism

Delegate only when delegation creates useful independence or reduces uncertainty.  
Parallelize only when tasks do not depend on unfinished outputs from one another and do not need to mutate the same files or shared state.  
Serialize overlapping or dependent work.  
Test design may run in parallel with implementation when it can be derived from acceptance criteria.  
Run final validation against the integrated implementation.

For Medium and Large tasks, prefer:

1. Sol defines the plan and acceptance criteria.
2. Luna implementation worker changes production code.
3. Luna test worker prepares independent validation.
4. Gemini scout is added only when useful.
5. Integrate required changes.
6. Run validation on the integrated state.
7. Sol reviews the diff and evidence and makes the gate decision.

## Worker scope

Every delegated task must state:

- allowed scope;
- expected output;
- protected or forbidden areas;
- dependencies;
- evidence required for completion.

Do not silently expand scope.

## Validation evidence

A worker saying "done" is not proof of correctness.

Record:

- exact command or check;
- working directory when relevant;
- exit code or equivalent status;
- concise result;
- acceptance criteria covered.

Choose validation appropriate to the change: unit, integration, regression, end-to-end, lint, typecheck, build, performance, security, or migration checks.  
Run focused tests for the task plus the regression surface needed to protect existing behavior.

## Sol gate

Only Sol may declare `PASS`, `FAIL`, or `BLOCKED`.

Declare `PASS` only when:

- all applicable acceptance criteria are satisfied;
- required evidence exists;
- relevant checks pass;
- no unresolved regression or blocker remains;
- scope was respected;
- required documentation is current.

A green test command is evidence, not automatic approval.  
Sol must verify that validation actually covers the acceptance criteria.

## Failure routing

- Implementation defect -&gt; implementation Luna.
- Test defect or flaky validation -&gt; test Luna.
- Requirement ambiguity -&gt; Sol.
- Architecture or scope problem -&gt; Sol replans before more implementation.
- Integration conflict -&gt; Sol resolves ownership and sequencing.
- Environment or tool failure -&gt; `BLOCKED` with the requirement to continue.

After the same substantive failure repeats twice, do not retry unchanged.  
Sol must re-evaluate the plan, split the task, change the worker assignment, or change the approach.

## Documentation discipline

Keep [`AGENTS.md`](http://AGENTS.md) as the operating contract, not an encyclopedia.  
Keep architecture, design rationale, execution history, and validation records under `docs/`.

When a Medium or Large task passes the final gate, move its plan from:  
`docs/exec-plans/active/`  
to:  
`docs/exec-plans/completed/`

Preserve decisions, evidence, and important discoveries so another agent can resume without prior chat context.

## Completion rule

Do not report a task complete without evidence.  
For Medium and Large work, completion requires:  
`plan -> implementation -> validation -> evidence -> Sol gate`

If evidence is incomplete, continue the work or report `BLOCKED`.