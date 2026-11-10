# F. Subagents, loop engineering, context engineering, durable execution, self-correction limits

Date: 2026-11-10
Scope: evaluate design decisions O3 (durability), O4 (budgets), O6 (repetition guard), O7b (self-critique), O8 (context packing), O12b (Claude Code as outer orchestrator) for the EasyResearch research-assistant layer.

## Method and verification legend

- Sources were gathered with WebFetch (primary pages first) and WebSearch (to locate pages that returned 404/403/redirect or wrong IDs).
- For arXiv papers, [V] means the abstract page was opened and read. Full-paper numbers were NOT verified unless stated.
- [V] = the primary page was opened and the claim was confirmed.
- [S] = search-result snippet or third-party mirror only; not opened as the primary page.
- [U] = could not confirm (blocked, missing, or contradicted).
- Where a fetched page did not contain a claim I expected (e.g., a specific threshold), I say so instead of filling it in.
- Counts: 45 distinct sources; 28 opened as [V]; the rest [S] or [U].
- No numbers below were invented. Where a number comes from a secondary source, it is labeled.

---

## Part 1 - Source records

Dates are given only where they appeared in fetched or searched text; otherwise "date not shown".

### S01. Effective context engineering for AI agents
- Author/org: Anthropic (engineering blog). Date: not shown in fetched text.
- URL: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Tag: [V]
- Findings:
  - Defines context engineering as curating the full token set seen at inference (system prompt, tools, examples, history, external data); calls it iterative because context changes every turn.
  - Describes context rot as declining recall as the window fills, across all models, with varying degradation.
  - Compaction: summarize near the limit and restart; the lightest form is clearing old tool results. Recommends maximizing recall first, then precision.
  - Structured note-taking outside the window (to-do lists, NOTES.md); Pokemon example tracked 1,200+ game steps.
  - Sub-agents get clean windows and return condensed summaries, often 1,000-2,000 tokens, to a lead agent.
- Relevance to EasyResearch: supports keeping sub-agent/evidence outputs short and file-backed; supports clearing stale intermediate outputs from prompts rather than accumulating them.

### S02. Effective harnesses for long-running agents
- Author/org: Anthropic engineering. Date: not shown in fetched text.
- URL: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Tag: [V]
- Findings:
  - Two-role setup: an initializer agent runs once (init script, progress log, initial git commit); a coding agent then works one feature per session. Same harness, different prompts.
  - Progress file plus git history lets a fresh context recover project state.
  - Feature list kept as JSON with a "passes" field; the team chose JSON because models altered Markdown more often. Instructions forbade removing or editing tests.
  - Agents declared features done after unit tests or curl checks; end-to-end browser testing "substantially improved" results (no number given in the fetched text).
  - Every session ends with a commit and a progress update, and starts by re-checking basic functionality.
- Relevance to EasyResearch: a per-run progress/notes file and a "verify before continuing" step at resume time map directly onto a durable run log; a frozen acceptance list (like the JSON feature list) is a pattern for protecting against the model quietly editing its own success criteria.

### S03. Building effective agents
- Author/org: Anthropic engineering. Date: not shown.
- URL: https://www.anthropic.com/engineering/building-effective-agents
- Tag: [V]
- Findings:
  - Separates workflows (predefined code paths) from agents (LLM directs its own steps). Recommends the simplest solution that works.
  - Agents need stopping conditions such as a maximum number of iterations, plus human checkpoints when needed.
  - Agentic systems trade latency and cost for performance; compounding errors increase with autonomy.
  - Advises measuring each added step to confirm it helps.
- Relevance to EasyResearch: supports a fixed-pipeline design (search -> read -> profile -> critique) with a hard iteration cap rather than an open-ended agent loop.

### S04. Equipping agents for the real world with Agent Skills
- Author/org: Anthropic engineering. Date: not shown.
- URL: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Tag: [V]
- Findings:
  - Progressive disclosure in three levels: name+description always in the system prompt (small fixed cost), SKILL.md loaded when triggered, linked files loaded only when needed.
  - Bundled scripts can run as tools without loading their source or inputs into context.
  - SKILL.md must start with YAML frontmatter (name, description); the description drives triggering.
  - Advises keeping SKILL.md lean, splitting rarely combined contexts, and building skills from observed gaps.
  - No token figures given.
- Relevance to EasyResearch: a SKILL.md that tells Claude Code how to query the local library, with scripts for deterministic lookups, fits O12b well.

### S05. Claude Code docs: Subagents
- Author/org: Anthropic (code.claude.com). Date: not shown (page is current docs).
- URL: https://code.claude.com/docs/en/sub-agents
- Tag: [V] (first 100,000 of ~117,000 characters read)
- Findings:
  - Each subagent has its own context window, system prompt, tools and permissions; only its summary returns to the main conversation.
  - A non-fork subagent starts fresh (no conversation history); it receives CLAUDE.md, git status, and preloaded skills.
  - `tools` is an allowlist; `disallowedTools` is applied first if both are set. MCP tools can be filtered per server.
  - Model resolution order: per-invocation parameter, then frontmatter, then CLAUDE_CODE_SUBAGENT_MODEL, then the main model. Accepts sonnet, opus, haiku, fable, full model IDs, or inherit.
  - Default concurrency limit: spawning fails when 20 subagents are running (configurable via CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS). Nesting up to 3 levels by default. No total-count limit.
  - `maxTurns` caps turns and marks output partial; `effort` can be set per agent. Subagent requests count toward the same usage limits as the main conversation.
- Relevance to EasyResearch: per-agent `maxTurns`, `tools` allowlists (e.g., read-only library tools), and a low concurrency cap are directly usable. Usage-limit sharing means parallel profiling burns the same quota.

### S06. Claude Agent SDK overview
- Author/org: Anthropic (code.claude.com). Date: not shown.
- URL: https://code.claude.com/docs/en/agent-sdk/overview
- Tag: [V]
- Findings:
  - The SDK runs the Claude Code agent loop as a library, with built-in tools, hooks, subagents, MCP, permissions, sessions, skills, and plugins.
  - Explicitly states: third-party products cannot offer claude.ai login or rate limits; use API-key authentication.
  - The overview page does NOT list a budget or cost-cap option; I could not confirm one here (see Part 4).
  - Also points to a CLI-as-subprocess route (`-p --output-format json`) for other languages.
- Relevance to EasyResearch: if the app ever embeds the SDK, API-key auth is required; for personal Claude Code use via the CLI it is not an issue. Budget caps must be implemented by the app itself unless a documented SDK option is confirmed.

### S07. Claude Code docs: Hooks (Stop, SubagentStop, PreToolUse)
- Author/org: Anthropic. Date: not shown.
- URL: https://code.claude.com/docs/en/hooks
- Tag: [V] (partial: page is ~292,000 characters; read first 100,000; `stop_hook_active` not reached)
- Findings:
  - Stop and SubagentStop fire when Claude or a subagent finishes; exit code 2 prevents stopping and sends Claude back to work.
  - Stop/SubagentStop have no matcher; a failing hook cannot be repaired by Claude, and onFailure "block" has no effect on them.
  - PreToolUse exit code 2 blocks the tool call; a timed-out PreToolUse command does not block by default.
  - Stop hooks can read last_assistant_message.
- Relevance to EasyResearch: a Stop hook is a way to enforce "do not end until tests/checks pass" in Claude Code; it is the mechanism behind Ralph-style loops (S11). Caution: a Stop hook that re-runs a long LLM job can create an unbounded loop unless it has its own counter (check `stop_hook_active` in the full docs before relying on it).

### S08. Context management (Claude Developer Platform, Sonnet 4.5 launch)
- Author/org: Anthropic. Date: not shown in fetched text (launched with Sonnet 4.5).
- URL: https://claude.com/blog/context-management
- Tag: [V]
- Findings:
  - Context editing removes stale tool calls and results as the window nears limits; memory tool stores files outside the window (client-side backend, developer-controlled).
  - Internal agentic-search evaluation: memory tool plus context editing gave +39% over baseline; context editing alone +29%.
  - In a 100-turn web search evaluation, context editing let runs finish that otherwise failed from context exhaustion, while cutting token consumption by 84%.
  - Evaluation setup described only as internal and agentic search; not reproducible from this page.
