# EasyResearch Development Orchestration

## Purpose

This document defines the detailed operating procedure for multi-agent software development in the EasyResearch repository.

Keep orchestration proportional to task complexity.
Use repository state, tests, and recorded evidence as the basis for decisions.
Do not treat agent confidence or a completion message as proof of correctness.

This file describes **how work flows between roles**.
It does not redefine the role and model policy in `AGENTS.md`, and it does not redefine the ExecPlan format in `.agent/PLANS.md`.

## Sources of Truth

Use each repository document for its own responsibility:

- `AGENTS.md` — role authority, model policy, task sizing, delegation rules, and final gate ownership.
- `.agent/PLANS.md` — ExecPlan structure, maintenance rules, and planning requirements.
- `docs/development/orchestration.md` — detailed execution, handoff, integration, validation, and failure-routing procedure.
- `docs/exec-plans/active/*.md` — task-specific living plans for active Medium and Large work.
- `docs/exec-plans/completed/*.md` — completed execution history and retained evidence.

If two documents appear to conflict, do not silently choose an interpretation.
Follow the document that is authoritative for that subject and escalate unresolved ambiguity to the Sol coordinator.

## Core Control Model

Use a star topology.

The Sol coordinator is the control plane.
Workers do not independently redefine the task, acceptance criteria, ownership, or completion state.

Normal flow:

`User -> Sol -> workers -> integrated state -> validation evidence -> Sol gate`

Worker-to-worker communication may be used for factual coordination, but decisions that change scope, requirements, ownership, sequencing, or acceptance criteria must return to Sol.

Avoid free-form multi-agent group chat as the primary control mechanism.

## Development States

Use the following states for non-trivial work:

`INTAKE -> TRIAGE -> PLAN -> DISPATCH -> EXECUTE -> INTEGRATE -> VALIDATE -> GATE`

The gate produces one of:

- `PASS` — the task satisfies the applicable acceptance criteria and completion requirements.
- `FAIL` — the task is actionable but does not yet satisfy completion requirements.
- `BLOCKED` — progress requires an unavailable dependency, access, environment change, user decision, or other external resolution.

A failed task returns to the appropriate earlier state.
A blocked task remains blocked until its stated resume condition is satisfied.

Small tasks may omit `PLAN` and multi-worker `DISPATCH` when the overhead would exceed the value.

## 1. Intake

Sol receives the user request and determines the intended outcome before assigning work.

At intake, identify:

- requested behavior or deliverable;
- user-visible constraints;
- explicit non-goals;
- relevant repository area;
- uncertainty that must be resolved;
- potentially destructive, security-sensitive, or irreversible operations.

Do not start implementation while the requested outcome is materially ambiguous.

Resolve questions from the repository first when possible.
Ask the user only for decisions or information that cannot be safely derived from repository state, documentation, or the task itself.

## 2. Triage

Sol classifies the task according to `AGENTS.md`.

Do not use file count as the primary classifier.
Use scope, risk, uncertainty, dependency depth, regression surface, and coordination requirements.

### Small

Use the minimum viable process.

Typical flow:

`Sol or Luna -> focused validation -> Sol gate`

An ExecPlan is optional.

### Medium

Create an ExecPlan.
Separate implementation responsibility from validation responsibility.

Typical flow:

`Sol plan -> Luna implementation + Luna test design -> integration -> validation -> Sol gate`

### Large

Create an ExecPlan with milestones and explicit dependencies.
Use multiple workers only where decomposition provides real independence or reduces uncertainty.

Typical flow:

`Sol plan -> staged workers -> milestone integration/validation -> final integration -> final validation -> Sol gate`

## 3. Planning

For Medium and Large tasks, Sol creates or updates an ExecPlan under:

`docs/exec-plans/active/<task-id>-<slug>.md`

Follow `.agent/PLANS.md`.

Before dispatch, the plan must be sufficiently decision-complete for workers to execute without inventing architecture or silently changing requirements.

