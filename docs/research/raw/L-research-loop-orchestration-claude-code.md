# L. End-to-end research loop orchestration and Claude Code practice

Date: 2026-11-10
Scope: (1) end-to-end research agent loops with backtracking and failure memory; (2) Claude Code practice for multi-agent workflows (subagents, skills, hooks, headless, SDK, workflows, plugins, costs); (3) human-in-the-loop autonomy policies. Complements reports A-I; this report goes deeper on orchestration of the full loop (topic -> methods -> hypotheses -> verification -> backtrack -> experiment -> report) and on Claude Code mechanics.

## Legend and method

- [V] Verified: the primary page (official Claude Code / Agent SDK docs, Anthropic engineering post, arXiv abstract page, or the project's own page) was fetched in this session. Official-doc text was read through a summarizing fetch, so exact spellings and values should be re-checked against the raw page before they are written into code (see Part 4).
- [S] Secondary or search-only: the claim comes from a search-result snippet, aggregator, news item, or third-party summary. Treat numbers as unverified.
- [U] Unverified or conflicting: the claim could not be confirmed, or sources disagree. Also used for numbers that the authors or a company reported about their own system.
- Quotes: at most one short phrase per source, under 15 words. Most sources are paraphrased.
- No numbers below are invented. Every figure is attributed to its source and tagged.

---

## Part 1. Source records

39 sources. Groups: A = research-loop systems and verification papers (L01-L17); B = Claude Code and Agent SDK docs (L18-L31); C = Anthropic engineering (L32-L36); D = community skill repos (L37-L38); E = autonomy frameworks (L39).

### Group A. End-to-end research loops and verification

**L01. Agent Laboratory: Using LLM Agents as Research Assistants**
- Org: AMD and Johns Hopkins (Schmidgall et al.). Date: v1 submitted 2025-01-08; v2 2025-06-17. Tag: [V] (arXiv abstract fetched).
- URL: https://arxiv.org/abs/2501.04227
- Stages: literature review, experimentation, report writing. Human feedback is accepted at each stage; the abstract says it significantly improves research quality.
- Backends: o1-preview gave the best outcomes per the abstract; other backends are not listed in the abstract.
- Cost claim: "84% decrease" relative to "previous autonomous research methods". The baseline is not named. [U]
- Relevance: the clearest published model of per-stage human gates inside a research pipeline. Shows stage-wise feedback as a design pattern, not a separate system. No explicit backtracking.

**L02. The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search**
- Org: Sakana AI and collaborators (Yamada, Lange, Lu, Hu, Lu, Foerster, Clune, Ha). Date: submitted 2025-04-10. Tag: [V] (arXiv abstract fetched).
- URL: https://arxiv.org/abs/2504.08066
- Components: progressive agentic tree search; a dedicated experiment manager agent; a VLM feedback loop for figures; an enhanced AI reviewer. Drops v1's human-written code templates.
- Result: of three fully autonomous manuscripts submitted to an ICLR workshop, one scored above the average acceptance threshold (authors' report).
- No compute cost or number of tree-search runs is reported in the abstract. [U on cost]
- Relevance: tree search with an experiment manager is the closest published analogue to backtracking over branches. The manager/worker split matches a Claude Code orchestrator plus experiment subagent.

**L03. The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (v1) and its 2026 Nature version**
- Org: Sakana AI, UBC, Vector Institute, Oxford. Dates: arXiv 2408 (v1); Nature publication reported by UBC news, 2026-03. Tag: [S].
- URLs: https://arxiv.org/pdf/2408.06292 ; https://www.cs.ubc.ca/news/2026/03/ai-scientist ; code https://github.com/SakanaAI/AI-Scientist
- Claims (from the arXiv abstract snippet and UBC release): about $15 per paper; ideation, literature search, experiment iteration, writing, and an automated reviewer. The reviewer is automated, not human. [S]
- Limitation acknowledged by the release: sometimes produces underdeveloped ideas.
- Nature title "Towards end-to-end automation of AI research" and DOI 10.1038/s41586-026-10265-5 come from one news source only. [U until checked on nature.com]
- Relevance: automated reviewer as a verifier is useful, but reviewer-as-judge is exactly what the falsifier role in Part 2 must not rely on alone.

**L04. AI-Researcher: Autonomous Scientific Innovation (HKUDS)**
- Org: University of Hong Kong (Tang, Xia, Huang et al.). Date: arXiv 2505.18705 (May 2025). Tag: [S].
- URLs: https://arxiv.org/html/2505.18705v1 ; https://github.com/HKUDS/AI-Researcher
- Scope: literature review, idea generation, implementation, experiments, manuscript. Introduces Scientist-Bench. Authors say it does better on open-ended exploration than on guided implementation.
- A blog reports a NeurIPS 2025 Spotlight and a leaderboard score of 7.4 vs 8.1 for human experts. Neither is confirmed here. [U]
- Relevance: a benchmark-first design (Scientist-Bench) is a good template for evaluating this app's own loop before trusting it.

**L05. DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively**
- Org: Weng et al. (incl. Yue Zhang). Date: arXiv 2509.26603, submitted 2025-09-30; listed as an ICLR 2026 poster. Tag: [S].
- URLs: https://arxiv.org/html/2509.26603v1 ; https://iclr.cc/virtual/2026/poster/10008492 ; code https://github.com/ResearAI/DeepScientist
- Loop: hypothesize, verify, analyze, with cumulative memory of prior findings; framed as Bayesian optimization.
- Author-reported scale: about 5,000 ideas, about 1,100 experimentally validated, 21 counted as innovations (under 0.5%). Claimed gains up to 183.7% over human SOTA on three tasks. [U]
- Authors name implementation and verification of hypotheses as the main bottleneck.
- Relevance: the success rate is the strongest argument for a failure ledger and for cheap early kill checks before expensive experiments.

**L06. InternAgent (formerly NovelSeek): When Agent Becomes the Scientist**
- Org: Shanghai AI Laboratory, InternAgent team (Bo Zhang first author). Date: arXiv 2505.16938; renamed 2025-07-10 per search summary. Tag: [S].
- URLs: https://arxiv.org/abs/2505.16938 ; https://github.com/Alpha-Innovator/InternAgent
- Closed loop: survey, idea innovation, method transformation, coding, assessment agents; human expert feedback interface inside the loop.
- Claims 12 task types from AI to science. Partial open-source released 2025-07-17 (per search summary). Follow-up InternAgent-1.5 reported on GAIA, HLE, GPQA, FrontierScience; not verified. [U]
- Relevance: a closed loop with an explicit assessment agent and a human feedback slot is the closest published match to the gate design in Part 2.

**L07. Kosmos: An AI Scientist for Autonomous Discovery**
- Org: Edison Scientific (a FutureHouse spinout), with Andrew White among authors (per profile results). Date: arXiv 2511.02824 (Nov 2025). Tag: [S].
- URLs: https://arxiv.org/html/2511.02824v2 ; https://edisonscientific.com/articles/announcing-kosmos
- Architecture: a data-analysis agent and a literature agent share a structured world model; each cycle runs up to ten tasks, summarizes results into the model, and plans the next cycle.
- Traceability: claims in the report can be traced to the analysis or source that produced them.
- Scale claims: about 42,000 lines of code, 166 analysis rollouts, 1,500 full papers read (paper, as summarized). "At least 79%" reproducible is a company marketing claim. [U]
- Relevance: the shared world model is a concrete answer to "where does state live" in a long loop, and traceability is the property the verification stage needs.

**L08. Robin: A multi-agent system for automating scientific discovery**
- Org: FutureHouse and University of Oxford (Ghareeb, Chang et al.). Date: arXiv 2505.13400, 2025-05-19. Tag: [S].
- URLs: https://arxiv.org/pdf/2505.13400 ; https://futurehouse.org/research-announcements/demonstrating-end-to-end-scientific-discovery-with-robin-a-multi-agent-system ; code https://github.com/Future-House/robin (Apache-2.0 per aggregator) [S]
- Loop: hypothesis generation coupled with experimental data analysis; literature agent (Crow, Falcon) and data agent (Finch).
- Drug repurposing case for dry AMD proposing ripasudil; reports a second round of candidates using first-round data.
- A trade article says Robin and co-scientist appeared in Nature; unclear if that is the same work. [U]
- Relevance: the second round of proposals built from first-round data is a working example of a loop that feeds results back into hypothesis generation.

**L09. Towards an AI co-scientist**
- Org: Google and collaborators (Gottweis first author among 34). Date: arXiv 2502.18864, submitted 2025-02-26. Tag: [S].
- URL: https://arxiv.org/abs/2502.18864
- Architecture: Gemini 2.0 multi-agent system with generate, debate, evolve steps and asynchronous task execution.
- Hypotheses ranked by Elo-style pairwise tournament; reports improving max and average Elo with more test-time compute.
- Authors report wet-lab-linked results (liver fibrosis targets, bacterial gene-transfer in silico). [U for detail]
- Relevance: the tournament is the best published pattern for choosing among hypotheses without absolute scores, which matches the pairwise judging in Part 3.

**L10. Automated Hypothesis Validation with Agentic Sequential Falsifications (POPPER)**
- Org: Stanford (Huang, Jin, Li, Li, Candes, Leskovec). Date: arXiv 2502.09858, Feb 2025; ICML 2025. Tag: [S].
- URLs: https://arxiv.org/pdf/2502.09858 ; https://proceedings.mlr.press/v267/huang25n.html ; code https://github.com/snap-stanford/POPPER
- Design: LLM agents design and run falsification experiments against measurable implications of a hypothesis; p-values are combined into sequential e-values, rejecting the null when the aggregate exceeds 1/alpha.
- Six domains; in one biology comparison, comparable performance to human scientists with roughly tenfold less validation time (authors). [U]
- Relevance: the strongest published design for a refutation stage. It says a hypothesis is "validated" only if repeated falsification attempts fail under a stated error budget.

**L11. Build Your Personalized Research Group: A Multiagent Framework for Continual and Interactive Science Automation (freephdlabor)**
- Org: Yale, UChicago, Oxford (Ed Li, Junyu Ren et al.). Date: arXiv 2510.15624, 2025-10-17. Tag: [S].
- URLs: https://arxiv.org/html/2510.15624v1 ; code https://github.com/ltjed/freephdlabor
- Star topology: a ManagerAgent delegates to specialists; agents share a workspace rather than passing long strings ("game of telephone" avoided).
- Automatic context compaction via callbacks; non-blocking human callbacks that inject feedback without stopping the run.
- Relevance: directly relevant to the context-hygiene and non-blocking-feedback requirements. The shared workspace pattern maps onto a run directory.

**L12. Zochi (Intology): ACL 2025 main-conference paper on multi-turn jailbreaking (Tempest)**
- Org: Intology. Date: acceptance announced 2025-05-26. Tag: [S].
- URLs: https://www.lesswrong.com/posts/LtsgfGsXpiLTSGpaW/zochi-publishes-a-paper ; https://www.casrai.org/news/fully-ai-generated-papers-passing-peer-review-zochi-sakana
- Company claims: meta-review score 4/5 and top 8.2% of ACL 2025 submissions; the agent identified the direction, formalized the method, ran experiments, and wrote the paper apart from figures. [U]
- Secondary coverage notes humans were the named accountable authors and that an earlier ICLR-workshop version drew criticism over undisclosed AI authorship. [S]
- Relevance: a reminder that autonomy claims need a stated human-accountability and disclosure policy. Also a safety-domain example where a pipeline ran a tree search over attack strategies, which this app should avoid by design.

**L13. AgentRxiv: Towards Collaborative Autonomous Research**
- Org: Schmidgall and Moor. Date: arXiv 2503.18102, 2025-03-23. Tag: [S].
- URLs: https://arxiv.org/pdf/2503.18102 ; https://arxiv.org/html/2503.18102v1
- Shared preprint server where agent labs upload and retrieve each other's work.
- Authors report +11.4% relative accuracy on MATH-500 when agents could read prior work; average +3.3% across other benchmarks; +13.7% with multiple labs sharing. [U]
- Relevance: cross-run memory shared as an artifact store, not as chat context. Suggests a findings store that later runs can read, with provenance.

**L14. TinyScientist: An Interactive, Extensible, and Controllable Framework for Building Research Agents**
- Org: UIUC (Haofei Yu, Keyang Xuan, Fenghai Li et al.). Date: arXiv 2510.06579 (Oct 2025); EMNLP 2025 system demonstrations. Tag: [S].
- URLs: https://arxiv.org/html/2510.06579v1 ; https://github.com/ulab-uiuc/tiny-scientist ; PyPI package tiny-scientist
- Table-based interface splits the workflow into editable stages; tools added via MCP.
- Authors report generation quality comparable to Agent Laboratory on ML and biology tasks. [U]
- A search result for a different paper (LightAgent) has a near-identical abstract, so indexing may be mixed. [U]
- Relevance: editable stage tables plus MCP extension is the closest published UI pattern for a per-stage gate.

**L15. The Denario project: Deep knowledge AI agents for scientific discovery**
- Org: Villaescusa-Navarro, Bolliet, Villanueva-Domingo et al. Date: arXiv 2510.26887, 2025-10-30. Tag: [S].
- URLs: https://arxiv.org/pdf/2510.26887 ; https://arxiv.org/html/2510.26887v1
- Six modules: idea, literature, methodology, data analysis, paper writing, peer review. Idea module is a propose-critique loop (generator plus evaluator).
- Built on AG2 and LangGraph (per summary). Authors report about 30 minutes and about $4 per paper. [U]
- Reviewers found it strong on technical implementation and weak on interpretive, contextual judgment. [S]
- Relevance: the reviewer finding matches where a human gate should sit: at interpretation, not at code execution.

**L16. Tree of Thoughts: Deliberate Problem Solving with Large Language Models**
- Org: Princeton and Google DeepMind (Yao et al.). Date: arXiv 2305.10601, May 2023. Tag: [S].
- URLs: https://arxiv.org/pdf/2305.10601 ; code https://github.com/princeton-nlp/tree-of-thought-llm
- Search over partial solutions with lookahead, state evaluation, and backtracking; BFS and DFS variants.
- Game of 24 result (CoT 4% vs ToT 74%) is from a secondary listing; treat as [S].
- Relevance: the formal basis for the backtrack rules in Part 2 (evaluate a node, prune, return to the parent).

**L17. Reflexion: Language Agents with Verbal Reinforcement Learning**
- Org: Northeastern, MIT, Princeton (Shinn et al.). Date: arXiv 2303.11366 (v4 Oct 2023); NeurIPS 2023. Tag: [S].
- URLs: https://arxiv.org/abs/2303.11366v4 ; https://ar5iv.labs.arxiv.org/html/2303.11366
- Agents reflect in text on failure signals and store reflections in an episodic memory buffer for later attempts, without weight updates.
- Reported HumanEval pass@1 of 91% and +22% absolute on AlfWorld over 12 iterations. Some third-party ablation numbers could not be confirmed. [U for ablations]
- Relevance: the failure-memory entry format in Part 2 is a structured version of a Reflexion reflection.

### Group B. Claude Code and Agent SDK primary docs

**L18. Create custom subagents (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (summarizing fetch of https://code.claude.com/docs/en/sub-agents).
- URL: https://code.claude.com/docs/en/sub-agents
- Frontmatter fields listed: name (required), description (required), tools, disallowedTools, model, permissionMode, maxTurns, skills (up to 32 preloaded), mcpServers, hooks, memory (user | project | local), background, effort, isolation (worktree), color, initialPrompt, omitClaudeMd, autoCompactWindow, experimental. Unknown fields are silently ignored.
- Model resolution when model is omitted: per-invocation model, then frontmatter, then CLAUDE_CODE_SUBAGENT_MODEL, then main model. Aliases: sonnet, opus, haiku, fable, inherit, or a full ID.
- Subagents can spawn subagents up to 3 layers by default (CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH; 1 disables nesting).
- Precedence: managed > --agents flag > .claude/agents/ > ~/.claude/agents/ > plugin agents/. Built-ins: Explore, Plan, general-purpose, claude, statusline-setup, claude-code-guide (Haiku).
- Relevance: the source for the roster in Part 2. All fields the user asked about exist.

**L19. Extend Claude with skills (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/skills).
- URL: https://code.claude.com/docs/en/skills
- Frontmatter: name, description, when_to_use (combined listing text capped at 1,536 characters), argument-hint, arguments, disable-model-invocation, user-invocable, allowed-tools, disallowed-tools, model, effort, context (fork), agent (subagent type for fork), background, hooks, paths, shell, plus informational metadata, license, compatibility.
- Progressive disclosure: name and description always loaded; SKILL.md on invocation; supporting files only when read. After compaction the latest invocation is re-attached, up to 5,000 tokens per skill and 25,000 shared.
- Forked skills get the SKILL.md as their whole prompt and do not see conversation history; a forked skill must be a complete task.
- Relevance: stage skills with context: fork plus agent: give each heavy stage a clean context. disable-model-invocation: true for side-effecting stages.

**L20. Hooks reference (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/hooks).
- URL: https://code.claude.com/docs/en/hooks
- 33 events, including SessionStart, UserPromptSubmit, PreToolUse, PermissionRequest, PermissionDenied, PostToolUse, PostToolBatch, SubagentStart, SubagentStop, TaskCreated, TaskCompleted, Stop, StopFailure, PreCompact, PostCompact, FileChanged, WorktreeCreate, WorktreeRemove.
- Hook types: command, http, mcp_tool, prompt, agent (agent marked experimental).
- Exit 0 with JSON; exit 2 blocks on blocking events (PreToolUse, UserPromptSubmit, Stop, SubagentStop, PreCompact, WorktreeCreate, others); exit 2 is ignored by PermissionRequest and has no blocking effect on PostToolUse. Other non-zero codes are non-blocking.
- PreToolUse decisions: permissionDecision allow | deny | ask | defer. PermissionRequest uses hookSpecificOutput.decision.behavior.
- Relevance: the mechanism for data-path guards, outbound-preview gates, and "do not stop while a gate is pending".

**L21. Run Claude Code programmatically (headless mode)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/headless).
- URL: https://code.claude.com/docs/en/headless
- -p / --print; --output-format text | json | stream-json; --json-schema for structured output (in structured_output); --continue and --resume; --allowedTools; --permission-mode (auto, dontAsk, acceptEdits, ...); --permission-prompts none (unattended runs; denies what would prompt); --max-budget-usd.
- --bare skips hooks, skills, subagents, plugins, MCP, auto memory, and CLAUDE.md. It is recommended for scripts, and it never reads OAuth or keychain credentials, so an ANTHROPIC_API_KEY is required (not subscription login).
- JSON output includes total_cost_usd (client-side estimate). Background-work wait ends after 10 minutes by default (CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS). SIGTERM exits with 143.
- Relevance: scheduled unattended stages; cost logging per stage. Note the --bare auth consequence for a subscription setup (Part 4).

**L22. Choose a permission mode (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/permission-modes).
- URL: https://code.claude.com/docs/en/permission-modes
- Modes: default (also "manual"), acceptEdits, plan, auto (classifier reviews actions), dontAsk (auto-denies anything that would prompt), bypassPermissions (isolated containers only).
- Auto requires a supported model (Opus 4.6+, Sonnet 4.6+, Haiku 5.5, or Fable on the API). Default classifier model: Sonnet 5, configurable with CLAUDE_CODE_AUTO_MODE_MODEL.
- Broad allow rules (for example Bash(*) or Agent rules) are dropped when entering auto mode; narrow rules such as Bash(npm test) stay. Subagents are checked when spawned, while running, and when their final report returns.
- Escalation: three consecutive blocks or twenty total pause auto mode and resume prompting.
- Docs: auto mode "reduces permission prompts but does not guarantee safety."
- Relevance: the autonomy presets in Part 3 are built from these modes plus hooks.

**L23. Plugins overview (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/plugins).
- URL: https://code.claude.com/docs/en/plugins
- A plugin bundles skills, agents, hooks, MCP servers, and output styles; manifest at .claude-plugin/plugin.json; marketplaces are catalogs (.claude-plugin/marketplace.json).
- Enabled plugins add their skill and agent descriptions to context on every turn, plus MCP processes and hooks.
- Install scopes: user, project, local. Cloud sessions do not load local plugin settings.
- Relevance: packaging the roster later as a plugin is possible, but frontmatter fields such as permissionMode, hooks, and mcpServers are ignored for plugin subagents (L18). Start with project-level .claude/agents/.

**L24. Output styles (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/output-styles).
- URL: https://code.claude.com/docs/en/output-styles
- Built-in styles: Proactive, Concise, Explanatory, Learning. Custom styles in .claude/output-styles/ with name, description, keep-coding-instructions, force-for-plugin.
- Styles change instructions, not enforcement; the doc says to use hooks for behavior that must always happen. Subagents run their own system prompt and are not changed by the session style.
- Proactive style asks Claude to check before data-deleting or production actions, but permission mode still decides prompts.
- Relevance: an output style can set the research-report voice (cite-every-claim), but must not be the only gate.

**L25. Model configuration (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V, partial; page truncated] (https://code.claude.com/docs/en/model-config).
- URL: https://code.claude.com/docs/en/model-config
- Aliases: default, best (= opus), opus, sonnet, haiku, fable, opus[1m], sonnet[1m], opusplan (Opus in plan mode, Sonnet for execution).
- On the Anthropic API, aliases resolve to Opus 5.5, Sonnet 5.5, Haiku 5.5. On Microsoft Foundry, Bedrock, and Google Cloud, sonnet resolves to Sonnet 4.5 per the same page. [conflict-check in Part 4]
- Effort levels low, medium, high, xhigh, max; default medium for Opus 5.5, Sonnet 5.5, Haiku 5.5. Resolution order: CLAUDE_CODE_EFFORT_LEVEL, session choice, --effort, settings, model default.
- Haiku 5.5 auto-compacts at about 967K tokens by default (per page).
- Relevance: pin full model IDs in agent files if the app will run on more than one provider.

**L26. Manage costs effectively (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/costs).
- URL: https://code.claude.com/docs/en/costs
- Stated enterprise averages: about $13 per developer per active day; $150-250 per developer per month; below $30 per active day for 90% of users. These are Anthropic's own enterprise figures, not this app's.
- Agent teams: Sonnet recommended for teammates; each active teammate keeps consuming tokens; the doc says agent teams use about 7x more tokens when teammates run in plan mode.
- Subagent requests draw on the same usage; choose a smaller model for simple subagent tasks; delegate verbose operations to subagents to keep the main context small.
- /usage shows attribution to skills, subagents, plugins, and MCP servers.
- Relevance: the cost model for this app. Usage-limit cost is the binding constraint on a subscription, not dollars.

**L27. Claude Agent SDK overview**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/agent-sdk/overview).
- URL: https://code.claude.com/docs/en/agent-sdk/overview
- The SDK runs the Claude Code agent loop in Python or TypeScript, with built-in tools, hooks, subagents, MCP, permissions, sessions, skills, plugins.
- Third-party products may not offer claude.ai login or rate limits; use API key authentication instead (per doc).
- Comparison: Client SDK (you write the loop) and Managed Agents (hosted by Anthropic). Non-Python/TS languages can run the CLI with -p.
- Relevance: if the app later drives the loop from its own server, this is the path. For a personal local app on a subscription, the CLI with -p or the orchestrator session is the lower-friction route.

**L28. Subagents in the Agent SDK**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/agent-sdk/subagents).
- URL: https://code.claude.com/docs/en/agent-sdk/subagents
- AgentDefinition fields: description, prompt, tools, disallowedTools, model, skills, memory, mcpServers, initialPrompt, maxTurns, autoCompactWindow, background, omitClaudeMd, effort, permissionMode.
- Subagent context starts fresh: only its prompt and the Agent tool's prompt string reach it. Parent history does not pass down. Final report returns to the parent.
- Caps: CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH (default 3), CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS (default 20), and maxBudgetUsd (spend cap that also stops background subagents).
- Subagents can be resumed by agentId; a subagent stopped at maxTurns returns partial output and can be resumed.
- Relevance: explicit caps and resumability are the basis for the cost controls in Part 3.

**L29. Orchestrate subagents at scale with dynamic workflows (Claude Code docs)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://code.claude.com/docs/en/workflows). The companion blog summary (L30) says workflows are new and best practices are still developing.
- URL: https://code.claude.com/docs/en/workflows
- A workflow is a JavaScript script run by the runtime; primitives agent(prompt, opts), pipeline(items, fn), parallel(tasks); phase() and log() for progress; results are script variables, not context.
- Constraints: no mid-run user input (runs pause only for agent permission prompts or a usage-limit wait); no direct filesystem or shell access from the script; up to 16 concurrent agents by default (CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS); up to 4,096 items per pipeline call; 1,000 agents per run.
- Resume: completed agents return saved results; failed agents rerun along with later agents.
- Cost examples in the doc: one run with 14 agents and 482k tokens; another with 22 agents and 1.1M tokens. A Large workflow warning appears above 25 agents or 1.5M projected tokens.
- In claude -p and the SDK, the workflow launch goes through normal permission evaluation; Workflow must be allowed explicitly.
- Relevance: the best fit for literature fan-out and cross-checking. Not suited to a stage that needs human sign-off in the middle.

**L30. A harness for every task: dynamic workflows in Claude Code (Anthropic blog)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (summary of https://claude.dev/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code/ after redirect from claude.com).
- URL: https://claude.dev/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code/
- Verification patterns named: adversarial verification by a separate agent against a rubric; skeptic/refuter agents; panels where hypotheses face verifiers and refuters; quarantine of agents that read untrusted content (no high-privilege tools; only structured summaries pass on).
- Aggregation patterns: synthesize barrier; generate-and-filter; tournament with pairwise judging ("more reliable than absolute scoring"); classifier routing; loop until done.
- Limits noted: large lists degrade in one prompt; parallel agents can exhaust a local machine; each agent adds coordination cost.
- Relevance: the verification and quarantine patterns map directly onto this app's verify stage and its handling of untrusted PDFs and web pages.

**L31. Agent Skills specification (agentskills.io)**
- Org: Agent Skills open format (Anthropic-originated). Date: undated in fetched text. Tag: [V] (https://agentskills.io/specification).
- URL: https://agentskills.io/specification
- Frontmatter: name (max 64 chars; lowercase, digits, hyphens; must match directory), description (1-1024 chars), license, compatibility (max 500), metadata (string map), allowed-tools (experimental).
- Optional dirs: scripts/, references/, assets/. Keep SKILL.md under 500 lines; references one level deep.
- Progressive disclosure: metadata about 100 tokens at startup; instructions under 5,000 tokens recommended; resources on demand.
- Relevance: keep stage skills portable. Claude Code-only keys (context, agent, disable-model-invocation) are not in the spec.

### Group C. Anthropic engineering posts

**L32. How we built our multi-agent research system**
- Org: Anthropic. Date: undated in fetched text (models named are Claude Opus 4 and Sonnet 4). Tag: [V] (https://www.anthropic.com/engineering/multi-agent-research-system).
- URL: https://www.anthropic.com/engineering/multi-agent-research-system
- Lead agent (Opus 4) plans, spawns Sonnet 4 subagents in parallel, and a CitationAgent attributes claims at the end. Multi-agent beat single-agent Opus 4 by 90.2% on the internal research eval (authors).
- Token use: agents about 4x chat; multi-agent about 15x. Token usage explained 80% of variance on BrowseComp.
- Lead saves its plan to memory because context beyond 200,000 tokens gets truncated. Durable checkpoints and retry logic let agents resume.
- Evaluation: LLM judge with rubric (factual accuracy, citation accuracy, completeness, source quality, tool efficiency); about 20 starting queries; human testing caught source-quality issues automation missed.
- Lessons: vague delegation caused duplicate work; explicit effort-scaling rules were needed; multi-agent suits parallelizable tasks, poorly suited to heavy shared context.
- Relevance: the most direct evidence for orchestrator-plus-workers, and for the cost trade-off. Models are 2025-era; numbers do not transfer directly.

**L33. Effective harnesses for long-running agents**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
- URL: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Initializer session writes a feature list, an init script, a progress file, and an initial commit; later sessions do one feature each.
- Feature list in JSON; agents may only flip a pass status; JSON reduced inappropriate overwrites compared with Markdown.
- Clean-state rule: every session ends mergeable, committed, and documented; each session starts with a fixed routine (pwd, progress file, git log, feature list, smoke test).
- Verify end-to-end as a user would; unit tests and curl alone missed failures.
- Failure modes listed: declaring victory early; leaving undocumented half-work; marking features passing without testing.
- Relevance: directly applicable to a research run that spans sessions: the "feature list" becomes a claim list with status, and "clean state" becomes a run checkpoint.

**L34. Building effective agents**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://www.anthropic.com/engineering/building-effective-agents).
- URL: https://www.anthropic.com/engineering/building-effective-agents
- Patterns: prompt chaining, routing, parallelization (sectioning or voting), orchestrator-workers, evaluator-optimizer.
- Workflows (predefined code paths) suit well-defined tasks; agents suit open-ended problems at higher cost and compounding error risk.
- Advice: start with the simplest solution; principles are simplicity, transparency (show planning), and careful tool documentation.
- Relevance: the stage graph should be a workflow with explicit transitions, with agent steps only where judgment is needed.

**L35. Effective context engineering for AI agents**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- URL: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Just-in-time retrieval: keep references (paths, queries) and load at runtime; CLAUDE.md loaded up front, the rest on demand.
- Compaction, clearing old tool results, and structured note-taking files outside the window.
- Sub-agents return condensed summaries, often 1,000-2,000 tokens, while using tens of thousands internally.
- Choice guidance: compaction for long back-and-forth, notes for iterative work with milestones, multi-agent for complex parallel research.
- Relevance: justifies the rule that subagents return short summaries plus artifact paths, and the orchestrator never loads full PDFs.

**L36. Claude Code auto mode: a safer way to skip permissions (Anthropic engineering)**
- Org: Anthropic. Date: undated in fetched text. Tag: [V] (https://www.anthropic.com/engineering/claude-code-auto-mode).
- URL: https://www.anthropic.com/engineering/claude-code-auto-mode
- Two layers: a server-side prompt-injection probe on tool outputs, and a transcript classifier (stated as running on Sonnet 4.6) reviewing actions. Stage 1 is a fast filter told to "err on the side of blocking"; stage 2 is chain-of-thought review of flagged actions.
- Reasoning-blind design: assistant prose and tool results are stripped from the classifier's view.
- Measured (table in post): real traffic (n=10,000) false positive rate 8.5% stage 1 only vs 0.4% full pipeline; real overeager actions (n=52) false negative 6.6% vs 17%; synthetic exfiltration (n=1,000) false negative 1.8% vs 5.7%.
- Post calls the 17% overeager miss rate "the honest number" and says most misses are actions the classifier judged covered by user consent. Says it is "not a drop-in replacement for careful human review on high-stakes infrastructure."
- Headless: after 3 consecutive or 20 total denials, the session escalates to a human; in headless mode the process terminates.
- Relevance: an empirical basis for keeping human gates on irreversible actions even in auto mode. Consent-based misses are the relevant failure mode for research approvals.

### Group D. Community skill repositories

**L37. K-Dense-AI scientific-agent-skills**
- Org: K-Dense AI. Date: undated (snapshot). Tag: [V, snapshot; star count from fetch] (https://github.com/K-Dense-AI/claude-scientific-skills — fetched URL is github.com/K-Dense-AI/claude-scientific-skills, the page reported the name scientific-agent-skills).
- URL: https://github.com/K-Dense-AI/claude-scientific-skills (fetched); the repository name in the page content is K-Dense-AI/scientific-agent-skills. [U on name]
- Page reports 177 skills across bioinformatics, cheminformatics, clinical, ML, physics, data analysis, research methodology, and more; skills/<name>/SKILL.md with metadata.version; some skills ship tests/<skill-name>/.
- MIT repository license; each skill declares its own license. Install: npx skills add, gh skill install, plugin packaging, manual clone into ~/.agents/skills/. Latest release 2.72.0 (page). Stars reported 56.7k (snapshot).
- Relevance: a reference set of SKILL.md conventions and a source for domain skills. Audit each skill before use; it is third-party code.

**L38. claude-scientific-skills (K-Dense-AI, mirrors and forks)**
- Org: K-Dense AI and mirrors. Date: undated. Tag: [S].
- URLs: https://www.sourcepulse.org/projects/17884895 ; https://github.com/cnopens/claude-scientific-skills (fork) ; https://github.com/InternScience/Awesome-Scientific-Skills (related list)
- Install for Claude Code: /plugin marketplace add K-Dense-AI/claude-scientific-skills, then install categories; or copy skill folders into ~/.claude/skills/.
- Counts differ by mirror: 170 and 139 skills cited. Stars range from about 5.1k to 40k across snapshots. Treat as unreliable. [U]
- Relevance: shows the marketplace install path; the naming and count conflict with L37 is why both are flagged.

### Group E. Autonomy frameworks

**L39. Levels of Autonomy for AI Agents**
- Org: University of Washington (K. J. Kevin Feng, David W. McDonald, Amy X. Zhang). Date: arXiv 2506.12469, submitted 2025-06-14; v2 2025-07-28. Tag: [S] (abstract and search summary; not fully read).
- URLs: https://arxiv.org/abs/2506.12469 ; https://arxiv.org/html/2506.12469v2
- Five user roles define autonomy: operator, collaborator, consultant, approver, observer. Autonomy is a user-centered design choice, not only a model capability.
- Proposes autonomy certificates that a third party could issue to bound an agent's permitted level, and assisted evaluation to measure autonomy separately from capability.
- Authors call it a descriptive sketch, not a prescription.
- Relevance: gives names to the per-stage autonomy settings (operator = auto, approver = ask before commit, observer = report only) used in the policy schema in Part 2.

---

## Part 2. Proposed agent roster, stage graph, backtracking, and gate policy

Design constraints drawn from the sources:
- Mid-run human input is not available inside a dynamic workflow (L29). Human gates must sit at stage boundaries: either between workflow runs, or in the orchestrator's own turns. (Design implication, not a documented feature.)
- Subagents return summaries and artifact paths, not raw content (L35, L32).
- Read-only roles should be enforced with tools allowlists, not prompts (L18, L28).
- Data invariants from AGENTS.md: data/ stays private and out of Git; source PDFs and notes are never overwritten; external transmission needs an explicit request and a preview; backup format must be checked on schema changes.

### 2.1 Runtime roles and where they run

Orchestrator: the main Claude Code session (Opus). It runs the research-loop skill, reads the gate policy, decides transitions, and is the only role that writes the run state file. It is not a subagent.

Model choices use Claude Code aliases. Effort is set per agent (L18 effort field; L25 levels).

| Role (file) | Model | Effort | Tools (allowlist) | Inputs | Outputs | Stages |
|---|---|---|---|---|---|---|
| orchestrator (main session, skill `research-loop`) | opus | high at replanning, medium otherwise | Agent, Read, Write (run dir only), EasyResearch MCP read/write tools | run state, gate policy, failure ledger | run state transitions, gate prompts | all |
| `survey-screener` | haiku | low | Read, Grep, Glob, EasyResearch MCP search/read | query list, candidate paper metadata | include/exclude decisions with reason codes | S1 |
| `method-explorer` | sonnet | medium | Read, Grep, EasyResearch MCP read | problem cards, method notes with quotes | 3-5 method cards (method, assumptions, source quotes) | S2 |
| `hypothesis-writer` | sonnet | high | Read, EasyResearch MCP read | method cards, failure ledger filtered for this topic | contribution hypotheses, each with a falsifiable prediction and a stated failure condition | S3, and regenerate on backtrack |
| `prior-work-verifier` | sonnet | medium | Read, WebSearch, WebFetch, EasyResearch MCP read (no write) | one hypothesis card | closest-prior-work list, overlap verdict (novel / partial / subsumed), citations | S4a |
| `falsifier` | sonnet | high | Read, Grep, EasyResearch MCP read (no write) | hypothesis card plus prior-work verdict | 2-4 refutation tests with measurable predictions; a verdict per test | S4b |
| `feasibility-checker` | haiku | medium | Read, Bash (allowlist: `python -c "import ..."`-style checks only, set by permission rules), EasyResearch MCP read | hypothesis, data inventory, compute budget | feasible / infeasible with reason (data, compute, time) | S4c |
| `citation-checker` | haiku | low | Read, Grep | draft claims with quote and source id | per-claim pass/fail: quote found verbatim in stored source text | S4 (every stage that emits claims), S8 |
| `failure-curator` | haiku | low | Read, Write (failure ledger file only) | rejected branch artifacts | one failure entry (schema below) | any backtrack |
| `experiment-runner` | sonnet | medium | Read, Edit, Write, Bash (allowlist: test and run commands declared in the run plan) | approved experiment plan | run logs, metrics, code diff, all inside a git worktree | S5-S6 (isolation: worktree, background: false) |
| `result-analyst` | sonnet | high | Read, Grep, Bash (read-only analysis scripts) | run logs and metrics, pre-registered predictions | result card: supports / refutes / inconclusive per prediction, with confidence and implementation-error check | S7 |
| `report-writer` | sonnet | medium | Read, Write (report dir only) | verified claims, result cards, citation-checker output | draft report where every claim has a source id | S8 |

Sample frontmatter for the verifier (project-level file, so permissionMode and tools apply; L18):

```markdown
---
name: prior-work-verifier
description: Finds the closest prior work for one contribution hypothesis and returns an overlap verdict with citations. Use in stage S4a only.
tools: Read, WebSearch, WebFetch, mcp__easyresearch__search_papers
model: sonnet
effort: medium
permissionMode: default
maxTurns: 25
background: false
memory: project
---
```

The MCP tool name above is a placeholder. The real server and tool names must come from services/mcp/easyresearch_mcp.py and must be checked before use (Part 4).

Subagent rules shared by all roles:
- Subagents must not spawn subagents: omit Agent from tools (L18).
- Each role's prompt must include the run id, artifact paths, and the output file it must write; the Agent tool prompt is the only input the subagent gets (L28).
- Every subagent returns at most about 2,000 tokens of summary plus artifact paths (L35).

### 2.2 Skills and hooks

Skills (project level, .claude/skills/):
- `research-loop` (SKILL.md, forked stages only through agents): orchestration procedure, stage table, backtrack rules. Keep SKILL.md under 500 lines; put the stage table and schemas in references/ (L31).
- `method-card`, `hypothesis-card`, `failure-entry`: schema references loaded by the roles that write them.
- `claim-quote-rules`: rules for quoting and page-label vs physical-page distinctions (AGENTS.md invariant).
- `stage-report`: `disable-model-invocation: true` so only the user or the orchestrator can start a report; `context: fork` with `agent: report-writer` (L19).

Hooks (project settings; scripts in .claude/hooks/):
- PreToolUse on Read/Write/Edit/Bash: deny paths under data/ outside the current run dir, and deny writes to the library DB and source PDFs. Exit 2 with a reason, or permissionDecision deny (L20).
- PreToolUse on WebFetch/WebSearch and any MCP send tool: check that the outgoing text does not contain private note text (preview required). Deny or ask (L20; AGENTS.md outbound rule).
- PermissionRequest: route approval for experiment execution to the user; hooks can answer, but a hook cannot wait on the user for long, so keep it to logging and deny-by-default (L20, L21).
- SubagentStop: copy the subagent's summary and artifact paths into the run state file, so the orchestrator never re-reads a full transcript (L20).
- Stop: refuse to end the orchestrator turn while a gate is pending. Needs a re-entry guard; the stop-hook input fields must be checked in the hooks reference before coding (Part 4).

### 2.3 Stage graph

```
S0 Intake (topic, constraints, budgets, gate policy load)
  -> S1 Survey (plan queries -> search -> screen)         [workflow fan-out allowed]
  -> S2 Problems & methods (problem cards, method cards)
  -> S3 Hypotheses (contribution hypotheses + failure conditions)
  -> S4 Verify
       S4a prior-work-verifier (closest prior work, overlap verdict)
       S4b falsifier (refutation tests)
       S4c feasibility-checker (data, compute, time)
       S4d citation-checker on all claims
       -> decision: PASS (novel-or-partial, not refuted, feasible, quotes verified)
  -> S5 Experiment design (pre-registered predictions, stop rules)     [gate]
  -> S6 Execute (experiment-runner in worktree)                         [gate per run]
  -> S7 Analyze (result-analyst; implementation-error check first)
       -> decision: supported | refuted | inconclusive | impl-error
  -> S8 Report (report-writer; citation-checker pass)                   [gate]
```

Backtracking transitions:

| From | Trigger | Action | Back-edge target | Limit |
|---|---|---|---|---|
| S4a | overlap = subsumed by prior work | record failure (novelty_overlap), keep the prior-work list | S3 (regenerate this hypothesis with the overlap as a constraint) | 2 per hypothesis |
| S4a | overlap = partial, and the novelty delta is unclear | ask the user at gate S4-kill (see 2.4) | S3 or continue | user decides |
| S4b | falsifier test refutes a core prediction, from literature evidence | record failure (refuted_by_literature) | S3 | 2 per hypothesis |
| S4c | infeasible (data or compute) | record failure (infeasible_data or infeasible_compute), add constraint | S3 with constraint | 2 per hypothesis |
| S4d | citation check fails on a claim | fix or remove claim; no backtrack unless the quote is the only evidence | S2 or S3 | 1 retry of the claim |
| S4 | evidence insufficient (few sources survive screen) | widen queries once | S1 | 1 widening round per topic |
| S2 | all hypotheses from current method cards failed twice | new method cards with the failure ledger as exclusion list | S2 | 1 per topic |
| S7 | impl-error (predictions fail because of code or setup, not theory) | fix and rerun | S6 | 2 reruns per experiment |
| S7 | refuted by experiment | record a negative result (refuted_by_experiment); report it | S8 (negative result report) or S3 (only if the user asks to continue) | user decides |
| any | global backtrack count reaches the cap | stop and gate to the user | none | global cap |

Global limits (in the policy file): max backtracks per topic 10; max wall time and max USD or token budget per run; stop when the cap is hit.

Failure ledger entry (append-only, JSONL, under the run directory; not in data/ source folders):

```json
{
  "id": "F-0007",
  "run_id": "R-2026-11-10-a",
  "stage": "S4a",
  "hypothesis_id": "H-03",
  "reason_code": "novelty_overlap",
  "evidence": [{"source_id": "P-112", "quote_sha256": "...", "page_label": "12", "physical_page": 14}],
  "what_failed": "one sentence",
  "do_not_retry_if": "same method family on the same dataset without a new mechanism",
  "expires_after_runs": 5,
  "created_by": "failure-curator"
}
```

Reason codes: novelty_overlap, refuted_by_literature, refuted_by_experiment, infeasible_data, infeasible_compute, evidence_missing, citation_failed, impl_error, scope. The page_label and physical_page pair reflects the AGENTS.md rule to distinguish printed labels from physical PDF pages.

Ledger rules: hypothesis-writer reads entries filtered to the topic and not expired; an entry can be overridden only by the user at a gate. Expiry stops old failures from blocking good ideas (a known risk, see Part 3 P4).

### 2.4 Approval-gate policy schema

Gates are declared per stage in one file (for example, research-policy.json in the run directory, created from a template at S0). Values: "auto" (proceed, log only), "ask" (stop at the boundary and wait for the user in the session), "report" (proceed, show a summary afterwards). Presets map to the roles in "Levels of Autonomy" (L39).

```json
{
  "policy_version": 1,
  "preset": "checkpointed",
  "stages": {
    "S0_intake":         {"gate": "ask"},
    "S1_survey":         {"gate": "auto", "budget": {"max_queries": 60, "max_candidates": 300}},
    "S2_methods":        {"gate": "report"},
    "S3_hypotheses":     {"gate": "ask", "show": "hypothesis cards with failure conditions"},
    "S4_verify":         {"gate": "auto"},
    "S4_kill_decision":  {"gate": "ask", "when": "partial overlap or any infeasible result"},
    "S5_experiment_plan":{"gate": "ask", "show": "predictions, stop rules, compute estimate"},
    "S6_execute":        {"gate": "ask", "per": "run"},
    "S7_result_claims":  {"gate": "ask", "when": "any supported or refuted claim"},
    "S8_publish":        {"gate": "ask"}
  },
  "outbound": {"gate": "ask", "preview_required": true, "allowed_hosts": ["api.openalex.org"]},
  "backtrack": {"max_per_hypothesis": 2, "max_global": 10, "auto_allowed": ["S4a->S3", "S4c->S3"]},
  "budget": {"max_usd_per_run": null, "max_tokens_per_run": null, "max_wall_minutes": 240},
  "hard_stops": ["write_outside_run_dir", "delete_library_item", "send_private_text_without_preview", "modify_source_pdf"]
}
```

Notes on the schema:
- max_usd_per_run and max_tokens_per_run are null because the subscription does not expose dollars per run; use /usage attribution and the workflow token figures as proxies (L26, L29).
- hard_stops are enforced by PreToolUse hooks, not by the policy text alone (L20; L36 notes instructions can be lost in compaction).
- Presets: "supervised" = every stage "ask"; "checkpointed" = as above; "unattended" = only hard stops and budget caps are enforced, and output is reviewed afterwards.

Implementation constraint: "ask" gates are implemented as stopping points between turns or between workflow runs, not as mid-workflow pauses (L29). Unattended runs using claude -p must use --permission-prompts none or --permission-mode dontAsk, so anything that would prompt is denied rather than hung (L21).

---

## Part 3. Concrete proposals

Cost is qualitative unless a source gives a number. Confidence: H = mechanism documented and low risk; M = documented mechanism, untested in this app; L = depends on unverified claims or on behavior not yet observed.

**P1. Opus orchestrator, Sonnet workers, Haiku for screening and checks.**
- Evidence: model resolution and aliases (L18, L25); Anthropic reports Opus lead with Sonnet subagents beat single-agent Opus by 90.2% on its own eval (L32, 2025 models); cost doc suggests Haiku for simple subagent tasks (L26).
- Cost: high on usage limits. Anthropic reports about 4x tokens for agents and about 15x for multi-agent systems (L32). Keep subagent count small per stage.
- Risk: the orchestrator may over-spawn. Mitigate with maxTurns and depth 1 (P19).
- Confidence: M-H.

**P2. Declare gates in one policy file, with three presets mapped to autonomy roles.**
- Evidence: per-stage human feedback in Agent Laboratory (L01); editable stage tables in TinyScientist (L14); autonomy roles operator / collaborator / consultant / approver / observer (L39).
- Cost: low to build; the cost is user attention per gate.
- Risk: gate fatigue leads users to approve blindly. Mitigate by making gates conditional ("when partial overlap") and by showing only the decision, not the whole transcript.
- Confidence: M.

**P3. Put every human gate at a stage boundary, never inside a workflow.**
- Evidence: workflows have no mid-run user input (L29); freephdlabor uses non-blocking callbacks for feedback (L11), which suggests the alternative of queueing feedback for the next boundary.
- Cost: low. Each stage becomes a separate invocation with a state file.
- Risk: more invocations and more state handoffs. Mitigate by one state file per run, written only by the orchestrator.
- Confidence: H (constraint documented).

**P4. Structured failure ledger with reason codes, expiry, and an override by the user.**
- Evidence: Reflexion episodic reflections (L17); DeepScientist cumulative memory and a sub-1% success rate (L05, author numbers); AgentRxiv shared findings with reported gains (L13, [U]); Anthropic's note-file pattern (L35).
- Cost: very low (JSONL append).
- Risk: stale or over-broad failures block valid ideas. Mitigate with expires_after_runs, do_not_retry_if conditions, and user override at a gate.
- Confidence: M.

**P5. Two-part refutation: a read-only falsifier agent, then experiment predictions pre-registered before execution, with sequential error control for multiple tests.**
- Evidence: POPPER's sequential falsification with e-values (L10); verifier and refuter panels (L30); result-analyst must check implementation error first (design).
- Cost: medium (falsifier adds one high-effort Sonnet call per hypothesis).
- Risk: the falsifier and hypothesis-writer share a model and can agree too easily. Mitigate by giving the falsifier only the hypothesis card and prior-work verdict, not the generation context (context isolation, L28).
- Confidence: M.

**P6. Backtracking as an explicit transition table with per-hypothesis and global caps.**
- Evidence: backtracking and lookahead formalized in ToT (L16); AI Scientist-v2 tree search with an experiment manager (L02, [V]).
- Cost: bounded by caps (2 per hypothesis, 10 global). Without caps, retries are unbounded.
- Risk: caps stop useful branches. Mitigate by letting the user raise a cap at a gate.
- Confidence: M-H.

**P7. Verify claims against stored source text, not against model memory, with a Haiku citation checker in front of every report.**
- Evidence: Anthropic's CitationAgent pattern (L32); Kosmos traceability to source (L07, [S]); verification-by-separate-agent (L30).
- Cost: low (Haiku, short inputs).
- Risk: quotes that match but mislead. Mitigate with a stored page label and physical page per quote (AGENTS.md rule), and a human check on claims marked "when" in the policy.
- Confidence: H for the mechanism.

**P8. Read-only roles enforced by tools allowlists; experiment execution isolated in a git worktree.**
- Evidence: tools allowlist semantics (L18, L28: an omitted tool is absent, with no prompt); isolation: worktree (L18); clean-state per session (L33).
- Cost: low.
- Risk: worktree lifecycle and cleanup; test before relying on it. Risk of experiment files landing in data/ if paths are not guarded (see P9).
- Confidence: M (worktree isolation not tested here).

**P9. Path and outbound guards as PreToolUse hooks, not as prompt text.**
- Evidence: exit 2 and permissionDecision semantics (L20); auto-mode docs say boundaries stated in conversation can be lost on compaction, and deny rules are the hard guarantee (L22); L36 notes the same concern.
- Cost: low (a few scripts).
- Risk: hook scripts themselves can have bugs; test with synthetic paths in a temporary data folder.
- Confidence: H.

**P10. Unattended stages through claude -p with explicit permission flags, but not --bare on a subscription.**
- Evidence: -p flags and --permission-prompts none (L21); --bare requires ANTHROPIC_API_KEY and skips hooks and CLAUDE.md (L21), so it would both bill the API and drop the guards in P9.
- Cost: subscription usage limits; use --max-budget-usd only where the cap applies (it is a dollar figure in the docs).
- Risk: an unattended run that hits usage limits. The workflow doc describes pause-and-resume for interactive sessions only (L29).
- Confidence: M.

**P11. Literature fan-out as a dynamic workflow with per-paper screen and per-claim verification.**
- Evidence: pipeline and parallel primitives, 16 concurrent agents default, 1,000 per run (L29); verification patterns (L30); bundled /deep-research example (L29).
- Cost: the doc's own examples are 482k tokens for 14 agents and 1.1M for 22 agents (L29). Set workflowSizeGuideline to small for S1 and keep CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS low.
- Risk: the companion blog says workflows are new and best practices are still developing (L30). Use only for S1, not for the whole loop.
- Confidence: M.

**P12. Context hygiene: subagents return summaries under about 2,000 tokens plus artifact paths; the orchestrator reads only state files and cards.**
- Evidence: 1,000-2,000 token sub-agent summaries (L35); subagent context isolation (L28); Reflexion-style compact memory (L17).
- Cost: lowers main-session usage, which is the subscription constraint.
- Risk: the orchestrator lacks detail needed for a gate decision. Mitigate by a "show" field in each gate that names the artifact to open.
- Confidence: H.

**P13. Skill packaging: a research-loop orchestration skill, forked stage skills, and disable-model-invocation for side effects.**
- Evidence: context fork and agent fields (L19); disable-model-invocation (L19); portable core fields in the spec (L31).
- Cost: low.
- Risk: Claude Code-only keys do not port to other agent products. Keep the portable core in SKILL.md frontmatter and mark Claude Code keys in a comment.
- Confidence: H.

**P14. Hard budget caps through SDK-level and subagent-level limits.**
- Evidence: CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH (default 3; set 1) and CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS (default 20) (L28); maxTurns per subagent (L18).
- Cost: lowers worst-case usage.
- Risk: depth 1 means a subagent cannot delegate, so the orchestrator must do the fan-out itself for S1 unless the workflow runtime is used (P11).
- Confidence: H.

**P15. Stop-hook checkpoint so the orchestrator cannot end a turn while a gate is pending.**
- Evidence: Stop is a blocking event for exit 2 (L20).
- Cost: low.
- Risk: infinite re-entry if the hook blocks every time. Needs a guard. The stop-hook input field for re-entry must be verified in the hooks reference first (Part 4).
- Confidence: L-M until verified.

**P16. Three autonomy presets with a visible audit trail.**
- Evidence: autonomy roles (L39, descriptive); auto-mode escalation after repeated denials (L22, L36).
- Cost: low.
- Risk: presets get misread as safety guarantees. The auto-mode doc itself says it does not guarantee safety (L22).
- Confidence: M.

**P17. Stage-level evaluation with an LLM rubric and human spot checks.**
- Evidence: single-call rubric scoring 0.0-1.0 with pass/fail worked best; human testing caught source-quality problems (L32); benchmark-first design (Scientist-Bench, L04).
- Cost: moderate (a rubric judge per run).
- Risk: the judge shares biases with the generator. Spot-check against the human-labeled cases each release.
- Confidence: M.

**P18. Keep the roster at project level in .claude/agents/ until it is stable.**
- Evidence: plugin subagents ignore permissionMode, hooks, and mcpServers (L18, L23).
- Cost: none.
- Risk: project-level files need trust; they are committed to Git. Keep no secrets in them.
- Confidence: H.

**P19. Cost logging per stage from headless JSON and /usage attribution into the run state.**
- Evidence: total_cost_usd in JSON output (L21, client-side estimate); /usage attribution to skills and subagents (L26).
- Cost: very low.
- Risk: subscription costs are estimates, not invoices (L21, L26). Log them as usage proxies, not bills.
- Confidence: H.

**P20. Tournament-style selection among hypotheses with pairwise judging instead of absolute scores.**
- Evidence: Elo-style tournament in co-scientist (L09, [S]); "pairwise comparison is more reliable than absolute scoring" in the Anthropic workflow blog (L30).
- Cost: N-choose-2 judge calls; cap at small N (for example, 6 hypotheses = 15 pairwise judgments).
- Risk: judge bias toward long or fluent hypotheses. Randomize order and check.
- Confidence: M.

---

## Part 4. Conflicts, unverified items, and things to check before coding

Claude Code frontmatter and config (verify against the raw page before writing files):
- C1. Official subagent doc lists the frontmatter fields used in Part 2 (name, description, tools, model, permissionMode, maxTurns, skills, memory, background, effort, isolation). The text was read through a summarizing fetch. Exact spelling (camelCase such as permissionMode and disallowedTools) must be checked on the raw page. Unknown fields are silently ignored, so a typo would fail without an error.
- C2. The skill doc uses hyphenated keys (allowed-tools, disable-model-invocation, argument-hint). The Agent Skills spec allows only name, description, license, compatibility, metadata, allowed-tools. Claude Code keys such as context, agent, and model are not portable (L19, L31).
- C3. Description length differs: spec says 1-1024 characters; Claude Code caps description plus when_to_use at 1,536 characters in the listing (L19, L31). Use the stricter number.
- C4. The model-config page says sonnet resolves to Sonnet 5.5 on the Anthropic API but to Sonnet 4.5 on Microsoft Foundry, Bedrock, and Google Cloud. Pin full model IDs if the app will run on more than one provider. The raw page was truncated; the Haiku auto-compact figure and CLAUDE_CODE_SUBAGENT_MODEL behavior were not fully read (L25).
- C5. Auto-mode classifier model: the permission-modes doc says default Sonnet 5; the engineering post says the transcript classifier runs on Sonnet 4.6. The post may predate the doc. Unresolved (L22, L36).
- C6. Auto-mode false-negative rate on overeager actions is 17% (n=52, small test set) per the post; the post says it is not a replacement for human review (L36). Do not read the low false-positive figure as a safety rate.
- C7. Plugin subagents ignore permissionMode, hooks, and mcpServers frontmatter (L18). Relevant if the roster is packaged later.
- C8. --bare changes authentication: it never reads subscription login and requires ANTHROPIC_API_KEY (L21). This conflicts with a subscription-only setup. Unattended runs without --bare load the project's hooks and MCP servers, which must be reviewed first.
- C9. Permission-mode default for claude -p changed in a recent version: the doc says runs start in manual mode when nothing sets a mode (version-dependent, L21). Pin the flag explicitly.
- C10. Dynamic workflows: the docs describe it as a new feature with changing behavior; availability depends on plan (all paid plans; Pro requires a toggle in /config) (L29). Confirm the user's plan before designing around it.
- C11. The Stop-hook re-entry field name and the exact hook input schema were not read. Verify before P15.
- C12. The Agent tool is named "Agent" in tool_use blocks; older SDK versions used "Task" (L28). Match both if parsing transcripts.
- C13. Background default: subagents started from the main conversation run in the background by default (L18, L28). Gate-bound stages must set background: false explicitly.
- C14. The MCP tool names in the sample frontmatter are placeholders. The real names come from services/mcp/easyresearch_mcp.py.

Research-system claims that are unverified or conflicting:
- C15. AI Scientist-v2 and AI Scientist v1: the Nature title and DOI come from one UBC news item only (L03, L02). Check on nature.com before citing.
- C16. AI-Researcher: the NeurIPS 2025 Spotlight and the 7.4 vs 8.1 score come from a blog (L04). Not confirmed.
- C17. DeepScientist, Kosmos, Robin, co-scientist, Denario, AgentRxiv, Reflexion, POPPER biology time savings, and Agent Laboratory's 84% cost reduction are either author-reported or company-reported. Use only as directional evidence. Agent Laboratory's baseline is unnamed (L01).
- C18. Zochi's acceptance is confirmed by secondary coverage; the 8.2% and 4/5 figures are the company's own (L12).
- C19. Robin's appearance in Nature is unclear (L08). InternAgent-1.5 numbers were not verified (L06).
- C20. TinyScientist may be mixed in the index with a similar paper (L14).
- C21. The Anthropic multi-agent post used Opus 4 and Sonnet 4; its percentages were measured on those models (L32).
- C22. The K-Dense repository name and counts conflict: the fetched page is titled scientific-agent-skills with 177 skills and 56.7k stars, while search results list claude-scientific-skills with 139 to 170 skills and 5.1k to 40k stars (L37, L38).
- C23. Levels of Autonomy was read from the abstract and a search summary, not the full paper (L39).
- C24. Sakana's 2026 Nature claim, the "partial overlap" branch in S4a, and the "widen queries" back-edge are design decisions in Part 2, not claims from the sources.

Scope note:
- C25. AGENTS.md defines development roles (Sol, Luna, Gemini scout, with GPT-6 and Gemini 3.8 Flash names). Those are the repo's development-team roles and are not Claude Code aliases. This report maps only runtime roles for the app's research loop. I did not verify the existence or behavior of those model names.
- C26. No Claude Code commands were run and no repository files were changed beyond this report. The roster has not been tested in this repo.

---

## Part 5. URL index

Research systems and verification:
- L01 https://arxiv.org/abs/2501.04227 ; https://AgentLaboratory.github.io/
- L02 https://arxiv.org/abs/2504.08066
- L03 https://arxiv.org/pdf/2408.06292 ; https://www.cs.ubc.ca/news/2026/03/ai-scientist ; https://github.com/SakanaAI/AI-Scientist
- L04 https://arxiv.org/html/2505.18705v1 ; https://github.com/HKUDS/AI-Researcher
- L05 https://arxiv.org/html/2509.26603v1 ; https://iclr.cc/virtual/2026/poster/10008492 ; https://github.com/ResearAI/DeepScientist
- L06 https://arxiv.org/abs/2505.16938 ; https://github.com/Alpha-Innovator/InternAgent
- L07 https://arxiv.org/html/2511.02824v2 ; https://edisonscientific.com/articles/announcing-kosmos
- L08 https://arxiv.org/pdf/2505.13400 ; https://futurehouse.org/research-announcements/demonstrating-end-to-end-scientific-discovery-with-robin-a-multi-agent-system ; https://github.com/Future-House/robin
- L09 https://arxiv.org/abs/2502.18864
- L10 https://arxiv.org/pdf/2502.09858 ; https://proceedings.mlr.press/v267/huang25n.html ; https://github.com/snap-stanford/POPPER
- L11 https://arxiv.org/html/2510.15624v1 ; https://github.com/ltjed/freephdlabor
- L12 https://www.lesswrong.com/posts/LtsgfGsXpiLTSGpaW/zochi-publishes-a-paper ; https://www.casrai.org/news/fully-ai-generated-papers-passing-peer-review-zochi-sakana
- L13 https://arxiv.org/pdf/2503.18102 ; https://arxiv.org/html/2503.18102v1
- L14 https://arxiv.org/html/2510.06579v1 ; https://github.com/ulab-uiuc/tiny-scientist
- L15 https://arxiv.org/pdf/2510.26887 ; https://arxiv.org/html/2510.26887v1
- L16 https://arxiv.org/pdf/2305.10601 ; https://github.com/princeton-nlp/tree-of-thought-llm
- L17 https://arxiv.org/abs/2303.11366v4 ; https://ar5iv.labs.arxiv.org/html/2303.11366

Claude Code and Agent SDK:
- L18 https://code.claude.com/docs/en/sub-agents
- L19 https://code.claude.com/docs/en/skills
- L20 https://code.claude.com/docs/en/hooks
- L21 https://code.claude.com/docs/en/headless
- L22 https://code.claude.com/docs/en/permission-modes
- L23 https://code.claude.com/docs/en/plugins
- L24 https://code.claude.com/docs/en/output-styles
- L25 https://code.claude.com/docs/en/model-config
- L26 https://code.claude.com/docs/en/costs
- L27 https://code.claude.com/docs/en/agent-sdk/overview
- L28 https://code.claude.com/docs/en/agent-sdk/subagents
- L29 https://code.claude.com/docs/en/workflows
- L30 https://claude.dev/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code/ (redirected from https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code)
- L31 https://agentskills.io/specification

Anthropic engineering:
- L32 https://www.anthropic.com/engineering/multi-agent-research-system
- L33 https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- L34 https://www.anthropic.com/engineering/building-effective-agents
- L35 https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- L36 https://www.anthropic.com/engineering/claude-code-auto-mode

Community repositories:
- L37 https://github.com/K-Dense-AI/claude-scientific-skills (fetch reported the name scientific-agent-skills)
- L38 https://www.sourcepulse.org/projects/17884895 ; https://github.com/cnopens/claude-scientific-skills ; https://github.com/InternScience/Awesome-Scientific-Skills

Autonomy:
- L39 https://arxiv.org/abs/2506.12469 ; https://arxiv.org/html/2506.12469v2