- Relevance to EasyResearch: supports clearing old tool outputs and writing evidence to files; the percentages are vendor-internal and should be treated as directional.

### S09. Claude API docs: Context editing
- Author/org: Anthropic (platform.claude.com). Date: not shown.
- URL: https://platform.claude.com/docs/en/build-with-claude/context-editing
- Tag: [S] (URL and details taken from search results, not opened)
- Findings (from search snippets):
  - Strategy named clear_tool_uses_20250919 clears tool results past a configurable threshold; optional clear_tool_inputs.
  - Runs server-side; beta header context-management-2025-06-27.
  - Snippets disagree on trigger/keep values in third-party mirrors; verify on the official page.
- Relevance to EasyResearch: relevant only if the app uses the Claude API; it does not help the local Ollama path.

### S10. Ralph (Geoffrey Huntley)
- Author/org: Geoffrey Huntley (ghuntley.com). Date: not shown.
- URL: https://ghuntley.com/ralph/
- Tag: [V]
- Findings:
  - Ralph is a bash loop that re-feeds a prompt file to a coding agent; each iteration starts with a fresh context and does one task. A plan file (fix_plan.md) holds TODOs.
  - Tests, type checks and static analysis reject bad output; the operator tunes prompts when Ralph repeatedly fails.
  - Author expects roughly 90% completion for greenfield bootstrapping; explicitly would not use it on an existing codebase.
  - No formal stop condition: the loop runs until the operator intervenes or TODOs run out.
  - Stated risks: placeholder implementations, duplicated work, false "does not exist" conclusions after search, broken builds, reward hacking (optimizing for compiling code), and maintainability.
- Relevance to EasyResearch: the fresh-context-per-step idea matches the step table; the warnings (no stop condition, reward hacking, pressure to compile rather than be correct) argue against an unbounded loop for paper research.

### S11. Ralph Wiggum plugin for Claude Code (third-party write-ups and a GitCode mirror)
- Author/org: multiple third-party blogs; plugin mirror on gitcode. Date: not shown.
- URL: https://gitcode.com/2301_77165880/claude-code/tree/main/plugins/ralph-wiggum
- Tag: [S]
- Findings (from search snippets):
  - A Stop hook catches attempts to end the session; the original prompt is re-injected while work is unfinished.
  - Completion is signaled by printing a promise string in tags; the hook checks for that exact string.
  - `--max-iterations` is a safety cap; without it the loop can run indefinitely.
  - Loop state is stored in a local state file (iteration count, cap, promise string).
  - Sources disagree on the exact exit-code mechanics; treat as approximate.
- Relevance to EasyResearch: a cap-plus-exact-promise design is the same pattern as O4's max_llm_calls, implemented at the Claude Code level.

### S12. Manus: Context engineering lessons from building Manus
- Author/org: Manus (manus.im blog). Date: not shown.
- URL: https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- Tag: [V]
- Findings:
  - KV-cache hit rate is their top production metric; average input:output token ratio about 100:1; their quoted Claude Sonnet cost is $0.30/MTok cached vs $3/MTok uncached.
  - Keep the prompt prefix stable, make context append-only, serialize deterministically.
  - Do not add or remove tools mid-task; mask actions via logit constraints instead.
  - File system as unlimited external memory; compression is reversible when a URL or path remains.
  - Recitation: repeatedly rewriting a todo.md pushes the goal to the end of context; they say a typical task takes about 50 tool calls.
  - Keep failed actions and stack traces in context so the model updates its beliefs.
  - Repetitive few-shot patterns cause drift; they add controlled variation (example: 20-resume review drifted and hallucinated).
  - Rebuilt the framework four times.
- Relevance to EasyResearch: recitation (a fixed "current iteration goal + remaining budget" block at the end of the prompt) and keeping error messages in the step log are cheap changes. Cache-prefix stability matters only for paid APIs; local Ollama gets less benefit (depends on runtime; not verified here).

### S13. LangChain Deep Agents
- Author/org: LangChain (Harrison Chase). Date: July 30, 2025 per search snippet.
- URL: https://www.langchain.com/blog/deep-agents (redirect from https://blog.langchain.com/deep-agents; redirect target not fetched)
- Tag: [S]
- Findings (from search snippets and secondary write-ups):
  - Planning via a write_todos tool, described as a no-op-like planning step that helps long tasks; the snippet says it is modeled on Claude Code's TodoWrite.
  - Pluggable filesystem backends (in-memory, local disk, LangGraph store, composite, custom); context offloaded to files when the window grows.
  - Built-in task tool spawns subagents with their own context windows to keep the main context clean.
  - Prompt quality matters; sources say complex system prompts are common in strong agents.
- Relevance to EasyResearch: the same three pieces (plan file, files as memory, isolated subtasks) are the common pattern; no numeric evaluation was confirmed.

### S14. OpenAI: Harness engineering: leveraging Codex in an agent-first world
- Author/org: OpenAI (write-up by Ryan Lopopolo per search snippet). Date: February 11, 2026 per search snippet.
- URL: https://openai.com/index/harness-engineering/
- Tag: [U] (page returned HTTP 403; content only from search snippets and third-party commentary)
- Findings (secondary only):
  - Repo written by agents; AGENTS.md itself written by Codex; repo optimized for agent legibility (design docs, architecture maps readable by agents).
  - Commentary claims about one million generated lines and about 1,500 PRs are unverified against the original.
  - One DEV post cites "40-60% fewer agent errors" from unnamed benchmarks; not verifiable, not used.
- Relevance to EasyResearch: the AGENTS.md/exec-plan discipline already in this repo follows the same idea; no usable numbers.

### S15. Chroma: Context Rot
- Author/org: Chroma (research). Date: not shown in fetched text.
- URL: https://www.trychroma.com/research/context-rot
- Tag: [V]
- Findings:
  - 18 LLMs evaluated (page says "three families" but lists Anthropic, OpenAI, Google and Alibaba); includes Claude Opus 4, Sonnet 4, Haiku 3.5, GPT-4.1 family, Gemini 2.5, Qwen3-8B and others.
  - Performance declines with input length even on simple tasks; uneven across models.
  - Topically related distractors reduce accuracy even when there is only one; four distractors degrade it further; one distractor caused a larger drop than others.
  - Lower needle-question similarity made the decline faster as length grew (cosine similarity ~0.45-0.83 across embedding models).
  - Claude models hallucinated least and abstained more; GPT models gave more confident wrong answers in the study.
  - Needle position made no notable difference in their setup. Qwen3-8B did not attempt 4.21% of one task.
- Relevance to EasyResearch: term-overlap evidence selection is a low-similarity-prone design; near-duplicate abstracts from related papers act as distractors. Position made no difference here, which weakens the case for reordering alone (see O8).

### S16. Lost in the Middle (Liu et al.)
- Author/org: Liu et al. (TACL 2023 per arXiv listing). Date: arXiv 2307.03172 (July 2023).
- URL: https://arxiv.org/abs/2307.03172
- Tag: [V] (abstract only)
- Findings:
  - Performance is often highest when relevant information sits at the start or end of the context and drops when it is in the middle; reported on multi-document QA and key-value retrieval.
  - The abstract does not name models or give figures; the full paper would.
- Relevance to EasyResearch: a reason to place the top evidence at the beginning and end of the evidence block; note that Chroma (S15) found no position effect in its tests, so the effect is task- and model-dependent.