At minimum, planning must establish:

- intended outcome;
- scope and non-goals;
- acceptance criteria;
- protected interfaces or invariants;
- task dependencies;
- worker ownership;
- validation intent;
- known blockers and assumptions.

Acceptance criteria are defined before implementation.

Workers may propose changes to acceptance criteria, but only the user or Sol may approve them.

## 4. Task Contracts

Every delegated task must have an explicit task contract.

A task contract must state:

**Goal**
What the worker must produce.

**Inputs**
Which plan, files, interfaces, evidence, or prior outputs the worker should use.

**Allowed scope**
Files, modules, tests, or other areas the worker may modify or inspect.

**Protected scope**
Files, interfaces, schemas, behaviors, or systems the worker must not change without escalation.

**Dependencies**
What must already be true before the task can complete.

**Expected output**
Code, tests, report, findings, patch, evidence, or another concrete artifact.

**Required evidence**
What the worker must return so Sol can evaluate the result.

A worker must stop and escalate when completing the task requires a material change outside the contract.

Do not silently expand scope.

## 5. Implementation Worker Procedure

The implementation worker changes production code within the assigned scope.

The implementation worker must:

- read the relevant ExecPlan and repository documentation first;
- preserve protected interfaces and invariants;
- keep changes focused on the assigned task;
- avoid unrelated cleanup and opportunistic refactors;
- run focused smoke checks when useful;
- report discoveries that affect scope, architecture, or acceptance criteria;
- return a concise implementation summary and evidence.

The implementation worker must not:

- declare the overall task complete;
- change acceptance criteria;
- weaken tests to make a failure disappear;
- silently modify protected areas;
- absorb unrelated defects into the task without approval.

If the implementation reveals a design problem, return the issue to Sol rather than inventing a new architecture locally.

## 6. Test Worker Procedure

For Medium and Large tasks, use a test worker separate from the primary implementation worker whenever practical.

The test worker derives validation from:

1. acceptance criteria;
2. observable behavior and invariants;
3. relevant repository test conventions;
4. the integrated implementation when final execution begins.

Prefer designing the validation approach before depending heavily on implementation internals.
This reduces the chance that the test reproduces the same assumptions as the implementation.

The test worker may:

- inspect production code;
- add or modify test code and fixtures within assigned scope;
- define exact validation commands;
- reproduce failures;
- run focused and regression checks;
- report missing coverage.

The test worker must not silently repair production code.
If production code is defective, report the failure to Sol with reproduction evidence.

Final validation must run against the integrated state, not only against an isolated worker branch or partial implementation.

## 7. Gemini Scout Procedure

Gemini is an optional reconnaissance worker.

Use a scout when broad reading or independent exploration materially improves the plan or reduces uncertainty.

Good scout tasks include:

- repository-wide impact discovery;
- dependency and call-path mapping;
- documentation or library investigation;
- alternative implementation approaches;
- edge-case discovery;
- large-context scanning;
- identifying potentially affected tests or interfaces.

A scout normally returns findings, not production changes.

Do not invoke a scout merely to duplicate work already assigned to Luna.
Do not use scout output as final approval.
Sol decides how, or whether, scout findings change the plan.

## 8. Parallelism

Parallelize only work that is meaningfully independent.

Parallel work is appropriate when:

- tasks do not require unfinished outputs from each other;
- tasks do not need to mutate the same files or shared state;
- integration boundaries are clear;
- each worker can produce independently useful output.

Serialize work when:

- one task depends on another task's design or output;
- workers would modify overlapping files or shared mutable state;
- the task requires a single coherent migration or schema change;
- concurrent work would create ambiguous ownership.

Test design may proceed in parallel with implementation when acceptance criteria provide enough information.

Final validation is serialized after integration.

Do not spawn additional workers only to increase apparent parallelism.

## 9. Integration

Sol owns integration decisions.

