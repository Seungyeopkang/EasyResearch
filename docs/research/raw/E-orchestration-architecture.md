# E. Orchestration architecture and multi-agent evidence

- Date of research: 2026-11-10
- Scope: orchestration design for the EasyResearch research assistant (O1, O2, O5, O7, O12), plus primary-source evidence on multi-agent systems, workflow frameworks, budget-aware agents, automated workflow search, and deep-research designs.
- Method: WebSearch to locate sources, then WebFetch on the primary page or paper. WebFetch returns a model-written extract of the page, not raw text, so claims below are extracts I checked for consistency across sources where possible. No verbatim quotes are used, because the extracts are not guaranteed to be verbatim. Where a page could not be opened, the source is tagged accordingly and no claim from it is treated as verified.
- Verification legend:
  - [V] = I opened the primary page (or its abstract/HTML) and confirmed the claim from it.
  - [S] = search-result snippet or secondary summary only.
  - [U] = could not confirm (blocked, unreadable, or not found).
- Source numbering S01 to S49 is used in all later parts. Section 5 gives the URL index.

---

## Part 1. Source records

### S01. Building effective agents
- Author/org: Anthropic (Barry Zhang, Erik Schluntz, et al. per the page; not re-verified)
- Date: 2024-12-19 (page date as extracted)
- URL: https://www.anthropic.com/research/building-effective-agents
- Tag: [V]
- Findings:
  - Separates "workflows" (fixed, developer-written control flow over LLMs and tools) from "agents" (LLM decides its own steps and tool use).
  - Names five workflow patterns: prompt chaining (trades latency for accuracy), routing, parallelization (sectioning or voting, aggregated in code), orchestrator-workers, and evaluator-optimizer.
  - Advises starting with the simplest solution, often a single optimized LLM call, and adding agentic complexity only when needed.
  - Workflows fit well-defined tasks needing predictability; agents fit open-ended tasks where step count cannot be predicted.
  - States that agentic systems often trade latency and cost for performance, and that autonomy raises the risk of compounding errors.
- Relevance to EasyResearch: Directly supports O1. The fixed stage order with code-controlled flow is the "workflow" pattern the page recommends for a well-defined pipeline.

### S02. How we built our multi-agent research system
- Author/org: Anthropic Engineering
- Date: 2025-06-13
- URL: https://www.anthropic.com/engineering/multi-agent-research-system
- Tag: [V]
- Findings:
  - Orchestrator-worker design: a lead agent (Claude Opus 4 per the page) plans, spawns subagents (Claude Sonnet 4) that search in parallel, and synthesizes results. Lead saves its plan to memory because context beyond 200,000 tokens is truncated.
  - A separate CitationAgent attaches claims to sources after the report is drafted.
  - Effort scaling is embedded in prompts: simple fact-finding uses 1 agent with 3 to 10 tool calls; direct comparisons use 2 to 4 subagents with 10 to 15 calls each; complex research uses more than 10 subagents.
  - Token cost: agents use about 4x chat tokens; multi-agent systems about 15x. Token usage explained about 80% of variance on BrowseComp (per the page).
  - Lead Opus with Sonnet subagents beat single-agent Opus 4 by 90.2% on the internal research eval. Parallelization cut research time by up to 90% on complex queries.
  - Poor-fit cases stated by the page: tasks needing shared context or many inter-agent dependencies; the lead cannot steer subagents mid-task; errors compound; debugging is harder.
- Relevance to EasyResearch: The result supports breadth-first retrieval with subagents, but the poor-fit list describes O2's dependency chain (problems to methods to contributions). The cost multiple is a warning for any LLM-heavy critique loop on a local 8B model.

### S03. Writing effective tools for agents
- Author/org: Anthropic Engineering
- Date: 2025-09-11
- URL: https://www.anthropic.com/engineering/writing-tools-for-agents
- Tag: [V]
- Findings:
  - Prefer a few purpose-built tools over thin wrappers around every endpoint; consolidate multi-step operations into one call.
  - Namespace tools by service and resource; test prefix versus suffix, since the best choice varies by model.
  - Return high-signal, human-readable context; offer concise and detailed response modes. A concise response was 72 tokens versus 206 for detailed (about one-third).
  - Error messages should say what went wrong and how to fix it, with a correctly formatted example.
  - Build realistic multi-step evaluation tasks with verifiable outcomes, track tokens, calls, and errors, and hold out a test set.
- Relevance to EasyResearch: Guides the design of the MCP read tools and error messages in O12, and suggests an evaluation harness with held-out topics for the research loop.

### S04. Effective context engineering for AI agents
- Author/org: Anthropic Engineering
- Date: 2025-09-29
- URL: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Tag: [V]
- Findings:
  - Principle: keep the smallest set of high-signal tokens that makes the desired outcome likely.
  - Recommends just-in-time retrieval (keep references and load content on demand) and compaction when a context nears its limit.
  - Structured note-taking outside the context window supports multi-step progress.
  - Sub-agents return condensed summaries (often about 1,000 to 2,000 tokens) even when exploring with tens of thousands of tokens.
  - Recommends choosing between compaction, note-taking, and multi-agent setups based on the task shape.
- Relevance to EasyResearch: Supports keeping the shared state compact in prompts (O2). A local 8B model has a small effective context, so passing a compacted state summary rather than full JSON matters.

### S05. Equipping agents for the real world with Agent Skills
- Author/org: Anthropic Engineering
- Date: 2025-10-16
- URL: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Tag: [V]
- Findings:
  - A skill is a directory with a SKILL.md file; YAML frontmatter requires name and description.
  - Progressive disclosure: metadata loads at startup, full SKILL.md when relevant, bundled files only when needed.
  - The name and description drive whether a skill triggers, so they need iteration.
  - Security: malicious skills can exfiltrate data or take unintended actions; install only trusted skills and audit bundled scripts and external network calls for less-trusted ones.
- Relevance to EasyResearch: Supports O12's four SKILL.md files. The trigger-description sensitivity and the audit note apply directly to the skills the app ships.

### S06. Don't build multi-agents
- Author/org: Cognition (Walden Yan)
- Date: 2025-06-12
- URL: https://cognition.com/blog/dont-build-multi-agents (redirect from cognition.ai)
- Tag: [V]
- Findings:
  - Two principles: agents should share context, including full traces rather than single messages; and actions carry implicit decisions that conflict when subagents act in parallel.
  - Example: two subagents building a Flappy Bird clone made mismatched style and physics assumptions. Sharing context alone still produced visual mismatch because assumptions were never set up front.
  - Recommends a single-threaded linear agent. For overflowing context, add a separate model that compresses history into decisions and events.
  - Advises against multi-agent architectures in 2025 as fragile.
- Relevance to EasyResearch: Supports O2 (one shared state, no subagents inside the app). The "implicit decisions" principle is a warning for parallel stages that write to the same state, such as parallel contribution drafts.

### S07. Multi-agents: what's actually working
- Author/org: Cognition (Walden Yan), per secondary coverage
- Date: 2026-04-22 (per a secondary summary)
- URL: https://cognition.com/blog/multi-agents-whats-actually-working (not opened; the redirect target was not fetched successfully in this session)
- Tag: [S]
- Findings (secondary summaries only):
  - Keeps objections to parallel agents writing code at once; endorses a pattern where extra agents contribute analysis while only one agent writes.
  - Describes hierarchical manager agents that spawn child agents, with context transfer still unsolved.
  - A ZenML summary reports that a review agent catches about 2 bugs per PR, 58% of them severe. Not verified against the source.
- Relevance to EasyResearch: The "many analysts, one writer" pattern maps to critique and review stages that read state but do not write it. Treat as a hypothesis until the primary post is read.

### S08. Towards a science of scaling agent systems: When and why agent systems work
- Author/org: Google Research (with Google DeepMind and MIT authors per secondary sources)
- Date: 2026-01-28
- URL: https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/
- Tag: [V]
- Findings:
  - Evaluates 180 agent configurations across four benchmarks (Finance-Agent, BrowseComp-Plus, PlanCraft, Workbench); five architectures: single agent, and independent, centralized, decentralized, and hybrid multi-agent.
  - Independent multi-agent systems amplify errors up to 17.2x; centralized systems limit amplification to 4.4x (orchestrator acts as a validation bottleneck).
  - Parallelizable task (Finance-Agent): centralized coordination improved performance by 80.9% over a single agent.
  - Sequential task (PlanCraft): every multi-agent variant degraded performance by 39 to 70%.
  - Coordination overhead grows with tool count (example given: 16 or more tools), without a specific percentage in the blog.
  - Predictive model picks the best architecture for 87% of unseen configurations (R-squared 0.513 per the blog text).
