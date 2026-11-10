# Skills, Subagents and Orchestration for EasyResearch: Sources and Drafts

- Date: 2026-11-10
- Input: ExecPlan 006 (`docs/exec-plans/active/006-claude-code-research-system.md`), the four skills in `services/mcp/skills/`, and existing reports E-L (not re-researched here).
- Scope: Claude Code skills, subagents, hooks, permissions, MCP config, skill authoring and evaluation, research-oriented skill and agent sets, verifier and debate designs.
- File name note: the requested name uses "N". The next free letter after L is M. Rename if you meant M.

## Legend

- [V] Read on the primary page in this session with WebFetch. Quotes come from the fetch summary, so check exact wording before quoting in user-facing text. Long pages were read in part (first 100k characters) where noted.
- [S] Search snippet or secondary/aggregator summary only. Not used as a basis for a design decision without a primary check.
- [U] Unverified. My proposal or inference. Needs a test in this repo before it is relied on.

## Top findings

1. Four platform facts change ExecPlan 006 (all [V]):
   - Subagents never get `AskUserQuestion`. Approval gates therefore have to run in the main thread, between subagent calls. A skill with `context: fork` cannot ask the user.
   - Background subagents (the default for subagents Claude spawns) keep `WebFetch` and `WebSearch`. The design's "no web tools" rule needs explicit `disallowedTools`.
   - A subagent's `permissionMode` is ignored when the main session runs in `acceptEdits`, `auto`, or `bypassPermissions`. Hooks and deny rules still apply.
   - Plugin subagents ignore `hooks`, `mcpServers`, and `permissionMode`. Keep the research agents as project files in `.claude/agents/`, not inside a plugin.
2. AGENTS.md is read only when there is no CLAUDE.md in the working directory or above. Add a `CLAUDE.md` that imports `@AGENTS.md` (documented pattern) and keep it short.
3. Project MCP servers prompt for approval in interactive sessions, but `claude -p` runs load them without prompting. The planned "run from the app" button needs this risk handled, not just the subscription check already listed in ExecPlan 006.
4. Source correction: arXiv 2502.18864 is "Towards an AI co-scientist" (Google), not ResearchAgent. ResearchAgent is arXiv 2404.07738.
5. Verifier criteria are thinly evidenced. ResearchAgent names three review criteria (novel, clear, valid). The AI Scientist abstract names none. Si et al. find that LLM ideas rate more novel but slightly less feasible, and novelty judgments are hard even for experts. So the verifier should check testable things (citations, prior-work distance, falsifiability, feasibility) and leave novelty to the human, as ExecPlan 006 already decides.
6. Skill listings cost context on every turn. Keep stage content in subagent bodies or preloaded skills, not in many user-visible skills.

## Field reference (verified)