Integration means producing the repository state that will actually be validated and considered for completion.

Before final validation:

- confirm that required worker outputs are present;
- resolve overlapping changes deliberately;
- verify that scope boundaries were respected;
- ensure the ExecPlan reflects material decisions and discoveries;
- ensure tests target the integrated behavior.

When Orca provides isolated worktrees, treat each worker worktree as an execution boundary.
Do not assume uncommitted files in one worktree are visible to another.

Use explicit commits, patches, merges, or another deliberate transfer mechanism when work must cross worktree boundaries.

Do not validate a state different from the state that Sol will gate.

## 10. Validation Strategy

Sol owns **what must be demonstrated**.
The test worker refines **how to demonstrate it**.

Select only the validation surfaces relevant to the task and its regression risk.

Possible validation surfaces include:

- unit tests;
- integration tests;
- regression tests;
- end-to-end tests;
- lint;
- static analysis;
- type checking;
- build checks;
- performance checks;
- security checks;
- migration checks;
- manual observable behavior when automation is not practical.

Do not run every possible check by default.
Use the smallest sufficient validation set plus the regression surface necessary to protect existing behavior.

For high-risk changes, expand validation explicitly in the ExecPlan.

## 11. Evidence Standard

A worker message such as "done", "fixed", or "tests pass" is not sufficient evidence.

For each material validation result, record:

- exact command or check;
- working directory when relevant;
- exit code or equivalent status;
- concise observed result;
- acceptance criteria covered;
- relevant failure output when the check does not pass.

Example:

```text
Command: pytest tests/retrieval -q
Working directory: <repo-root>
Exit: 0
Result: 47 passed
Covers: AC-1, AC-2, AC-4
```

Evidence should be concise but reproducible.

When a validation command passes but does not actually exercise the required behavior, treat the criterion as unverified.

## 12. Sol Gate

Only Sol may assign the final task state: `PASS`, `FAIL`, or `BLOCKED`.

Sol reviews:

- current ExecPlan when required;
- integrated diff or repository state;
- acceptance criteria;
- implementation notes;
- validation commands and results;
- unresolved discoveries or blockers;
- relevant documentation updates.

Declare `PASS` only when:

- every applicable acceptance criterion is satisfied;
- required validation evidence exists;
- relevant checks pass;
- the tested state matches the integrated state;
- no unresolved regression or blocker remains;
- protected scope was respected;
- required repository documentation is current.

A green test suite is evidence, not automatic approval.

If coverage is inadequate, return the work for additional validation even if all executed commands are green.

## 13. Failure Routing

Route failures by cause.

**Implementation defect**
Return to the implementation worker with reproduction evidence and the affected acceptance criterion.

**Test defect or flaky validation**
Return to the test worker to repair or stabilize validation without weakening the intended criterion.

**Requirement ambiguity**
Return to Sol.
Sol resolves from repository/user context or escalates to the user.

**Architecture or scope defect**
Stop implementation.
Sol updates the plan before new implementation work begins.

**Integration conflict**
Sol resolves ownership, ordering, and the integration method.

**Environment, access, or tool failure**
Mark `BLOCKED`.
Record the exact condition required to resume.

**Scout discovery**
Sol determines whether the finding is relevant.
If it changes scope or design, update the ExecPlan before acting on it.

## 14. Repeated Failure Rule

Do not repeat the same substantive repair loop indefinitely.

After the same substantive failure occurs twice:

1. stop unchanged retries;
2. return control to Sol;
3. re-evaluate the assumption, plan, decomposition, or worker assignment;
4. split the task further or change the approach when appropriate;
5. update the ExecPlan before resuming if the task is Medium or Large.

Repeated failure is a planning signal, not only an implementation problem.

## 15. Blocked Work

Use `BLOCKED` when the next correct action depends on something unavailable to the current team.

Examples include:

- missing credentials or permission;
- unavailable external service;
- unresolved product decision;
- destructive action requiring user approval;
- missing dependency or environment;
- contradictory repository requirements that Sol cannot safely reconcile.

A blocked report must include:

- what is blocked;
- evidence for the blocker;
- what has already been tried;
- the exact condition or decision required to resume;
- whether any safe independent work can continue.

Do not disguise blocked work as partial completion.

## 16. Human Escalation

Escalate to the user when a decision is materially product-defining, irreversible, destructive, security-sensitive, or cannot be resolved from repository context.

Examples include:

- changing externally visible product behavior without an existing specification;
- destructive data or schema operations without an approved recovery path;
- choosing between materially different product requirements;
- requesting credentials, secrets, purchases, or external permissions;
- overriding explicit repository policy.

Do not ask the user to resolve ordinary implementation details that Sol can safely decide.

## 17. Documentation Updates

Repository knowledge should survive the current agent session.

For Medium and Large work, keep the active ExecPlan synchronized with execution.

Record material:

- decisions;
- discoveries;
- ownership changes;
- validation evidence;
- blockers;
- scope changes;
- final outcome.

When Sol declares `PASS`, move the ExecPlan from:

`docs/exec-plans/active/`

to:

`docs/exec-plans/completed/`

Do not move a plan to `completed` on `FAIL` or `BLOCKED`.

Update long-lived architecture or development documentation when the completed change alters durable repository behavior or conventions.

## 18. Cost and Orchestration Discipline

Use the minimum coordination necessary to reach a reliable result.

Do not use multiple workers when one focused worker plus validation is sufficient.

Prefer:

- Small: Sol or one Luna, focused validation, Sol gate.
- Medium: Sol plan, implementation Luna, test Luna, Sol gate.
- Large: Sol plan with milestones, multiple independent workers where useful, test worker, optional Gemini scout, staged integration, Sol gate.

Gemini remains conditional.
Additional implementation workers remain conditional.
More agents are not automatically better.

Spend coordinator reasoning on ambiguity, architecture, integration, failure analysis, and final judgment rather than routine implementation.

## 19. Anti-Patterns

Avoid the following:

- worker self-approval;
- acceptance criteria written after implementation to match the result;
- multiple workers editing the same mutable area without an integration plan;
- Gemini or another worker acting as the final judge;
- tests weakened solely to obtain a green result;
- unrecorded scope expansion;
- treating chat history as the only source of project knowledge;
- continuing identical retries after repeated failure;
- marking a task complete without reproducible evidence;
- creating extra workers when delegation adds no useful independence.

## 20. Default Workflow

Use this default for Medium work:

```text
User request
    |
    v
Sol intake and triage
    |
    v
ExecPlan + acceptance criteria
    |
    +--------------------+
    |                    |
    v                    v
Luna implementation   Luna test design
    |                    |
    +---------+----------+
              |
              v
          Integration
              |
              v
       Final test execution
              |
              v
       Validation evidence
              |
              v
           Sol gate
        /      |       \
      PASS    FAIL    BLOCKED
       |        |        |
       v        v        v
   complete   route    await/resume
             + retest
```

Add Gemini scout only when reconnaissance is expected to reduce uncertainty or expose useful context.

## 21. Large-Task Milestone Workflow

For Large tasks, gate milestone transitions rather than waiting until the end to discover integration failure.

Recommended pattern:

```text
Plan
  |
Milestone 1 -> integrate -> focused validation
  |
Milestone 2 -> integrate -> focused validation
  |
Milestone N -> integrate -> focused validation
  |
Final integrated validation
  |
Sol final gate
```

A milestone check is not the final task gate.
Only the final integrated state may receive final `PASS`.

## 22. Completion

For Medium and Large work, the minimum completion chain is:

`plan -> implementation -> integration -> validation -> evidence -> Sol gate`

Completion is not a worker status.
Completion is a Sol decision supported by repository-visible evidence.