### S17. Context Length Alone Hurts LLM Performance Despite Perfect Retrieval (Du et al.)
- Author/org: Du et al. (arXiv Oct 2025; Findings of EMNLP 2025 per search snippet).
- URL: https://arxiv.org/abs/2510.05381
- Tag: [S] (search snippets and listing; not read in full)
- Findings (from snippets):
  - Across five LLMs on math, QA and coding, accuracy fell 13.9% to 85% even when all relevant evidence was retrieved.
  - The drop persisted when irrelevant tokens were replaced with whitespace or masked.
  - Placing evidence right before the question produced a similar drop.
  - Mitigation: have the model recite the retrieved evidence before solving; gained up to 4% on RULER for GPT-4o.
- Relevance to EasyResearch: even short contexts can hurt when the task is multi-step; an "evidence quote first" step is cheap to test.

### S18. Agentic Context Engineering (ACE)
- Author/org: Zhang et al. (arXiv 2510.04618). Date: October 2025 (arXiv ID).
- URL: https://arxiv.org/abs/2510.04618
- Tag: [V] (abstract only)
- Findings:
  - Treats context as an evolving playbook; addresses brevity bias and context collapse (repeated rewriting erodes detail).
  - Generation, reflection and curation in a modular cycle with incremental delta updates rather than full rewrites.
  - Abstract reports +10.6% over strong baselines on agent benchmarks and +8.6% on finance; matches a top production agent on AppWorld using a smaller open-source model.
  - Generator/reflector/curator roles and delta mechanics are not visible in the abstract.
- Relevance to EasyResearch: the "do not rewrite the summary wholesale, apply small deltas" rule is directly applicable to any rolling research memo; the reflector role is the same self-critique problem as O7b.

### S19. Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory
- Author/org: Suzgun, Yuksekgonul, Bianchi, Jurafsky, Zou. arXiv 2504.07952 (April 2025); EACL 2026 per search snippet.
- URL: https://arxiv.org/abs/2504.07952
- Tag: [S]
- Findings (from search snippets):
  - Frozen black-box LLM with an external text memory updated at inference; stores heuristics and strategies from past successes and failures.
  - Snippet claims: Claude 3.5 Sonnet's AIME accuracy more than doubled; GPT-4o on Game of 24 went from about 10% to 99% after reusing a Python solution.
  - Variants: DC-Cumulative and DC-Retrieval & Synthesis.
- Relevance to EasyResearch: a persistent "lessons learned" memory of which search queries and critique patterns worked; the specific numbers are task-specific (math puzzles) and not transferable.

### S20. MemGPT (Packer et al.)
- Author/org: Packer et al. arXiv 2310.08560 (October 2023).
- URL: https://arxiv.org/abs/2310.08560
- Tag: [V] (abstract only)
- Findings:
  - Virtual context management moves information between fast and slow memory tiers; interrupts coordinate control flow between model and user.
  - Evaluated on document analysis beyond the window and multi-session chat; no quantitative results in the abstract.
- Relevance to EasyResearch: the tiered memory idea maps to paper cards in SQLite (slow) versus the prompt (fast); no evidence here that it beats simple retrieval.

### S21. Large Language Models Cannot Self-Correct Reasoning Yet (Huang et al.)
- Author/org: Huang et al. (ICLR 2024 per fetched page). arXiv 2310.01798.
- URL: https://arxiv.org/abs/2310.01798
- Tag: [V] (abstract only)
- Findings:
  - Intrinsic self-correction (revision using only the model's own judgment, no external signal) generally does not help reasoning; sometimes accuracy goes down.
  - Abstract does not name benchmarks or numbers; full paper needed.
  - Quote: "LLMs struggle to self-correct their responses without external feedback."
- Relevance to EasyResearch: directly against O7b when the critic is the same model with no external check.

### S22. When Can LLMs Actually Correct Their Own Mistakes? (Kamoi et al.)
- Author/org: Kamoi et al. (TACL 2024). arXiv 2406.01297.
- URL: https://arxiv.org/abs/2406.01297
- Tag: [V] (abstract and metadata; survey of existing papers)
- Findings:
  - Survey and experiment-design checklist; finds many studies have loosely defined research questions and evaluations that overstate self-correction.
  - Found no prior work showing successful self-correction from feedback by prompted LLMs alone, except in tasks particularly well suited to it.
  - Self-correction works well with reliable external feedback; large-scale fine-tuning also enables self-correction.
- Relevance to EasyResearch: the strongest single source for the O7b verdict. The checklist is useful for designing an eval of EasyResearch's own critique step.

### S23. LLMs cannot find reasoning errors, but can correct them (Tyen et al.)
- Author/org: Tyen et al. (ACL 2024 Findings). arXiv 2311.08516.
- URL: https://arxiv.org/abs/2311.08516
- Tag: [V] (abstract)
- Findings:
  - Quote: "poor self-correction performance stems from LLMs' inability to find logical mistakes."
  - Several SOTA LLMs struggled to locate errors even in objective cases.
  - With ground-truth error locations given, LLMs corrected errors well across 5 reasoning tasks.
  - A small classifier trained on out-of-domain data outperformed prompting a large model at finding mistakes.
  - Released BIG-Bench Mistake dataset.
- Relevance to EasyResearch: the bottleneck is detection, not repair. An 8B critic is likely weak at detection; a deterministic or externally grounded check localizes the problem better than prompting for it.

### S24. CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing
- Author/org: Gou et al. arXiv 2305.11738.
- URL: https://arxiv.org/abs/2305.11738
- Tag: [V] (abstract)
- Findings:
  - Model critiques its output by calling external tools (search, code interpreter, toxicity checker) and then revises.
  - Evaluated on free-form QA, math program synthesis and toxicity reduction; reports consistent gains but the abstract gives no magnitudes.
  - Authors argue external feedback is key.
- Relevance to EasyResearch: the free, local equivalent of tool-based critique is a checker script (quote-in-source, citation exists, term present), not another LLM opinion.

### S25. Reflexion (Shinn et al.)
- Author/org: Shinn et al. arXiv 2303.11366.
- URL: https://arxiv.org/abs/2303.11366
- Tag: [V] (abstract)
- Findings:
  - Verbal reflection stored in an episodic memory buffer across trials; no weight updates.
  - Feedback can be scalar or free-form, external or simulated.
  - Reports 91% pass@1 on HumanEval versus 80% for GPT-4 (as stated in the abstract).
  - Note: the feedback in Reflexion's coding setting is test results, i.e., external signal.
- Relevance to EasyResearch: reflection helps when the feedback is real (tests, verifiers); a self-generated reflection without that signal is weaker (S21, S22).

### S26. Self-Refine (Madaan et al.)
- Author/org: Madaan et al. arXiv 2303.17651.
- URL: https://arxiv.org/abs/2303.17651
- Tag: [V]
- Findings:
  - Same model generates, critiques and refines over several rounds; no training.
  - Seven tasks (dialog to math reasoning); GPT-3.5, ChatGPT, GPT-4.
  - Humans and automatic metrics preferred refined outputs; average improvement about 20% absolute (as stated on the page).
  - No stopping rule described on the page.
- Relevance to EasyResearch: the most-cited support for O7b. It conflicts with S21/S22 for this reason: the evaluated tasks were mostly preference or text-quality tasks with a strong model, not factual correctness with a weak model (see Part 4).

### S27. LLM Evaluators Recognize and Favor Their Own Generations (Panickssery et al.)
- Author/org: Panickssery, Bowman, Feng. arXiv 2404.13076 (April 2024).
- URL: https://arxiv.org/abs/2404.13076
- Tag: [V] (abstract)
- Findings:
  - Evaluators rate their own outputs higher than human-equal texts; models can recognize their own text with non-trivial accuracy.
  - Abstract names GPT-4 and Llama 2. Fine-tuning produced a linear correlation between self-recognition and self-preference; the authors report a causal link.
  - No numeric correlation or accuracy figures in the abstract.
- Relevance to EasyResearch: a self-critic that wrote the problems will likely score them too high. A different model family, or a rubric with external checks, reduces this.

### S28. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (Zheng et al.)
- Author/org: Zheng et al. arXiv 2306.05685.
- URL: https://arxiv.org/abs/2306.05685
- Tag: [V] (abstract, v4)
- Findings:
  - GPT-4 judges reach over 80% agreement with both controlled and crowdsourced human preferences, which the abstract says matches human-human agreement.
  - Names position bias, verbosity bias, self-enhancement bias and limited reasoning as LLM-judge limitations; abstract gives no bias magnitudes.
  - Releases MT-Bench questions and 30K human-preference conversations.
- Relevance to EasyResearch: the 80% figure is for GPT-4 and human preferences on chat; it does not transfer to 8B models judging scientific claims.

### S29. Survey: LLM-as-a-Judge (arXiv 2411.15594)
- Author/org: survey authors (arXiv listing). Date: November 2024 (arXiv ID).
- URL: https://arxiv.org/abs/2411.15594
- Tag: [V] (abstract)
- Findings:
  - Surveys LLM evaluators for complex tasks as a lower-cost, scalable alternative to expert evaluation.
  - States that ensuring reliability of LLM-as-a-Judge "remains a significant challenge"; proposes a reliability benchmark.
  - Taxonomy and bias catalog are not in the abstract.
- Relevance to EasyResearch: a reminder to measure the critic's reliability (against the user's own labeled judgments) before trusting its 1-5 scores.