| Area | Verified facts | Source |
|---|---|---|
| Skill frontmatter | `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context` (`fork`), `agent`, `background` (default true with fork), `hooks`, `paths`, `shell` (`bash` or `powershell`), `metadata`, `license`, `compatibility` (max 500 chars) | S1 |
| Skill listing | `description` + `when_to_use` truncated at 1,536 chars in the listing; SKILL.md under 500 lines recommended | S1 |
| Invocation | default: user and Claude can invoke; `disable-model-invocation: true` = user only, cannot be preloaded by a subagent; `user-invocable: false` = Claude only, description always in context | S1, S2 |
| Skill arguments | `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, named `$name` from `arguments`, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_EFFORT}` | S1 |
| Skill locations | `~/.claude/skills/` (personal), `.claude/skills/` (project); Claude Code skills are filesystem-based and have full network access | S11 |
| Subagent frontmatter | `name` (max 256 chars, no `:`), `description`, `tools`, `disallowedTools`, `model` (`sonnet`, `opus`, `haiku`, `fable`, full ID, `inherit`), `permissionMode` (`default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan`, `manual`), `maxTurns`, `skills` (full content preloaded, max 32 names), `mcpServers`, `hooks`, `memory` (`user`, `project`, `local`), `background`, `omitClaudeMd`, `effort`, `isolation` (`worktree`), `color`, `initialPrompt`, `experimental`, `autoCompactWindow` | S2 |
| Subagent tools | `tools` = allowlist, `disallowedTools` = denylist applied first; inherits everything if `tools` omitted | S2 |
| Always removed from subagents | `AskUserQuestion`, `EndConversation`, `EnterPlanMode`, `ExitPlanMode` (unless plan mode), `ScheduleWakeup`, `WaitForMcpServers`, `Workflow`; `Agent` at the depth limit | S2 |
| Background subagent tools | `Read`, `Grep`, `Glob`, `LSP`, `Bash`, `PowerShell`, `Edit`, `Write`, `NotebookEdit`, `WebFetch`, `WebSearch`, `TodoWrite`, `Skill`, `ToolSearch`, `EnterWorktree`, `ExitWorktree`, `Monitor`, `TaskStop`, `SendMessage`, `Artifact`, `SubagentHandback`; all MCP tools kept. Forks get the full pool | S2 |
| Nesting | default 3 layers below main; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (`1` disables nesting); `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` default 20 | S2 |
| Memory scopes | `user` ~/.claude/agent-memory/<name>/, `project` .claude/agent-memory/<name>/, `local` .claude/agent-memory-local/<name>/; first 200 lines or 25KB of MEMORY.md; enables Read/Write/Edit automatically | S2, S7 |
| Built-in subagents | Explore, Plan, general-purpose, claude, statusline-setup (Sonnet), claude-code-guide (Haiku); disable with `permissions.deny: ["Agent(Explore)"]` | S2 |
| Hook events | SessionStart, Setup, SessionEnd, UserPromptSubmit, UserPromptExpansion, Stop, StopFailure, PreToolUse, PermissionRequest, PermissionDenied, PostToolUse, PostToolUseFailure, PostToolBatch, SubagentStart, SubagentStop, TaskCreated, TaskCompleted, TeammateIdle, InstructionsLoaded, ConfigChange, CwdChanged, DirectoryAdded, FileChanged, WorktreeCreate, WorktreeRemove, PreCompact, PostCompact, PreModelSwitch, PostModelSwitch, Notification, MessageDisplay, Elicitation, ElicitationResult | S3 |
| Hook input | common: `session_id`, `prompt_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `permission_mode`, `effort`, `hook_event_name`; agent context: `agent_id`, `agent_type`; tool events: `tool_name`, `tool_input`, `tool_use_id` | S3 |
| Hook decisions | exit 0 = success (JSON parsed if single object); exit 2 = block on blocking events, stderr is the reason; other codes = non-blocking error (exit 1 is not a block). PreToolUse JSON: `hookSpecificOutput.permissionDecision` = `allow`, `deny`, `ask`, `defer`. Multiple PreToolUse results combine most-restrictive-first: deny, defer, ask, allow | S3, S4 |
| Hook matchers | `*`, empty, or omitted = all; letters/digits/`_`/`-`/`,`/`\|` = exact name or list; anything else = unanchored JavaScript regex. MCP tools are `mcp__<server>__<tool>`; `mcp__memory__.*` matches all tools on a server; bare `mcp__memory` matches nothing | S3, S4 |
| Hook types | `command` (`command`, `args`, `shell` = `bash` or `powershell`, `onFailure`), `http`, `mcp_tool`, `prompt`, `agent` (experimental); default timeouts 600s (command, http, mcp_tool), 30s (prompt), 60s (agent); `if` field takes a permission-rule expression | S3 |
| Protected-file hook example | `PreToolUse` with `matcher: "Edit\|Write"`, script exits 2 on protected patterns | S4 |
| ConfigChange | matcher values `user_settings`, `project_settings`, `local_settings`, `policy_settings`, `skills`; exit 2 or `{"decision":"block"}` blocks the change | S4 |
| Permission modes | `default` (reads only auto), `acceptEdits`, `plan`, `auto` (classifier; explicit ask rules still prompt), `dontAsk` (deny what would prompt; explicit allow still works), `bypassPermissions`; deny rules block in every mode; allow rules have no effect in `bypassPermissions`; `defaultMode` `auto` and `bypassPermissions` do not take effect from project or local settings | S5, S8 |
| Protected paths | documented examples `.git`, `.claude`, `.bashrc`, `.mcp.json` are not auto-approved by allow rules; `AGENTS.md` and `data/` are not among the examples, so they need explicit deny rules | S5 |
| Permission rule names | `Bash(npm run build)`, `Bash(git push *)`, `Read(./.env)`, `Edit(path)` covers all built-in editing tools, `WebFetch(domain:example.com)`, `Agent(model:opus)`, `Agent(isolation:worktree)`, `Agent(Explore)` | S6, S2 |
| MCP rules | `mcp__server` and `mcp__server__tool`; allow globs only after a literal `mcp__<server>__` prefix (`mcp__puppeteer__*` valid, `mcp__*` allow skipped); deny `mcp__*` removes all MCP tools; parentheses in `mcp__` rules are skipped with a warning | S6 |
| Bare tool deny | a bare name in `deny` (e.g. `WebFetch`) removes the tool from Claude's context for the whole session, including the main thread | S6 |
| Read/Edit limits | `Grep(docs/**)` deny does not stop Grep; use `Read(docs/**)`; `.claudeignore` has no effect; Read deny is best effort for Grep/Glob and @-mentions | S6 |
| Settings precedence | managed > command line (`--settings`) > `.claude/settings.local.json` > `.claude/settings.json` > `~/.claude/settings.json`; list keys such as `permissions.allow` merge across files; `.claude/settings.json` `allow` rules for the project wait for workspace trust; `deny` and `ask` apply at once | S8 |
| Project MCP file | `.mcp.json` at project root, key `mcpServers`; `type` = `http`, `sse` (deprecated), `ws`, alias `streamable-http`; stdio entries have no `type`; `${VAR}` and `${VAR:-default}` expansion in command, args, env, url, headers; `timeout` per server (ms); interactive sessions prompt for approval on first use; `claude -p` and Agent SDK sessions load project servers without prompting; `disabledMcpjsonServers` blocks a server | S9 |
| MCP output | warning at 10,000 tokens; default max 25,000 tokens (`MAX_MCP_OUTPUT_TOKENS`); text results over 50,000 characters are saved to a file unless the server raises the limit | S9 |
| Plugins | manifest `.claude-plugin/plugin.json`; components `skills/`, `agents/`, `hooks/hooks.json`, `.mcp.json`; plugin skills run as `/<plugin>:<skill>`; enabled plugins add name and description of every model-invocable skill and agent to context each turn | S10 |
| CLAUDE.md / AGENTS.md | CLAUDE.md target under 200 lines; AGENTS.md read only when no CLAUDE.md in working directory or above (requires Claude Code v2.1.277+); CLAUDE.md can `@AGENTS.md`-import it; `.claude/rules/*.md` with `paths:` frontmatter loads only for matching files | S7 |
| Skill spec (open) | name max 64 chars, lowercase/digits/hyphens, no leading/trailing or double hyphen, must match directory; description max 1024 chars; compatibility max 500; `allowed-tools` space-separated, experimental | S13 |
| Skill spec (API) | name cannot contain reserved words `anthropic` or `claude`; description max 1,024 chars, no XML tags | S11, S12 |

## Part 1. Source records

Records are grouped by type. Each lists title, organization, date, URL, tag, bullets, relevance. Quotes: at most one per record, under 15 words.

### A. Official Claude Code and platform docs

**S1. Extend Claude with skills (Claude Code docs)**
- Org: Anthropic. Date: undated page, read 2026-11-10. URL: https://code.claude.com/docs/en/skills. Tag: [V].
- Full frontmatter list, invocation-control table, string substitutions, `context: fork`, `agent`, `background`, `hooks`, `paths`, `shell`.
- Listing truncation at 1,536 chars for description plus when_to_use. SKILL.md under 500 lines.
- `allowed-tools` pre-approves tools only during the turn that invokes the skill. `model` and `effort` apply to the rest of the turn.
- Relevance: all skill frontmatter in Part 2 comes from this page.

**S2. Create custom subagents (Claude Code docs)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://code.claude.com/docs/en/sub-agents. Tag: [V].
- Frontmatter table, tool inheritance, background tool filter, always-removed tools, nesting depth and env vars.
- Skill preloading: full content injected, max 32 names; `disable-model-invocation` skills cannot be preloaded.
- `permissionMode` override by the main session mode; plugin subagents ignore hooks, mcpServers, permissionMode.
- Relevance: all agent definitions in Part 3 use only these fields.

**S3. Hooks reference (Claude Code docs)**
- Org: Anthropic. Undated, read 2026-11-10 (first 100k of 292k chars). URL: https://code.claude.com/docs/en/hooks. Tag: [V].
- Full event list (including SubagentStart, SubagentStop, PermissionDenied, ConfigChange, FileChanged), common and tool input fields, exit code semantics.
- PreToolUse decisions (`allow`, `deny`, `ask`, `defer`); MCP tools appear as `mcp__<server>__<tool>` in matchers; hook types command, http, mcp_tool, prompt, agent.
- SubagentStop is listed among events where top-level `decision` applies. Known issue reports for SubagentStop in the VS Code extension exist ([S], S36).
- Relevance: guard hooks in Part 4.

**S4. Automate actions with hooks (hooks guide)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://code.claude.com/docs/en/hooks-guide. Tag: [V].
- Protected-files example: PreToolUse on `Edit|Write`, script exits 2 with a message; Claude receives the message as feedback.
- Exit 0 does not approve the tool call; the normal permission flow still runs.
- ConfigChange matcher values and exit 2 blocking; the `if` field filters on permission-rule syntax.
- Relevance: model for the Part 4 guard script and the ConfigChange guard.

**S5. Permission modes (Claude Code docs)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://code.claude.com/docs/en/permission-modes. Tag: [V].
- Mode table; deny rules block in every mode including `bypassPermissions`; ask rules prompt even in `bypassPermissions`.
- Documented protected-path examples (`.git`, `.claude`, `.bashrc`, `.mcp.json`) are not auto-approved by allow rules; auto mode drops broad allow rules such as `Bash(*)` and `Agent`. `AGENTS.md` and `data/` are not among the examples, so they need explicit deny rules [U].
- Relevance: explains why `permissionMode` on research agents is unreliable when the main session is in a permissive mode.

**S6. Configure permissions (Claude Code docs)**
- Org: Anthropic. Undated, read 2026-11-10 (saved summary of permissions page). URL: https://code.claude.com/docs/en/permissions. Tag: [V].
- Rule syntax for Bash (wildcards, compound commands split, wrappers stripped), Read/Edit path patterns (`//`, `~/`, `/`), `WebFetch(domain:...)`, `Agent(...)` parameter rules.
- MCP rules: `mcp__server__tool`, globs only after a literal server prefix, `mcp__*` deny removes all MCP tools.
- `.claudeignore` has no effect; Read deny is best effort for Grep and Glob.
- Relevance: all permission rules in Part 4.

**S7. How Claude remembers your project (CLAUDE.md, AGENTS.md, auto memory)**
- Org: Anthropic. Undated, read 2026-11-10 (saved summary). URL: https://code.claude.com/docs/en/memory. Tag: [V].
- AGENTS.md is read in place of CLAUDE.md only when no CLAUDE.md exists in the working directory or above; a CLAUDE.md can import AGENTS.md; needs v2.1.277+.
- CLAUDE.md under 200 lines recommended; `.claude/rules/` with `paths:` frontmatter loads on matching files only.
- Auto memory first 200 lines or 25KB; subagents can keep their own memory.
- Relevance: root-level instruction setup in Part 4.

**S8. Settings files and precedence (Claude Code docs)**
- Org: Anthropic. Undated, read 2026-11-10 (saved summary). URL: https://code.claude.com/docs/en/settings. Tag: [V].
- Scopes and files: `~/.claude/settings.json`, `.claude/settings.json` (commit it), `.claude/settings.local.json` (kept out of git), managed.
- Precedence and list merging; `permissions.defaultMode` `auto` and `bypassPermissions` do not take effect from project or local files.
- Project `allow` rules and `additionalDirectories` wait for workspace trust; `deny` and `ask` apply immediately.
- Relevance: where guard rules go and which keys cannot be set from the repo.

**S9. Connect Claude Code to tools via MCP (Claude Code docs)**
- Org: Anthropic. Undated, read 2026-11-10 (first 100k of 157k). URL: https://code.claude.com/docs/en/mcp. Tag: [V].
- `.mcp.json` format, transport types, `${VAR:-default}` expansion, first-use approval, `claude -p` loads without prompting.
- Output limits: 10,000-token warning, 25,000-token default, 50,000-character file spill.
- Relevance: MCP wiring and the output-size plan for paper text tools.

**S10. Plugins overview (Claude Code docs)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://code.claude.com/docs/en/plugins. Tag: [V].
- Plugin components and manifest location; plugin skills appear as `/<plugin>:<skill>`.
- Enabled plugins add name and description of model-invocable skills and agents to context on every turn.
- Relevance: why the research system stays in `.claude/` rather than a plugin for now.

**S11. Agent Skills overview (Claude Platform docs)**
- Org: Anthropic. Undated (metadata lists models up to claude-haiku-5-5), read 2026-11-10. URL: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview. Tag: [V].
- Three loading levels: metadata (about 100 tokens), instructions (under 5k tokens), resources (on demand).
- Claude Code skills are filesystem-based, placed in `~/.claude/skills/` or `.claude/skills/`, with full network access (contrast with the API sandbox, which has none).
- Relevance: progressive-disclosure budget for Part 2.

**S12. Skill authoring best practices (Claude Platform docs)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices. Tag: [V].
- Description: third person, both what and when; name max 64 chars, reserved words `anthropic`/`claude`; description max 1,024 chars.
- Keep references one level deep; table of contents for files over 100 lines; forward slashes in paths.
- Evaluation-first development; test with Haiku, Sonnet and Opus; validate-fix-repeat loops; explicit "solve, don't defer" for scripts.
- Relevance: authoring rules for every skill in Part 2.

**S13. Agent Skills specification (agentskills.io)**
- Org: Agent Skills project (open spec). Undated, read 2026-11-10. URL: https://agentskills.io/specification. Tag: [V].
- Frontmatter table: `name` 1-64 chars, must match parent directory, no consecutive hyphens; `description` 1-1024; `compatibility` 1-500; `metadata` string map; `allowed-tools` experimental, space-separated.
- Optional directories `scripts/`, `references/`, `assets/`; progressive disclosure levels with token guidance.
- Relevance: portable subset of frontmatter; keeps the four migrated skills valid.

**S14. anthropics/skills (GitHub repository)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://github.com/anthropics/skills. Tag: [V].
- Public skill collection; repository layout `.claude-plugin`, `skills`, `spec`, `template`; Apache 2.0 for many skills.
- Installable as a Claude Code plugin marketplace (`/plugin marketplace add anthropics/skills`).
- Relevance: source of the skill-creator workflow (S15) and a template for a skills marketplace later.

**S15. skill-creator SKILL.md (anthropics/skills)**
- Org: Anthropic. Undated, read 2026-11-10 via raw file. URL: https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md. Tag: [V].
- Eval file `evals/evals.json` with `id`, `prompt`, `expected_output`, `files`; `assertions` added later.
- Runs with-skill and baseline in the same turn; grader writes `grading.json` with `text`, `passed`, `evidence`; `aggregate_benchmark` script; `agents/comparator.md` for blind A/B.
- Description optimization: about 20 queries (8-10 should trigger, 8-10 should not, near-miss negatives), 60/40 train/test split, each query run 3 times, up to 5 iterations, best description chosen by held-out score.
- Relevance: procedure for M4 skill evaluation (Part 2, skill-eval-ab).

**S16. How we built our multi-agent research system (Anthropic engineering)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://www.anthropic.com/engineering/multi-agent-research-system. Tag: [V].
- Orchestrator-worker design: lead agent plans and spawns subagents that search in parallel; a separate CitationAgent attributes claims.
- Reported Opus-lead plus Sonnet-subagent system beat single-agent Opus by 90.2% on an internal research eval. Agents use about 4x chat tokens; multi-agent about 15x.
- Subagent briefs must include an objective and an output format. LLM-as-judge rubric: factual accuracy, citation accuracy, completeness, source quality, tool efficiency; a 0.0-1.0 pass/fail judgment was most consistent.
- Relevance: brief template for delegation (Part 3) and cost warning for the 7-agent design.

**S17. Building effective agents (Anthropic engineering)**
- Org: Anthropic. Undated, read 2026-11-10. URL: https://www.anthropic.com/engineering/building-effective-agents. Tag: [V].
- Five patterns: prompt chaining, routing, parallelization (sectioning and voting), orchestrator-workers, evaluator-optimizer.
- Advice: start with the simplest solution; agents cost more and can compound errors, so they need guardrails.
- Relevance: justify workflow-style stages in `/research` where order is fixed (gates, backtracks), and agents only for open-ended steps.

**S18. AGENTS.md (open format)**
- Org: AGENTS.md project. Undated, read 2026-11-10. URL: https://agents.md. Tag: [V].
- Plain Markdown with no required fields; nearest file in the directory tree takes precedence; explicit chat instructions override it.
- Relevance: the existing repository `AGENTS.md` is valid as is; it must be made Claude-correct (design section 2).

### B. Community skill and agent sets

**S19. K-Dense scientific agent skills (GitHub)**
- Org: K-Dense-AI. Undated, read 2026-11-10. URL: https://github.com/K-Dense-AI/claude-scientific-skills (the page resolves to the repo named scientific-agent-skills). Tag: [V].
- About 177 skills, each in `skills/<name>/SKILL.md`; test suites under `tests/<skill-name>/` for scripted skills.
- Verified skill names from the page: `database-lookup`, `paper-lookup`, `scientific-writing`. The page also lists research categories (literature review and paper search, evidence-traceable writing, confidential peer review, hypothesis generation, scientific brainstorming, critical thinking, citation management); exact directory names for those were not confirmed (a directory fetch returned 404).
- Install through `npx skills add`; installing files does not install Python dependencies; per-skill licenses differ from MIT.
- Relevance: candidates for reuse of literature-screen and citation-check wording after license review. Do not copy wholesale.

**S20. obra/superpowers (GitHub)**
- Org: obra. Undated, read 2026-11-10. URL: https://github.com/obra/superpowers. Tag: [V].
- Skills named: brainstorming, writing-plans, subagent-driven-development, executing-plans, test-driven-development, requesting-code-review, verification-before-completion, finishing-a-development-branch, dispatching-parallel-agents, systematic-debugging, writing-skills.
- Subagent-driven development: fresh subagent per task, two-stage review (spec compliance, then code quality).
- "Evidence over claims" as a core principle; verification-before-completion as a completion gate.
- Relevance: pattern for the verifier gate and the two-stage review (spec, then quality) for research cycles.

### C. Research automation and critique papers

**S21. The AI Scientist (arXiv:2408.06292)**
- Org: not stated on the abstract page (authors Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jeff Clune, David Ha). Date: 2024-08-12 (v1), 2024-09-01 (v3). URL: https://arxiv.org/abs/2408.06292. Tag: [V].
- End-to-end: ideas, code, experiments, paper, simulated review; under $15 per paper per the abstract; three ML subfields.
- The automated reviewer is described as reaching "near-human performance in evaluating paper scores"; the abstract names no reviewer criteria and gives no agreement numbers.
- Relevance: evidence that an LLM reviewer is used, but its criteria are not public in the abstract; treat as a design sketch, not validation.

**S22. The AI Scientist-v2 (arXiv:2504.08066)**
- Org: not stated on the abstract page (first authors Yutaro Yamada, Robert Tjarko Lange, Cong Lu). Date: 2025-04-10. URL: https://arxiv.org/abs/2504.08066. Tag: [V].
- Agentic tree search guided by an experiment manager agent; removes human-written code templates; vision-language feedback for figures.
- Three fully autonomous manuscripts submitted to a workshop; one scored above the average human acceptance threshold (per abstract).
- Limitations are not listed on the abstract page. Relevance: the search-tree idea maps to backtracking in ExecPlan 006 section 4; no evidence transfer to literature research.

**S23. ResearchAgent (arXiv:2404.07738)**
- Org: not stated on the abstract page (authors Jinheon Baek, Sujay Kumar Jauhar, Silviu Cucerzan, Sung Ju Hwang). Date: 2024-04-11 (v1), 2025-02-09 (v2). URL: https://arxiv.org/abs/2404.07738. Tag: [V].
- Pipeline: core paper, enrichment from a literature graph, knowledge store, then reviewing agents whose feedback drives revision.
- Reviewing criteria named on the abstract: novel, clear, valid. Reviewing agents are "tuned to human preferences".
- No quantitative results on the abstract page.
- Relevance: the only source here that names an explicit critic criteria set; use as the basis for the verifier's reading criteria, with evidence rules added.

**S24. Towards an AI co-scientist (arXiv:2502.18864)**
- Org: not stated on the page (51 authors; abstract says the system is built on Gemini). Date: 2025-02-26 (v1), 2026-06-29 (v2). URL: https://arxiv.org/abs/2502.18864. Tag: [V].
- Generate, debate, and evolve: agents produce, critique and refine hypotheses; tournament-style evolutionary ranking; test-time compute scaling.
- Validation on drug repurposing, target discovery, and antimicrobial resistance; no reviewing criteria or numbers on the page.
- Relevance: supports a debate-and-tournament pattern; the tournament over hypotheses is a later option, not M3.

**S25. POPPER: Automated Hypothesis Validation with Agentic Sequential Falsifications (arXiv:2502.09858)**
- Org: authors Kexin Huang, Ying Jin, Ryan Li, Michael Y. Li, Emmanuel Candes, Jure Leskovec (affiliation not read). Date: 2025-02-14. URL: https://arxiv.org/abs/2502.09858. Tag: [V].
- Takes free-form hypotheses as input; LLM agents design and run experiments aimed at measurable consequences; sequential testing controls Type-I error.
- Six domains; reports matching human scientists on complex biology hypotheses with about 10x less time (abstract).
- Relevance: falsifiability rule in the verifier (expected result fixed before testing; failure threshold written in the card).

**S26. Improving Factuality and Reasoning through Multiagent Debate (arXiv:2305.14325)**
- Org: affiliation not read (authors Yilun Du, Shuang Li, Antonio Torralba). Date: 2023-05-23. URL: https://arxiv.org/abs/2305.14325. Tag: [V].
- Several model instances propose answers and debate over rounds to a joint answer.
- Reports gains in math and strategic reasoning and fewer hallucinations; the page does not name benchmarks or rounds.
- Relevance: basis for a bounded two-round debate; limit rounds, because the reported gains are not tied to numbers here.

**S27. Debating with More Persuasive LLMs Leads to More Truthful Answers (arXiv:2402.06782)**
- Org: affiliation not read (authors Akbir Khan, John Hughes, Dan Valentine and six others). Date: 2024-02-09 (v4 2024-07-25). URL: https://arxiv.org/abs/2402.06782. Tag: [V].
- Two expert debaters argue opposing answers; a non-expert judge picks. Non-expert accuracy 76% with debate vs 48% baseline; human judges 88% vs 60%.
- Persuasive debaters improved judge accuracy.
- Relevance: supports a judge who sees both sides and cites; also warns that persuasion is not truth, so verdicts must rest on quotes.

**S28. Reflexion (arXiv:2303.11366)**
- Org: Noah Shinn, Federico Cassano, Edward Berman and others. Date: 2023-03-20 (v4 2023-10-10). URL: https://arxiv.org/abs/2303.11366. Tag: [V].
- Verbal reflections stored in episodic memory guide later attempts; no weight updates.
- Reports 91% pass@1 on HumanEval vs 80% for GPT-4 baseline on the abstract.
- Relevance: failure-ledger design (store reflection, reuse on the next attempt); coding benchmark, not research.

**S29. Self-Refine (arXiv:2303.17651)**
- Org: Aman Madaan, Niket Tandon, Prakhar Gupta and others. Date: 2023-03-30 (v2 2023-05-25). URL: https://arxiv.org/abs/2303.17651. Tag: [V].
- One model generates, critiques itself, and refines; no training data needed.
- About 20 percentage points average gain over single-pass output across seven tasks (abstract summary).
- Relevance: supports critique-then-revise loops; same-model self-critique is the weakness the verifier must be designed around (S33).

**S30. Agentic Context Engineering (arXiv:2510.04618)**
- Org: affiliation not read (first author Qizheng Zhang and 12 co-authors per search summary). Date: 2025-10-06 (v3 2026-03-29). URL: https://arxiv.org/abs/2510.04618. Tag: [V] (abstract); roles from [S].
- Context as an evolving playbook updated by small deltas; reported +10.6% on agent benchmarks and +8.6% on finance (abstract).
- Names "context collapse, where iterative rewriting erodes details over time".
- Generator, Reflector, and Curator roles (search summary only).
- Relevance: lesson ledger should be itemized and append-only, not rewritten wholesale (lesson-curator design).

**S31. ReasoningBank (arXiv:2509.25140)**
- Org: Siru Ouyang and 16 co-authors (Google, Yale, UIUC per search summary). Date: 2025-09-29 (v2 2026-03-16). URL: https://arxiv.org/abs/2509.25140. Tag: [V] (abstract, no numbers).
- Memory items distilled from successes and failures, judged by the agent without labels; retrieved into the system prompt on later tasks.
- Abstract reports gains over memory methods that store raw trajectories or only successes; it gives no numbers. Numbers seen in search snippets were not on the abstract, so none are used here.
- Relevance: supports keeping failure lessons as well as successes; retrieval by embedding search is a later option.

**S32. Can LLMs Generate Novel Research Ideas? (arXiv:2409.04109)**
- Org: affiliation not read (authors Chenglei Si, Diyi Yang, Tatsunori Hashimoto). Date: 2024-09-06. URL: https://arxiv.org/abs/2409.04109. Tag: [V].
- Large human study with 100+ NLP researchers: LLM ideas judged more novel than expert ideas (p < 0.05) and slightly weaker on feasibility.
- Authors note even experts find novelty judgments difficult and propose execution studies to test them.
- Relevance: the verifier must not decide novelty; feasibility is a separate criterion; human novelty decision stays (ExecPlan 006 section 5).

**S33. LLM Evaluators Recognize and Favor Their Own Generations (arXiv:2404.13076)**
- Org: affiliation not read (authors Arjun Panickssery, Samuel R. Bowman, Shi Feng). Date: 2024-04-15. URL: https://arxiv.org/abs/2404.13076. Tag: [V].
- GPT-4 and Llama 2 recognize their own text above chance; fine-tuning shows a linear link between self-recognition and self-preference.
- No numbers on the abstract page.
- Relevance: same-family verifier bias is real. Mitigations are in Part 3 (verifier independence) and Part 5 (risks).

**S34. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (arXiv:2306.05685)**
- Org: affiliation not read (authors Lianmin Zheng, Wei-Lin Chiang, Ying Sheng and co-authors). Date: 2023-06-09 (revised 2023-12-24). URL: https://arxiv.org/abs/2306.05685. Tag: [V].
- Position, verbosity, and self-enhancement biases documented; strong judges agree with human preferences over 80% of the time, comparable to human-human agreement (per abstract).
- Relevance: use LLM judgments as checkable signals with reason codes, not as final authority; randomize order in A/B tests.

**S35. OpenReviewer (arXiv:2412.11948)**
- Org: Maximilian Idahl and Zahra Ahmadi. Date: 2024-12 (v1), later revisions 2025. URL: https://arxiv.org/abs/2412.11948. Tag: [S] (search summary; not opened).
- 8B model fine-tuned on about 79,000 expert reviews; takes PDF and conference review template; open source; NAACL 2025 demo track.
- Author statement: not intended to replace human peer review; a third-party summary cites an error figure that was not checked.
- Relevance: review-template approach for a later reviewer skill; check the paper before using any figure.

**S36. SubagentStop command hook known issue (GitHub issue tracker)**
- Org: Claude Code issue tracker (community-reported). Date: undated in search result. URL: https://claudeissues.com/issue/39030-bug-subagentstop-command-hook-not-firing-in-vs-code-ide-extension. Tag: [S].
- Report says SubagentStop command hooks in project settings did not fire when subagents completed in the VS Code extension.
- Another report describes SubagentStop firing at startup.
- Relevance: do not rely on SubagentStop for hard gates; use PreToolUse and the app's own checks, and test in the CLI.

## Part 2. Skill catalog

Conventions for every skill:
- Directory name equals `name`; lowercase, hyphens, no `claude` or `anthropic` substring (S12, S13).
- `SKILL.md` under 500 lines; reference files one level deep; table of contents for files over 100 lines (S12).
- Description drafts are at most 1024 characters (S12, S13) and written in the third person; combined with `when_to_use` they stay under the 1,536-character listing cutoff (S1).
- Paths use forward slashes (S12).
- Inline skills that open gates are main-thread only; preloaded skills contain no write instructions without a gate (see "Design rule" below).

Design rule for gates: a preloaded skill (loaded into a subagent) cannot ask the user (S2). Any write that needs approval must return a proposal to the main thread, which asks the user and then calls the write tool. This is why `gap-finder` is split into `gap-scan` and `gap-save`.

### 2.1 Orchestration

**research** (/research)
> Runs one EasyResearch research cycle from a topic to an experiment-plan handoff. Plans the cycle, delegates literature search, paper reading, hypothesis building, verification and lesson curation to the project subagents, asks the user at gate points defined by the approval policy, and enforces backtrack limits. Use when the user asks to start, resume or report on a research cycle for a topic. Does not browse the web or run experiments.

- Invocation: `disable-model-invocation: true` (user-only; it writes cycle state and spends budget). User-invocable. [S1]
- `allowed-tools`: `mcp__easyresearch__list_research_runs mcp__easyresearch__get_research_run mcp__easyresearch__list_library_papers Agent` [U: names proposed; space-separated per S13; `Agent` entry unverified in Claude Code].
- `argument-hint`: `[topic] [policy: careful|balanced|auto]`. `arguments: [topic, policy]` for `$topic`, `$policy`.
- `effort: high`. Do not set `model` here (it would switch the whole main session; [U]).
- Context: inline, not forked (gates need AskUserQuestion; Agent spawning needs the main thread).
- Supporting files: `stages.md` (stage table with input, output, subagent, gate), `backtrack-rules.md` (per hypothesis 2, per cycle 10, escalate on repeated reason code; from ExecPlan 006 section 4).
- Preloads: none (main thread). Delegates to 6 subagents listed in Part 3.
- Inputs: topic, policy name (missing = careful), optional cycle id. Outputs: stage status, pending gate question, final handoff summary.

**research-app-run** (offline mode, migrated from research-loop app-run section)
> Checks or advances an EasyResearch research run started in the desktop app, without the Claude Code cycle. Use when the user asks for the status of an app-side research run, or to read its results. Does not start, advance or cancel runs through MCP.

- Invocation: default user-invocable, `disable-model-invocation: true`. Allowed-tools: `mcp__easyresearch__list_research_runs mcp__easyresearch__get_research_run`. Inline. Outputs: status, stage, waiting-for-review flag.

### 2.2 Gate and policy

**gate-policy**
> Reads the EasyResearch approval policy and reports, for a given stage boundary, whether the user must confirm before the next step, plus the non-disableable rules for consent to send library content, experiment-plan lock, and skill or prompt changes. Use while a research cycle is running, before advancing a stage. Never writes policy.

- Invocation: `user-invocable: false` (Claude-only; listed every turn, so keep the description short if many skills exist). [S1]
- `allowed-tools`: `mcp__easyresearch__get_gate_policy` (read-only) [U].
- Inline in the main thread; loaded when the orchestrator needs it.
- Supporting: `gates.md` (gate ids, default per preset, lock rules).
- Inputs: cycle id, stage id, preset. Outputs: `{gate, action: "ask" | "auto", reason}`. Missing policy means `careful`.

### 2.3 Stage skills (preloaded into subagents)

**literature-screen** (preloaded by literature-scout)
> Designs at least three literature search queries from different angles for one research question, runs them through the app's search tool, removes duplicates, and screens each result into include or exclude with a reason code. Use when a research cycle needs candidate papers or citation-following for a topic. Does not read full text.

- Invocation: `user-invocable: false`. No `allowed-tools` needed (inherits agent tools) [U].
- Supporting: `screening-criteria.md` (generic reason codes such as `off_topic`, `no_method`, `duplicate`, `low_relevance`, `include`; exact list to be set by the user).
- Inputs: question, cycle id, limits (max results per query). Outputs: queries used, included list with reason, citation-following candidates.

**paper-deep-read** (migrated paper-profile; preloaded by paper-analyst; user-invocable)
> Builds a structured, page-cited reading of one paper in the EasyResearch library: problem, method, limitations, open questions, datasets and results, with 1-based physical page quotes, each marked author-stated or inferred. Use when the user or a research cycle asks to profile, summarize or extract limitations from a specific library paper.

- Invocation: default (user and Claude). Preloaded into paper-analyst.
- `allowed-tools`: `mcp__easyresearch__get_page_text mcp__easyresearch__get_paper_profile mcp__easyresearch__get_paper_evidence mcp__easyresearch__list_library_papers` [U].
- Write: draft save goes through a tool the orchestrator calls after the gate (`save_profile_draft`, [U]). The user-only form may still call `save_paper_profile` after confirmation.
- Supporting: `profile-shape.md` (JSON shape, `origin`, `evidence` keys, 500-char quote limit from current skill).
- Inputs: paper id. Outputs: draft profile JSON, evidence list with verify status.

**gap-scan** (preloaded by hypothesis-builder; split from gap-finder)
> Finds gap candidates across the library papers' saved profiles and quotes: unaddressed limitations, common limitations, missing datasets or metrics, untested settings, and conflicting findings. Each gap needs at least one quote with page. Read-only; proposes candidates without saving them. Use when a hypothesis needs evidence of an open problem across several papers.

- Invocation: `user-invocable: false`. No write tools.
- Inputs: paper ids (max 20), project id. Outputs: candidate list with gap type, paper ids, evidence entries.

**gap-save** (user-only; split from gap-finder)
> Saves gap candidates that the user has accepted into the EasyResearch library as agent candidates. Use only after the user has chosen which candidates to keep. Never saves unconfirmed candidates.

- Invocation: `disable-model-invocation: true`. `allowed-tools`: `mcp__easyresearch__add_gap_candidate` [U].
- Inputs: accepted candidates. Outputs: saved ids; the API error is shown and the run stops (as in current skill).

**hypothesis-card** (preloaded by hypothesis-builder)
> Defines the required fields of one hypothesis card for verification: problem with cited evidence, the proposed change, the expected result with a numeric threshold fixed before any test, the closest prior work from at least three searches with evidence ids, the falsification test, failure criteria, and declared assumptions. Use when drafting or revising a hypothesis that will be sent to the verifier.

- Invocation: `user-invocable: false`.
- Supporting: `card-template.json` (fields below), `example-card.md`.
- Inputs: gap candidates, lessons, failure-ledger entries. Outputs: one card (JSON) plus the list of cited evidence ids.

Card fields (proposed): `hypothesis_id`, `problem` {text, evidence_ids}, `change` {text, evidence_ids}, `expected_result` {metric, threshold, direction, prereg_timestamp}, `closest_prior` [{paper_id, difference, evidence_ids}] (at least 3), `falsification_test` {design, data, decision_rule}, `failure_criteria`, `assumptions` [{text, status: supported|unsupported}], `search_log_ids`.

**debate-protocol** (preloaded by hypothesis-builder and verifier)
> Defines the two-round exchange between a hypothesis writer and a verifier: objection codes and severities, the four allowed response types (fix, evidence, concede, rebut), the evidence needed for a rebuttal, the round limit, and when to escalate to the human. Use when a hypothesis card receives objections from the verifier, or when writing responses to them.

- Invocation: `user-invocable: false`.
- Supporting: `objection-codes.md`, `transcript-format.md` (fields stored in `cycle_events`).
- Inputs: card, objections. Outputs: response list, round record.

**verifier-rubric** (preloaded by verifier)
> Rubric for judging a hypothesis card against cited evidence: problem openness, contribution specificity, citation accuracy, distance from the closest prior work, falsifiability, feasibility and internal consistency. Gives PASS, REVISE or REJECT with evidence ids and applies automatic rejection rules first. Use when a hypothesis card must be passed, revised or rejected.

- Invocation: `user-invocable: false`.
- Supporting: `rubric.md` (criteria, pass conditions, examples), `auto-reject-codes.md`.
- Inputs: card, evidence bundle (quotes with status), failure ledger entries, lessons. Outputs: verdict, per-criterion result, objections.

**citation-check** (preloaded by citation-checker)
> Checks every quote-backed claim in a draft or hypothesis card against the stored page text. Runs the quote verifier, tries the neighboring physical page once for label mismatches, and labels each claim supported, partial or unsupported. Use when a draft cites papers and must be checked before verification or reporting.

- Invocation: `user-invocable: false`. Tools: `verify_quote`, `get_page_text` [U names].
- Inputs: claim list with paper id, page, quote. Outputs: per-claim status (`exact`, `normalized`, `not_found`) and support label.

**lesson-curation** (preloaded by lesson-curator)
> Turns rejected hypotheses, objections and human feedback from a finished research cycle into short, checkable lessons and append-only ledger entries, and drafts changes to skills or prompts for human review without applying them. Use after a research cycle ends or when a repeated failure pattern needs recording.

- Invocation: `user-invocable: false`.
- Supporting: `lesson-schema.md` (fields: `id`, `pattern`, `trigger`, `reason_code`, `example_cycle_ids`, `status` active|retired, `created_at`; cap on active lessons set by the user), `proposal-template.md`.
- Inputs: cycle events, failure ledger. Outputs: lesson rows to append via MCP, proposal file under `docs/research/proposals/`.

### 2.4 Interactive and human-only skills

**idea-refiner** (migrated; main-thread, interactive)
> Refines a rough idea or a chosen gap into a specific question by asking one or two Heilmeier-style questions at a time and checking each claim against library quotes. Use when the user wants help sharpening an idea interactively, not inside an automated research cycle.

- Invocation: default. Inline. Uses AskUserQuestion (main thread only).
- `allowed-tools`: read tools for library, `suggest_paper_link` only on request [U].
- Inputs: idea or gap id. Outputs: refined card fields (problem, change, evaluation, closest prior work), `supported`/`unsupported` labels.
- Migration: the card format moves to `hypothesis-card`; "three refinement rounds" stays.

**experiment-plan** (human-only; handoff for later experiment stage)
> Writes an experiment-plan handoff for one accepted hypothesis: baseline, metrics, datasets with source and hash, numeric expected-result thresholds, failure criteria and budget. Prepares the plan for locking. Use when the user asks to turn an accepted hypothesis into an experiment plan. Locking needs explicit confirmation.

- Invocation: `disable-model-invocation: true`. Inline (confirmation needed).
- `allowed-tools`: `mcp__easyresearch__get_hypothesis mcp__easyresearch__save_experiment_plan_draft` [U]. Lock is a separate call the user confirms.
- Outputs: draft plan JSON; lock returns a SHA-256 of canonical JSON (ExecPlan 006 AC7).

**skill-eval-ab** (M4; human-only)
> Runs the hidden evaluation set against the current and proposed versions of a skill or prompt, blind-compares outputs with a comparator, and reports whether the proposal passes the pre-set threshold. Use only when the user asks to evaluate a change proposed by lesson curation.

- Invocation: `disable-model-invocation: true`. `context: fork` with a comparator subagent [U]. Keep the hidden set outside the repository (Part 5).
- Procedure follows the skill-creator loop (S15): eval json, grader, comparator, aggregate; plus randomized A/B order (S34).

### 2.5 Migration of the four existing skills

| Existing skill | New home | Changes |
|---|---|---|
| easyresearch-research-loop | `research` (orchestration) + `research-app-run` | Stage list changes: `critique` becomes `verifier` + `citation-check`; "3 refinement iterations" becomes the design's backtrack rules (per hypothesis 2, per cycle 10). Human checkpoint moves to `gate-policy`. App-run section becomes `research-app-run`. Add `disable-model-invocation: true` and `allowed-tools`. Keep "Do not run experiments" and the output rules. |
| easyresearch-paper-profile | `paper-deep-read` | Keep body and 12-page budget. Branch "show draft first unless already asked to save" moves to gate-policy. Prefix MCP tool names with the server name. Keep `user-invocable` (default). |
| easyresearch-gap-finder | `gap-scan` (read-only, preloaded) + `gap-save` (user-only) | Split so no preloaded skill contains a write. Keep quote and page rules and reason codes. |
| easyresearch-idea-refiner | `idea-refiner` (interactive) + `hypothesis-card` (format) | Interactive part stays main-thread (needs questions). Card format becomes a preloaded skill. "Do not decide novelty" rule kept. |

Common migration steps:
- Move `services/mcp/skills/<name>/` to `.claude/skills/<name>/` (the four folders are not discovered there today; ExecPlan 006 section 2). Keep `services/mcp/skills/` as the source copy only if a build step copies it; otherwise delete the duplicate after migration.
- Keep `metadata` and `compatibility` (accepted by Claude Code; S1). Remove `version` only if the user asks.
- Descriptions already start with the use case; keep them, add a `when_to_use` only if needed to stay within the 1,536-character listing limit.

## Part 3. Subagent definitions

Common rules for all seven agents:
- Allowed tools are listed explicitly. Research agents get no `Bash`, `PowerShell`, `WebFetch`, `WebSearch`, `Edit`, `Write` unless the agent's role needs it (noted per agent). Background subagents keep web tools by default (S2), so they are denied explicitly.
- `Agent` is withheld from all agents except `research-lead`. Depth is effectively 1 for the research system.
- `memory` is not used. Lessons and failure ledger live in the app database (MCP), where the human controls writes. A `.claude/agent-memory/` folder would be an unreviewed write area inside protected `.claude/`.
- `maxTurns` is set on each agent (values are proposals, [U]).
- MCP tool names use the placeholder server `easyresearch`: `mcp__easyresearch__<tool>`. Confirm the server name in `.mcp.json`.
- Brief template (from S16): each delegation includes objective, output format, allowed sources (library only), limits, and the evidence ids the agent must return.
- `permissionMode: dontAsk` for all research agents (explicit allow rules still run; anything else is denied rather than prompting) [S5]. Note the parent-mode override (Part 5).

### 3.1 research-lead (Opus, effort high)

```markdown
---
name: research-lead
description: Coordinates one EasyResearch research cycle from topic to experiment-plan handoff. Use when the user starts, resumes or asks for status of a research cycle. Delegates search, reading, hypothesis building, verification and lesson curation to the other project subagents. Does not browse the web and does not run experiments.
tools: Agent, Read, Grep, Glob, mcp__easyresearch__list_research_runs, mcp__easyresearch__get_research_run, mcp__easyresearch__create_research_cycle, mcp__easyresearch__advance_cycle_stage, mcp__easyresearch__get_gate_policy, mcp__easyresearch__list_failure_ledger, mcp__easyresearch__list_lessons
disallowedTools: WebFetch, WebSearch, Bash, PowerShell, Edit, Write, NotebookEdit, mcp__easyresearch__set_gate_policy, mcp__easyresearch__append_failure, mcp__easyresearch__append_lesson
model: opus
effort: high
permissionMode: dontAsk
maxTurns: 80
skills: [gate-policy, debate-protocol]
---
```

System prompt outline:
1. Role: plan and drive stages; never write policy; never call verifier with builder transcript.
2. Stage order: plan (research-lead) -> literature-scout -> paper-analyst -> hypothesis-builder -> verifier + citation-checker -> gate -> experiment-plan handoff -> lesson-curator.
3. Gate handling: before each stage boundary call get_gate_policy; if action is ask, stop and ask the user in the main session. Subagents cannot ask (S2).
4. Backtrack rules: per hypothesis max 2; per cycle max 10; repeated reason code twice in a row closes that direction and asks the user.
5. Verifier input: hypothesis card + evidence bundle + ledger entries + lessons only. Never the hypothesis-builder's prose or reasoning.
6. Report: stage table, verdicts with reason codes, open questions, cost (subagent count).

Note: when this agent runs as the main session agent (`claude --agent research-lead`, which S2 documents as the `--agent` setting), it is the same role as the `research` skill. Pick one entry point (Part 5, open question).

### 3.2 literature-scout (Haiku)

```markdown
---
name: literature-scout
description: Searches the EasyResearch library and OpenAlex through app tools, designs multi-angle queries for a research question, de-duplicates results, and screens them with reason codes. Use when a research cycle needs candidate papers or citation-following. Does not read full text and does not write.
tools: Read, Grep, Glob, mcp__easyresearch__search_literature, mcp__easyresearch__get_related, mcp__easyresearch__list_library_papers
disallowedTools: WebFetch, WebSearch, Bash, PowerShell, Edit, Write, NotebookEdit, Agent
model: haiku
effort: medium
permissionMode: dontAsk
maxTurns: 25
skills: [literature-screen]
---
```

Outline: queries from at least three angles (problem, method, dataset/metric); record every search in the search log; screen with reason codes; return list with paper ids and reasons; cap results per query.

### 3.3 paper-analyst (Sonnet)

```markdown
---
name: paper-analyst
description: Reads one EasyResearch library paper page by page and drafts a structured profile with page-cited quotes, each marked author-stated or inferred. Use when a research cycle needs the problem, method, limitations and open questions of specific papers. Writes drafts only through the app; never confirms profiles.
tools: Read, mcp__easyresearch__get_paper_profile, mcp__easyresearch__get_paper_evidence, mcp__easyresearch__get_page_text, mcp__easyresearch__list_library_papers, mcp__easyresearch__save_profile_draft
disallowedTools: WebFetch, WebSearch, Bash, PowerShell, Edit, Write, NotebookEdit, Agent
model: sonnet
effort: medium
permissionMode: dontAsk
maxTurns: 30
skills: [paper-deep-read]
---
```

Outline: read at most 12 pages per paper; quote verbatim; 1-based physical page numbers; never quote from abstracts beyond the page text; each author-stated item needs an evidence entry; drafts only.

### 3.4 hypothesis-builder (Sonnet)

```markdown
---
name: hypothesis-builder
description: Builds alternative methods and contribution hypotheses from cited gaps, failure ledger entries and lessons, in the required hypothesis-card format, and answers verifier objections under the debate protocol. Use when a research cycle needs new or revised hypotheses. Writes drafts only; does not verify its own hypotheses.
tools: Read, Grep, mcp__easyresearch__list_gaps, mcp__easyresearch__get_paper_evidence, mcp__easyresearch__get_paper_profile, mcp__easyresearch__search_literature, mcp__easyresearch__list_failure_ledger, mcp__easyresearch__list_lessons, mcp__easyresearch__save_hypothesis_draft
disallowedTools: WebFetch, WebSearch, Bash, PowerShell, Edit, Write, NotebookEdit, Agent
model: sonnet
effort: high
permissionMode: dontAsk
maxTurns: 25
skills: [hypothesis-card, gap-scan, debate-protocol]
---
```

Outline: read failure ledger and lessons before generating (ExecPlan section 4); propose 2-4 alternatives; each card needs cited evidence ids and at least three closest prior works from search; numeric threshold written before any test; respond to objections only with fix, evidence, concede, or rebut (debate protocol).

Note: `list_gaps` is the existing MCP tool from the current skills; the read-only `gap-scan` skill uses it. Skill and tool names are kept separate on purpose.

### 3.5 verifier (Opus, effort high)

```markdown
---
name: verifier
description: Critically evaluates a hypothesis card against cited evidence using a fixed rubric and automatic rejection rules, looks for disconfirming evidence, and returns PASS, REVISE or REJECT with objections. Use after a hypothesis card is drafted, before any human gate. Sees only the card and evidence bundle, never the drafting conversation.
tools: Read, mcp__easyresearch__get_paper_evidence, mcp__easyresearch__get_page_text, mcp__easyresearch__search_literature, mcp__easyresearch__verify_quote, mcp__easyresearch__list_failure_ledger, mcp__easyresearch__list_lessons, mcp__easyresearch__record_verdict
disallowedTools: WebFetch, WebSearch, Bash, PowerShell, Edit, Write, NotebookEdit, Agent, mcp__easyresearch__save_hypothesis_draft, mcp__easyresearch__append_failure
model: opus
effort: high
permissionMode: dontAsk
maxTurns: 15
skills: [verifier-rubric, debate-protocol]
---
```

Outline: see the rubric and auto-reject rules below; run at least one disconfirming search before PASS; record verdict with reason codes via `record_verdict` (the only write).

#### Verifier rubric (full)

Automatic rejection (checked by code in the app first; the verifier only sees the result plus its reason):
- A1 `no_evidence`: any problem, change or prior-work claim without an evidence id.
- A2 `quote_not_found`: any quote whose `verify_quote` status is `not_found` after the neighbor-page retry.
- A3 `no_prior_search`: fewer than three closest-prior searches recorded in the search log.
- A4 `repeat_failure`: the same reason code and overlapping key terms as an unexpired, unreleased failure-ledger entry.
- A5 `not_prereg`: expected result has no numeric threshold or direction, or the threshold was changed after the first submission.
- A6 `novelty_claim`: the card states novelty or priority as established fact ("first", "no prior work", "novel") without a human-check flag.

Criteria (judged by the verifier; each returns PASS, REVISE or REJECT with evidence ids):
- C1 Problem openness: the problem is stated as open in at least one cited paper (limitations, future work or an explicit question), with a quote. Fails if the paper says it is solved.
- C2 Contribution specificity: states a concrete change in input, method or evaluation and what it makes possible. A rename, or a plain combination of two cited methods with no stated difference, is REJECT.
- C3 Citation accuracy: each claim matches its quote (support label `supported`); `partial` is REVISE.
- C4 Distance from prior work: for each of the three closest prior works, names the concrete difference; no difference for any one of them is REJECT.
- C5 Falsifiability: the falsification test can produce a result that contradicts the expectation; the decision rule is written before testing.
- C6 Feasibility: the data and metric are named and available (library or metadata); unknown availability is REVISE.
- C7 Internal consistency: no claim contradicts its own evidence; assumptions marked `unsupported` are listed.

Verdict rule: any A-code = REJECT (no discussion); otherwise any C4 REJECT = REJECT; otherwise any REVISE = REVISE; else PASS.

Disconfirmation step (required before PASS): one search for a result that contradicts the expected result or for a paper that already reports the same contribution; record the query and the result; if such a paper is found, the outcome is C4 REJECT unless the card states the difference.

Score-free: no numeric quality score. Reason codes only, to keep the failure ledger usable.

### 3.6 citation-checker (Haiku)

```markdown
---
name: citation-checker
description: Checks each quote-backed claim in a draft or hypothesis card against stored page text. Runs the quote verifier, retries the neighboring physical page once for label mismatches, and labels each claim supported, partial or unsupported. Use before verification or reporting. Does not change any text.
tools: Read, mcp__easyresearch__verify_quote, mcp__easyresearch__get_page_text
disallowedTools: WebFetch, WebSearch, Bash, PowerShell, Edit, Write, NotebookEdit, Agent
model: haiku
effort: medium
permissionMode: dontAsk
maxTurns: 25
skills: [citation-check]
---
```

Outline: one line per claim; status `exact`, `normalized`, `not_found`; support label; return a table, never edit.

### 3.7 lesson-curator (Sonnet)

```markdown
---
name: lesson-curator
description: After a research cycle ends, turns rejected hypotheses, verifier objections and human feedback into short, checkable lessons and failure-ledger entries, and drafts proposed changes to skills or prompts for human review. Use at the end of a research cycle or when a failure pattern repeats. Appends only; never edits skills or policy.
tools: Read, Grep, Glob, mcp__easyresearch__list_cycle_events, mcp__easyresearch__list_failure_ledger, mcp__easyresearch__list_lessons, mcp__easyresearch__append_lesson, mcp__easyresearch__append_failure, Write
disallowedTools: WebFetch, WebSearch, Bash, PowerShell, Edit, NotebookEdit, Agent, mcp__easyresearch__set_gate_policy
model: sonnet
effort: medium
permissionMode: dontAsk
maxTurns: 15
skills: [lesson-curation]
---
```

Outline: lessons are in the form "hypotheses of type X fail when Y, reason code Z"; each lesson names its example cycle ids; retire by a new row, never delete; `Write` is allowed only for `docs/research/proposals/**` (enforced by the Part 4 guard; the agent must not write elsewhere); skill and prompt changes stay proposals until skill-eval-ab passes and the user approves.

### 3.8 Debate protocol (builder vs verifier)

Applies to hypothesis-builder and verifier, run by research-lead, at most two rounds per hypothesis (matching the design's per-hypothesis backtrack limit):

- Round 0 (blind submission). Verifier receives the card, evidence bundle, ledger entries and lessons. It does not receive the builder's reasoning prose. Output: PASS, REVISE or REJECT, plus objections.
- Objection record: `{id, criterion (C1-C7 or A1-A6), severity: blocking | minor, claim_ref, required_action}`. A blocking objection without a cited evidence id or a stated missing-evidence reason is invalid and is dropped.
- Round 1 (response). Builder answers each objection with exactly one type:
  - `fix`: card change with the changed field named (diff listed);
  - `evidence`: a new evidence id from a tool call made in this round (no new evidence = not accepted);
  - `concede`: the hypothesis or the claim is dropped;
  - `rebut`: argument plus evidence ids. Assertions without ids are not accepted.
  The builder cannot change the criteria, the threshold or the reason code.
- Round 1 verdict. Verifier marks each objection `sustained` or `overruled` with the reason, then gives the overall verdict.
- Round 2 is the last round. Unresolved blocking objections mean REJECT with the reason code written to the failure ledger.
- Escalation: a second REJECT on the same reason code for the same direction closes it and asks the user (design section 4).
- Logging: every message is written to `cycle_events` with role, round, objection id, and reason code, for lesson-curator to read later.
- Anti-sycophancy rules: the verifier may not PASS a card that has zero disconfirming searches; the builder may not reply "the verifier is wrong" without evidence ids.
- Known limit: builder and verifier are the same model family (S33). Overturned verdicts that a human later reverses are logged for calibration; they are not used to change the rubric automatically.

## Part 4. Hooks, settings, and MCP wiring

### 4.1 CLAUDE.md (new, short)

Create `CLAUDE.md` at the repository root that imports the operating contract (S7):

```markdown
@AGENTS.md

Claude Code specifics: research subagents live in .claude/agents/; the /research skill runs inline in the main thread; never edit data/, AGENTS.md or .claude/ from a research agent.
```

Reason: AGENTS.md is ignored when a CLAUDE.md exists in or above the working directory (S7), so the import keeps one source of truth. Keep the file under 200 lines (S7).

### 4.2 .claude/settings.json (shared, committed)

Proposal, based on S5, S6, S8. Commit only the project-safe keys. Keep personal approvals in `settings.local.json`.

```json
{
  "permissions": {
    "allow": [
      "mcp__easyresearch__*"
    ],
    "deny": [
      "WebFetch",
      "WebSearch",
      "Read(./data/**)",
      "Edit(./data/**)",
      "Edit(./AGENTS.md)",
      "Edit(./CLAUDE.md)",
      "Edit(./eval/hidden/**)",
      "Edit(./backup/**)",
      "Agent(general-purpose)",
      "Agent(Explore)",
      "Agent(Plan)",
      "Bash(git push *)"
    ]
  },
  "env": {
    "MAX_MCP_OUTPUT_TOKENS": "25000"
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -File .claude/hooks/guard-protected.ps1",
            "shell": "powershell",
            "timeout": 10
          }
        ]
      }
    ],
    "ConfigChange": [
      {
        "matcher": "project_settings",
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -File .claude/hooks/block-config-change.ps1",
            "shell": "powershell"
          }
        ]
      }
    ],
    "PermissionDenied": [
      {
        "matcher": "mcp__easyresearch__.*",
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -File .claude/hooks/log-denial.ps1",
            "shell": "powershell"
          }
        ]
      }
    ]
  }
}
```

Notes on each block:
- `allow` `mcp__easyresearch__*`: allow globs are valid only after the literal `mcp__<server>__` prefix (S6). Server name is a placeholder [U].
- `deny` bare `WebFetch` and `WebSearch`: removes these tools from the main session too (S6). Acceptable under the design (no web access; app MCP only). Revisit if the orchestrator needs web reading.
- `deny` `Read(./data/**)`, `Edit(./data/**)`: private research data (AGENTS.md invariant). Read deny is best effort for Grep/Glob (S6), so `data/` also stays out of the agents' tool lists.
- `deny` `Edit(./AGENTS.md)` and `CLAUDE.md`: AGENTS.md is not in the protected list (S5), so it needs an explicit rule.
- `deny` `Agent(general-purpose)`, `Agent(Explore)`, `Agent(Plan)`: forces the seven project agents (S2 uses the same `Agent(Explore)` form).
- `ConfigChange` `project_settings`: exit 2 blocks a settings change during a session (S4). This stops an agent from weakening the guard by editing settings. Managed and user settings are not matched.
- `PermissionDenied`: logs denials for review. Note: PermissionDenied is an event name listed in S3; its input fields were not read [U].

### 4.3 Guard script (outline)

`.claude/hooks/guard-protected.ps1` (proposal):
1. Read JSON from stdin; take `tool_input.file_path` (documented as the primary content field for Edit and Write, S6).
2. Normalize to a project-relative forward-slash path.
3. Block (write message to stderr, `exit 2`) when the path matches: `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `.mcp.json`, `data/**`, `eval/hidden/**`, `backup/**`, `services/**/backup*`, and `docs/exec-plans/completed/**` (completed plans are immutable after the gate).
4. Allow `docs/research/proposals/**` only for `lesson-curator` (agent identity: `agent_type` is a documented common field, S3; the exact comparison is [U]).
5. Otherwise `exit 0`.

Exit code 2 is the documented block (S3, S4). Do not use exit 1 (not a block, S3).

### 4.4 .mcp.json (project, committed; no secrets)

```json
{
  "mcpServers": {
    "easyresearch": {
      "command": "python",
      "args": ["services/mcp/easyresearch_mcp.py"],
      "env": {
        "EASYRESEARCH_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

Notes:
- Stdio entries have no `type` (S9). Paths are relative to the project root; if the server path must come from the project directory, use `${CLAUDE_PROJECT_DIR:-.}` (S9) [U on Windows path handling].
- Do not put API keys in `.mcp.json`. Use environment variables from the user's shell or `settings.local.json`.
- First use prompts for approval in an interactive session (S9). `claude -p` loads it without prompting (S9): see Part 5.
- Tool names become `mcp__easyresearch__<tool>` (S9). Keep tool names stable; they appear in skill `allowed-tools`, agent `tools`, and hook matchers.
- Tool names in Part 3 are the existing MCP tools from the current skills (`list_*`, `get_*`, `search_literature`, `verify_quote`, `save_*`, `add_gap_candidate`) plus proposed new ones (`create_research_cycle`, `advance_cycle_stage`, `get_gate_policy`, `set_gate_policy`, `record_verdict`, `append_lesson`, `append_failure`, `list_cycle_events`, `save_profile_draft`, `save_hypothesis_draft`). Proposed names are [U] until the server exposes them.

### 4.5 Settings to keep out of the repository

- `.claude/settings.local.json`: personal approvals ("Yes, and don't ask again" writes here, S8).
- `~/.claude/settings.json`: `permissions.defaultMode` `auto` or `bypassPermissions` can only be set here or in managed settings (S8). Do not set them in the repo.

### 4.6 Optional, later

- `FileChanged` hook matching `AGENTS.md|CLAUDE.md` to ask for a restart note (S3). Not needed for M1.
- `SubagentStop` or `Stop` hooks that block until the citation-checker has run. Do not rely on them until the VS Code known issue (S36) is ruled out in the CLI; use the app's own checks for hard gates.
- `http` hook posting events to the local app for `cycle_events`. Data sent to the app is private research data; it stays on 127.0.0.1 only. Note: the input JSON includes `transcript_path` and possibly the last assistant message (S3); decide what is logged before enabling.

## Part 5. Risks and open questions

Platform risks (verified, [V] unless marked):
1. Gate placement. Subagents cannot ask the user (S2). Gates must be in the main thread between subagent calls. A `context: fork` `/research` would silently skip them. Keep `/research` inline.
2. Parent permission mode overrides agent `permissionMode` when the main session is `acceptEdits`, `auto` or `bypassPermissions` (S2). A research cycle started in a permissive mode will run the agents more loosely than their frontmatter says. Mitigation: hooks and deny rules still apply (S5), and the cycle start checks the mode via `/status` [U].
3. Background web tools. Background subagents keep `WebFetch` and `WebSearch` (S2). Denied explicitly in every research agent and at the project level (Part 4). Verify with a test in M1 (AC2).
4. Nesting. Default depth is 3 layers (S2). If research-lead runs as a subagent (for example from a fork), its children are at depth 2. The design's depth-1 rule is enforced by omitting `Agent` from the other six agents, not by the environment variable. S2 says `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` turns nesting off; whether that also blocks research-lead's own calls when it is the main thread is an inference [U].
5. Two entry points. Both `research` (skill, main thread) and `research-lead` (agent via `--agent`) would encode the same procedure. Pick one as the source of truth. Recommendation: the skill holds the procedure; the agent file is a thin wrapper that loads it [U].
6. `memory` field and protected folders. `memory: project` writes under `.claude/agent-memory/`, inside the protected `.claude/` area (S5, S2). The design avoids it (Part 3). Keep it off.
7. Plugins ignore subagent hooks, mcpServers and permissionMode (S2). Do not move the research system into a plugin until those fields are handled at the plugin level.
8. Skill listing cost. Every model-invocable and `user-invocable: false` skill description stays in context each turn (S10 for plugins; S1 for `user-invocable: false`). Twelve skills with long descriptions compete with the conversation. Keep descriptions short; move procedure text into preloaded skills or agent bodies.
9. The total skill-listing budget is not documented in the pages read. Only the per-skill 1,536-character cutoff is verified (S1). Open question.
10. `claude -p` and the app button. Project MCP servers load without approval in `claude -p` (S9). If the app starts runs this way, a malicious `.mcp.json` in a cloned repository would run without a prompt. Mitigations: only start runs for the app's own project path; pin the server path; keep `disabledMcpjsonServers` for unknown servers; check the subscription login behavior (ExecPlan 006 section 11) [U].
11. Permission precedence surprises. Allow rules do not override ask or deny (S6). A "Yes, and don't ask again" choice writes to `settings.local.json` and does not beat an ask rule from a project file (S8).
12. Hidden evaluation set. Read deny is best effort for Grep and Glob (S6), and Bash in the main session could read it. Keep the hidden set outside the repository and expose only scores through an MCP tool. Verify that agents cannot read it (AC6).

Method risks (from the sources):
13. Same-family verifier. LLM evaluators favor their own generations (S33). Opus verifying Sonnet output is still one family. Mitigations: auto-reject rules that are code-checked (A1-A6), quote verification by tool, and human decisions on novelty (S32, ExecPlan 006 section 5).
14. LLM judges are noisy. Strong judges agree with human preferences over 80% of the time on chat tasks (S34). Research judgments are harder; treat verdicts as checkable signals with reason codes.
15. Novelty judgments. LLM ideas were rated more novel but less feasible in a human study (S32). A verifier criterion for novelty would be unreliable; it is excluded (A6 only flags claims).
16. Debate gains are reported on factual and reasoning tasks (S26, S27), not on research idea quality. The protocol is kept to two rounds to limit cost and sycophancy.
17. Self-critique gains (S29) are reported on generation tasks with one model. They may not transfer to same-model verification of research claims.
18. Reported gains are self-reported on abstracts (S21, S22, S24, S30). None was independently replicated in the pages read.
19. Lesson accumulation. Itemized, append-only lessons reduce context collapse (S30), but a growing list increases prompt size. Cap the active set; the user prunes.
20. Cost. Multi-agent systems used about 15x chat tokens in one report (S16). Per-cycle budgets (calls and turns) are required in M3.

Open questions:
- Confirm the MCP server name (`easyresearch`) and tool names, then update all `tools` and `allowed-tools` lists.
- Confirm that `allowed-tools` accepts a space-separated list in Claude Code (the spec says so, S13; the Claude Code page did not show the field format) [U].
- Confirm how `skills:` preloads behave for a main-session agent started with `--agent` [U].
- Confirm `SubagentStop` blocking in the CLI (not VS Code) before relying on it [U].
- Decide whether `WebFetch`/`WebSearch` should be denied for the main session too (design says yes; the orchestrator might later need a source check).
- Decide where the hidden evaluation set lives and who writes it.

## Part 6. URL index

Official Claude Code and platform:
1. https://code.claude.com/docs/en/skills
2. https://code.claude.com/docs/en/sub-agents
3. https://code.claude.com/docs/en/hooks
4. https://code.claude.com/docs/en/hooks-guide
5. https://code.claude.com/docs/en/permission-modes
6. https://code.claude.com/docs/en/permissions
7. https://code.claude.com/docs/en/memory
8. https://code.claude.com/docs/en/settings
9. https://code.claude.com/docs/en/mcp
10. https://code.claude.com/docs/en/plugins
11. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
12. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
13. https://agentskills.io/specification
14. https://github.com/anthropics/skills
15. https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md
16. https://www.anthropic.com/engineering/multi-agent-research-system
17. https://www.anthropic.com/engineering/building-effective-agents
18. https://agents.md

Community:
19. https://github.com/K-Dense-AI/claude-scientific-skills
20. https://github.com/obra/superpowers
36. https://claudeissues.com/issue/39030-bug-subagentstop-command-hook-not-firing-in-vs-code-ide-extension

Papers:
21. https://arxiv.org/abs/2408.06292
22. https://arxiv.org/abs/2504.08066
23. https://arxiv.org/abs/2404.07738
24. https://arxiv.org/abs/2502.18864
25. https://arxiv.org/abs/2502.09858
26. https://arxiv.org/abs/2305.14325
27. https://arxiv.org/abs/2402.06782
28. https://arxiv.org/abs/2303.11366
29. https://arxiv.org/abs/2303.17651
30. https://arxiv.org/abs/2510.04618
31. https://arxiv.org/abs/2509.25140
32. https://arxiv.org/abs/2409.04109
33. https://arxiv.org/abs/2404.13076
34. https://arxiv.org/abs/2306.05685
35. https://arxiv.org/abs/2412.11948

Count: 36 sources (S1-S36). Sources not opened by full text: S35 (search only), S36 (search only), S19 (opened), S30 roles from search.
