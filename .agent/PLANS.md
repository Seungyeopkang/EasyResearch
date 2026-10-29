# EasyResearch Execution Plans (ExecPlans)

This file defines how to write and maintain an ExecPlan for EasyResearch.

An ExecPlan is a self-contained, living implementation specification that

allows an agent with no prior chat context to understand, execute, validate,

and resume a non-trivial engineering task.

Agent roles, model assignments, task sizing, delegation policy, and final

PASS/FAIL authority are defined in [`AGENTS.md`](http://AGENTS.md). This file does not redefine

those policies. It defines only how ExecPlans are authored and maintained.

## When to Use an ExecPlan

Follow the task classification in [`AGENTS.md`](http://AGENTS.md).

An ExecPlan is required for every Medium or Large task.

An ExecPlan is optional for a Small task unless the coordinator determines

that the task has unusual risk, ambiguity, or coordination requirements.

Store active ExecPlans under:

`docs/exec-plans/active/<task-id>-<slug>.md`

After the final gate passes, move the plan to:

`docs/exec-plans/completed/<task-id>-<slug>.md`

## How to Use This File

Before authoring an ExecPlan, read this file in full.

When authoring a plan, inspect the repository first. Resolve questions that

can be answered from the working tree, source code, tests, configuration, or

repository documentation before treating them as assumptions.

When executing a plan, keep the plan synchronized with reality. Update it as

work progresses, discoveries occur, ownership changes, validation runs, or

design decisions change.

Do not rely on prior chat history. A new agent should be able to continue the

task using the current repository and the ExecPlan alone.

## Non-Negotiable Requirements

Every ExecPlan must be self-contained.

Every ExecPlan must remain a living document throughout execution.

Every ExecPlan must describe an observable working outcome rather than merely

a set of code edits.

Every ExecPlan must define enough repository context for a contributor with no

prior knowledge of the task to continue the work.

Every ExecPlan must state explicit acceptance criteria and the validation

needed to demonstrate them.

Every ExecPlan must preserve evidence for important validation results and

design decisions.

Do not leave substantive implementation decisions to a downstream worker when

they can be resolved during planning.

## Writing Style

Write in clear, direct prose.

Prefer explanations of intent, behavior, and reasoning over large checklists

or tables.

Use repository-relative paths and stable names for files, modules, functions,

interfaces, and commands.

Define non-obvious terminology when first used.

State assumptions explicitly.

Do not refer to information that exists only in chat history.

The `Progress` section is the primary checklist. Other sections should remain

prose-first unless a short list is clearer.

## Plan Before Mutation

Before implementation begins:

1. Inspect the relevant repository state.

2. Define the intended outcome.

3. Define scope and non-goals.

4. Resolve material implementation decisions.

5. Define acceptance criteria.

6. Define the task graph and ownership.

7. Define the validation strategy.

The plan should be sufficiently decision-complete that implementation workers

do not need to invent architecture or silently redefine requirements.

If an unresolved question is genuinely a product or user decision, record it

as a blocker and escalate according to [`AGENTS.md`](http://AGENTS.md).

## Milestones

Use milestones for work that benefits from staged implementation.

Each milestone must describe:

- what new behavior or capability will exist;

- what work is required to produce it;

- how it will be validated;

- what observable result demonstrates completion.

Each milestone should be independently verifiable and should move the system

toward the final outcome.

Milestones describe the implementation story. `Progress` records the actual

execution state. Keep both consistent.

## Parallel Work

The ExecPlan may assign independent tasks to multiple workers when permitted by

[`AGENTS.md`](http://AGENTS.md).

Describe dependencies explicitly.

Do not plan concurrent mutation of the same files or shared state unless the

plan also defines a safe integration strategy.

Test design may proceed in parallel with implementation when the acceptance

criteria provide enough information to design the tests independently.

Final validation must run against the integrated state.

## Required Living Sections

Every ExecPlan must contain and maintain the following sections.

### Progress

Use timestamped checkboxes.

Record completed, incomplete, and partially completed work.

Update this section whenever work pauses, ownership changes materially, a

milestone completes, or the execution path changes.

### Surprises &amp; Discoveries

Record unexpected repository behavior, bugs, dependency behavior, performance

results, constraints, or other discoveries that materially affect the work.

Include concise evidence when useful.

### Decision Log

Record material implementation or planning decisions.

For each decision, record:

- the decision;

- the rationale;

- the date;

- the responsible decision maker.

If the execution path changes, record why.

### Outcomes &amp; Retrospective

At completion, summarize:

- what was delivered;

- which acceptance criteria were satisfied;

- remaining gaps or follow-up work;

- important lessons or tradeoffs discovered during execution.

## Validation and Evidence

Validation is mandatory.

The plan must state what needs to be validated. The test worker may refine how

to validate it, consistent with [`AGENTS.md`](http://AGENTS.md).

Use the validation surfaces appropriate to the change, such as unit tests,

integration tests, regression tests, end-to-end scenarios, lint, type checking,

build checks, performance checks, security checks, or migration checks.

For important validation runs, record:

- the command or check;

- the working directory when relevant;

- the exit status or equivalent;

- the concise observed result;

- the acceptance criteria covered.

Do not treat compilation or a green test command as sufficient by itself when

the acceptance criteria require observable behavior not covered by that check.

Validation evidence informs the Sol gate defined in [`AGENTS.md`](http://AGENTS.md); it does not

replace that gate.

## Scope Changes and Blockers

If execution reveals that the current scope is insufficient, do not silently

expand it.

Record the discovery and proposed change in the ExecPlan and escalate it

according to [`AGENTS.md`](http://AGENTS.md).

If scope changes are approved, update all affected sections so the plan remains

coherent and self-contained.

If execution cannot continue because of an environment, dependency, access, or

product decision, record the blocker and the exact condition required to

resume.

## Safe Execution and Recovery

Prefer incremental, testable, and reversible changes.

When an operation is risky, destructive, or difficult to repeat, describe the

safe execution procedure and a recovery or rollback path.

When a prototype or spike is used to reduce uncertainty, state:

- the question it is intended to answer;

- how to run it;

- what evidence determines whether the approach is accepted or discarded;

- how temporary prototype code will be removed or promoted.

## ExecPlan Skeleton

# &lt;Short, action-oriented title&gt;

This ExecPlan is a living document and must be maintained in accordance with

`.agent/[PLANS.md](http://PLANS.md)`.

## Purpose / Big Picture

Explain what becomes possible after this work and how a user or developer can

observe the result.

## Progress

- \[ \] (YYYY-MM-DD HH:MMZ) Initial repository investigation.

- \[ \] ...

- \[ \] ...

## Surprises &amp; Discoveries

- Observation:

  Evidence:

## Decision Log

- Decision:

  Rationale:

  Date / Decision maker:

## Outcomes &amp; Retrospective

Describe the final outcome, remaining gaps, and lessons learned.

## Context and Orientation

Describe the current repository state relevant to this task.

Name important files, modules, interfaces, services, and tests using

repository-relative paths.

Define terminology needed to understand the plan.

## Scope and Non-Goals

Describe what this plan changes and what it intentionally does not change.

Identify protected interfaces, files, or behaviors when relevant.

## Acceptance Criteria

Describe success as observable behavior, invariants, or measurable outcomes.

Acceptance criteria must be defined before implementation begins and may be

changed only according to [`AGENTS.md`](http://AGENTS.md).

## Task Graph and Ownership

Describe the implementation and validation tasks, their dependencies, and their

assigned roles.

Use the agent roles defined in [`AGENTS.md`](http://AGENTS.md); do not redefine model policy here.

Identify which tasks can run in parallel and which must be serialized.

## Plan of Work

Describe the implementation sequence in enough detail that the assigned worker

does not need to invent unresolved design decisions.

Name the relevant files, modules, functions, or interfaces and explain the

intended changes.

## Milestones

For each milestone, explain:

- the capability produced;

- the work required;

- the validation to run;

- the observable result expected.

Omit this section only when the task is simple enough that milestones provide

no useful structure.

## Concrete Steps

State the exact commands and working directories required to implement,

inspect, build, run, or validate the change.

Include concise expected results where they help distinguish success from

failure.

## Validation and Acceptance

Map validation back to the acceptance criteria.

State the required test or verification commands and what successful output or

behavior should be observed.

Record final validation evidence here or in the Progress section as execution

proceeds.

## Idempotence and Recovery

Explain how interrupted or failed steps can be safely retried.

Describe rollback or recovery procedures for risky operations.

## Interfaces and Dependencies

Describe any interfaces, dependencies, schemas, configuration contracts, or

public behaviors that must exist when the work is complete.

## Artifacts and Notes

Preserve concise evidence that materially helps future contributors understand

or verify the work.

## Revision Note

When the plan changes materially, record what changed and why.