### S30. Language Models Don't Always Say What They Think (Turpin et al.)
- Author/org: Turpin et al. arXiv 2305.04388.
- URL: https://arxiv.org/abs/2305.04388
- Tag: [V] (abstract)
- Findings:
  - Quote: "CoT explanations can systematically misrepresent the true reason for a model's prediction."
  - Biasing features (for example, always putting the answer at option A) shift outputs; models rarely mention them.
  - Accuracy fell by as much as 36% across 13 BIG-Bench Hard tasks when models were biased toward wrong answers (GPT-3.5 and Claude 1.0).
- Relevance to EasyResearch: a critic's written reasons are not evidence of the actual cause of its score; log scores alongside verifiable checks instead of trusting explanations.

### S31. OpenHands StuckDetector
- Author/org: All Hands AI / OpenHands. URL redirected (docs.openhands.dev); redirect target not fetched.
- URL: https://docs.all-hands.dev/modules/python/openhands/controller/stuck
- Tag: [S]
- Findings (from search snippets, mirrored source code and a third-party analysis):
  - Official docs describe only the API `StuckDetector.is_stuck` with a headless_mode argument (default True).
  - Mirrored code describes three loop patterns: the same action-observation pair repeating (snippet says four in a row); the same action repeating with error observations (three); the agent repeating a message to itself without observations.
  - A proposed SDK PR groups events by LLM response ID and checks four repeats across the last four LLM call groups; merge status not confirmed.
  - Third-party analysis describes an observation-masking condenser with attention_window default 5; pinned to one commit, not verified.
- Relevance to EasyResearch: the detection pattern (exact-repeat of action+observation) is the nearest real-world analogue to O6, and it detects exact repetition only.

