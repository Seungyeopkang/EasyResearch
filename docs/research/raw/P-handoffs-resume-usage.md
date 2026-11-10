# P. Stage handoffs, long-run resumption, and usage budget (Holes C and D)

- Date: 2026-11-10
- Scope: ExecPlan 006 Hole C (what each research stage passes to the next) and Hole D (long runs, resume, usage limits) in Claude Code.
- Related: [ExecPlan 006](../../exec-plans/active/006-claude-code-research-system.md), sections 4, 6, 8, 11.

## Legend and method

- [V] Verified: the claim appears in an official page or primary source that was fetched in this run. WebFetch returns a model-written summary of each page, so quoted phrases are short and must be re-checked against the page before they are relied on in code or docs.
- [S] Secondary: a search-result snippet, a third-party write-up, or a paper summary that was not read in full.
- [U] Unverified: a design proposal, an inference, or a point the fetched text did not settle. Every proposed number in Parts 2 to 4 is [U] unless stated otherwise. These numbers are policy choices, not sourced facts.

Quotes: at most one per source, under 15 words.

---

## Part 1. Source records

### A. Claude Code official documentation (code.claude.com)

**S01. Hooks reference**
- Org: Anthropic (Claude Code docs). Date: current page, fetched 2026-11-10. Tag: [V].
- URL: https://code.claude.com/docs/en/hooks.md
- Bullets:
  - Lists 33 hook events, including `SessionStart`, `PreCompact`, `PostCompact`, `SubagentStart`, `SubagentStop`, `Stop`, `StopFailure`, `PreModelSwitch`, `SessionEnd`.
  - `SessionStart` input adds `source` with values `startup`, `resume`, `clear`, `compact`, `fork`. On `resume` or `fork` it can also add `seconds_since_last_response`, `context_tokens`, `prompt_cache_likely_expired`, `estimated_cache_write_usd` (requires v2.1.251 or later).
  - `SessionStart` injects context with `hookSpecificOutput.additionalContext`, or with plain stdout on exit 0.
  - `PreCompact` matcher values are `manual` and `auto`. Input has `trigger` and `custom_instructions` (null for auto). Exit 2 blocks compaction. Stdout on exit 0 becomes instructions for the summary, capped at 10,000 characters.
  - `PostCompact` input has `trigger` and `compact_summary`. It has no decision control.
  - `SubagentStop` input has `agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message`, `stop_hook_active`, `background_tasks`, `session_crons`. Decision: top-level `decision: "block"` with `reason`.
- Relevance: these are the exact event and field names the resume and handoff design needs. Field names were taken from the page text, not from an official schema file.

**S02. Hooks guide: re-inject context after compaction**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/hooks-guide.md
- Bullets:
  - Recommends a `SessionStart` hook with a `compact` matcher to re-inject critical context after every compaction.
  - Matcher table: `SessionStart` values `startup`, `resume`, `clear`, `compact`, `fork`.
- Relevance: the official pattern for Hole D, used in Part 3.

**S03. Subagents**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/sub-agents.md
- Bullets:
  - Frontmatter fields include `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `autoCompactWindow` (v2.1.296 or later, range 100000 to 1000000, write it as a plain integer).
  - `maxTurns`: when the limit is reached, "Claude Code returns its output marked as partial", and the subagent can be resumed (requires v2.1.246 or later).
  - Resume: each completed subagent returns an agent ID. `SendMessage` resumes it with full history. Explore and Plan are one-shot and cannot be resumed.
  - Transcripts: `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`. Transcripts persist within their session. Compaction of the main conversation does not affect them.
  - Fresh context: a non-fork subagent does not see the main conversation or files Claude already read. It gets its own system prompt, the task message, CLAUDE.md (except Explore and Plan), a git status snapshot (except Explore and Plan), and preloaded skills.
  - Nesting: default depth 3. `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` sets it. Concurrent subagents default to 20 (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`).
  - Foreground subagents block the main conversation. Background subagents run concurrently. `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` makes Claude wait.
- Relevance: a subagent cannot read the lead's conversation, so each brief must carry everything it needs. Subagent state is resumable only inside the same session.

**S04. Manage costs**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/costs.md
- Bullets:
  - `/usage` on Pro, Max, Ultra, Team, Enterprise shows plan usage bars and an attribution breakdown: skills, subagents, plugins, MCP servers, each as a share of recent usage.
  - Subagents: "The subagent's own requests still draw on your usage." Every subagent sends its own requests on top of the main conversation's.
  - Team and Enterprise seats: a per-seat allowance that resets on a rolling five-hour window and a weekly window.
  - Cache: a cache read costs about 0.1x base input (see S21). Changing tool definitions or the cached prefix forces a rebuild.
  - Advice: clear between unrelated tasks, use `/compact` with instructions, keep CLAUDE.md under 200 lines, move specialized instructions into skills, route verbose work to subagents, use `model: haiku` for simple subagent tasks.
  - Thinking cannot be turned off on Opus 5.5, Sonnet 5.5, Haiku 5.5, or the Fable models. Control cost with effort.
  - Idle work also costs tokens: session recap, idle compaction, prompt suggestions, scheduled `/loop` tasks, goal check-ins (`CLAUDE_CODE_GOAL_CHECKIN_MINUTES`, default 30, `0` turns it off).
- Relevance: the source for Part 4. It explains which background activity spends plan usage.

**S05. Checkpointing and rewind**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/checkpointing.md
- Bullets:
  - Keeps file snapshots for the 100 most recent checkpoints in a session. Snapshots are deleted in the retention sweep, about 30 days after the session last saved one.
  - Not tracked: Bash command changes to files after Claude has edited them, external edits, edits from other sessions, symlinked and hard-linked paths.
  - Subagent edits are usually not restored by rewind, except a foreground forked skill.
  - "Checkpoints are designed for quick, session-level recovery." Use Git for permanent history.
- Relevance: rewind must not be used as a research-state mechanism. Research state lives in the app DB.