- Relevance to EasyResearch: Strongest quantitative evidence for O2. EasyResearch's stage chain is sequential and dependent, which is the regime where the blog reports multi-agent degradation. Centralized control (code orchestrator) is the less harmful multi-agent form if one is ever added.

### S09. Towards a Science of Scaling Agent Systems (arXiv 2512.08296)
- Author/org: Google Research / Google DeepMind / MIT (per secondary sources)
- Date: 2025-12-09 (v1 per the abstract page)
- URL: https://arxiv.org/abs/2512.08296
- Tag: [V] (metadata and abstract only)
- Findings:
  - The abstract page reports 260 agent configurations across six agentic benchmarks.
  - Cross-validated R-squared for the predictive model: 0.373 across all six benchmarks, rising to 0.413 with a task-grounded capability metric.
  - PlanCraft, Finance-Agent, and error amplification figures were not in the extract I received, so I did not confirm them here.
- Relevance to EasyResearch: Confirms the paper exists and is the same study as S08, but its configuration count and fit statistics differ from the blog (see Part 4). Cite the blog numbers only with the caveat.

### S10. Why Do Multi-Agent LLM Systems Fail? (MAST)
- Author/org: Cemri et al. (Berkeley and collaborators)
- Date: v1 2025-03-17; v3 2025-10-26
- URL: https://arxiv.org/abs/2503.13657
- Tag: [V]
- Findings:
  - Taxonomy with 3 categories and 14 failure modes: system design issues (FM-1.1 to 1.5, including disobeying task or role specification, step repetition, loss of conversation history, unaware of termination conditions); inter-agent misalignment (FM-2.1 to 2.6, including ignored other agent's input, information withholding, reasoning-action mismatch); task verification (FM-3.1 to 3.3, including premature termination and incomplete or incorrect verification).
  - More than 1,600 annotated traces; expert analysis of 150 traces built the taxonomy. Reported human kappa 0.88.
  - Seven frameworks in MAST-Data: MetaGPT, ChatDev, HyperAgent, AppWorld, AG2 (MathChat), Magentic-One, OpenManus.
  - Fix experiments: improving ChatDev role specifications and a CEO final-say workflow each +9.4% task success; adding a task-objective verification step +15.6% on ProgramDev. The authors say tactical fixes were inconsistent and task completion stayed low.
- Relevance to EasyResearch: Gives a failure checklist for O1, O2, O5: step repetition and premature termination map to the loop caps; "ignored input" and "information withholding" map to shared-state handling; verification gaps map to the critique stage.

### S11. Magentic-One: A Generalist Multi-Agent System for Solving Complex Tasks
- Author/org: Fourney et al. (Microsoft Research)
- Date: 2024-11-07 (v1)
- URL: https://arxiv.org/abs/2411.04468 and https://arxiv.org/html/2411.04468v1
- Tag: [V]
- Findings:
  - Orchestrator maintains a task ledger (facts, guesses, plan; updated in an outer loop) and a progress ledger (updated each inner-loop step, answering: complete, looping, making progress, next speaker, next instruction).
  - Stall counter increments on loops or lack of progress. With threshold 2 (paper setting), the orchestrator re-plans after the counter exceeds the threshold.
  - Specialized agents: WebSurfer, FileSurfer, Coder, ComputerTerminal.
  - GAIA: 38.00% (Magentic-One, GPT-4o and o1) versus 32.33% for GPT-4o alone. WebArena: 32.8% on all 812 tasks. AssistantBench: 27.7% accuracy with GPT-4o and o1.
- Relevance to EasyResearch: Gives a concrete bounded-replan mechanism (stall counter plus re-plan) that fits a loop that re-runs stages only when a stage's output fails a check. Also a source for the O1-to-O2 comparison: Magentic-One is multi-agent but orchestrator-centralized.

### S12. LLMs Can't Plan, But Can Help Planning in LLM-Modulo Frameworks
- Author/org: Kambhampati et al.
- Date: 2024-02-02 (v1); v3 2024-06-12
- URL: https://arxiv.org/abs/2402.01817
- Tag: [V] (abstract and intro only)
- Findings:
  - Autoregressive LLMs cannot on their own do planning or self-verification.
  - Both over-optimistic claims (LLMs can plan with prompting) and over-pessimistic claims (LLMs only translate formats) are judged misguided.
  - Proposes LLMs paired with external model-based verifiers in a bi-directional loop.
  - Verifier models can themselves be acquired with LLM help.
- Relevance to EasyResearch: Supports the O1 design that code, not the LLM, controls flow and validates output. Also undercuts any claim that the LLM critique alone verifies a plan. The rule-based checks in the screen and validation stages are the "external verifiers" here.

### S13. STORM: Writing Wikipedia-Like Articles From Scratch
- Author/org: Shao et al. (Stanford)
- Date: 2024-02-22 (v1); v2 2024-04-08
- URL: https://arxiv.org/abs/2402.14207
- Tag: [V]
- Findings:
  - Pipeline: perspective discovery, simulated conversations between writers with different perspectives and a topic expert grounded in internet sources, then outline generation.
  - Evaluated on FreshWiki. Against an outline-driven RAG baseline, STORM articles were judged better organized (25% absolute increase) and broader in coverage (10%).
  - Expert feedback flagged source-bias transfer and over-association of unrelated facts.
- Relevance to EasyResearch: The perspective-question step is a candidate for query planning (plan_queries) in O1, and the failure notes warn that retrieval bias carries into outlines.

### S14. Co-STORM: Collaborative STORM
- Author/org: Jiang et al. (Stanford)
- Date: 2024-08-27 (v1); v2 2024-10-17
- URL: https://arxiv.org/abs/2408.15232
- Tag: [V]
- Findings:
  - Users observe a discussion among several LM agents and can steer it; agents ask questions on the user's behalf and information is organized in a dynamic mind map.
  - Outperforms baselines on discourse trace and report quality (WildSeek dataset).
  - Human study: 70% of participants preferred Co-STORM over a search engine, 78% over a RAG chatbot.
  - The page does not describe a moderator agent or turn-taking mechanics in detail.
- Relevance to EasyResearch: Supports the human-in-the-loop idea behind O5, where the user steers the next iteration. The mind-map idea could show the user the evolving problem/method/contribution state at the review gate.

### S15. Should we be going MAD? A Look at Multi-Agent Debate Strategies for LLMs
- Author/org: Smit et al. (ICML 2024)
- Date: 2023-11 (arXiv); ICML 2024
- URL: https://arxiv.org/abs/2311.17371
- Tag: [S] (search results and summaries only; abstract not opened)
- Findings (from snippets):
  - Benchmarks MAD against other prompting strategies; finds current MAD does not reliably outperform them.
  - Argues sensitivity to hyperparameters and protocol tuning, and reports that an agreement-modulating variant performed best among tested protocols.
- Relevance to EasyResearch: Argues against using debate as the default critique mechanism. Low cost to follow up.

### S16. Stop Overvaluing Multi-Agent Debate
- Author/org: Zhang et al.
- Date: 2025-02-12 (v1); v3 2025-06-21
- URL: https://arxiv.org/abs/2502.08788
- Tag: [V]
- Findings:
  - Systematic evaluation of 5 MAD methods; MAD often fails to beat single-agent baselines such as Chain-of-Thought and Self-Consistency, despite more inference compute.
  - Argues for better benchmark coverage, stronger baselines, and consistent setups; reports 9 benchmarks (not named in the extract).
  - Reports that model heterogeneity consistently improves MAD frameworks (the paper's phrase for it: a universal antidote). No specific numbers were in the extract.
- Relevance to EasyResearch: If any multi-agent critique is considered, it must beat single-call and self-consistency baselines at equal cost. Heterogeneous models are not available on a single local GPU without new downloads, which the user excludes.

### S17. Debate or Vote: Which Yields Better Decisions in Multi-Agent LLMs?
- Author/org: Choi, Zhu, Li
- Date: 2025-08-24 (v1); revised 2025-10; NeurIPS 2025 poster
- URL: https://arxiv.org/abs/2508.17536 (also https://arxiv.org/html/2508.17536v2)
- Tag: [S] (search snippets and conference listing; paper not opened)
- Findings (from snippets):
  - Splits MAD into majority voting and inter-agent debate; across seven NLP benchmarks, voting accounts for most of the gains attributed to debate.
  - Models debate as a martingale over agent beliefs and argues debate alone does not raise expected correctness.
  - Suggests simple ensembling remains a strong alternative.
- Relevance to EasyResearch: If a self-consistency style check is wanted for the critique stage, voting over several independent samples is the cheaper and better-supported option than debate rounds. Costs more LLM calls, which matters on a local 8B model.

### S18. AFlow: Automating Agentic Workflow Generation
- Author/org: Zhang et al. (MetaGPT group)
- Date: 2024-10-14 (v1); v4 2025-04-15
- URL: https://arxiv.org/abs/2410.10762
- Tag: [V] (abstract)
- Findings:
  - Treats workflow design as search over code-represented workflows (nodes invoking LLMs, edges), using Monte Carlo Tree Search with code modification, tree-structured experience, and execution feedback.
  - Abstract reports 5.7% average improvement over state-of-the-art baselines across six datasets (datasets not named in the extract).
  - Smaller models with the optimized workflow reportedly match or beat GPT-4o on some tasks at 4.55% of its inference cost.
  - Search cost and runtime were not in the extract.
- Relevance to EasyResearch: Automated workflow search is not justified for a single-user app with a fixed pipeline. The 5.7% gain is modest and the search cost is unreported. Useful only as a later offline tuning method for prompts, not a runtime design.

### S19. Automated Design of Agentic Systems (ADAS / Meta Agent Search)
- Author/org: Hu, Lu, Clune et al.
- Date: 2024-08-15 (v1); v2 2025-03-02
- URL: https://arxiv.org/abs/2408.08435
- Tag: [V] (abstract)
- Findings:
  - A meta agent writes new agents as code, drawing on an archive of earlier designs.
  - Abstract claims discovered agents "greatly outperform" hand-designed agents on coding, science, and math; transfer across domains and models is claimed.
  - No benchmark numbers or search cost in the extract.
- Relevance to EasyResearch: Same as S18: an offline research idea, not a runtime structure. The absence of cost numbers in the extract is a gap.

### S20. MaAS: Multi-agent Architecture Search via Agentic Supernet
- Author/org: Zhang et al.
- Date: 2025-02-06 (v1); v2 2025-06-09
- URL: https://arxiv.org/abs/2502.04180
- Tag: [V] (abstract)
- Findings:
  - Optimizes a distribution (agentic supernet) of architectures and samples a query-dependent system per input, allocating LLM and tool calls.
  - Abstract claims use of about 6% to 45% of the inference cost of prior handcrafted or automated systems, with 0.54% to 11.82% better performance across six benchmarks (not named in the extract).
  - Claims cross-dataset and cross-backbone transfer.
- Relevance to EasyResearch: The query-dependent idea (only spend calls where a query needs them) is the useful part. A full supernet is out of scope; a rule-based version (skip the critique or extra queries when screening yields enough papers) captures the spirit.

### S21. Budget-Aware Tool-Use Enables Effective Agent Scaling (BATS)
- Author/org: UC Santa Barbara, Google, NYU researchers (per the hyper.ai summary in search)
- Date: [U] (not confirmed in the page I opened)
- URL: https://arxiv.org/html/2511.17006v1
- Tag: [V] (HTML version opened)
- Findings:
  - Budget Tracker: a prompt-level plug-in that appends used and remaining calls per tool after each tool response; no training. Budgets are counted in tool calls (100 per tool by default). Tokens are folded into a unified cost (a flat $0.001 per call in the paper).
  - ReAct plateaus around 100 calls because the agent stops early. Budget Tracker improves beyond that under sequential scaling.
  - Table 1 (Budget Tracker vs ReAct, BrowseComp): Gemini-2.5-Pro 12.6 to 14.6; Gemini-2.5-Flash 9.7 to 10.7; Claude-Sonnet-4 12.2 to 14.0.
  - BATS (budget-aware planning plus self-verification with early stopping), BrowseComp: Gemini-2.5-Pro 24.6, Claude-Sonnet-4 19.1, Gemini-2.5-Flash 14.3 (vs ReAct 12.6, 12.2, 9.7).
  - The paper's own browse-call reduction figure (21.4%) does not match my recalculation from the table (about 20%); treat the exact figure as unverified.
- Relevance to EasyResearch: The budget-status idea can be implemented in code (count OpenAlex calls and LLM calls per run and inject remaining budget). The gains are for browsing agents with frontier models and do not show that an 8B local model benefits.

### S22. LangGraph: Interrupts (human-in-the-loop)
- Author/org: LangChain
- Date: [U] (undated in extract)
- URL: https://docs.langchain.com/oss/python/langgraph/interrupts
- Tag: [V]
- Findings:
  - interrupt() saves state through a checkpointer and pauses; the value is returned to the caller. Resume with Command(resume=...) on the same thread_id.
  - Important caveat: on resume, the node restarts from its beginning, so code before interrupt() runs again. Work before an interrupt must be idempotent; non-idempotent actions go after the interrupt or into a separate node.
  - Do not wrap interrupt() in a bare try/except, because the pause is implemented as an exception.
  - Multiple interrupts in one node are matched to resume values by position.
- Relevance to EasyResearch: O5's awaiting_review gate can be built this way, but the stage before the gate must be idempotent. Saving to the project must happen after the gate.

### S23. LangGraph: Persistence and checkpointers
- Author/org: LangChain
- Date: [U]
- URL: https://docs.langchain.com/oss/python/langgraph/persistence
- Tag: [V]
- Findings:
  - Checkpointers persist a thread's graph state; threads are linked by thread_id. Supports short-term memory, human-in-the-loop, time travel, and fault tolerance.
  - In-memory savers are lost on restart; SqliteSaver is named for local development; Postgres savers for production.
  - Checkpoints accumulate over long conversations and need pruning or retention.
- Relevance to EasyResearch: The SQLite-backed state object in O2 has the same role as a SqliteSaver checkpoint. Retention matters for the user's private data; keep it in the existing local store and do not copy it into logs.

### S24. LangGraph: Workflows and agents
- Author/org: LangChain
- Date: [U]
- URL: https://docs.langchain.com/oss/python/langgraph/workflows-agents
- Tag: [V]
- Findings:
  - Lists prompt chaining, parallelization, routing, orchestrator-worker (using Send), and evaluator-optimizer, plus a tool-using agent loop that decides which tools to call.
  - Notes that a human can serve as the evaluator in evaluator-optimizer.
  - Plan-and-execute and supervisor patterns are not described on this page.
- Relevance to EasyResearch: Confirms O1's stage design maps to standard named patterns (prompt chaining with code gates plus an evaluator loop).

### S25. A practical guide to building agents (OpenAI)
- Author/org: OpenAI
- Date: [U] (2025 per secondary coverage)
- URL: https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- Tag: [S] (direct PDF unreadable in this session; content from secondary search summaries)
- Findings (secondary):
  - Describes a manager pattern (a central LLM calls specialist agents as tools, keeping one user-facing interface) and a decentralized pattern (peer agents transfer control by handoff).
  - Describes layered guardrails (relevance and safety classifiers, PII filters, moderation) and human intervention for high-risk actions or repeated failure.
- Relevance to EasyResearch: Background for O12 and O5; treat as unverified until the PDF can be read.

### S26. OpenAI Agents SDK: Handoffs
- Author/org: OpenAI
- Date: [U]
- URL: https://openai.github.io/openai-agents-python/handoffs/
- Tag: [V]
- Findings:
  - A handoff transfers the conversation to another agent (exposed to the model as a tool) and stays within one run; the receiver sees history unless an input filter changes it.
  - Agent.as_tool() is recommended when a nested specialist should answer without taking over the conversation.
  - Handoff input filters, and an opt-in beta for nested history that does not redact sensitive data.
- Relevance to EasyResearch: The distinction helps frame O2: EasyResearch should not use handoffs, because one shared state object is the design. If a helper agent is ever used, Agent.as_tool with structured output is the closer fit.

### S27. OpenAI Agents SDK: Guardrails
- Author/org: OpenAI
- Date: [U]
- URL: https://openai.github.io/openai-agents-python/guardrails/
- Tag: [V]
- Findings:
  - Input guardrails run only on the first agent; the default parallel mode can let the agent consume tokens or call tools before a tripwire cancels it. Blocking mode finishes before the agent starts.
  - Output guardrails run after completion, only on the last agent; a rejected output is not persisted.
  - Tool guardrails wrap function tools per invocation; they do not cover handoffs or Agent.as_tool.
  - A guardrail function that raises is treated as an unknown verdict, not a rejection.
- Relevance to EasyResearch: For the screen and validation stages, the equivalent is blocking, code-level validation before the next LLM call. Parallel validation risks wasted local GPU time.

### S28. OpenAI Agents SDK: Human-in-the-loop (tool approval)
- Author/org: OpenAI
- Date: [U]
- URL: https://openai.github.io/openai-agents-python/human_in_the_loop/
- Tag: [V]
- Findings:
  - Approval can be static or a callable per call. The run pauses and returns interruptions; state is serialized with to_json and resumed with Runner.run.
  - Approvals are not exactly-once: side-effecting tools need stable idempotency keys and reconciliation.
  - Approval decisions should be authenticated on the server and checked against stored pending items to block replay.
  - Serialized state contains arguments and context and should be treated as sensitive.
- Relevance to EasyResearch: Directly applies to O5's "save to project" action: make it an explicit, idempotent action with a stored pending item, and keep the serialized state in the private store.

### S29. 12-Factor Agents
- Author/org: HumanLayer (Dex Horthy et al.)
- Date: [U]
- URL: https://github.com/humanlayer/12-factor-agents
- Tag: [V] (factor titles only; per-factor text lives in linked files that I did not open)
- Findings:
  - Factor titles include: own your prompts; own your context window; tools are structured outputs; unify execution and business state; launch, pause, and resume with simple APIs; contact humans with tool calls; own your control flow; compact errors into the context window; small focused agents; make the agent a stateless reducer.
  - Thesis: good agents are mostly software, not a prompt-and-tools loop.
- Relevance to EasyResearch: Supports O1 (own control flow) and O2 (unify execution and business state, stateless reducer over the shared object). Per-factor claims are [U] and should be read from the linked files before citing specifics.

### S30. ADK workflow agents (Sequential, Parallel, Loop)
- Author/org: Google (Agent Development Kit)
- Date: [U] (ADK 2.0 note present)
- URL: https://adk.dev/agents/workflow-agents/ (redirect from google.github.io/adk-docs)
- Tag: [V]
- Findings:
  - SequentialAgent runs sub-agents in order; ParallelAgent runs them concurrently; LoopAgent repeats until a termination condition (types and max-iterations not stated in the extract).
  - Template workflow agents are deterministic and do not use an LLM to orchestrate; from ADK 2.0 (Python and Go), graph-based and dynamic workflows supersede them.
- Relevance to EasyResearch: Confirms that a deterministic code pipeline (O1) is a first-class pattern, and that the framework is moving toward graph-based workflows. Not a dependency to adopt.

### S31. ADK multi-agent systems
- Author/org: Google (ADK)
- Date: [U]
- URL: https://google.github.io/adk-docs/agents/multi-agents (redirect to adk.dev/agents/multi-agents; page returned 404 or redirect in this session)
- Tag: [S] (search snippet only)
- Findings (snippet):
  - output_key stores a sub-agent's output in session state; parallel branches share session.state, so each should use distinct keys to avoid race conditions.
  - LoopAgent is commonly capped with max_iterations and early exit via escalate.
- Relevance to EasyResearch: The "distinct keys for parallel writers" rule is the same lesson as S06. Verify before relying on it.

### S32. Microsoft Agent Framework: Workflow capabilities
- Author/org: Microsoft
- Date: ms.date 2026-07-29 (page metadata)
- URL: https://learn.microsoft.com/en-us/agent-framework/workflows/
- Tag: [V]
- Findings:
  - Workflow capabilities include agents in workflows, declarative workflows, human-in-the-loop (pause for external input and resume), checkpoints and resuming, observability, and visualization.
  - Multi-agent orchestrations include sequential, concurrent, handoff, group-chat, and Magentic patterns.
- Relevance to EasyResearch: Confirms that checkpoint plus human-in-the-loop is the enterprise standard shape for O5. No reason to adopt the framework for a single-user app.

### S33. Microsoft Agent Framework: Checkpoints
- Author/org: Microsoft
- Date: updated 2026-11-01 (page metadata)
- URL: https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints
- Tag: [V]
- Findings:
  - Checkpoints are created at the end of each superstep (after all executors finish) and capture executor state, pending messages, pending requests and responses, and shared state.
  - Storage options: in-memory, local file, Cosmos DB; the same checkpoint interface across them.
  - Security: treat checkpoint storage as trusted; never load checkpoints from untrusted sources; pickle-based restricted unpickler.
  - Executors that hold state must save and restore it explicitly.
- Relevance to EasyResearch: Supports saving state at each stage boundary (not only at the review gate) and treating the SQLite state as trusted local data. Restore must rebuild the same stage identities.

### S34. CrewAI Flows
- Author/org: CrewAI
- Date: [U]
- URL: https://docs.crewai.com/en/concepts/flows
- Tag: [V]
- Findings:
  - Flows are event-driven and coordinate Crews; they manage shared state, branch, and loop. Single Agents can attach to Flow steps.
  - State can be unstructured (dict-like) or structured (Pydantic BaseModel), with a UUID id.
  - @persist saves state to SQLite by default; runs can be resumed by id or forked from a saved state.
  - @human_feedback pauses for input; with emit outcomes, an LLM can map free-form feedback to a branch (requires CrewAI 1.8.0 or later).
- Relevance to EasyResearch: The structured state with SQLite persistence and resume-by-id is nearly the O2 design. The LLM-mapped feedback branch would be a risk for O5 because it lets an LLM choose the next step; prefer explicit user choice.

### S35. smolagents: CodeAgent vs ToolCallingAgent
- Author/org: Hugging Face
- Date: 2024-12-31
- URL: https://huggingface.co/blog/smolagents
- Tag: [V]
- Findings:
  - CodeAgent writes actions as code; ToolCallingAgent writes JSON/text tool calls.
  - Argues code actions are more composable and better represented in training data; cites research that tool-calling LLMs do better with code. No benchmark numbers in the text.
  - The "fewer LLM steps" claim is not made by this page.
- Relevance to EasyResearch: Code-as-action is not a fit for a local 8B model, which is weak at code generation and would widen the attack surface. Keep the code-controlled loop instead.

### S36. Open Deep Research (Hugging Face)
- Author/org: Hugging Face
- Date: 2025-02-04
- URL: https://huggingface.co/blog/open-deep-research
- Tag: [V]
- Findings:
  - Open reproduction built on smolagents with a CodeAgent and a text-based browser (adapted from Magentic-One) plus a text inspector.
  - CodeAct rationale: code actions are more concise than JSON; the cited paper reports about 30% fewer steps and the authors connect that to about 30% lower run cost.
  - GAIA validation: open reproduction 55.15%; OpenAI Deep Research 67.36% (as reported in the post); Magentic-One about 46%; switching from code to JSON actions dropped the reproduction to about 33% on average.
- Relevance to EasyResearch: Shows a real-world reliance on code actions for search agents with frontier models. The JSON-action drop is a caution that action format changes results a lot, which matters for any local-model migration.

### S37. open_deep_research (LangChain)
- Author/org: LangChain
- Date: [U] (August 2025 update mentioned on the page)
- URL: https://github.com/langchain-ai/open_deep_research
- Tag: [V]
- Findings:
  - Current pipeline as described: four configurable model roles (summarization, research, compression, final report) set through init_chat_model; Tavily search by default with MCP and native search options.
  - Reported Deep Research Bench results: RACE 0.4943 (GPT-5 config, about 204.6M tokens), 0.4309 (defaults, about $45.98), 0.4401 (Claude Sonnet 4 config, about $187.09), 0.4344 (leaderboard submission, about $87.83). The RACE judge is an LLM (Gemini) against expert reports.
  - The legacy variants section mentions a plan-and-execute with human-in-the-loop planning and a supervisor-researcher multi-agent design, and says the current version outperforms both.
  - The page does not describe a scoping stage, a research brief, or current supervisor/researcher subagents; the premise that it uses supervisor plus researcher subagents with compression could not be confirmed from this page.
- Relevance to EasyResearch: The compression role and the per-role model configuration are good ideas. The cost table (up to about $187 per benchmark run) shows why per-run budgets are needed even for a local app; the local equivalent is time, not money.

### S38. GPT-Researcher
- Author/org: Assaf Elovic et al. (open source)
- Date: [U]
- URL: https://github.com/assafelovic/gpt-researcher
- Tag: [V]
- Findings:
  - Planner agent breaks a task into research questions; execution agents gather information in parallel; each source is summarized and source-tracked; a publisher aggregates into the report. Built with LangGraph and AG2 (per the page).
  - Context filter before the LLM sees content (default Jev with BM25 fallback, embeddings optional, or none).
  - Self-reported on 28 tasks: relevance of kept passages 73% (Jev) versus 46% (embeddings); cost per report $0.115 (Jev), $0.117 (embeddings), $0.192 (no filter). Deep research about 5 minutes and about $0.40 per run (o3-mini). These are project-reported and unverified.
- Relevance to EasyResearch: The context filter is the most transferable idea: a deterministic relevance filter before the LLM reduces prompt size on a small local model. Use BM25-like lexical scoring, which matches O1's lexical screen.

### S39. Introducing deep research (OpenAI)
- Author/org: OpenAI
- Date: [U]
- URL: https://openai.com/index/introducing-deep-research/
- Tag: [U] (HTTP 403; not read)
- Findings: none verified. A number (67.36% GAIA validation) appears in S36 as attributed to OpenAI; it is not checked here.
- Relevance to EasyResearch: Background only.

### S40. Deep research system card (OpenAI)
- Author/org: OpenAI
- Date: [U]
- URL: https://cdn.openai.com/deep-research-system-card.pdf
- Tag: [U] (PDF unreadable in this session)
- Findings: none verified.
- Relevance to EasyResearch: Background for safety notes on browsing agents; not used in verdicts.

### S41. Gemini Deep Research
- Author/org: Google
- Date: 2024-12-11
- URL: https://blog.google/products/gemini/google-gemini-deep-research/
- Tag: [V]
- Findings:
  - Creates a multi-step research plan the user can revise or approve before searching.
  - Then searches, reads, and iterates several times; output is a report with source links; follow-up questions and refinements allowed.
  - No benchmark figures in the post.
- Relevance to EasyResearch: The plan-approval gate is a cheap way to strengthen O5 (approve or edit the queries before OpenAlex is called). Strong fit with the single-user, review-first design.

### S42. Benchmarking multi-agent architectures
- Author/org: LangChain
- Date: 2025-06-10
- URL: https://www.langchain.com/blog/benchmarking-multi-agent-architectures
- Tag: [V]
- Findings:
  - Compares single agent, swarm (sub-agents hand off to each other and reply to the user), and supervisor (central agent delegates; only the supervisor replies).
  - Single agent falls off sharply with two or more distractor domains; with one distractor it was slightly better than multi-agent.
  - Swarm scored slightly higher than supervisor; the author attributes this to a translation step in the supervisor. A supervisor fix (removing handoff messages, a message-forwarding tool) reportedly gave a nearly 50% gain on this benchmark.
  - Token use: single agent grows with distractors; swarm and supervisor stay roughly flat; supervisor uses more than swarm.
- Relevance to EasyResearch: Multi-agent helps when one agent must juggle unrelated domains. EasyResearch is single-topic per run, so the single-agent-plus-tools baseline should be the comparator. Also warns about translation overhead when a central agent relays messages.

### S43. Claude Code subagents
- Author/org: Anthropic (Claude Code docs)
- Date: [U] (current docs)
- URL: https://code.claude.com/docs/en/sub-agents
- Tag: [V]
- Findings:
  - Each subagent has its own context window and custom system prompt; returns a summary to the parent, keeping verbose output out of the main conversation.
  - Tool allowlist or denylist per subagent; AskUserQuestion is removed from subagents.
  - Nesting is allowed by default up to three layers below the main conversation (controlled by an environment variable; a value of 1 disables nesting). This contradicts the common assumption that subagents cannot spawn subagents.
  - Defaults: up to 20 concurrent subagents; each subagent consumes its own usage; CLAUDE.md and git status are loaded at startup.
- Relevance to EasyResearch: Supports using Claude Code as an outer orchestrator for read-only review tasks. The cost is per-subagent usage, and any content the subagent reads is sent to the model provider, which matters for private research data (see O12 risks).

### S44. MCP specification: Tools
- Author/org: Model Context Protocol (spec version 2025-06-18)
- Date: 2025-06-18 (spec version)
- URL: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- Tag: [V]
- Findings:
  - Tools have name, title, description, inputSchema, optional outputSchema, and annotations. Clients must treat annotations as untrusted unless from a trusted server.
  - Strong guidance that a human should be in the loop with the ability to deny tool invocations; clients should confirm sensitive operations and show inputs before calling.
  - Errors are either protocol errors or tool results with isError true; the second is what the model should see and fix.
  - Servers must validate inputs, enforce access controls, rate-limit, and sanitize outputs.
- Relevance to EasyResearch: Directly supports O12: draft-only write tools that require approval, server-side validation, and isError results with corrective text.

### S45. Scaling LLM test-time compute optimally can be more effective than scaling model parameters
- Author/org: Snell, Lee, Xu, Kumar
- Date: 2024-08-06 (v1)
- URL: https://arxiv.org/abs/2408.03314
- Tag: [V]
- Findings:
  - Proposes adaptive, per-prompt allocation of test-time compute based on difficulty; reports more than 4x efficiency over best-of-N.
  - FLOPs-matched evaluation: a smaller base model with test-time compute outperformed a 14x larger model, but only on problems where the smaller model had non-trivial success rates.
  - Base models are not named in the extract.
- Relevance to EasyResearch: The condition (only when the small model has non-trivial success) is the key caveat for an 8B local model: extra samples help on tasks it already partly solves, not on tasks it cannot solve.

### S46. Reflexion: Language Agents with Verbal Reinforcement Learning
- Author/org: Shinn et al.
- Date: 2023-03-20 (v1); v4 2023-10-10
- URL: https://arxiv.org/abs/2303.11366
- Tag: [V]
- Findings:
  - Agents improve by verbal self-reflection stored in episodic memory, guided by feedback that can be scalar or free-form and external or simulated.
  - HumanEval pass@1 91% versus 80% for GPT-4 (prior state of the art, per the paper).
  - Other gains (sequential decision-making, reasoning) reported without figures in the extract.
- Relevance to EasyResearch: The gains depend on feedback from the environment (tests, errors). A critique with no external signal is the weaker case; an OpenAlex overlap check is an external signal.

### S47. Large Language Models Cannot Self-Correct Reasoning Yet
- Author/org: Huang et al.
- Date: 2023-10-03 (v1); v2 2024-03-14
- URL: https://arxiv.org/abs/2310.01798
- Tag: [V]
- Findings:
  - Intrinsic self-correction (revising answers with no external feedback) often fails; in some cases performance gets worse after self-correction.
  - Benchmarks are not named in the extract.
- Relevance to EasyResearch: Major evidence against O7's premise that the same model can critique its own output as an independent reviewer and reliably improve it.

### S48. LLM Evaluators Recognize and Favor Their Own Generations
- Author/org: Panickssery et al.
- Date: 2024-04-15
- URL: https://arxiv.org/abs/2404.13076
- Tag: [V]
- Findings:
  - LLM evaluators can distinguish their own outputs from other LLM and human text; self-recognition is linked to self-preference (a causal link reported against simple confounders).
  - GPT-4 and Llama 2 show non-trivial accuracy at self-recognition out of the box; fine-tuning increased the linear correlation between self-recognition and self-preference.
  - No single effect-size figure in the extract.
- Relevance to EasyResearch: Same model scoring its own contributions and problems inflates scores. Directly against the O7 framing of "independent."

### S49. ReWOO: Decoupling Reasoning from Observations
- Author/org: Xu et al.
- Date: 2023-05-23 (v1)
- URL: https://arxiv.org/abs/2305.18323
- Tag: [V] (abstract only; planner, worker, and solver details not in the extract)
- Findings:
  - Detaches reasoning from external observations, avoiding repeated prompts and interleaved tool calls; reports 5x token efficiency on HotpotQA (baseline not named in the extract) and a 4% accuracy gain.
  - Reports offloading reasoning from a 175B model into a 7B model via instruction fine-tuning.
  - Robustness under tool-failure scenarios reported.
- Relevance to EasyResearch: Supports O1's split of planning (one LLM call) from retrieval (no LLM) and synthesis (one LLM call). The token saving is the same mechanism.

---

## Part 2. Verdicts on O1, O2, O5, O7, O12

### O1. Deterministic, code-driven state machine with fixed stage order; LLM has no tools; one LLM call per LLM stage

**Verdict: Supported**, with one caveat on the critique stage.

Reasoning and sources:
- Anthropic's workflow/agent split (S01) defines fixed, developer-written control flow as the predictable choice for well-defined tasks. EasyResearch's pipeline is well defined, so the workflow pattern is the recommended one.
- 12-Factor (S29, factor 8 "own your control flow") and LangGraph's workflow patterns (S24) describe the same design.
- ReWOO (S49) supports separating planning from observation, which is the plan_queries to search split.
- LLM-Modulo (S12) says LLMs cannot self-verify plans; keeping validation in code is consistent with that.
- MAST (S10) lists failures such as step repetition, premature termination, and unaware of termination conditions. A fixed stage order with explicit caps closes those failure modes for this pipeline.
- Google (S08) reports that centralized control contains error amplification (4.4x versus 17.2x for independent), which favors a code orchestrator over free-running agents.

Caveats and risks:
- The critique stage is the one LLM stage whose output is judged by an LLM (see O7). Its output should be treated as advisory.
- A fixed order cannot recover from upstream failure except through the loop. Add explicit stage-level failure handling (for example, zero accepted papers triggers a query re-plan with a cap; see Part 3 idea 1).
- "LLM has NO tool access" is stricter than Anthropic's augmented-LLM model (S01), which includes tools. That is a valid choice here but should be stated as a deliberate constraint.
- No source tests a fixed pipeline of this shape with an 8B local model. Evidence is about frontier models and general agents.

### O2. One shared JSON state object persisted in SQLite; no multi-agent, no subagents inside the app

**Verdict: Supported.**

Reasoning and sources:
- Cognition (S06) argues that shared context and single-threaded agents avoid conflicting implicit decisions. Problems, methods, and contributions depend on each other, which is exactly that failure mode.
- Google (S08) reports that multi-agent variants degraded sequential-task performance by 39 to 70% (PlanCraft), and that centralized coordination helps mainly on parallelizable tasks. The EasyResearch chain is sequential.
- Anthropic (S02) lists shared-context and dependency-heavy tasks as poor fits for multi-agent systems.
- LangChain (S42) shows a single agent is preferred when there are no distractor domains; EasyResearch is single-topic.
- Persistence is well supported: LangGraph checkpointers (S23), CrewAI @persist with SQLite (S34), and Microsoft checkpoints at superstep boundaries (S33) all use the same pattern.
- Anthropic context engineering (S04) and Cognition (S06) both point to compaction of long state.

Caveats and risks:
- Parallelism is still possible without subagents: OpenAlex queries and screening can be parallel code (no LLM). S02 and S08 suggest parallel retrieval helps breadth; this does not violate O2.
- A single JSON object grows across iterations. Without compaction, the local 8B model will see a truncated or diluted prompt. Store the full state, but send a compacted view to each LLM call.
- Concurrent writes to one SQLite file need a single writer or transactions. Not covered by any source here; it is standard engineering.

### O5. Human-in-the-loop: run stops at awaiting_review after critique; user feedback feeds the next iteration; max 3 iterations; saving is an explicit user action

**Verdict: Supported.**

Reasoning and sources:
- LangGraph (S22, S23) implements pause and resume through a checkpointer and thread_id; the pause/resume shape matches O5.
- OpenAI Agents SDK (S28) recommends serialized pending state, server-side authentication of approvals, and idempotency keys for side effects. Those map to the "save to project" action.
- MCP (S44) states that a human should be able to deny tool invocations for sensitive operations.
- Gemini Deep Research (S41) asks the user to approve a plan before searching; Co-STORM (S14) keeps the user in the loop and was preferred over a search engine by 70% of participants (its own study).
- The cap of 3 is supported indirectly: Magentic-One (S11) uses a bounded stall counter before re-planning; MAST (S10) lists unaware of termination conditions as a failure mode.

Caveats and risks:
- LangGraph re-runs the node from its start on resume (S22). If the review gate is inside a node that calls the LLM or OpenAlex before interrupt(), those calls run again. Make the gate a separate step and keep earlier steps idempotent (or cache them by stage hash).
- CrewAI's @human_feedback can use an LLM to map feedback to the next branch (S34). Do not adopt that for O5; the user should choose explicitly, so the LLM does not decide the next step.
- No source tests a three-iteration cap specifically. It is a product choice; a cost and time estimate per iteration on the local GPU is needed.

### O7. Critique: same model as independent reviewer; 1 to 5 scores; novelty labeled an estimate; closest prior work from top 3 OpenAlex hits per contribution

**Verdict: Partly supported. The "independent reviewer" framing is Contradicted; the structured rubric and grounding are Partly supported; the novelty label and top-3 retrieval are No evidence.**

Reasoning and sources:
- Independence is contradicted. Panickssery et al. (S48) show LLM evaluators recognize and favor their own outputs. Same-model self-review therefore inflates scores. Huang et al. (S47) find intrinsic self-correction often fails and can make results worse. Zhang et al. (S16) argue that same-model debate adds little, and that model heterogeneity helps, which the user's no-new-models constraint rules out. Debate or Vote (S17, snippets only) suggests the apparent gains come from voting rather than debate.
- Grounding helps. Reflexion (S46) reports large gains when feedback comes from the environment. LLM-Modulo (S12) places verification in external checks. A critique that must cite retrieved OpenAlex works or a deterministic check is closer to these results.
- Novelty score: No source evaluates LLM novelty scoring. The "estimate, not a verdict" labeling is the right instinct and matches the caution in S48 and S47, but it cannot be validated from these sources.
- Closest prior work with top 3 OpenAlex hits: No evidence in this set about how many hits are needed. Lexical retrieval recall is a known limitation (S38 uses BM25-style filtering for relevance, self-reported). Treat top 3 as a starting point and measure recall on a few known topics.

Risks:
- Presenting LLM scores to the user as "independent review" is a misleading label and could be overtrusted. Rename to "self-critique (same model)" in the UI and docs.
- Scores on a 1 to 5 scale from an 8B model are likely to cluster. Calibrate with a few fixed examples before trusting differences.
- Keep the critique advisory; do not let its scores gate the flow automatically.

### O12. MCP server with read tools and draft-only write tools; four Agent Skills; Claude Code as outer orchestrator with its own subagents

**Verdict: Supported**, with privacy and approval caveats.

Reasoning and sources:
- MCP (S44) supports exposing tools with schemas and isError results, and recommends a human in the loop for sensitive actions. Draft-only writes that require approval match this.
- Agent Skills (S05) use SKILL.md with progressive disclosure; the four skills fit the design if their descriptions are tuned for triggering.
- Claude Code subagents (S43) have their own context and return summaries; that is the right shape for read-only review tasks outside the app.
- Anthropic's tool guidance (S03) supports purpose-built, few tools with clear error messages.
- The OpenAI SDK (S28) requires server-side authorization of approvals and idempotency for side effects; the MCP write tools need the same checks on the server, not only in the client.

Risks:
- Privacy: any MCP read tool that returns note text or PDF excerpts into a Claude Code session sends that text to the model provider. The project invariant says external transmission requires explicit user request and a preview of what will be sent. This must be built as an explicit per-action preview or limited to metadata by default.
- Prompt injection: text from papers and web sources returned by read tools can carry instructions. MCP (S44) says annotations are untrusted, and the same applies to content. Mark returned text as data in tool results.
- Subagent nesting (S43) can multiply cost; set the spawn depth to 1 for this project.
- Skills from untrusted sources are a risk (S05); the four skills are first-party and should be audited on each change.

---

## Part 3. Better ideas (at least 8)

Each item: what to change; evidence; expected benefit; cost; fit with constraints (free, no new local model downloads, privacy, single user, Korean UI); risks; confidence.

### Idea 1. Bounded re-plan when a stage yields too little
- Change: Add a stall-style counter to the search and screen stages. If accepted papers fall below a threshold, re-run plan_queries once with the failed queries listed, up to a cap of 2. Record the counter in state.
- Evidence: Magentic-One stall counter with threshold 2 and re-plan (S11). MAST lists step repetition and premature termination as common failures (S10).
- Benefit: fewer dead-end runs when OpenAlex returns little; no open-ended loops.
- Cost: low; one extra LLM call only in the failure case.
- Fit: free; no model download; single user; keep Korean query text in the state.
- Risks: a re-plan can drift from the user's focus; log which queries were replaced.
- Confidence: high.

### Idea 2. Require citation-grounded critique items
- Change: The critique JSON must cite a state field or an OpenAlex work ID for each weakness. Code rejects any weakness without a valid reference and asks for one retry.
- Evidence: Reflexion gains rely on external feedback (S46); LLM-Modulo places verification outside the LLM (S12); self-correction without feedback fails (S47); self-preference bias (S48).
- Benefit: reduces unsupported critique; makes O7 output checkable.
- Cost: low; validation code plus one retry.
- Fit: fully local; no new model; supports the privacy rule because no extra data leaves the machine.
- Risks: may drop valid but abstract critiques; allow a "general" category with a lower score.
- Confidence: high.

### Idea 3. Deterministic novelty signal, shown next to the LLM estimate
- Change: Compute a lexical overlap score between each contribution statement and the top-3 OpenAlex abstracts (for example, token overlap or BM25 with title match). Show it beside the LLM novelty estimate, labeled as a retrieval check, not a verdict.
- Evidence: Independence of the LLM judge is contradicted (S48, S47); lexical filtering reported as more relevant than embeddings in one self-reported project benchmark (S38, unverified); external verification is the recommended pattern (S12).
- Benefit: a second, non-LLM signal for novelty; cheap to test.
- Cost: low; CPU only.
- Fit: free, local, no downloads.
- Risks: lexical overlap misses paraphrased prior work; present it as a warning, never as proof of novelty.
- Confidence: medium.

### Idea 4. Replace "independent reviewer" with a checklist review and measure it against a baseline
- Change: Rename the critique to a self-critique pass. Evaluate it against a no-critique baseline and a self-consistency baseline on a fixed set of 10 to 20 topics the user already knows. Keep it only if it wins on a rubric the user scores.
- Evidence: MAD papers find that complex critique often fails to beat single-call baselines (S16, S15); voting explains much of the gain (S17, snippet); test-time compute helps only on problems the model partly solves (S45).
- Benefit: avoids paying LLM time for a critique that adds nothing; gives a decision basis.
- Cost: moderate, mostly the user's time to score 10 to 20 outputs; a few hours of local GPU time.
- Fit: local, private; keeps data on the device.
- Risks: small sample; user fatigue; keep the eval set in a temporary data folder per the project invariant.
- Confidence: high that the measurement is needed; medium on the outcome.

### Idea 5. Self-consistency for the problems stage instead of debate
- Change: For the problems stage only, sample 2 or 3 candidate lists at a low temperature and merge in code (union with lexical dedupe, or pick the most frequent). Do not add debate rounds.
- Evidence: Voting accounts for most debate gains (S17, snippet); MAD does not beat self-consistency (S16); Snell et al. note test-time compute helps only where the model partly solves the task (S45).
- Benefit: more stable candidates; cheap to implement.
- Cost: 2 to 3 times the LLM calls for this stage; on an RTX 4060 with an 8B Q5 model this could be slow. Test wall-clock first.
- Fit: local, no new model.
- Risks: slower runs; the local model may produce near-duplicate samples.
- Confidence: medium.

### Idea 6. Persist state at every stage boundary with stage hashes
- Change: Save state after each stage with a hash of its inputs. On resume or re-run, skip stages whose input hash has not changed.
- Evidence: Checkpoints at superstep boundaries (S33); checkpointers for resume and fault tolerance (S23); LangGraph's re-run-on-resume caveat means idempotent stages matter (S22).
- Benefit: crash recovery; no duplicate OpenAlex calls; cheaper iterations (only the changed stages rerun).
- Cost: low; one table or JSON column with hashes.
- Fit: SQLite already in use; private; no external service.
- Risks: stale cache when the user edits the note; include user feedback in the hash.
- Confidence: high.

### Idea 7. Make the review gate a separate, idempotent step with a stored pending item
- Change: Split the iteration into stage runs. The awaiting_review state is written as a pending record. Feedback is a separate action that creates the next iteration. "Save to project" is a separate action that reads the pending record and checks an idempotency key.
- Evidence: LangGraph node restart caveat (S22); OpenAI SDK approval not exactly-once and needs idempotency keys and server-side checks (S28); MCP human-in-the-loop (S44).
- Benefit: avoids duplicate saves and repeated LLM calls after a page reload.
- Cost: low to moderate.
- Fit: single user; no network; private.
- Risks: more states to test.
- Confidence: high.

### Idea 8. Compact the state before each LLM call
- Change: Build a per-stage view from the state: the current focus, the top-N accepted papers (title, year, one-line reason), and prior iteration weaknesses (max 5). Send only that view to the local model. Keep the full state in SQLite.
- Evidence: Compaction and high-signal tokens (S04); Cognition's compression model for long histories (S06); sub-agent summaries of 1,000 to 2,000 tokens (S04).
- Benefit: keeps prompts short for an 8B model; reduces prompt-quality drift.
- Cost: low.
- Fit: local, private.
- Risks: lossy; keep the full record and let the user view it.
- Confidence: high.

### Idea 9. Structured error feedback for one retry per LLM stage
- Change: On JSON or schema failure, return a compact error (field name, expected type, one example) to the model for one retry; then fall back to a stage-level failure state rather than a loop.
- Evidence: Compact errors and error messages that say how to fix (S29 factor 9; S03); MCP isError results (S44).
- Benefit: higher parse success on a small local model; bounded cost.
- Cost: low.
- Fit: local; no downloads.
- Risks: retries can mask prompt problems; log the failure rate per stage.
- Confidence: high.

### Idea 10. Plan approval before any OpenAlex call
- Change: After plan_queries, show the user the queries and focus and require approval or edits before search. Keep the approval as a stored record.
- Evidence: Gemini Deep Research lets the user revise or approve the plan before searching (S41); HITL with explicit approval (S28, S44).
- Benefit: avoids wasted API calls and off-topic results; uses the user's judgment early, where it is cheapest.
- Cost: low; one UI step.
- Fit: single user; the OpenAlex call is a read, but keep it user-triggered to respect the external-network rule.
- Risks: adds a click per run; offer an "approve and run" default.
- Confidence: high.

### Idea 11. A budget tracker in code, not in the prompt
- Change: Count OpenAlex calls, LLM calls, and wall-clock time per run; stop when a per-run budget is reached and show the remaining budget in the UI. Optionally inject remaining budget into the prompt as a short status line.
- Evidence: Budget-aware status improves use of limited budgets (S21, unverified details of the cost figure); token multiples are large for multi-agent systems (S02); DRB runs cost $20 to $100 for 100 tasks (S37, S36).
- Benefit: avoids runaway runs; lets the user see the cost of each iteration on the local GPU.
- Cost: low.
- Fit: local, no network cost.
- Risks: in-prompt budget messages do little for an 8B model; keep the budget in code.
- Confidence: medium.

### Idea 12. Parallel retrieval, sequential reasoning
- Change: Run OpenAlex queries concurrently (bounded, for example 3 at a time with rate-limit backoff) and merge results in code before screening. Keep all LLM stages sequential.
- Evidence: Parallel subagent search cut time up to 90% on broad research (S02), and centralized parallel work helps parallelizable tasks (S08); sequential tasks degrade under multi-agent (S08). Parallelism here is code, not agents.
- Benefit: faster search stage without the dependency problem.
- Cost: low to moderate; needs polite rate limiting for OpenAlex and a contact setting that does not expose private data.
- Fit: free; external network only for OpenAlex search (already part of the design).
- Risks: rate limits; make the concurrency configurable and default to 1 if needed.
- Confidence: medium.

### Idea 13. Use Claude Code subagents as an offline reviewer, read-only, depth 1
- Change: Ship one optional skill (for example, "review-run") that runs a read-only subagent on an exported run record (the user chooses which fields to share, with a preview). Set spawn depth to 1.
- Evidence: Subagents have their own context and return summaries (S43); Anthropic's orchestrator-worker is for breadth (S02); data leaves the machine via the model provider, which the privacy invariant restricts (AGENTS.md).
- Benefit: a second opinion on a finished run without loading the app's LLM.
- Cost: uses Claude usage on each review.
- Fit: only with explicit user consent per export, since it sends private text out.
- Risks: privacy; keep it off by default.
- Confidence: medium.

### Idea 14. Evaluation harness with held-out topics and verifiable outcomes
- Change: Build 10 to 20 fixed research prompts with expected accepted papers (from the user's own library, not external data) and score each stage: JSON validity, accepted-paper precision, weakness citation rate, calls and time per run. Store results in a temporary folder.
- Evidence: Anthropic's evaluation guidance (S03, S02); MAST taxonomy for failure categories (S10).
- Benefit: makes the design decisions measurable, and supports the verdict on O7 and idea 5.
- Cost: moderate; a few hours to set up.
- Fit: local; no external data needed; respects the private-data invariant by using temp folders.
- Risks: the user's library may be biased; state the limitation.
- Confidence: high.

---

## Part 4. Conflicts between sources and unverified items

### Conflicts

1. Google scaling study: blog versus arXiv abstract page.
   - Blog (S08, 2026-01-28): 180 configurations, 4 benchmarks, predictive model R-squared 0.513, 87% accuracy on unseen configurations.
   - arXiv abstract page (S09, v1 2025-12-09): 260 configurations, 6 benchmarks, cross-validated R-squared 0.373 (0.413 with a task-grounded metric).
   - Likely explanation: different versions of the paper. Not resolved here. Cite the study with the version used and do not mix numbers.
2. Google study: Finance-Agent parallel gain. The blog says 80.9%; a search snippet said 80.8%. Use 80.9% (blog) if it is cited.
3. Google study: "45% threshold" for diminishing returns. A search snippet claimed it; the blog text did not mention it (S08). Treated as unverified.
4. Anthropic (S02) versus Cognition (S06): one reports large gains from parallel subagents on breadth-first research; the other argues multi-agent is fragile for coding. Reconciled by task shape: breadth and independence favor subagents; dependent, write-heavy work favors a single thread. EasyResearch is dependency-heavy.
5. Claude Code subagent nesting (S43) versus the common assumption that subagents cannot spawn subagents. The docs say nesting is on by default up to three layers. Verify the current behavior in the installed version before designing around it.
6. LangChain open_deep_research (S37): the premise I was given (supervisor plus researcher subagents, compression) could not be confirmed from the current page. The page lists four model roles and describes supervisor and plan-and-execute only as legacy variants.
7. LangChain swarm versus supervisor (S42): swarm slightly beat supervisor, and a supervisor fix gave about 50%. The direction depends on the implementation details; this is a single benchmark with no independent replication in this set.
8. Debate literature: Smit et al. (S15, cautious, tuning-sensitive) versus Zhang et al. (S16, MAD often fails to beat baselines). Not contradictory, but they differ in harshness. Choi et al. (S17) reframes the gains as voting.
9. AFlow (S18): the premise I was given (benchmark list and "manual baselines") is not in the extract. The abstract says 5.7% average gain over state-of-the-art baselines on six datasets (names not in the extract).
10. BATS (S21): the paper's browse-call reduction (21.4%) does not match my recalculation from its table (about 20%). Minor, but do not cite the exact figure.
11. Google ADK (S30): the template workflow agents are described as deterministic and superseded in ADK 2.0 by graph-based workflows. Check the ADK version before choosing ADK-specific patterns.
12. MAST (S10): the page lists frameworks and fix experiments, but the "where failures concentrate" finding was not stated. My prompt implied such a finding; it is not confirmed.
13. Open Deep Research (S36) says GAIA 67.36% for OpenAI Deep Research. S39 (the OpenAI page) was not readable, so this figure is secondhand.

### Unverified items (not opened or not confirmed)

- S07 Cognition 2026 follow-up: secondary summaries only; the ZenML bug-rate figure (2 per PR, 58% severe) is unverified.
- S15 Smit et al. and S17 Choi et al.: snippets only; the paper pages were not opened.
- S25 OpenAI practical guide: the PDF could not be read; manager and decentralized patterns come from third-party summaries.
- S31 ADK multi-agent docs: snippet only; the page redirected and was not readable.
- S39 and S40 OpenAI deep research blog and system card: HTTP 403 or unreadable PDF; no claims verified.
- S29 12-Factor: per-factor text not opened; only titles.
- S19 ADAS and S20 MaAS: benchmark names and numbers not in the extract (MaAS claims cost and performance ranges from the abstract, [V]).
- S16 benchmark list and model-heterogeneity numbers: not in the extract.
- S21 BATS publication date: not confirmed.
- S22 to S24 LangGraph pages: undated in the extracts.
- S12 LLM-Modulo: abstract-level only; the generate-test roles are not spelled out in the fetched text.
- S49 ReWOO planner/worker/solver details and the LLM call counts: not in the abstract.
- S43 Claude Code subagents: the second page of the doc was not read.
- S09 PlanCraft and error amplification figures from the arXiv version: not confirmed.

---

## Part 5. URL index

- S01 https://www.anthropic.com/research/building-effective-agents
- S02 https://www.anthropic.com/engineering/multi-agent-research-system
- S03 https://www.anthropic.com/engineering/writing-tools-for-agents
- S04 https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- S05 https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- S06 https://cognition.com/blog/dont-build-multi-agents
- S07 https://cognition.com/blog/multi-agents-whats-actually-working (not opened)
- S08 https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/
- S09 https://arxiv.org/abs/2512.08296
- S10 https://arxiv.org/abs/2503.13657
- S11 https://arxiv.org/abs/2411.04468 and https://arxiv.org/html/2411.04468v1
- S12 https://arxiv.org/abs/2402.01817
- S13 https://arxiv.org/abs/2402.14207
- S14 https://arxiv.org/abs/2408.15232
- S15 https://arxiv.org/abs/2311.17371 (not opened)
- S16 https://arxiv.org/abs/2502.08788
- S17 https://arxiv.org/abs/2508.17536 (not opened)
- S18 https://arxiv.org/abs/2410.10762
- S19 https://arxiv.org/abs/2408.08435
- S20 https://arxiv.org/abs/2502.04180
- S21 https://arxiv.org/html/2511.17006v1
- S22 https://docs.langchain.com/oss/python/langgraph/interrupts
- S23 https://docs.langchain.com/oss/python/langgraph/persistence
- S24 https://docs.langchain.com/oss/python/langgraph/workflows-agents
- S25 https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf (unreadable)
- S26 https://openai.github.io/openai-agents-python/handoffs/
- S27 https://openai.github.io/openai-agents-python/guardrails/
- S28 https://openai.github.io/openai-agents-python/human_in_the_loop/
- S29 https://github.com/humanlayer/12-factor-agents
- S30 https://adk.dev/agents/workflow-agents/
- S31 https://adk.dev/agents/multi-agents/ (not readable; snippet from google.github.io/adk-docs/agents/multi-agents)
- S32 https://learn.microsoft.com/en-us/agent-framework/workflows/
- S33 https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints
- S34 https://docs.crewai.com/en/concepts/flows
- S35 https://huggingface.co/blog/smolagents
- S36 https://huggingface.co/blog/open-deep-research
- S37 https://github.com/langchain-ai/open_deep_research
- S38 https://github.com/assafelovic/gpt-researcher
- S39 https://openai.com/index/introducing-deep-research/ (403)
- S40 https://cdn.openai.com/deep-research-system-card.pdf (unreadable)
- S41 https://blog.google/products/gemini/google-gemini-deep-research/
- S42 https://www.langchain.com/blog/benchmarking-multi-agent-architectures
- S43 https://code.claude.com/docs/en/sub-agents
- S44 https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- S45 https://arxiv.org/abs/2408.03314
- S46 https://arxiv.org/abs/2303.11366
- S47 https://arxiv.org/abs/2310.01798
- S48 https://arxiv.org/abs/2404.13076
- S49 https://arxiv.org/abs/2305.18323
- Also referenced (not separately opened): https://arxiv.org/abs/2408.15232 (S14), https://arxiv.org/abs/2402.14207 (S13), https://www.anthropic.com/research/building-effective-agents (S01).