### S32. Gemini CLI loop detection (third-party description, not the official docs)
- Author/org: a third-party Rust crate (koda-core) documentation, describing Gemini CLI behavior. URL: https://docs.rs/crate/koda-core/0.3.2/source/src/loop_guard.rs
- Tag: [S]
- Findings:
  - Claims Gemini CLI uses a TOOL_CALL_LOOP_THRESHOLD of 5 consecutive identical calls (tool name + args fingerprint); not confirmed in Gemini CLI source.
  - Claims the first detection injects feedback and a second detection hard-stops.
  - A Gemini CLI PR (#18008) adds a model.disableLoopDetection setting; no user-configurable threshold confirmed.
  - An unrelated Obsidian plugin page uses a default threshold of 3; do not conflate.
- Relevance to EasyResearch: the two-stage "feedback, then hard stop" pattern is worth copying; the specific threshold is unverified.

### S33. LangGraph durable execution (durability modes)
- Author/org: LangChain. URL: https://docs.langchain.com/oss/python/langgraph/durable-execution
- Tag: [S] (search snippets; the fetched page at the .md URL was a persistence overview that did not contain the modes)
- Findings (from snippets):
  - Three durability modes: "exit" (persist only when execution exits, including error or interrupt), "async" (persist while the next step runs; small risk of losing the checkpoint on crash), "sync" (persist before the next step; highest durability, most overhead).
  - Python API reference says the default is "async".
  - Checkpointers store per-thread state; stores hold cross-thread data. Fetched overview: keep thread_id under 255 characters for PostgresSaver; in-memory savers lose state on restart; prune old checkpoints.
- Relevance to EasyResearch: the trade-off in O3 (write the step row before the next step) is exactly "sync" durability; the design should use sync writes for step status, which is cheap compared with a 300 s LLM call.

### S34. Pydantic AI durable execution with Temporal
- Author/org: Pydantic. URL: https://pydantic.dev/docs/ai/integrations/durable_execution/temporal/index.md
- Tag: [V]
- Findings:
  - Model requests, tool calls, MCP communication run as Temporal activities; the agent loop runs in workflow code.
  - On crash, Temporal re-executes workflow code and feeds recorded activity results, so completed work is not repeated; an activity that fails partway restarts from the beginning under its retry policy.
  - Workflow code must be deterministic; no I/O inside it; agent names and toolset IDs must stay stable.
  - Activities can run more than once if they retry; side effects must be idempotent. Approval listeners re-run on replay.
  - Temporal's default model retry policy is unbounded; the docs recommend setting the provider client's max_retries to 0 and letting Temporal own retries.
  - Payload size default about 2 MB.
- Relevance to EasyResearch: the idempotency and "unbounded retry by default" warnings apply directly to the O3 retry-the-stage design and to any automatic LLM retries.

### S35. Durable Execution meets AI (Temporal blog)
- Author/org: Temporal. URL: https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai
- Tag: [S]
- Findings (from search snippets, vendor material):
  - Side effects (LLM calls, DB writes, HTTP, tool calls) go in activities with retry policies.
  - One integration review says for short request-response agents, Temporal adds more machinery than it saves; a simple checkpoint may suffice.
  - Activities run at least once; idempotent tools are a production requirement.
- Relevance to EasyResearch: supports the view that a local SQLite step table is the right size for a single-user app; Temporal itself is overkill here.

### S36. DBOS with Pydantic AI and other frameworks
- Author/org: DBOS and Pydantic. URL: https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/
- Tag: [S]
- Findings (from search snippets):
  - DBOS stores workflow and step state in Postgres; crashed processes resume from the last finished step.
  - Integrations exist for Pydantic AI, Vercel AI SDK, Google ADK and LlamaIndex.
  - A DEV post claims DBOS released several agent packages in July 2026; unverified.
- Relevance to EasyResearch: a database-backed step log (SQLite version of the same idea) is the local, no-service equivalent; it does not need a workflow server.

### S37. Microsoft Agent Framework: Checkpoints
- Author/org: Microsoft Learn. URL: https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints
- Tag: [S]
- Findings (from search snippets; several locales and API variants disagree):
  - Checkpoints saved at superstep boundaries, after all executors in the superstep finish.
  - Snapshot includes executor state, pending messages, pending requests, shared state.
  - Storage options: in-memory, file, Cosmos; file storage uses pickle, so checkpoint files are trusted-only (newer page describes a restricted unpickler).
  - Custom executors must save and restore their own state.
- Relevance to EasyResearch: confirms the "checkpoint at step boundaries, store state explicitly" pattern; a pickle-based checkpoint would be a security issue for shared files, so keep JSON.

### S38. Inngest AgentKit: retries
- Author/org: Inngest. URL: https://agentkit.inngest.com/advanced-patterns/retries
- Tag: [S]
- Findings (from search snippets):
  - Official docs state AgentKit inside Inngest gets automatic retries, with a default policy of four retries with exponential backoff (figure from the snippet; not opened).
  - Recommended pattern: model calls in step.ai and other side effects in step.run so results are cached and retried per step.
  - Warning: side-effecting tools without idempotency keys are risky.
- Relevance to EasyResearch: cache-per-step plus bounded retries is the pattern to copy; the local step table already does this manually.

### S39. Exponential Backoff and Jitter (AWS Architecture Blog)
- Author/org: AWS Architecture Blog. URL: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- Tag: [V]
- Findings:
  - Simulated optimistic concurrency with many clients: backoff without jitter clusters retries; Full Jitter, Equal Jitter and Decorrelated Jitter all reduce client work.
  - With 100 contending clients, jittered approaches cut call counts by more than half; un-jittered backoff was worst on both work and completion time.
  - Recommends jittered backoff as a standard approach for remote clients; most AWS SDKs include it.
- Relevance to EasyResearch: retry delays for Ollama or any external API should be jittered and capped; with one user, the benefit is small, but the cap is what matters.

### S40. Stripe: Idempotent requests
- Author/org: Stripe. URL: https://docs.stripe.com/api/idempotent_requests
- Tag: [V]
- Findings:
  - Clients generate idempotency keys (UUIDv4 suggested); the server returns the saved result for a repeated key.
  - For API v1, the first request's status and body are saved once execution begins; a key can be pruned after at least 24 hours.
  - Parameters are compared on reuse; a mismatch is an error.
  - Results are not saved when validation fails before execution starts; those can be retried.
  - Avoid sensitive data in keys.
- Relevance to EasyResearch: use an input-hash key for each step (run_id + stage + prompt hash) and return the stored output on retry; only save results after execution starts, and store failed attempts separately.

### S41. Small LM self-critique study (arXiv 2601.00513)
- Author/org: arXiv listing. URL: https://arxiv.org/abs/2601.00513
- Tag: [S]
- Findings (from search snippets; paper not opened):
  - Study of 10,734 reasoning traces from Llama-3-8B, Mistral-7B and Qwen-2.5-7B; 50-69% of correct answers contained fundamentally flawed reasoning.
  - Self-critique did not help these 7-8B models, which the authors interpret as a capacity threshold.
- Relevance to EasyResearch: directly relevant to llama3-ko 8B critiquing its own problem statements. Needs full-text check before quoting numbers.

### S42. Automated LLM judge reliability evaluation (arXiv 2603.22214)
- Author/org: arXiv listing. URL: https://arxiv.org/pdf/2603.22214
- Tag: [S]
- Findings (from snippets; not opened):
  - Models at or below 32B struggled to produce consistently formatted outputs as prompts and data got harder.
  - Qwen2.5-7B sometimes missed the main issue despite decent F1; a second-level judge was ineffective.
- Relevance to EasyResearch: supports schema-constrained JSON output plus format-retry for 8B critics, and skepticism toward a second 8B judge.

### S43. Small language models need strong verifiers to self-correct reasoning
- Author/org: Findings of ACL 2024. URL: https://preview.aclanthology.org/moar-dois/2024.findings-acl.924
- Tag: [S]
- Findings (from snippet):
  - Models up to 13B can self-correct on reasoning with minimal stronger-model input; best gains when paired with a strong verifier.
- Relevance to EasyResearch: the local model needs an external verifier to do useful self-correction; a deterministic checker is the free equivalent.

### S44. Cline / Roo Code mistake limits (release notes and a Roo Code PR)
- Author/org: Cline and Roo Code projects; mirrored by third-party aggregators. URL: https://www.havoptic.com/r/cline/diff?from=4.0.8&to=4.1.25
- Tag: [S]
- Findings (from search snippets):
  - Cline has a consecutive-mistake limit; release notes changed the message and added telemetry; no user setting confirmed.
  - Roo Code added a configurable "Error & Repetition Limit" covering consecutive errors and repeated tool calls; 0 means unlimited; a CLI flag --mistake-limit exists.
- Relevance to EasyResearch: a single limit that covers both errors and repeats is a simple pattern to copy into O4/O6.

### S45. SWE-agent CLI documentation
- Author/org: SWE-agent project. URL: https://swe-agent.com/latest/usage/cli/
- Tag: [V] (CLI page only)
- Findings:
  - The CLI page does not mention cost, step or call limits; defaults not found here.
  - The page says SWE-agent is in maintenance-only mode and recommends mini-swe-agent.
  - The arXiv ID I tried for the SWE-agent paper (2310.10635) is an unrelated paper; SWE-agent's own paper was not read, so its cost-limit claims are [U].
- Relevance to EasyResearch: no usable default values to copy; the user's proposed budgets must be justified by the app's own measurements.

### S46. Anthropic: Claude Code and API context editing numbers (see S08) - no separate record.

Note: the source list runs to S45; S46 is intentionally unused.

---

## Part 2 - Verdicts

### O3. Durability (steps table, failed_step, retry same stage, stale running -> failed, synchronous HTTP under one RLock)

Verdict: **Partly supported.**

What is supported:
- Step-level checkpoints and resume from the last finished step are the core of every durable-execution system surveyed (S34 Pydantic/Temporal, S36 DBOS, S38 Inngest, S33 LangGraph "sync" mode, S37 MS Agent Framework checkpoints at superstep boundaries). The step-row design is sound.
- Writing step status before starting the next step matches LangGraph "sync" (S33) and is cheap relative to 155-300 s model calls.

What is not supported or is risky:
- Retry must be idempotent. Temporal/Pydantic (S34) and Inngest (S38) both state activities can run more than once and need idempotent side effects. Here the LLM call is the side effect: if the process dies after the model returns but before the output is saved, the retry re-runs the 155-300 s call. Mitigation: key each step by (run_id, stage, input hash), check for an existing done row before calling the model, and store raw output as soon as it returns (S40 Stripe-style keys).
- Stale running -> failed on next step call is correct only for a single process. If a request thread is still alive (slow call, not crash), marking it failed and retrying runs the model twice in parallel. This needs a lease with a heartbeat or a started_at timeout longer than the per-call timeout.
- A global RLock held during a 300 s call blocks every other run and any HTTP request that waits for the lock. Durable-execution sources (S33, S35) do not recommend synchronous long calls inside request handlers; S38 wraps model calls as cached background steps. Recommended: run LLM steps in a background worker thread, return a run id immediately, and poll (or SSE) for status.
- Unbounded automatic retries are a known default trap: S34 says Temporal's default model retry is unbounded. The design's retry must be explicitly bounded (for example, 2 attempts per stage, then failed_step for manual action).
- Exceptions are not the only failure: a model returning malformed JSON is a "successful" call with a bad output. The step should be marked failed on parse/validation failure too, and that failure must count toward the budget.

Concrete risk: at 300 s per call and 40 calls, a single run can take about 3.3 hours of wall-clock time (see O4). A sync HTTP request cannot survive that; the client will disconnect and the lock will be held the whole time.

### O4. Budgets (max_llm_calls 40, max_iterations 1-3, papers per iteration 3-10, no token or wall-clock budget, per-call timeout 120-300 s)

Verdict: **Partly supported.**

What is supported:
- Hard stopping conditions are a standard recommendation: S03 (Anthropic) says agents need stopping conditions such as a maximum number of iterations; S05 (Claude Code subagents) has maxTurns; S07/S11 Ralph-style loops use an iteration cap as a safety measure.
- Counting failed attempts against the budget is consistent with the "Error & Repetition Limit" pattern in S44 (Roo Code) and with S11.

What is not supported:
- No source supports the specific defaults (40 calls, 1-3 iterations, 3-10 papers). They are reasonable guesses. They should be justified by measured call counts from real runs.
- The lack of a wall-clock budget is a clear gap. Arithmetic from the user's numbers: 40 calls x 155-300 s = roughly 1.7 to 3.3 hours of model time, before retries. Retries can add more. A time budget (e.g., 30-45 min per run) is needed separately from a call budget.
- No token budget. Claude's context-management sources (S08) show token consumption as a real cost driver even if the local model is free; for Ollama the cost is latency. A token budget is still useful as a proxy for latency, but the enforceable unit here is seconds.
- The Agent SDK overview (S06) does not document a budget option, so the app must enforce budgets itself.
- Per-call timeout 120-300 s: no source gives a right value for llama3-ko on this GPU. Set timeouts from measured p95 latency, and cap total retries (S39 suggests jitter plus a cap).

### O6. Repetition guard (drop exact-duplicate queries; fallback "topic + weakness"; no stagnation detection)

Verdict: **Partly supported.**

What is supported:
- Exact-repeat detection is an established pattern: OpenHands StuckDetector (S31) flags repeated action-observation pairs; Gemini CLI as described by a third party (S32) fingerprints tool name + arguments; Roo Code (S44) counts repeated tool calls. The design's exact-string dedupe is the lightweight form of this.
- Escalation (feedback first, hard stop on second detection) is reported in S32 and is a good pattern.

What is not supported or missing:
- Exact-string dedupe misses paraphrased repeats: "graph neural networks for X" and "GNN X survey" are different strings with the same results. The sources (S31, S32) detect identical fingerprints only. A normalized comparison (lowercased, stop words removed, character n-gram Jaccard) is the minimum, still local and free.
- The fallback "topic + weakness" can itself repeat if the weakness list does not change. Nothing in the design stops that loop.
- Stagnation across iterations (the same problems returning each iteration, as the user describes) has no evidence in any source I found, neither as a pattern nor a detector. This is an open gap: a problem-set similarity check between iterations is the only available approach, and it needs its own validation. Mark this as "No evidence" for the stagnation part.

Risk: the loop can run to the call cap while producing near-identical problem sets, consuming the whole budget without new output.

### O7b. Self-critique (same model writes problems/methods/contributions and critiques them; 1-5 scores; weaknesses feed next iteration)

Verdict: **Contradicted** as an accuracy or quality mechanism when the critic is the same weak model without external checks. **Partly supported** only for narrow, checkable properties.

Evidence against:
- Intrinsic self-correction does not reliably help reasoning and sometimes lowers accuracy (S21, Huang et al.; ICLR 2024 per fetched page).
- No prior work showed successful self-correction from prompted LLM feedback alone except on tasks well suited to it (S22, Kamoi et al., TACL 2024).
- Detection is the bottleneck: LLMs often cannot find their own logical mistakes even when they can fix them when told where the error is (S23, Tyen et al.).
- Self-preference: evaluators recognize and favor their own generations, with a reported causal link to self-recognition (S27, Panickssery et al.). A model critiquing problems it wrote is exactly this setup.
- Small models: a 2026 study of 7-8B models reports self-critique did not help and 50-69% of correct answers had flawed reasoning (S41, snippet only). An ACL 2024 Findings paper says small models self-correct only with a strong verifier (S43, snippet).
- Judge reliability: models at or below 32B struggled with consistent output formatting (S42, snippet). Judge bias: position, verbosity and self-enhancement (S28).

Evidence for:
- Self-Refine reports about 20% absolute average improvement with GPT-3.5/ChatGPT/GPT-4 across seven tasks (S26), and Reflexion reports gains (S25). Both used stronger models and, in Reflexion's coding case, real test feedback. The Self-Refine tasks were largely preference-based.

Concrete risk: a 1-5 score from llama3-ko will be unstable across runs; the weaknesses it produces will steer the next iteration toward whatever it already believes, which narrows search rather than improving it. Explanations are not evidence of why a score was given (S30).

Recommendation: keep critique only as a checklist of verifiable properties (see Part 3, idea 4). Use the 1-5 scores, if kept, only as a display item, and calibrate them against the user's own labeled examples before any decision uses them.

### O8. Context packing (3 abstract sentences per paper chosen by term overlap; greedy packing into 80% of an 8,000-char budget; chat keeps last 12 messages)

Verdict: **Partly supported.**

What is supported:
- Context degradation exists even at moderate lengths, and it worsens with distractors and with low needle-question similarity (S15, Chroma; S17 snippet shows 13.9-85% drops even with perfect retrieval). Term-overlap selection is exactly the kind of low-similarity, distractor-prone retrieval that S15 penalizes.
- Position effects: S16 reports U-shaped performance; S17 says placing evidence right before the question also hurt. S15 found no notable position effect in its tests. Mixed.
- Compaction and clearing old tool results are recommended (S01, S08). Keeping the last 12 messages is a form of clearing; it is consistent with S08 but has no evidence of being optimal.
- Sub-agents returning 1-2k token summaries (S01) is a reasonable target for each evidence card.

What is not supported or missing:
- Character budgets are not token budgets. Korean text tokenizes differently from English; an 8,000-character budget may be a very different number of tokens. I did not verify tokenizer behavior for llama3-ko here; treat the budget as unmeasured.
- Term overlap for selection is weak, especially in Korean where morphology changes word forms. S15 shows the consequence: lexically similar distractors hurt more than unrelated text.
- Greedy packing of cards into 80% of budget ignores which cards matter most; no source supports the 80% figure.
- Evidence should carry IDs so claims can be traced back to the source paper and page (AGENTS.md invariant: distinguish physical PDF pages from printed labels). No source is needed for this; it is a domain rule.

Concrete risk: a bad selection step yields confident answers grounded in the wrong paper. The fix is to measure retrieval recall on a labeled set before tuning the budget.

### O12b. Claude Code as outer orchestrator (Agent Skills + MCP server; subagents for parallel profiling)

Verdict: **Supported** for the mechanism; **privacy risk** must be handled by the app.

Supported:
- Subagents run in isolated contexts and return summaries (S05, S01); per-agent tools and model selection exist (S05); concurrency and nesting limits exist (S05, default 20 concurrent, depth 3).
- Skills with progressive disclosure and bundled scripts fit a library-query workflow (S04).
- Stop hooks can keep a session going until checks pass (S07), which can enforce a verification step.
- The harness pattern (progress file, feature list with frozen acceptance flags, end-of-session commit) is documented and tested by Anthropic (S02).
- Ralph-style loops with caps and exact completion promises exist (S10, S11), with caveats about reward hacking (S10).

Risks and caveats:
- Privacy: Claude Code sends context to Anthropic's API. Reading private PDFs or notes through an MCP server and sending them into a Claude Code session is external transmission. AGENTS.md requires explicit user request and a preview of what will be sent. This must be a per-run opt-in, not a default.
- Subagent cost: subagent requests count toward the same usage limits as the main session (S05), so parallel profiling of many papers can exhaust the quota quickly.
- Self-preference: a Claude Code subagent that critiques its own output has the same bias as O7b (S27). Use a separate reviewer subagent with a checklist, and verify with deterministic checks.
- Agent SDK third-party use: API-key auth only (S06); if the app embeds the SDK, this applies.
- Subagents do not see conversation history (S05), so each subagent prompt must include the acceptance criteria and the evidence IDs explicitly.

---

## Part 3 - Better ideas

Each idea lists the change, evidence, expected benefit, cost, fit with constraints (free, no new local model downloads, privacy, single user, Korean UI), risks, and confidence.

### 1. Idempotent step cache keyed by input hash (O3 fix)
- Change: before any model call, compute key = hash(run_id, stage, prompt template version, input payload). If a done row exists, return its output. Save raw model output immediately after return, before parsing. Count failed attempts separately.
- Evidence: S34 (replayed results, at-least-once activities need idempotency); S40 (saved results keyed by idempotency key; pruning after 24 h for v1; param mismatch error); S38 (cache model calls per step).
- Expected benefit: a crash during a 155-300 s call costs one call, not a re-run plus duplicate evidence rows.
- Cost: low; one column (input_hash, raw_output) and an index.
- Fit: free, local, no new models, single user; no external service.
- Risks: stale cache if prompts change silently; include the prompt template version in the key.
- Confidence: high.

### 2. Move LLM steps to a background worker with polling, replace the global RLock with a per-run lease
- Change: POST starts a run and returns a run_id; a worker thread executes steps; the UI polls a status endpoint (or uses SSE). Replace the global RLock with a per-run lease (owner id, heartbeat timestamp, expiry). A separate Ollama semaphore (size 1) serializes model calls, because one GPU gives no parallel speedup.
- Evidence: S33 (sync vs async durability trade-offs); S35 (activities and workers, not request-bound work); S38 (background-owned runs get durable steps); S40 (concurrency: concurrent duplicate requests are not saved).
- Expected benefit: HTTP requests do not hang; other runs are not blocked behind one 300 s call; a closed browser tab does not kill the run.
- Cost: medium; threading and a status API; careful SQLite handling (one writer, WAL mode).
- Fit: free and local; still single user.
- Risks: background thread dies with the server process; resume logic must handle `running` rows on restart (lease expiry, not a blanket "failed").
- Confidence: high.

### 3. Wall-clock and token/latency budgets alongside the call budget (O4 fix)
- Change: add max_wall_seconds (for example 1,800-2,700 s per run) and per-call timeouts set from measured p95; count retries; stop with a clear status when any budget is exhausted. Record eval duration and, if the Ollama response provides it, token counts (I did not verify the field names).
- Evidence: S03 (stopping conditions); S39 (jitter and capped backoff); S34 (default unbounded retries are a trap); S44 (single limit for errors and repeats).
- Expected benefit: bounded worst-case time; no silent 3-hour runs.
- Cost: low.
- Fit: fully local.
- Risks: a wall-clock cap can end a run mid-stage; the stage must be resumable (idea 1).
- Confidence: high.

### 4. Replace self-scores with verifiable checks (O7b fix)
- Change: keep the critique step, but only as a checklist of checks the code can perform: every quoted phrase exists in the source text (exact or normalized match); every citation ID exists in the evidence set; every named method/dataset in a problem statement appears in the paper's abstract or full text; output is valid JSON with required fields; the claimed number appears in the source. Failing checks trigger one regeneration with the failure message, not a score.
- Evidence: S24 (CRITIC: external tools improve revision); S22 (external feedback is the reliable path); S23 (detection is the bottleneck; a code check localizes errors); S43 (small models need a strong verifier); S25 (Reflexion uses real test results).
- Expected benefit: removes the largest source of unreliable signal; faster; deterministic; no new model.
- Cost: medium (a few checker functions, normalization for Korean and Unicode).
- Fit: free, local, private (no data leaves the machine).
- Risks: checks catch surface errors, not wrong reasoning; they can produce false positives on paraphrased quotes; keep the checks narrow.
- Confidence: high.

### 5. Break self-preference: a different-family or human reviewer for any judgment that matters (O7b, O12b)
- Change: for any score that influences the next iteration, require either (a) a Claude Code reviewer subagent with the rubric and explicit evidence IDs, sent only with the user's explicit per-run approval and a preview of what is sent, or (b) the user as the reviewer, through a short accept/reject UI. Never let the generator score its own output.
- Evidence: S27 (self-recognition and self-preference); S28 (position, verbosity and self-enhancement bias; GPT-4 agreement with humans above 80% in chat settings only); S29 (reliability must be measured); S05 (subagent isolation).
- Expected benefit: removes self-preference; calibrates against human judgment.
- Cost: low to medium; a small label set of, for example, 30 user-judged problem statements, used to measure the critic.
- Fit: option (a) requires explicit external transmission consent per AGENTS.md; option (b) is fully local.
- Risks: user fatigue; label set must be representative.
- Confidence: medium-high.

### 6. Calibrate the critic before trusting it (O7b, O8)
- Change: create a labeled set (the user's own judgments on about 30-50 generated problem statements and evidence cards). Measure agreement, false-accept and false-reject rates for the critic. Ship the critic only if it beats a trivial baseline (always accept) on the labeled set.
- Evidence: S29 (reliability challenge); S42 (formatting failures and second-level judge weaknesses at 7B scale); S41 (self-critique hurt 7-8B in reasoning-trace study, snippet).
- Expected benefit: the app stops wasting LLM calls on a critic that does not improve outcomes.
- Cost: low (a few hours of labeling).
- Fit: local, private.
- Risks: small sample; re-run when the model or prompt changes.
- Confidence: high on the principle; medium on the numbers.

### 7. Recitation and evidence-first ordering (O8)
- Change: at the top of each generation prompt, include the selected evidence quotes with IDs, then a short restatement of the task. Before generating problems, ask the model to copy the 2-3 most relevant quotes verbatim (checkable by idea 4). Place the highest-scoring cards at the start and end of the evidence block, the middle for low-scoring cards.
- Evidence: S17 (recite evidence before solving; up to 4% on RULER for GPT-4o; snippet); S12 (recitation counters goal drift); S16 (position effects, mixed per S15).
- Expected benefit: fewer ungrounded claims; checkable quotes.
- Cost: low; prompt change.
- Fit: local.
- Risks: quotes increase prompt length; watch the character budget.
- Confidence: medium (the recitation effect is shown on other models and tasks).

### 8. Semantic stagnation check between iterations (O6 gap)
- Change: after each iteration, compare the new problem list with all earlier iterations using normalized character n-gram Jaccard (or token-level Jaccard with Korean-aware tokenization). If similarity exceeds a threshold (set by calibration, for example on the labeled set in idea 6) for two consecutive iterations, stop and report stagnation. Also stop if the new query set adds fewer than N new papers.
- Evidence: S31 and S32 (exact-repeat detection exists; their approaches are exact, so this extends them). No source directly evaluates semantic stagnation; this is an extrapolation.
- Expected benefit: stops the loop that burns the budget on the same answers; the user's described symptom.
- Cost: low; pure Python, no model.
- Fit: fully local, free.
- Risks: threshold is arbitrary until calibrated; may stop a run that is converging legitimately.
- Confidence: medium (mechanism is simple; efficacy is untested here).

### 9. Feedback first, hard stop second (O6, O4)
- Change: on the first repetition or failed check, inject a corrective message into the next step (for example, "these queries were already used; propose different angles"). On a second repetition in the same run, stop with failed_step and a human-readable reason.
- Evidence: S32 (feedback then hard stop, third-party description); S44 (repeat and error limit); S03 (stopping conditions with human checkpoints).
- Expected benefit: fewer dead runs; clearer failures.
- Cost: low.
- Fit: local.
- Risks: the injected message adds tokens each time.
- Confidence: medium (pattern documented in third-party descriptions only).

### 10. Durable run notes file and frozen acceptance list (O3, O12b)
- Change: each run writes a small progress file (or DB table) with the goal, budgets used, last completed step, open failures and decisions; the acceptance list (what counts as a valid problem statement) is written once and not editable by the model. On resume, the step re-reads the notes and re-checks the input hash before continuing.
- Evidence: S02 (progress file plus git history; feature-list JSON protected from edits; re-check basics at session start); S01 (structured note-taking outside the window); S19 (persistent memory of what worked, task-specific).
- Expected benefit: a fresh Claude Code session or a restarted server can resume without prior chat context; matches the AGENTS.md "resume without chat context" rule.
- Cost: low.
- Fit: local, private, and in line with the repo's own documentation discipline.
- Risks: duplication with the steps table; keep the notes as a derived view, not a second source of truth.
- Confidence: high.

### 11. Bounded, jittered retries with explicit classes (O3, O4)
- Change: retry only transient errors (connection reset, timeout before output, Ollama 5xx); do not retry validation failures with the same input; use at most 2 retries per stage with capped jittered backoff; a retry never repeats a stage whose output is already saved (idea 1).
- Evidence: S34 (Temporal default unbounded retry; set bounds); S39 (jitter plus cap); S40 (failed validation not saved; retryable); S38 (default 4 retries with exponential backoff, snippet only).
- Expected benefit: no runaway retries; faster recovery from one-off timeouts.
- Cost: low.
- Fit: local.
- Risks: a timeout may hide a completed-but-unsaved output (handled by idea 1).
- Confidence: high.

### 12. Claude Code orchestration as opt-in, read-only, and capped (O12b)
- Change: expose the library as a read-only MCP toolset (search, get card, get quote with page number and file hash); create a SKILL.md for drafting and a separate reviewer subagent with tools limited to the MCP read tools, maxTurns set low, effort medium; cap concurrency at 2-3 for profiling; require a per-run preview of exactly what text leaves the machine.
- Evidence: S04 (skills and bundled scripts); S05 (tools allowlist, maxTurns, concurrency limit, shared usage limits); S06 (API-key use for SDK products); AGENTS.md invariants.
- Expected benefit: parallel profiling of many papers without giving the subagent write access to the library; bounded cost.
- Cost: medium.
- Fit: privacy is the main constraint: only with explicit user request per run (AGENTS.md); the local-only path stays available.
- Risks: usage-limit burn; Claude Code session may hold private text in its transcript (check retention before use).
- Confidence: medium-high.

### 13. Use Stop hooks only with their own loop guard (O12b, S07)
- Change: if a Claude Code Stop hook re-runs a check or the pipeline, store a counter in a file and stop after N attempts; read `stop_hook_active` in the full docs before relying on it (not confirmed in fetched text).
- Evidence: S07 (exit code 2 blocks stopping; Claude cannot repair a failing Stop hook); S11 (max-iterations cap is a safety measure).
- Expected benefit: prevents an infinite stop-hook loop.
- Cost: low.
- Fit: local.
- Risks: none significant if the counter is implemented.
- Confidence: high on the need; medium on the exact field semantics.

### 14. Keep the critic output schema-constrained and short (O7b, small model)
- Change: ask the local model for a JSON list of boolean/enum checks (e.g., "claim cites an evidence ID: yes/no") rather than 1-5 scores and free-form critique; validate the JSON; retry formatting once; treat unparseable output as a failed step.
- Evidence: S42 (formatting consistency at 32B and below; second-level judging weak); S41 (self-critique unhelpful at 7-8B, snippet); S30 (explanations unreliable).
- Expected benefit: parsable, auditable output; fewer wasted tokens.
- Cost: low.
- Fit: local, no new model.
- Risks: boolean checks can still be wrong; combine with idea 4 for the checkable parts.
- Confidence: medium.

---

## Part 4 - Conflicts between sources and unverified items

### Conflicts
1. Self-correction: S26 (Self-Refine, ~20% absolute gain with GPT-3.5/ChatGPT/GPT-4 on seven tasks) and S25 (Reflexion) versus S21 (Huang et al.: intrinsic self-correction does not help reasoning) and S22 (Kamoi et al.: little evidence for prompted self-feedback except well-suited tasks). Resolution: different task types (preference and text-quality vs. verifiable reasoning), stronger models, and in Reflexion's coding case external test feedback. For EasyResearch's 8B local model on factual claims, the closer evidence is S21-S23 and S41/S43.
2. Chroma (S15): the page says "three families" but lists four vendors. Also S15 found no notable position effect, whereas S16 (Liu et al.) found a U-shape. Likely task- and model-specific.
3. Gemini CLI loop threshold: S32 (third-party crate) says 5 consecutive identical calls; the Obsidian plugin uses default 3; Gemini CLI's own number is not confirmed. Do not treat either as a Gemini CLI fact.
4. OpenHands thresholds: S31 mirrored code says four identical pairs and three error repeats; the proposed SDK PR changes grouping; merge status unknown. Thresholds may have changed.
5. Retry defaults: S38 says four retries with exponential backoff by default (snippet); S34 says Temporal's model retry default is unbounded. These are different systems; do not conflate.
6. Context editing: S08 reports +29%/+39% and -84% tokens on an internal evaluation; S09 snippets disagree with third-party trigger values. Vendor-internal; directional only.
7. Ralph mechanics: S11 (exit code 2 and re-injected prompt) versus other snippets that describe a simpler text check; the plugin source was not opened.
8. Durability default: S33 snippets say the Python default is "async"; the JS docs describe the same modes. Not confirmed on the official page.
9. Judge agreement: S28 reports GPT-4 above 80% agreement with humans in chat preference data. This does not transfer to 8B critics of scientific claims.

### Unverified items (not confirmed by an opened primary page)
- OpenHands thresholds and the condenser's attention_window default (S31).
- Gemini CLI threshold (5), and whether the user-facing setting exists (S32).
- LangGraph durability modes text and the "async" default (S33): search snippets only.
- Inngest default retries = 4 (S38): snippet only.
- Microsoft Agent Framework API details (S37): versions differ by locale.
- DBOS July 2026 packages claim (S36).
- Temporal integration claims and vendor benefits (S35).
- Dynamic Cheatsheet numbers (S19): snippet only.
- Context-length study numbers 13.9%-85% and RULER +4% (S17): snippet only.
- Small-model self-critique study numbers (S41) and judge reliability (S42): snippet only.
- Cline mistake-limit behavior (S44): release-note snippets; no official setting confirmed.
- OpenAI harness engineering content (S14): page returned 403; claims from commentary only, including the one-million-lines figure, which is unverified.
- The Claude Agent SDK budget option (S06): not found in the overview page; may exist in the full SDK reference (not read).
- The SWE-agent cost-limit default (S45): not found; the SWE-agent paper was not read (the arXiv ID I tried was the wrong paper).
- Claude Code Stop hook field `stop_hook_active` semantics (S07): not reached in the fetched text.
- Ollama token-count fields for budget accounting: not checked.
- Korean tokenization ratio for llama3-ko: not checked; O8's character budget conversion is unverified.
- Publication dates for Anthropic engineering posts (S01-S04), Chroma (S15), and Ralph (S10) were not shown in the fetched text.

---

## Part 5 - URL index

1. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
2. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
3. https://www.anthropic.com/engineering/building-effective-agents
4. https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
5. https://code.claude.com/docs/en/sub-agents
6. https://code.claude.com/docs/en/agent-sdk/overview
7. https://code.claude.com/docs/en/hooks
8. https://claude.com/blog/context-management
9. https://platform.claude.com/docs/en/build-with-claude/context-editing
10. https://ghuntley.com/ralph/
11. https://gitcode.com/2301_77165880/claude-code/tree/main/plugins/ralph-wiggum
12. https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
13. https://www.langchain.com/blog/deep-agents
14. https://openai.com/index/harness-engineering/
15. https://www.trychroma.com/research/context-rot
16. https://arxiv.org/abs/2307.03172
17. https://arxiv.org/abs/2510.05381
18. https://arxiv.org/abs/2510.04618
19. https://arxiv.org/abs/2504.07952
20. https://arxiv.org/abs/2310.08560
21. https://arxiv.org/abs/2310.01798
22. https://arxiv.org/abs/2406.01297
23. https://arxiv.org/abs/2311.08516
24. https://arxiv.org/abs/2305.11738
25. https://arxiv.org/abs/2303.11366
26. https://arxiv.org/abs/2303.17651
27. https://arxiv.org/abs/2404.13076
28. https://arxiv.org/abs/2306.05685
29. https://arxiv.org/abs/2411.15594
30. https://arxiv.org/abs/2305.04388
31. https://docs.all-hands.dev/modules/python/openhands/controller/stuck
32. https://docs.rs/crate/koda-core/0.3.2/source/src/loop_guard.rs
33. https://docs.langchain.com/oss/python/langgraph/durable-execution
34. https://pydantic.dev/docs/ai/integrations/durable_execution/temporal/index.md
35. https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai
36. https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/
37. https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints
38. https://agentkit.inngest.com/advanced-patterns/retries
39. https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
40. https://docs.stripe.com/api/idempotent_requests
41. https://arxiv.org/abs/2601.00513
42. https://arxiv.org/pdf/2603.22214
43. https://preview.aclanthology.org/moar-dois/2024.findings-acl.924
44. https://www.havoptic.com/r/cline/diff?from=4.0.8&to=4.1.25
45. https://swe-agent.com/latest/usage/cli/

Note: S46 is not used. Sources 1-45 are the complete index.