**S06. Run Claude Code programmatically (headless)**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/headless.md
- Bullets:
  - `claude -p` exits 0 on success and non-zero on failure. `--output-format json` returns `session_id`, `result`, `total_cost_usd`, and `structured_output` (with `--json-schema`).
  - `--max-turns` limits agentic turns in print mode, with no limit by default.
  - `--bare` skips hooks, skills, subagents, MCP servers, auto memory, and CLAUDE.md, and "bare mode doesn't use your subscription login" (it needs `ANTHROPIC_API_KEY`).
  - Without `--bare`, `-p` runs project hooks and `.mcp.json` servers without a trust dialog.
  - Background work: after the turn ends, `-p` waits for background subagents, background commands, Monitor watches. A 10-minute idle cap applies by default (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`). SIGTERM exits with 143. SIGINT interrupts the turn.
  - `CLAUDE_CODE_RESUME_INTERRUPTED_TURN=1` makes resume continue the interrupted turn.
  - `--permission-prompts none` (v2.1.259 or later) denies anything that would prompt, so unattended runs do not hang.
  - `api_retry` events carry `error` categories: `rate_limit`, `billing_error`, `overloaded`, and others.
- Relevance: the interface for unattended stages and for detecting limit errors. Its JSON field list is partial (see Part 5).

**S07. How Claude remembers your project (memory)**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/memory.md
- Bullets:
  - CLAUDE.md is loaded at session start. Auto memory: first 200 lines or 25 KB of `MEMORY.md` load at start.
  - AGENTS.md: Claude reads AGENTS.md directly in v2.1.277 or later **only when no CLAUDE.md or CLAUDE.local.md exists in the working directory or above**. A CLAUDE.md that imports `@AGENTS.md` makes it load through the import.
  - `AGENTS.local.md` and `AGENTS.override.md` are not read.
  - Subagents that start without project instructions do not get these files.
- Relevance: the plan's `CLAUDE.md` with `@AGENTS.md` import is the correct way to keep one project instruction file. See Part 5 on whether AGENTS.md survives compaction.

**S08. Interactive mode**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/interactive-mode.md
- Bullets:
  - Usage-limit wait: when a claude.ai usage limit stops Claude mid-task, Claude Code waits in the open session and continues on its own after the reset. On by default in interactive sessions with a claude.ai subscription (v2.1.234 or later).
  - If the computer slept more than about 30 minutes across the reset, the first line reads "Your usage limit has reset" and the user presses Enter.
  - Cancel with Esc or Ctrl+C at an empty prompt; `/rate-limit-options` offers "Wait here, then continue automatically" and "Don't continue automatically".
  - Managed setting `autoContinueAtUsageLimit` controls the automatic wait.
  - `Ctrl+X Ctrl+K` stops all background subagents in the session.
- Relevance: the only documented way a long stage survives a 5-hour limit without human action, and only in an interactive session.

**S09. Manage sessions**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/sessions.md
- Bullets:
  - Entry points: `claude --continue`, `claude --resume`, `claude --resume <name>`, `claude --resume <transcript-path>`, `/resume`, `claude --from-pr <number>`.
  - A resumed session restores conversation history, interrupted tool calls are not rerun, model, agent, active goal, session-scoped scheduled tasks (unexpired). Background subagents and background Bash that ended with the old process show as "didn't finish" notes.
  - Not restored: `--mcp-config`, `--settings`, `--plugin-dir`, `--fallback-model`, `--add-dir` directories. Pass them again.
  - Sessions created with `claude -p`, the Agent SDK, or `/loop` are left out of the picker and out of `claude --continue`. `--resume <session-id>` still works.
  - Transcripts: `~/.claude/projects/<project>/<session-id>.jsonl`. Format is internal and may change between versions.
  - Retention: `cleanupPeriodDays`, default 30 days.
  - "Resume this conversation?" dialog estimates the share of the 5-hour limit the saved conversation alone would use.
- Relevance: explains why `--continue` is the wrong resume tool for a research cycle, and why transcripts cannot be the system of record.

**S10. Errors reference (partial)**
- Org: Anthropic. Tag: [V] for the part read. URL: https://code.claude.com/docs/en/errors.md
- Bullets:
  - Usage-limit messages: "You've hit your session limit", "You've hit your weekly limit", "You've hit your Opus limit" or "Sonnet limit" (switching model family with `/model` can keep the user working), spend-limit variants.
  - A `529` overload is not a usage limit.
  - `CLAUDE_CODE_RETRY_WATCHDOG` makes Claude Code fail at once on a standard-speed `429` that reports a spend limit or exhausted usage credits.
  - Rewind error text: "No files were restored: N files failed (backup missing...)".
- Relevance: the message strings a limit detector can match. The usage-limit section beyond the first 100,000 characters was not read.

**S11. Model configuration**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/model-config.md
- Bullets:
  - Aliases: `default`, `best` (same as `opus`), `fable`, `sonnet`, `opus`, `haiku`, `sonnet[1m]`, `opus[1m]`, `opusplan`. Pin a full model name to avoid drift.
  - `CLAUDE_CODE_AUTO_COMPACT_WINDOW` sets the window; `/autocompact <value>` sets it per model. Haiku 5.5 auto-compacts at about 967K tokens by default (other models not confirmed).
  - Effort priority: `CLAUDE_CODE_EFFORT_LEVEL`, then `/effort` or `/model`, then `--effort`, then settings, then the model default. Fable 5.2, Opus 5.5, Sonnet 5.5, and Haiku 5.5 default to `medium`.
  - Subagents inheriting the model follow `/model` switches. Set `model` in the subagent definition to pin it.
- Relevance: per-stage model pinning (Part 4).

**S12. Explore the context window**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/context-window.md
- Bullets:
  - "What survives compaction": system prompt and output style still apply. Project-root CLAUDE.md and unscoped rules are re-injected from disk. Auto memory is re-injected.
  - Files Claude read or edited: up to five most recently modified are re-read. Files over 5,000 tokens come back as references.
  - Invoked skill bodies re-injected, capped at 5,000 tokens per skill and 25,000 total, oldest dropped first. Truncation keeps the start of the file.
  - Background commands and background subagents keep running. Claude is reminded which ones are still running.
  - SessionStart hooks that match the `compact` source run again and add output to the compacted context.
  - Path-scoped rules and nested CLAUDE.md load on demand. Content that hooks added earlier is summarized away.
- Relevance: defines exactly what state survives compaction without help, and what must be re-injected by hook.

**S13. CLI reference**
- Org: Anthropic. Tag: [V]. URL: https://code.claude.com/docs/en/cli-reference.md
- Bullets:
  - `--resume <session>` and `-r`, `--continue`/`-c`, `--fork-session`, `--session-id <uuid>`, `--name`/`-n`.
  - `--max-turns` (print mode only); `--no-session-persistence` (print mode only).
  - `--bare` as in S06. `--json-schema` requires `--output-format json`.
  - `--permission-mode` values include `auto`, `dontAsk`, `acceptEdits`.
- Relevance: flags used by the resume procedure in Part 3.

**S14. Environment variables (partial)**
- Org: Anthropic. Tag: [V] for the names listed; some names not in the read portion. URL: https://code.claude.com/docs/en/env-vars.md
- Bullets:
  - `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` default 3; `1` turns nesting off.
  - `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` default 20.
  - `CLAUDE_CODE_AUTO_COMPACT_WINDOW` range 100000 to 1000000.
  - `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` removes `run_in_background` and turns off Ctrl+B and background forked skills.
  - `CLAUDE_CODE_EFFORT_LEVEL` takes precedence over `/effort` and settings.
  - `CLAUDE_CODE_GOAL_CHECKIN_MINUTES` default 30; `0` turns off goal check-ins.
- Relevance: budget knobs in Part 4.

**S15. Settings reference (partial)**
- Org: Anthropic. Tag: [V] for names; descriptions from the index. URL: https://code.claude.com/docs/en/settings-reference.md
- Bullets:
  - `autoContinueAtUsageLimit` (user or managed): wait and continue after a claude.ai limit resets.
  - `cleanupPeriodDays`: transcript retention.
  - `modelPricing` (managed only): report spend at contracted rates.
  - `idleCompaction`: stop compacting a conversation the user stepped away from.
  - `crossSessionInbound`: whether messages from other sessions are delivered.
  - `permissions.defaultMode`, and `disableAllHooks` as a top-level key.
- Relevance: the settings that control auto-continue, retention, and idle spend.

### B. Anthropic engineering and API documentation

**S16. How we built our multi-agent research system**
- Org: Anthropic (Engineering). Date: not shown in the fetched text. Tag: [V]. URL: https://www.anthropic.com/engineering/multi-agent-research-system
- Bullets:
  - Lead agent gives each subagent an objective, an output format, guidance on tools and sources, and clear task boundaries. Vague instructions caused duplicated work and gaps.
  - The lead saves its plan to memory because context beyond a 200,000-token limit is cut off.
  - Subagents write outputs to external storage and return lightweight references, which avoids information loss and reduces overhead.
  - A CitationAgent runs after the research loop to attribute claims to sources.
  - Token use: agents about 4x chat; multi-agent systems about 15x chat. Multi-agent pays off only for high-value tasks.
  - Scaling rules in prompts: simple fact-finding 1 agent and 3 to 10 tool calls; direct comparisons 2 to 4 subagents at about 10 to 15 calls each; complex research more than 10 subagents with divided responsibilities.
- Relevance: the base for the artifact-by-reference design (Part 2) and for per-stage budget caps (Part 4).

**S17. Effective harnesses for long-running agents**
- Org: Anthropic (Engineering). Date: not shown in the fetched text (a secondary source gives November 2025 [S]). Tag: [V]. URL: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Bullets:
  - Initializer session creates `init.sh`, `claude-progress.txt`, an initial git commit, and a feature list in JSON with `category`, `description`, `steps`, and `passes` (initially `false`).
  - Later sessions: check directory, read git log and progress file, pick the top unfinished feature, run `init.sh` and an end-to-end check, fix breakage first, implement one feature, test as a user would, set `passes` only after testing, commit, update progress.
  - Only the `passes` field may be changed. Quoted rule: "It is unacceptable to remove or edit tests" (approximate wording, from the fetched summary).
  - Failure modes named: one-shotting, premature completion, completion declared without end-to-end checks.
- Relevance: the pattern for an external "definition of done" (the plan's acceptance checks) and for one-stage-per-session progress notes.

**S18. Effective context engineering for AI agents**
- Org: Anthropic (Engineering). Tag: [V]. URL: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Bullets:
  - Compaction: keep architectural decisions, unresolved bugs, implementation details; discard redundant tool output. Clearing old tool results is the lightest form of compaction.
  - Structured note-taking: write to persistent memory outside the window (to-do list, NOTES.md) and read it back.
  - Sub-agents return condensed summaries, reportedly about 1,000 to 2,000 tokens.
  - Just-in-time retrieval: keep references (paths, queries, IDs) and load on demand.
  - Principle: the smallest set of high-signal tokens.
- Relevance: justifies storing artifacts in the DB and passing IDs in prompts.

**S19. Building effective agents**
- Org: Anthropic (Engineering). Tag: [V]. URL: https://www.anthropic.com/engineering/building-effective-agents
- Bullets:
  - Orchestrator-workers: a central LLM breaks down the task, delegates, and synthesizes; subtasks are not predefined.
  - Prompt chaining with programmatic gates on intermediate steps: trades latency for accuracy.
  - Agents should get "ground truth" from the environment (tool results, execution) at each step.
  - Autonomy raises cost and risk of compounding errors; test in sandboxes.
  - Tool descriptions should state example usage, edge cases, input format, and boundaries from other tools.
- Relevance: the gates in the research loop are prompt-chaining gates; the verifier's auto checks are the ground-truth step.

**S20. Claude API: structured outputs**
- Org: Anthropic (Platform docs). Tag: [V]. URL: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Bullets:
  - Send `output_config.format` with `type: "json_schema"`. The older `output_format` is deprecated and returns 400 without the beta header.
  - Guarantees valid JSON matching the schema; no retries needed for schema violations.
  - Supported: object, array, string, integer, number, boolean, null, `enum`, `const`, `anyOf`, `allOf` (not with `$ref`), `$ref` internal only, `required`, `additionalProperties: false`, some string formats (`date-time`, `uuid`, `uri`, `email`...), `minItems` only 0 or 1.
  - Unsupported (400): recursive schemas, `minimum`, `maximum`, `minLength`, `maxLength`, `additionalProperties` other than `false`, backreferences and lookarounds in regex.
  - Limits: 20 strict tools, 24 optional parameters, 16 union-typed parameters per request. Grammar compile timeout 180 seconds.
  - `stop_reason: "refusal"` and `"max_tokens"` can yield non-matching output. Changing `output_config.format` invalidates the prompt cache for that thread.
- Relevance: if any stage calls the API directly (the offline mode in plan section 8), the artifact schemas must avoid the unsupported keywords. Length rules go in validator code.

**S21. Claude API: prompt caching**
- Org: Anthropic (Platform docs). Tag: [V] (first 100,000 characters). URL: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Bullets:
  - Default TTL 5 minutes (refreshed on use). Optional `"ttl": "1h"`.
  - Price: 5-minute cache write 1.25x base input; 1-hour write 2x; cache read 0.1x. Opus 5.5 and Sonnet 5.5 hits 0.05x (footnote).
  - Cache hits are not deducted against the rate limit.
  - Invalidation order: tools, then system, then messages. Changing tool definitions invalidates everything below. Adding or removing images invalidates system and messages.
  - Minimum cacheable length varies by model (512 tokens for Haiku 5.5 and Sonnet 5.5, 4096 for Haiku 4.5).
- Relevance: keep the stage prompt prefix stable across a cycle; do not change MCP tool sets mid-run.

### C. Other agent frameworks and standards

**S22. Claude Help Center: Pro and Max plan usage (Claude Code)**
- Org: Anthropic (Help Center). Date: current, fetched 2026-11-10. Tag: [V] for the statements below; the article title was not shown in the fetched text. URL: https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan
- Bullets:
  - "Pro and Max plans have a five-hour session limit and a weekly limit." Max also has a separate weekly limit for Fable.
  - No message counts or hour totals are given.
  - Claude, Claude Code, and IDE usage all count against the same limits.
  - Near the five-hour limit, Claude Code may finish the current step and show "Usage limit reached · wrapping up". This allowance is small and counts toward the weekly limit.
  - Options at the limit: turn on usage credits, use Console API credits, upgrade, or wait for reset.
  - Whether subagent usage counts was not stated.
- Relevance: the only official statement of the limit structure. Part 4 does not hardcode any number.

**S23. OpenAI Agents SDK: handoffs**
- Org: OpenAI. Date: current docs, fetched 2026-11-10. Tag: [V]. URL: https://openai.github.io/openai-agents-python/handoffs/
- Bullets:
  - `handoff()` parameters include `agent`, `on_handoff`, `input_type`, `input_filter`, `is_enabled`, `nest_handoff_history`.
  - `input_type` describes model-generated arguments only. Application state belongs in `RunContextWrapper.context`.
  - `is_enabled` runs before arguments are parsed, so it cannot authorize on parsed fields. Check in `on_handoff` and raise to block.
  - By default the receiving agent sees the full previous conversation history.
  - `input_filter` receives `HandoffInputData` and returns a new one. `remove_all_tools` strips structured tool items but not tool text already in messages.
  - `nest_handoff_history` is opt-in beta and does not redact sensitive data.
- Relevance: the design rule "structured payload by reference, not transcript by default" matches the Part 2 handoffs. The docs warn that default full-history handoff leaks context.

**S24. OpenAI Agents SDK: sessions**
- Org: OpenAI. Tag: [V]. URL: https://openai.github.io/openai-agents-python/sessions/
- Bullets:
  - A session stores conversation items (user input, responses, tool calls), keyed by `session_id`. It does not authenticate access.
  - Backends: `SQLiteSession(session_id, db_path)`, `RedisSession`, `SQLAlchemySession`.
  - Run state is separate. `result.to_state()` produces state for interrupted runs. Resume with `Runner.run(agent, state, session=session)` using the same session ID and backend.
- Relevance: separating durable items from run state is the same split Part 2 uses (DB rows versus the cycle state row).

**S25. LangGraph: persistence**
- Org: LangChain. Tag: [V]. URL: https://docs.langchain.com/oss/python/langgraph/persistence
- Bullets:
  - Checkpointers persist graph state per `thread_id`. Uses named: conversation continuity, human-in-the-loop, time travel, fault tolerance.
  - `InMemorySaver` (RAM) is lost on process restart. `PostgresSaver` and `SqliteSaver` persist. `PostgresSaver` stores `thread_id` in a column under 255 characters.
  - Stores are separate long-term key-value memory across threads.
- Relevance: a graph-level version of the cycle_id pattern. The lesson is that in-memory state dies with the process.

**S26. LangGraph: interrupts**
- Org: LangChain. Tag: [V]. URL: https://docs.langchain.com/oss/python/langgraph/interrupts
- Bullets:
  - `interrupt()` suspends at that point and the checkpointer saves state. Resume with `Command(resume=...)` on the same `thread_id`.
  - On resume the node runs again from its start, so code before `interrupt()` runs again.
  - Quoted: "Side effects called before `interrupt` should (ideally) be idempotent." (The docs also warn that retrying a node can repeat its effect.)
  - Do not wrap `interrupt` in bare try/except.
- Relevance: the reason every stage needs an idempotency key, and why a gate should sit between stages, not inside a stage.

**S27. 12-factor agents**
- Org: HumanLayer (open-source guide). Date: not confirmed in this run. Tag: [V] for factor titles. URL: https://github.com/humanlayer/12-factor-agents
- Bullets:
  - Factor 3: deliberately manage the context window.
  - Factor 5: unify execution state and business state.
  - Factor 6: simple APIs to launch, pause, and resume agents.
  - Factor 7: contact humans through tool calls.
  - Factor 10: small, focused agents. Factor 12: agent as a stateless reducer.
- Relevance: supports storing state outside the agent and making pause and resume explicit.

**S28. Manus: context engineering lessons**
- Org: Manus (blog). Date: not confirmed. Tag: [V]. URL: https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- Bullets:
  - Use the file system as external memory. Compression stays reversible: keep the URL, drop the page body.
  - Recite a todo file to keep the goal in recent attention (cited for tasks around 50 tool calls).
  - Keep the prompt prefix stable and the context append-only for KV-cache hits.
  - Keep failed actions and errors in context so the model updates its beliefs.
- Relevance: the stage checkpoint file pattern and the rule to keep failures (the failure ledger) visible.

**S31. Stripe: idempotent requests**
- Org: Stripe. Tag: [V]. URL: https://docs.stripe.com/api/idempotent_requests
- Bullets:
  - Client-generated `Idempotency-Key`, up to 255 characters. Retries with the same key return the saved response.
  - v1: keys may be pruned after at least 24 hours. Reuse with different parameters errors.
  - Results are saved only after execution starts. Validation failures are not saved.
  - Avoid personal data in keys.
- Relevance: the idempotency key scheme for stage writes (Part 2 and Part 3). This is an external API concept applied to an internal DB.

**S32. JSON Schema, draft 2020-12**
- Org: JSON Schema project. Date: published 16 June 2022 (per the fetched page). Tag: [V]. URL: https://json-schema.org/draft/2020-12
- Bullets:
  - Draft 2020-12 replaces 2019-09 with `prefixItems`, `items`, `$dynamicRef`, `$dynamicAnchor`.
  - The `format` keyword is split into annotation and assertion parts.
- Relevance: the schema dialect for artifact validation. Keep `$schema` set explicitly.

### D. Papers and memory systems

**S29. Agentic Context Engineering (ACE)**
- Org: authors include Qizheng Zhang and Changran Hu (per search snippet; affiliations not checked). arXiv 2510.04618, revised through v3 (March 2026, per search). Tag: [S].
- URL: https://arxiv.org/abs/2510.04618
- Bullets:
  - Context is an evolving playbook maintained by a Generator, a Reflector, and a Curator.
  - Localized incremental edits prevent "context collapse" from full rewrites.
  - Reported gains are authors' numbers (10.6% on agent benchmarks in v1). Not used for decisions here.
- Relevance: supports append-and-curate lessons (Part 2, lesson rows) rather than rewriting them.

**S30. ReasoningBank**
- Org: Google, Yale, UIUC researchers (per search snippet). arXiv 2509.25140. Tag: [S].
- URL: https://arxiv.org/pdf/2509.25140
- Bullets:
  - Distills memory items from both successful and failed attempts, judged without ground-truth labels.
  - Each item has a title, description, and content; retrieval by embedding search.
  - Reported gains on WebArena are the authors' numbers.
- Relevance: supports storing failures as first-class lesson inputs (Part 2 failure ledger).

### E. Secondary sources on usage limits (search only, not read)

**S33. Third-party explainers on Claude Code limits**
- Org: various third-party blogs. Date: 2026 (varies). Tag: [S].
- URLs: https://portkey.ai/blog/claude-code-limits ; https://www.ai-toolbox.co/claude-management-and-productivity/claude-usage-limits-2026 ; https://alexcloudstar.com/blog/claude-code-usage-limits-2026/
- Bullets (from search snippets):
  - Describe a rolling five-hour session limit plus a weekly limit, pooled across chat, terminal, IDE, web, and subagents.
  - Max 5x and 20x described as multiples of Pro's five-hour usage. Weekly multiples not published by Anthropic.
  - Sources disagree on the weekly period (rolling seven days versus a weekly usage period).
- Relevance: context only. Anthropic's help center (S22) is the authority, and these snippets contradict each other on details.

---

## Part 2. Proposed handoff artifacts

### 2.1 Design rules

1. The DB is the system of record. Prompts carry IDs and short claims, not full texts. This follows S18 (references, not payloads) and S16 (external storage with references).
2. A subagent sees only its brief. It does not see the lead's conversation (S03). So every stage input is a stored artifact, and the brief names those artifacts by ID.
3. A subagent returns a small receipt, not its work. Its final message is a receipt: artifact IDs, counts, status. Its work goes to the DB (S16).
4. Every artifact has a `content_sha256` and an `input_hash`. Stage retries use the key `cycle_id + stage + attempt + input_hash` (S31, S26).
5. Verdicts reference evidence IDs. An objection with no evidence ID is invalid (plan section 11.4, rule "no numeric scores").
6. Schemas use `$schema` 2020-12 (S32). Validators in code enforce length and count rules that API structured outputs cannot express (S20).

### 2.2 Common envelope (one row per artifact)

```json
{
  "artifact_id": "art_01J...",
  "cycle_id": "cyc_01J...",
  "kind": "search_log | screened_list | evidence_bundle | hypothesis_card | verdict | lesson | failure | gate_record | experiment_plan | brief | receipt",
  "stage": 2,
  "attempt": 1,
  "hypothesis_id": "H-03",
  "version": 1,
  "schema": "easyresearch.handoff.v1",
  "input_hash": "sha256:...",
  "content_sha256": "sha256:...",
  "created_by": "literature-scout",
  "created_at": "2026-11-10T09:00:00Z",
  "payload": {}
}
```

[U] The `schema` string and version scheme are a proposal.

### 2.3 Stage 2 output: search log

Written by `literature-scout`. Stored in DB. Passed to the next stage as its ID and counts only.

```json
{
  "queries": [
    {
      "query_id": "q1",
      "purpose": "topic | nearest_prior | counter_evidence | citation_follow",
      "text": "retrieval-augmented evaluation multilingual",
      "source": "openalex",
      "filter": "cites:W2741809807",
      "page": 1,
      "returned": 42,
      "kept": 7,
      "cache_hit": false,
      "budget_units": 1,
      "run_at": "2026-11-10T09:01:12Z"
    }
  ],
  "counts": {"queries": 14, "nearest_prior_queries": 4, "counter_evidence_queries": 1}
}
```

The `nearest_prior_queries` count feeds automatic check A3 (at least 3). The `counter_evidence_queries` count feeds the counter-search requirement in the verifier. [U] Filter syntax follows the plan's OpenAlex notes (`cites:`, `cited_by:`, `related_to:`).

### 2.4 Stage 2 output: screened paper list

```json
{
  "candidates": [
    {
      "paper_ref": "oa:W2741809807",
      "library_item_id": "lib_...",
      "title": "string",
      "year": 2024,
      "decision": "include | exclude | maybe",
      "reason_code": "TOPIC_MISMATCH | NO_METHOD | DUPLICATE | NOT_RETRIEVABLE | OTHER",
      "found_by": ["q1", "q4"],
      "pdf_sha256": "sha256:... | null"
    }
  ],
  "included_count": 12
}
```

[U] The reason-code list is a proposal. Keep the list short; add codes only after the verifier shows a need.

### 2.5 Stage 3 output: evidence bundle

The most important handoff. The quote text lives in the DB. The next stage receives quote IDs, claims, and page locations.

```json
{
  "papers": [
    {
      "paper_ref": "oa:W2741809807",
      "library_item_id": "lib_...",
      "pdf_sha256": "sha256:...",
      "page_map_note": "physical page index and printed page label kept separately"
    }
  ],
  "quotes": [
    {
      "quote_id": "Q-017",
      "paper_ref": "oa:W2741809807",
      "physical_page": 12,
      "printed_label": "11",
      "text": "string, at most 60 words, copied from extracted page text",
      "text_sha256": "sha256:...",
      "supports": ["problem", "limitation"],
      "claim": "short paraphrase of what the quote supports",
      "verify": {"status": "pending | verified | mismatch", "checked_by": "citation-checker", "neighbor_page_checked": false}
    }
  ],
  "profiles": [
    {
      "paper_ref": "oa:W2741809807",
      "problem": {"text": "string", "quote_ids": ["Q-017"]},
      "method": {"text": "string", "quote_ids": ["Q-018"]},
      "limitations": [{"text": "string", "quote_ids": ["Q-021"]}],
      "future_work": [{"text": "string", "quote_ids": ["Q-022"]}]
    }
  ]
}
```

Rules, all from the plan or the sources:
- Keep physical page and printed label separate (plan invariant; AGENTS.md domain invariant).
- The `verify` block is written by `citation-checker` only (S16 citation pass; plan section 11.2 `verify_quote`).
- A physical page mismatch triggers one check of the neighbouring physical page (plan section 11.2).

### 2.6 Stage 4 output: hypothesis card

```json
{
  "hypothesis_id": "H-03",
  "version": 2,
  "parent_version": 1,
  "rewind_reason": "A3 | C4 | null",
  "statement": "string, one sentence",
  "contribution_type": "method | analysis | benchmark | system",
  "gap": {"claim": "string", "quote_ids": ["Q-017"]},
  "alternatives": [
    {"alt_id": "A1", "summary": "string", "why_not_chosen": "string", "quote_ids": []}
  ],
  "closest_prior": [
    {"paper_ref": "oa:W2741809807", "difference": "string", "quote_ids": ["Q-018"]}
  ],
  "prediction": {
    "metric": "string",
    "dataset": "string",
    "baseline": "string",
    "direction": "higher | lower",
    "threshold": 0.05,
    "unit": "string",
    "falsified_if": "string"
  },
  "feasibility": {"data": "string", "compute": "string", "eval_method": "string", "missing": []},
  "known_risks": ["string"]
}
```

Counts enforced in code (proposal): `alternatives` 2 to 4; `closest_prior` at least 3 (rule A3 and criterion C4); `prediction.threshold` required and numeric (rule A5); a `falsified_if` text is required (criterion C5).

### 2.7 Stage 5 output: verdict with objections

```json
{
  "verdict_id": "V-...",
  "hypothesis_id": "H-03",
  "hypothesis_version": 2,
  "round": 1,
  "auto_checks": [
    {"rule": "A1", "result": "pass", "detail": "3 evidence quotes attached"},
    {"rule": "A2", "result": "pass", "detail": "all quote_ids verified"}
  ],
  "rubric": [
    {"criterion": "C4", "status": "revise", "evidence_ids": ["Q-018"], "reason_code": "DIFF_WEAK"}
  ],
  "counter_search": [
    {"query_id": "q9", "found": "none | contradicting | overlapping", "paper_refs": []}
  ],
  "objections": [
    {
      "obj_id": "O1",
      "target": "closest_prior[2].difference",
      "claim": "string",
      "evidence_ids": ["Q-018"],
      "severity": "blocking | minor"
    }
  ],
  "author_responses": [
    {"obj_id": "O1", "response": "fix | new_evidence | concede | reasoned_rebuttal", "evidence_ids": ["Q-030"]}
  ],
  "decision": "pass | revise | reject",
  "rewind_to": 2,
  "reason_codes": ["DIFF_WEAK"]
}
```

Rules from the plan and S16/S19:
- Auto checks A1 to A6 are computed by code before the verifier writes the rubric. A failed auto check cannot be overridden by the model (plan section 5.3).
- Debate is at most 2 rounds (N report 3.8). Each objection and response is its own row, so the transcript never needs to be passed.
- `rewind_to` is 2 or 4 only (plan section 4).

### 2.8 Lessons and failures

```json
{
  "failure_id": "F-...",
  "cycle_id": "cyc_01J...",
  "hypothesis_key": "sha256 of normalized statement",
  "reason_code": "C4 | A3 | A4 | C2 | ...",
  "evidence_ids": ["Q-018"],
  "expires_at": "2027-02-10T00:00:00Z",
  "released_by_user": false
}
```

```json
{
  "lesson_id": "L-...",
  "pattern": "string, at most 200 characters",
  "applies_to": ["hypothesis", "rubric:C4"],
  "topic_tags": ["retrieval"],
  "evidence": {"cycle_ids": ["cyc_01J..."], "verdict_ids": ["V-..."]},
  "failure_codes": ["C4"],
  "status": "active | retired",
  "created_by": "lesson-curator",
  "approved_by": "user | null"
}
```

Rules: failures are append-only (plan section 4). Lessons are append-only; retirement is a new row with `status: "retired"` (plan section 6). A lesson enters a prompt only after `approved_by` is set, unless the policy preset allows auto-approval (plan section 7 row "교훈 덧붙이기").

### 2.9 Stage 7: experiment plan (locked)

```json
{
  "plan_id": "EP-...",
  "hypothesis_id": "H-03",
  "hypothesis_version": 2,
  "baseline": {"name": "string", "source_paper_ref": "oa:...", "reported_value": 0.71, "quote_id": "Q-040"},
  "metrics": [{"name": "string", "definition": "string", "direction": "higher", "threshold": 0.05}],
  "data": {"name": "string", "version": "string", "license_checked": true, "sha256": "sha256:..."},
  "procedure": ["string"],
  "expected_result": {"metric": "string", "value": 0.76},
  "failure_criteria": ["string"],
  "budget": {"max_gpu_hours": 0},
  "plan_sha256": "sha256:...",
  "locked_at": "2026-11-10T12:00:00Z"
}
```

`plan_sha256` is the hash of the canonical JSON of all other fields. [U] Use a canonical form (for example RFC 8785 JCS; not fetched in this run). Changing a locked plan is not allowed. A new `plan_id` is created instead (plan AC7).

### 2.10 Gate record

```json
{
  "gate_id": "G-...",
  "cycle_id": "cyc_01J...",
  "stage": 6,
  "policy_sha256": "sha256:...",
  "required": true,
  "decision": "auto | approved | rejected | pending",
  "decided_by": "policy | user",
  "summary_artifact_id": "art_01J..."
}
```

Gate records are the only way a stage is allowed to advance. A stage row without a gate record for a required gate cannot advance (Part 3).

### 2.11 Brief (what the subagent receives)

The brief is the prompt. It is assembled from DB rows and stored as a `brief` artifact so it can be replayed.

```json
{
  "task": "paper-analyst",
  "cycle_id": "cyc_01J...",
  "objective": "Extract problem, method, limitations for the listed papers. Quote text must be copied from the page, not paraphrased.",
  "inputs": {"paper_refs": ["oa:W2741809807"], "artifact_ids": ["art_01J..."]},
  "output": {"artifact_kind": "evidence_bundle", "receipt_schema": "receipt.v1"},
  "boundaries": ["Do not write hypothesis cards.", "Do not call save tools outside the listed kinds."],
  "lessons": ["L-..."],
  "budget": {"max_turns": 20, "max_mcp_calls": 40},
  "done_when": "All listed papers have a profile with at least one quote_id per field, or status partial with reasons."
}
```

Brief budget (proposal): at most about 6 KB, excluding referenced artifacts. Lessons: at most 10 per brief.

### 2.12 Receipt (what the subagent returns)

```json
{
  "status": "done | partial | blocked",
  "artifact_ids": ["art_01J..."],
  "counts": {"quotes": 14, "papers_done": 3, "papers_skipped": 0},
  "blocked_reason": null,
  "note": "string, at most 300 characters"
}
```

The receipt is the subagent's final message. `SubagentStop` reads it from `last_assistant_message` (S01) and rejects non-JSON or missing fields (Part 3).

### 2.13 Storage location and size limits

| Item | Where | Limit (proposal, [U]) | Passed in prompt? |
|---|---|---|---|
| Cycle state row (`research_cycles`) | DB | one row per cycle | ID, stage, status, pending gate only |
| Events (`cycle_events`): dialogue, decisions, subagent start and stop | DB | append-only, each event at most 4 KB | No (summaries via tool) |
| Search log | DB (new artifact row) | at most 500 queries per cycle | Counts only |
| Screened list | DB | at most 200 candidates per cycle, at most 60 included | IDs and titles of included papers |
| Evidence bundle, quotes | DB | at most 60 words per quote, at most 150 quotes per cycle | Quote IDs and claims for one hypothesis |
| Hypothesis card (each version) | DB | at most 8 KB JSON | Card ID and version; full card only for verifier input |
| Verdict | DB | at most 16 KB JSON per round | Decision and objection IDs |
| Failure ledger | DB (`failure_ledger`) | append-only | Reason codes relevant to the topic |
| Lessons (`lessons`) | DB | at most 30 active; at most 10 per brief | Pattern text, up to 10 |
| Gate policy (`gate_policy`) | DB | one active row; changes need user action | Policy hash only |
| Experiment plan (`experiment_plans`) | DB | locked, hash recorded | Stage 7 only, never by verifier |
| Brief and receipt | DB | brief at most 6 KB; receipt note at most 300 characters | Yes: the brief is the subagent's prompt |
| Raw PDFs and extracted page text | `data/` (private, outside Git) | per library rules | Never |
| Human-readable export (optional) | `docs/research/` only on user request, no private text | n/a | Never |

Note on the table: the plan's table list (section 8) does not include a generic artifact table. This document proposes one new table, `cycle_artifacts` (kind, stage, attempt, input_hash, content_sha256, payload JSON), for the search log, screened list, evidence bundle, cards, verdicts, briefs, receipts, and gate records. It belongs to the schema v8 work and needs a backup and restore check (AGENTS.md domain invariant; plan AC8).

---

## Part 3. Resume procedure and hooks

### 3.1 Why resume is possible

- The cycle state and every artifact live in the DB (Part 2). Transcripts are not required.
- Transcripts are not a system of record: they are deleted after about 30 days (S09, S03), and their JSON format can change between versions (S09).
- Checkpoints do not cover research state and do not cover subagent edits or Bash changes (S05).
- Compaction keeps CLAUDE.md, auto memory, and at most five recent files, and drops everything else (S12). So the cycle state must be re-read from the DB after compaction, not assumed to survive.

### 3.2 Cycle states

`research_cycles.status` (proposal): `created`, `running`, `waiting_gate`, `paused_limit`, `paused_user`, `failed`, `done`.

`research_cycles.stage` (proposal): `1_plan`, `2_search`, `3_read`, `4_hypothesis`, `5_verify`, `6_confirm`, `7_experiment_plan`, `8_report`. A rewind sets `stage` back and increments `rewinds` (plan section 4 limits: 2 per hypothesis, 10 per cycle).

Each stage row carries `stage_status`: `started`, `receipt_received`, `done`, and a `last_input_hash`.

### 3.3 Idempotency rules

1. Before a stage starts, compute `input_hash` from the brief inputs (artifact IDs and their `content_sha256`).
2. If a `cycle_artifacts` row with the same `kind`, `stage`, `attempt`, and `input_hash` exists, reuse it. Do not call OpenAlex again and do not write again (S31, S26).
3. A stage that was `started` but has no receipt is retried with `attempt + 1`. The old partial artifacts stay (append-only), and the retry writes new rows.
4. Writes to `failure_ledger` and `lessons` are idempotent by key (`hypothesis_key`, `pattern_sha256`). A duplicate key returns the existing row.
5. A gate is checked before advancing, and a gate decision is never overwritten. A new decision is a new `gate_record`.
6. Side effects that cannot be made idempotent (for example sending a message) are not part of this pipeline. They are behind an approval gate (plan section 7).

### 3.4 Resume procedure: `/research resume <cycle_id>`

Run this in a new Claude Code session (or after `/clear`). Do not use `--continue` (S09: `-p` and `/loop` sessions are excluded from `--continue`; the picker may show another session).

1. Read the state. Call `research_cycle_get(cycle_id)`. If the cycle does not exist, stop.
2. Check the policy. Call `gate_policy_get`. Record `policy_sha256` in an event. If it differs from the stage's `policy_sha256`, stop and ask the user (the policy changed mid-cycle).
3. Check the pending gate. If `gate_record.decision == pending`, call `approval_status`.
   - `pending`: print the summary artifact and stop with status `waiting_gate`.
   - `approved`: continue.
   - `rejected`: stop with status `paused_user`. Do not retry the gate.
4. Check for a limit pause. If `status == paused_limit`, run `/usage` (Part 4) before continuing. Continue only if the budget gate in Part 4 passes.
5. Find the next stage. If `stage_status == started` without a receipt, treat it as interrupted. Check `cycle_artifacts` for the stage's `input_hash`.
   - Matching artifacts exist: mark the stage `receipt_received` using the existing receipt and go on.
   - No matching artifacts: start the stage with `attempt + 1`.
6. Subagent handling. If the old session had a running subagent, its transcript may exist under `~/.claude/projects/<project>/<old-session-id>/subagents/` (S03). Do not resume it by ID across sessions by default. Re-spawn the subagent from the stored brief (idempotency rule 2). Resume by `SendMessage` only inside the same session, for a subagent that hit `maxTurns` and returned a partial receipt (S03).
7. Run the stage. Use the same brief template. The stage prompt is built only from DB rows (Part 2, 2.11).
8. Write the receipt and an event (`kind: resume`, `claude_code_version`, `session_id`, `attempt`). Advance the stage only after its gate passes.
9. At each gate, stop the session cleanly with status `waiting_gate` and tell the user to start a new session with `/research resume <cycle_id>`. This keeps context small (S18, S04 "clear between tasks") and makes each stage restart from the DB.
10. Finish. Set `status: done` only when the final stage receipt is accepted and the report gate passes (plan AC items).

### 3.5 Hooks

All hooks are project-level (in `.claude/settings.json`), not plugin-level, because plugin subagents ignore hooks (S03). Scripts must not print private text to logs (AGENTS.md invariant). Scripts call the local app API over localhost with a token from an environment variable [U: hooks calling MCP directly is not verified; use the local HTTP API].

| Hook | Matcher (to verify) | What it does | Output | Source |
|---|---|---|---|---|
| `SessionStart` | `resume\|compact` (regex form [U]) | Reads the active cycle pointer, calls `research_cycle_get`, prints a short status block (cycle, stage, pending gate, next action). | `hookSpecificOutput.additionalContext`, at most about 1,500 characters [U] | S01, S02 |
| `PreCompact` | `manual\|auto` | Writes a snapshot event with cycle ID, stage, pending gate, open objection IDs, and the last receipt ID. Prints the "keep" list for the summary. | stdout on exit 0, under 10,000 characters (S01) | S01 |
| `PostCompact` | `manual\|auto` | Stores `compact_summary` as an event (not printed). Side effect only. | none (S01: no decision control) | S01 |
| `SubagentStop` | agent names (`literature-scout`, and so on) | Parses `last_assistant_message` as the receipt JSON. Missing or invalid fields produce a `decision: "block"` with a reason, unless `stop_hook_active` is true (to avoid a loop). Logs the receipt event. | `decision`, `reason` (S01) | S01 |
| `PreToolUse` | `mcp__easyresearch__.*` | Denies MCP writes outside the caller's allowed kinds. Needs the caller identity; a field that identifies the subagent was not verified. | permission decision [U] | S01, plan 11.1 |
| `StopFailure` | [U] | Records a stop caused by an API error (for example rate limit) as a `paused_limit` event. The `error` field is used for matching. Matcher values not verified. | event write | S01 |

Example settings fragment (proposal; matcher syntax to be checked with `/hooks`):

```json
{
  "hooks": {
    "SessionStart": [
      {"matcher": "resume|compact", "hooks": [{"type": "command", "command": "node .claude/hooks/research-status.js"}]}
    ],
    "PreCompact": [
      {"matcher": "manual|auto", "hooks": [{"type": "command", "command": "node .claude/hooks/research-precompact.js"}]}
    ],
    "SubagentStop": [
      {"hooks": [{"type": "command", "command": "node .claude/hooks/validate-receipt.js"}]}
    ]
  }
}
```

[U] The hook script paths and `node` runtime are placeholders. On this Windows machine the commands need PowerShell or a cross-platform runtime; verify before use.

Protected-area writes (plan section 6) are enforced by `permissions.deny` for `Edit`/`Write` on protected paths, plus a `PreToolUse` hook on those tools. Subagent `disallowedTools` already removes `Edit`, `Write`, `Bash` from research agents (plan 11.1).

### 3.6 Subagent limits relevant to resume

- `maxTurns`: partial output is marked as partial and can be resumed (S03). Treat `partial` in the receipt as "re-run with a larger budget or split the batch", not as a failure.
- Spawn depth: 1 (plan). Default 3 (S14).
- Concurrency: default 20 (S14). The per-cycle cap in Part 4 is far below that.
- A subagent that the user stopped (`x` in the panel, or `Ctrl+X Ctrl+K`) does not auto-resume (S03). Re-spawn it from the brief.

---

## Part 4. Usage-budget policy

### 4.1 Facts that set the policy

- Pro and Max: a five-hour session limit and a weekly limit, shared by chat, Claude Code, and IDE (S22). Exact numbers are not published in the sources read.
- A subagent's requests draw on the same usage (S04). Each subagent's requests are on top of the lead's requests (S04). Attribution by subagent appears in `/usage` (S04).
- Interactive sessions can wait out a five-hour limit and continue automatically (S08). Headless `-p` behavior at a limit was not verified (Part 5).
- Idle work spends tokens: idle compaction, prompt suggestions, `/loop`, goal check-ins, session recap (S04).
- Cache reads are 0.1x (S21). A stable prefix is worth keeping (S21, S28).
- Multi-agent research uses about 15x chat tokens (S16). Each extra subagent is a cost multiplier, so per-stage caps matter.

### 4.2 Measurement

- Before each gate and at the start of `/research resume`, run `/usage` and record the five-hour and weekly bar percentages in a `cycle_events` row (`kind: usage_check`). Do not hardcode numbers.
- Record the subagent share from the attribution block when it is shown.
- [U] Check whether the status line exposes plan usage. The fields were not verified.

### 4.3 Per-cycle subagent caps (proposal, [U])

| Subagent | Spawns per cycle (default) | Turns (`maxTurns`) | Notes |
|---|---|---|---|
| `literature-scout` | 4 | 12 | Search batches, not one search per call |
| `paper-analyst` | up to 8, each for 3 papers | 20 | One spawn covers 3 papers |
| `hypothesis-builder` | 3 | 15 | Initial plus up to 2 rewinds to stage 4 |
| `verifier` | 4 | 15 | 2 hypotheses times 2 rounds |
| `citation-checker` | 2 | 10 | One pass before verifier, one after rewind |
| `lesson-curator` | 1 | 10 | Runs once at the end of a cycle |

Total default: 22 spawns per cycle. Anthropic's scaling guidance (S16) is 1 agent for simple tasks and more than 10 subagents for complex research. This plan sits between the two, and the policy preset can raise or lower each cap.

Enforcement: a counter in `research_cycles.spawn_counts`. The lead refuses a spawn above the cap and asks the user (a gate).

### 4.4 Model and effort per stage

| Stage or agent | Model (explicit in frontmatter) | Effort | Reason |
|---|---|---|---|
| Lead (main session) | Plan says Opus. This policy allows Sonnet if budget is tight (Sol decision) | `high` per plan; `medium` if budget tight | The main context grows with each stage, so keep the lead small |
| `literature-scout` | `haiku` | `low` or `medium` | Search and triage (S04 suggests `haiku` for simple subagents) |
| `paper-analyst` | `sonnet` | `medium` | Quote extraction needs accuracy |
| `hypothesis-builder` | `sonnet` | `medium`; `high` on rewind to stage 4 | Creative but bounded |
| `verifier` | `opus` | `high` for the final round; `medium` for auto-check-only rounds | Plan requires Opus and independent context |
| `citation-checker` | `haiku` | `low` | Mechanical match of quote text |
| `lesson-curator` | `sonnet` | `medium` | Summaries of rejected attempts |

Set `model` explicitly in every subagent. Otherwise a `/model` change in the lead reaches the subagents (S11). Thinking cannot be turned off on Opus 5.5, Sonnet 5.5, or Haiku 5.5 (S04), so cost control comes from effort and from fewer calls.

### 4.5 Pausing near limits

Proposed thresholds ([U], policy choice):

1. Before starting a stage: if the five-hour bar is at or above 80%, or the weekly bar is at or above 85%, do not start a new stage. Write a checkpoint, set `paused_limit`, and tell the user to resume later.
2. During a stage: let the current subagent finish. If it returns `partial` (`maxTurns`), do not spawn a continuation unless the bar is below 70%.
3. Hard stop at 95% (five-hour) or 97% (weekly). Do not spawn any subagent. Leave the state in the DB.
4. An automatic wait for a five-hour reset (S08) is allowed only in an interactive session, only for resets within about 24 hours, and only when the policy preset allows it. A weekly limit is a stop, not a wait.
5. If `StopFailure` or a `rate_limit` error appears in `-p` mode, mark `paused_limit` and exit non-zero (S06). Do not retry in a loop.

Remember that the five-hour window starts with the first message, not at a clock hour (S33, secondary).

### 4.6 Cost-control habits

- Stage boundaries: restart the session (`/clear` or a new `claude`) and run `/research resume`. This keeps the context short. Use `/compact <focus>` only inside a long stage (S04).
- Do not use `/loop` for research. Set `CLAUDE_CODE_GOAL_CHECKIN_MINUTES=0` if goals are used (S04, S14).
- Disable idle work: check `idleCompaction` and prompt suggestions in settings (S15, S08). [U] The exact setting that turns off prompt suggestions was not verified.
- Keep CLAUDE.md under 200 lines (S04). Keep specialized rules in skills, which load on demand (S04, S12). Note that skill bodies are re-injected after compaction only up to 5,000 tokens each (S12).
- Keep the MCP tool list small. MCP tool definitions are deferred by default (S04). Do not add or remove MCP servers mid-cycle, because that changes the tool prefix and invalidates the cache (S21).
- Keep the stage prompt prefix stable: fixed system text, fixed tool list, fixed CLAUDE.md. Put variable IDs at the end of the brief (S28, S21).
- Use `maxTurns` on every subagent (S03).
- Use `--max-turns` and `--max-budget-usd` for any `-p` stage (S06, S13). [U] `--max-budget-usd` was named in S04 and S06; its exact behavior was not read.

### 4.7 Budget gate summary

| Check | When | Action |
|---|---|---|
| `/usage` snapshot | Before each gate; on resume | Record bars; apply 4.5 thresholds |
| Spawn cap | Before each spawn | Refuse above cap; ask user |
| Rewind cap | On rewind | Stop at 2 per hypothesis or 10 per cycle (plan section 4) |
| Limit error | On `StopFailure` or `rate_limit` | Set `paused_limit`; no retry loop |

---

## Part 5. Conflicts and unverified items

1. Usage-limit numbers. No official numbers were found. S22 gives structure only. S33 (secondary) gives multiples and weekly periods that disagree with each other. Do not hardcode numbers. Read `/usage` at runtime.
2. Subagent usage and plan limits. S04 says subagent requests draw on usage and appear in attribution. S22 does not say whether subagents count toward the five-hour and weekly limits. Treat them as counting.
3. Headless behavior at a limit. S08 documents automatic wait in interactive sessions only. How a `-p` run reports or handles a limit was not verified. The `api_retry` `rate_limit` category (S06) exists, but the final result subtype was not confirmed.
4. `claude -p` JSON fields. Confirmed: `session_id`, `result`, `total_cost_usd`, `structured_output`. Not confirmed in the read text: `num_turns`, `is_error`, and error subtypes such as `error_max_turns`. Verify with a probe run before relying on them.
5. Hook matchers. All 33 event names are confirmed (S01). Matcher syntax for `SessionStart` and `PreCompact` is shown as plain values (`compact`, `manual`, `auto`). A regex form (`resume|compact`) is an assumption from the text describing `SubagentStart` matchers. Verify with `/hooks`.
6. `StopFailure` matcher values and fields beyond `error`, `error_details`, `last_assistant_message` were not read.
7. Identifying a subagent's caller inside `PreToolUse` was not verified. The plan's open question on role-based MCP writes (plan section 11.2) remains open. Possible routes: a per-role MCP server config, or a token per subagent via `mcpServers`. Both need a test.
8. `CLAUDE_CODE_RESUME_INTERRUPTED_TURN`: documented in S06 and S09, not found in the part of S14 that was read.
9. `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` and `MCP_TIMEOUT`: named in S06 (`MCP_TIMEOUT` default 30 seconds). Not confirmed in the read part of S14. A related name, `MCP_TOOL_TIMEOUT`, appears in another description.
10. Auto-compact thresholds. Only Haiku 5.5 (about 967K tokens) is stated in the read text (S11). Other models were not confirmed.
11. AGENTS.md after compaction. S12 says project-root CLAUDE.md is re-injected from disk. S07 says AGENTS.md is read directly only when there is no CLAUDE.md above it. The plan uses `CLAUDE.md` with `@AGENTS.md`. Whether an imported AGENTS.md is re-injected after compaction was not stated. Test it: compact a session and check `/memory` (S07 says `/memory` lists AGENTS.md).
12. Subagent default background mode. S03 (fetched summary) says a subagent spawned from the main conversation starts in the background by default. Plan section 11.1 treats background subagents as a risk. Set `background: false` explicitly for gated stages, and check the default with a probe.
13. Subagent summary size. S18 says "around 1,000 to 2,000 tokens". This is a reported figure, not a limit. Do not use it as a cap.
14. Harness post file names. S17 names `feature_list.json`; one secondary summary names `tests.json` [S]. Use the post's naming only as a reference.
15. Dates. The multi-agent post (S16) and the harness post (S17) show no date in the fetched text. A secondary source dates S17 to November 2025 [S]. 12-factor (S27) and Manus (S28) dates were not confirmed.
16. ACE and ReasoningBank numbers (S29, S30) are the authors' numbers, from search snippets. They are not used as evidence in this policy.
17. Idle compaction default. S15 names `idleCompaction` but the default was not read. Check before the first long run.
18. Structured outputs. S20 says `output_format` is deprecated in favor of `output_config.format`. Code samples in other pages may use the old name.
19. Stripe retention (S31) is a v1 API fact (24 hours minimum). The local DB design sets its own retention; this is only a pattern reference.
20. `--max-budget-usd` and `--max-turns` on `-p`: `--max-turns` is confirmed (S13). `--max-budget-usd` is named (S04, S06) but its behavior was not read.
21. `-p` and subscription login. S06 says bare mode does not use the subscription login. It does not say whether non-bare `-p` runs use the subscription. The plan's `claude -p` button question (plan section 12) stays open.

---

## Part 6. URL index

Fetched in this run (tag [V]):
- https://code.claude.com/docs/en/hooks.md
- https://code.claude.com/docs/en/hooks-guide.md
- https://code.claude.com/docs/en/sub-agents.md
- https://code.claude.com/docs/en/costs.md
- https://code.claude.com/docs/en/checkpointing.md
- https://code.claude.com/docs/en/headless.md
- https://code.claude.com/docs/en/memory.md
- https://code.claude.com/docs/en/interactive-mode.md
- https://code.claude.com/docs/en/sessions.md
- https://code.claude.com/docs/en/errors.md
- https://code.claude.com/docs/en/model-config.md
- https://code.claude.com/docs/en/context-window.md
- https://code.claude.com/docs/en/cli-reference.md
- https://code.claude.com/docs/en/env-vars.md
- https://code.claude.com/docs/en/settings-reference.md
- https://www.anthropic.com/engineering/multi-agent-research-system
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://www.anthropic.com/engineering/building-effective-agents
- https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan
- https://openai.github.io/openai-agents-python/handoffs/
- https://openai.github.io/openai-agents-python/sessions/
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://github.com/humanlayer/12-factor-agents
- https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- https://docs.stripe.com/api/idempotent_requests
- https://json-schema.org/draft/2020-12

Search results only (tag [S]):
- https://arxiv.org/abs/2510.04618
- https://arxiv.org/pdf/2509.25140
- https://portkey.ai/blog/claude-code-limits
- https://www.ai-toolbox.co/claude-management-and-productivity/claude-usage-limits-2026
- https://alexcloudstar.com/blog/claude-code-usage-limits-2026/

Linked from a fetched page but not fetched: https://docs.langchain.com/oss/python/langgraph/checkpointers.md (linked from S26).
