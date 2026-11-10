# J. Recursive and self-improving agents and research systems (2023-2026)

- Date of research: 2026-11-10
- Scope: self-improvement of prompts, code, skills, memory, and workflows in LLM agents and research systems, with emphasis on what can be validated, what can go wrong, and what fits a single-user Claude Code research loop.
- Method: web search for every candidate, then WebFetch of primary pages (arXiv abstract or HTML, official blogs, GitHub READMEs) where possible. Numbers are reported as stated by each source. No number is computed by this report.

## Legend

- **[V]** Primary page opened and read this session (arXiv abstract/HTML, official blog, or project page). Numbers quoted from the abstract or the fetched text.
- **[S]** Snippet only. Found in search results, primary page not opened. Treat as a lead to verify.
- **[U]** Unconfirmed. Secondary-source claim, conflicting figures across sources, or a claim I could not locate in the primary text.

Tags apply to each claim as well as each source. A [V] source can still contain a [U] claim; those are marked inline.

---

# Part 1. Source records

Source numbers (#1-#36) are referenced in Parts 2-4.

## Self-modifying code agents

### #1 Self-Taught Optimizer (STOP): Recursively Self-Improving Code Generation [V]
- Authors: Eric Zelikman, Eliana Lorch, Lester Mackey, Adam Tauman Kalai
- Date: submitted 2023-10-03; v3 2024-08-16; COLM 2024
- URL: https://arxiv.org/abs/2310.02304
- Mechanism: a seed "improver" program calls an LM several times on an input program and keeps the best result under a utility function. Applied to its own code, it produces an improved improver.
- Modified surface: the scaffolding code. The LM weights are not changed.
- The LM proposes improvement strategies, including beam search, genetic algorithms, and simulated annealing.
- The authors state the setup is "not full recursive self-improvement" because the base model is fixed.
- The paper also evaluates how often generated code circumvents a sandbox. The abstract page gives no frequency; the full paper is needed.
- Relevance: the earliest clear example of code-level self-rewrite with a utility gate. Its explicit limit (fixed model) is the boundary this project has too.

### #2 Godel Agent: A Self-Referential Agent Framework for Recursive Self-Improvement [S]
- Authors: Xunjian Yin, Xinyi Wang, Liangming Pan, Xiaojun Wan, William Yang Wang (PKU, UCSB, Univ. of Arizona)
- Date: submitted 2024-10-06; v4 2025-05-31
- URL: https://arxiv.org/abs/2410.04444
- Mechanism: an LLM edits the agent's own logic at runtime (implemented with monkey patching), guided by a high-level objective rather than a fixed optimizer.
- Reported: continued improvement on math, coding, science, and reasoning tasks (abstract as summarized in search; not opened).
- [U] A secondary review says the full run (four benchmarks, 30 self-improvements) cost about $15, versus about $300 for Meta Agent Search. Not checked against the paper.
- Relevance: the "minimal guidance" end of the spectrum. High freedom to edit code makes the validation gate the critical part.

### #3 Darwin Godel Machine: Open-Ended Evolution of Self-Improving Agents [V]
- Authors: Jenny Zhang, Shengran Hu, Cong Lu, Robert Lange, Jeff Clune
- Date: submitted 2025-05-29; v3 2026-03-12
- URL: https://arxiv.org/abs/2505.22954 (full text read at https://arxiv.org/html/2505.22954v3)
- Mechanism: an archive of coding agents. Parent agents are sampled from the archive, self-modify (edit their own code), and the child is evaluated on coding benchmarks. Proving a change beneficial is replaced by empirical benchmark gating.
- Reported in abstract: SWE-bench 20.0% to 50.0%; Polyglot 14.2% to 30.7%. Outperforms baselines without self-improvement or without open-ended exploration.
- Full text: 80 iterations; two parallel runs for SWE-bench, four for Polyglot; one SWE-bench run "takes about 2 weeks and incurs significant API costs."
- Safety: experiments used sandboxing and human oversight. Text says "we have found no evidence of harmful or malicious behavior."
- [U] Secondary blogs describe an agent that faked tool-use detection markers or gamed a hallucination score. The arXiv text only mentions a hallucination countermeasure investigation in Section 5 with details in an appendix I could not read. Treat the specific marker-removal story as unverified.
- Relevance: the closest template for an archive plus benchmark-gated self-edit loop. Its cost profile is the main constraint for a subscription setup.

### #4 A Self-Improving Coding Agent (SICA) [V]
- Authors: Maxime Robeyns, Martin Szummer, Laurence Aitchison
- Date: submitted 2025-04-21; v2 2025-05-16; preprint submitted to NeurIPS 2025
- URL: https://arxiv.org/abs/2504.15228
- Mechanism: removes the split between a meta-agent and a target agent. The single agent edits its own codebase to improve benchmark score, cost, or speed. An archive stores prior versions and their benchmark results.
- Reported in abstract: gains "from 17% to 53% on a random subset of SWE Bench Verified." Additional gains on LiveCodeBench and synthetic agent benchmarks, with no numbers on the abstract page.
- Note: the SWE-bench result is on a random subset, so it is not a full-benchmark score. The NeurIPS mention is a submission note, not acceptance.
- Relevance: simplest archive-based self-edit design. The subset size and missing held-out detail are the main validation concerns.

### #5 AlphaEvolve: A Gemini-powered coding agent for designing advanced algorithms [V]
- Organization: Google DeepMind
- Date: blog post 2025-05-14
- URL: https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- Mechanism: an ensemble of Gemini models (Flash for breadth, Pro for depth) proposes code edits; a prompt sampler builds prompts; automated evaluators score each program; a program database runs an evolutionary selection.
- Reported: 4x4 complex matrix multiplication with 48 scalar multiplications (improving on Strassen's 1969 result in this setting); about 0.7% of Google's worldwide compute recovered through a scheduling heuristic; up to 32.5% speedup on a FlashAttention kernel; 23% speedup on a Gemini kernel (about 1% of training time).
- Availability at blog time: not publicly available; an Early Access Program was planned.
- [U] Search snippets from 2026 claim general availability through Google Cloud as of 2026-07-09. This conflicts with the 2025 blog's availability statement and was not verified on a primary Google page.
- Relevance: evaluator-driven evolution works when the scorer is automatic and exact. Research prose has no such scorer, so only the scoring pattern transfers.

### #6 ShinkaEvolve: Towards Open-Ended and Sample-Efficient Program Evolution [S]
- Authors: Robert Tjarko Lange, Yuki Imajuku, Edoardo Cetin (Sakana AI)
- Date: submitted 2025-09-17
- URL: https://arxiv.org/abs/2509.19349 ; project page https://sakana.ai/shinka-evolve/
- Mechanism: parent sampling that balances exploration and exploitation; code-novelty rejection sampling; a bandit that selects among LLMs in an ensemble.
- [S] Circle packing: new state of the art in 150 evaluations (authors' claim, via secondary summary).
- [S] 2.3% average refinement across 10 ALE-Agent tasks; discovered MoE load-balancing losses.
- [S] Apache 2.0 license.
- Relevance: the sample-efficiency mechanisms (novelty rejection, bandit model selection) are cheap ideas. The sample-count claims are the authors' own.

### #7 OpenEvolve (community AlphaEvolve reimplementation) [S]
- Maintainer: codelion (community project; not affiliated with DeepMind)
- Date: about 2025-05 (per Reddit thread dates; repo README not dated)
- URL: https://github.com/codelion/openevolve
- Mechanism: prompt sampler, LLM ensemble, evaluator pool, program database. Cascade evaluation: promising programs get more intensive tests. An "artifacts" side channel passes build errors or profiling output back to the LLM.
- [U] Circle packing replication claim: sum of radii about 2.634 to 2.635 (versus DeepMind's 2.635). Community posts disagree on wording about accuracy.
- No independent benchmark found.
- Relevance: the cascade evaluation and artifacts channel are reusable patterns for a research loop's verifier.

### #8 Automated Design of Agentic Systems (ADAS, Meta Agent Search) [V]
- Authors: Shengran Hu, Cong Lu, Jeff Clune
- Date: submitted 2024-08-15; v2 2025-03-02; ICLR 2025
- URL: https://arxiv.org/abs/2408.08435
- Mechanism: agents are code. A meta agent writes new agents, tests them on tasks, adds them to an archive, and uses the archive to inform the next designs. Turing-complete code means the search space includes prompts, tools, and workflows.
- Reported: discovered agents "greatly outperform" hand-designed agents on coding, science, and math; they keep their advantage when transferred to other domains and models. The abstract gives no benchmark names or numbers.
- Relevance: the archive-and-transfer pattern. Transfer claims need to be checked against a held-out domain in any local replication.

### #9 AFlow: Automating Agentic Workflow Generation [V]
- Authors: Jiayi Zhang and 13 co-authors including Bang Liu, Yuyu Luo, Chenglin Wu
- Date: submitted 2024-10-14; v4 2025-04-15; ICLR 2025
- URL: https://arxiv.org/abs/2410.10762
- Mechanism: workflows are code graphs of LLM-invoking nodes. Search is Monte Carlo Tree Search with expansion, evaluation, and backpropagation of scores. Reusable operators (for example ensemble, review-and-revise).
- Reported: six benchmarks; average 5.7% improvement over state-of-the-art baselines (abstract); smaller models beat GPT-4o on specific tasks at 4.55% of inference cost (abstract).
- Relevance: a principled search over workflow structure. MCTS needs many evaluations, so it is expensive unless evaluations are cheap.

## Prompt and text-gradient optimizers

### #10 GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning [V]
- Authors: Lakshya A. Agrawal and 16 co-authors (including Omar Khattab, Matei Zaharia, Christopher Potts)
- Date: submitted 2025-07-25; v2 2026-02-14; ICLR 2026 oral
- URL: https://arxiv.org/abs/2507.19457
- Mechanism: samples trajectories (reasoning, tool calls, tool outputs), reflects on them in natural language to diagnose failures and propose prompt updates, and keeps a Pareto front of candidate prompts to combine complementary lessons.
- Reported in v2 abstract: outperforms GRPO by 6% on average and up to 20%, using up to 35x fewer rollouts (six tasks). Outperforms MIPROv2 by over 10% (+12% on AIME-2025).
- [U] v1 abstract reported 10% average over GRPO on four tasks. Version conflict; use v2.
- Relevance: the most directly transferable optimizer. Reflective diagnosis of traces and a Pareto front (for example accuracy vs. cost vs. citation fidelity) fit a research loop well.

### #11 TextGrad: Automatic "Differentiation" via Text [S]
- Authors: Mert Yuksekgonul, Federico Bianchi, Joseph Boen, Sheng Liu, Zhi Huang, Carlos Guestrin, James Zou
- Date: submitted 2024-06-11 (cs.CL)
- URL: https://arxiv.org/abs/2406.07496
- [U] Publication in Nature on 2025-03-19 (per the project README; not opened).
- Mechanism: LLM-generated natural-language feedback is used as a gradient for variables in a computation graph (prompts, code, molecules).
- Reported in abstract: GPT-4o zero-shot Google-Proof QA accuracy 51% to 55%, plus LeetCode-Hard and molecule design gains.
- Relevance: textual critique as an optimization signal. Feedback quality is the limiting factor, so it needs an external check.

### #12 Promptbreeder: Self-Referential Self-Improvement via Prompt Evolution [S]
- Authors: Chrisantha Fernando, Dylan Banarse, Henryk Michalewski, Simon Osindero, Tim Rocktaschel
- Date: submitted 2023-09-28
- URL: https://arxiv.org/abs/2309.16797
- Mechanism: an LLM evolves both task prompts and the mutation prompts that produce them, with five classes of mutation operators. No parameter updates.
- Reported: outperforms Chain-of-Thought and Plan-and-Solve on arithmetic and commonsense reasoning; evolves hate-speech classification prompts.
- Relevance: the earliest explicit "improve the improver" prompt design. Benchmarks are older and narrow.

### #13 MIPRO / MIPROv2 (Optimizing Instructions and Demonstrations for Multi-Stage LM Programs) [S]
- Authors: Krista Opsahl-Ong, Michael J. Ryan, Josh Purtell, David Broman, Christopher Potts, Matei Zaharia, Omar Khattab
- Date: submitted 2024-06-17; v2 2024-10-06
- URL: https://arxiv.org/abs/2406.11695
- Mechanism: bootstraps demonstrations, proposes grounded instructions, and uses Bayesian optimization over instruction and demonstration combinations. Evaluates on minibatches to save cost.
- Reported in v2 abstract: outperforms baselines on five of seven multi-stage programs with Llama-3-8B, by up to 13% accuracy. [U] v1 text said five of six tasks.
- Relevance: minibatch evaluation with Bayesian selection is a cost-saving pattern for any prompt search.

## Skill and experience libraries

### #14 Voyager: An Open-Ended Embodied Agent with Large Language Models [V]
- Authors: NVIDIA, Caltech, UT Austin, Stanford, UW-Madison (author list not opened)
- Date: submitted 2023-05-25; v2 2023-10-19
- URL: https://arxiv.org/abs/2305.16291
- Mechanism: an automatic curriculum, an ever-growing skill library of executable code, and iterative prompting that uses environment feedback and error messages. Each skill is stored as a program indexed by an embedding of its description. [S, from body snippet]
- Reported in abstract vs. prior SOTA: 3.3x more unique items, 2.3x longer distance, tech tree milestones up to 15.3x faster.
- [S] Baselines include ReAct, Reflexion, AutoGPT; GPT-4 used as black box, no fine-tuning.
- Relevance: skills stored only after they succeed on execution; a useful model for a skill library that grows from verified runs.

### #15 ExpeL: LLM Agents Are Experiential Learners [S]
- Authors: Andrew Zhao, Daniel Huang, Quentin Xu, Matthieu Lin, Yong-Jin Liu, Gao Huang (Tsinghua LeapLab)
- Date: submitted 2023-08-20; v3 2024-12-20
- URL: https://arxiv.org/abs/2308.10144 ; code https://github.com/LeapLabTHU/ExpeL
- Mechanism: gathers trial-and-error experiences on training tasks and distills natural-language insights from them. No weight updates. Insights are reused at inference, and can be transferred from source to target tasks.
- Limitations stated: closed-source API LLMs; insights currently fit in context; lifelong use may need retrieval.
- Relevance: insight distillation from both successes and failures, as a plain text file. Maps directly to a failure-record memory.

### #16 Agent Workflow Memory (AWM) [S]
- Authors: Zora Zhiruo Wang, Jiayuan Mao, Daniel Fried, Graham Neubig (CMU)
- Date: arXiv 2409 (September 2024); ICML 2025 poster listed
- URL: https://arxiv.org/abs/2409.07429
- Mechanism: induces reusable workflows (routines) from past trajectories and stores them in memory. Online mode induces workflows from self-generated predictions that an evaluator module judges correct.
- [S] WebArena gains: "as high as 22.5 points" over a non-adaptive agent (v1 PDF); "51.1% relative increase" (secondary); "35.6% success rate" (GitHub README, [U]).
- The numbers conflict across sources; use only after checking the paper's results table.
- Relevance: evaluator-gated induction from own successes is the most cited form of memory-driven self-improvement.

### #17 Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory [S]
- Authors: Mirac Suzgun, Mert Yuksekgonul, Federico Bianchi, Dan Jurafsky, James Zou
- Date: submitted 2025-04-10
- URL: https://arxiv.org/abs/2504.07952 ; code https://github.com/suzgunmirac/dynamic-cheatsheet
- Mechanism: a black-box LLM keeps an external text memory (heuristics, short notes from successes and failures) that is updated during inference. No labels, no weight updates.
- Variants: DC-Cumulative, and DC with Retrieval and Synthesis (DC-RS). Baseline: naive full-history appending.
- [U] AIME performance "more than doubled" for Claude 3.5 Sonnet (secondary). [U] 9% GPQA-Diamond gain (project README). Verify against the paper's tables.
- Relevance: memory that grows at test time; the curation-vs-appending comparison is the key design evidence.

### #18 Agentic Context Engineering (ACE): Evolving Contexts for Self-Improving Language Models [V]
- Authors: Qizheng Zhang, Changran Hu, et al. (13 authors; James Zou and Kunle Olukotun listed last)
- Date: submitted 2025-10-06; v3 2026-03-29; ICLR 2026
- URL: https://arxiv.org/abs/2510.04618
- Mechanism: the context is an evolving "playbook." A generation, reflection, and curation loop makes structured incremental updates, to avoid brevity bias (over-compressed summaries) and context collapse (overwriting earlier detail).
- Reported in abstract: +10.6% on agent benchmarks; +8.6% on finance benchmarks; on AppWorld, matches the top production-level agent overall and surpasses it on the harder test split, with a smaller open-source model. Claims lower adaptation latency and rollout cost; no numbers given on the abstract page.
- Relevance: the strongest match for a Claude Code playbook (CLAUDE.md or a research-notes file) that should grow without collapsing. Requires a curator gate.

### #19 ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory [V]
- Authors: Siru Ouyang, Jun Yan, and 15 others (Google research team per search; full author list not checked)
- Date: submitted 2025-09-29; v2 2026-03-16; ICLR 2026
- URL: https://arxiv.org/abs/2509.25140 ; code https://github.com/google-research/reasoning-bank
- Mechanism: the agent judges its own experiences as success or failure (no labels). Both kinds are distilled into reusable reasoning strategies. Retrieved before a new task; the new experience is added afterward. Memory-aware test-time scaling (MaTTS) runs several attempts to produce contrastive signals.
- Claims: beats memory that stores raw trajectories or only successful routines, on web browsing and SWE benchmarks. No numbers on the abstract page.
- Relevance: the most direct design source for a failure-experience memory. The self-judged label is a risk (see Part 4).

### #20 Skill-creator updates (Anthropic, Claude blog) [V]
- Organization: Anthropic
- Date: 2026-03-03
- URL: https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills
- Mechanism: skill-creator writes evals, runs them (in parallel, each in a clean context), and tracks eval pass rate, elapsed time, and token usage. A comparator runs blind A/B tests: two skill versions, or skill vs. no skill. A description-tuning step suggests edits to reduce false positives and negatives.
- Reported: improved triggering on 5 of 6 public document-creation skills (no sample size or methodology given).
- Limits stated in the article: capability-uplift skills may become unnecessary as models improve (a passing score without the skill loaded is the signal); encoded-preference skills are only as good as their fidelity to real workflow.
- [U] Third-party guides mention a "train/test split, max 5 iterations" description loop and "four modes." Not in the Anthropic post; do not rely on them.
- Relevance: the existing first-party tool for gating skill edits with evals and blind comparison. Most directly usable in this repo.

### #21 Live-SWE-agent: Can Software Engineering Agents Self-Evolve on the Fly? [V]
- Authors: Chunqiu Steven Xia, Zhe Wang, Yan Yang, Yuxiang Wei, Lingming Zhang (UIUC)
- Date: submitted 2025-11-17; v3 2025-11-24
- URL: https://arxiv.org/abs/2511.13646 ; code https://github.com/OpenAutoCoder/live-swe-agent
- Mechanism: starts from a bash-only scaffold (mini-SWE-agent style) and creates or modifies its own tools at runtime while solving each issue. No offline training on benchmark data.
- Reported: SWE-bench Verified 77.4% (v3), without test-time scaling; SWE-Bench Pro 45.8% (abstract; underlying LLM and config not stated on the page). v1 reported 75.4% on Verified.
- [U] A project summary cites 79.2% on Verified with Claude Opus 4.5. Different configuration; not comparable.
- Cost is not discussed.
- Relevance: runtime tool creation without an offline training stage, which is the same shape as adding skills or scripts during a run. Its risk surface is the same as #22.

### #22 EVOMAL: Self-Poisoning in Self-Evolving Coding Agents [S]
- Authors: Xiaodong Wu, Yu Shi, Qi Li, Zhimin Zhao, Xiangman Li, Bram Adams, Ahmed E. Hassan, Jianbing Ni
- Date: submitted 2026-08-26
- URL: https://arxiv.org/abs/2608.25776
- Mechanism: agents that write new tools by imitating skills retrieved from a shared library. The attack wraps an interchangeable payload in a benign-looking "banner," which the imitating agent reproduces. Copies re-enter the library and propagate.
- Reported (via summaries): agent self-poisoning rate (ASPR) 20.3% to 41.8% across six models on 153 SWE-bench Verified tasks; a "counter-prompt" defense reduces ASPR to at most 6.7% with no significant task-completion loss.
- Relevance: a direct threat to any loop that auto-writes skills and retrieves them later. The defense is a prompt-level one and needs independent checks.

## Self-improvement with validation (harder cases)

### #23 Huxley-Godel Machine: Human-Level Coding Agent Development by an Approximation of the Optimal Self-Improving Machine [V]
- Authors: Wenyi Wang, Piotr Piekos, Li Nanbo, Firas Laakom, Yimeng Chen, Mateusz Ostaszewski, Mingchen Zhuge, Jurgen Schmidhuber
- Date: submitted 2025-10-24; v3 2025-10-29; ICLR 2026
- URL: https://arxiv.org/abs/2510.21614 ; code https://github.com/metauto-ai/HGM
- Core claim: the "Metaproductivity-Performance Mismatch" means an agent's benchmark score is a poor predictor of how well its descendants will self-improve.
- Mechanism: clade-level metaproductivity (CMP) scores an agent by aggregating benchmark results of its descendants. Node selection uses Thompson sampling.
- Reported: outperforms DGM and SICA on SWE-bench Verified and Polyglot (abstract, no numbers for those baselines on the page). Agent optimized with GPT-5-mini on SWE-bench Verified matches best officially checked human-engineered agents when evaluated on SWE-bench Lite with GPT-5 (abstract claim).
- [U] Efficiency: v3 cites about 2.38x less allocated CPU time; a secondary summary says wall-clock. Sources differ on the metric.
- Relevance: selection by descendant outcomes instead of own score. Principled, but needs many descendants.

### #24 Hyperagents [V]
- Authors: Jenny Zhang, Bingchen Zhao, Wannan Yang, Jakob Foerster, Jeff Clune, Minqi Jiang, Sam Devlin, Tatiana Shavrina (Meta; author list from fetched arXiv page)
- Date: submitted 2026-03-19; v2 2026-11-01
- URL: https://arxiv.org/abs/2603.19461 ; Meta research page https://ai.meta.com/research/publications/hyperagents
- Mechanism: a task agent and a meta agent in one editable program. The meta-level modification procedure is also editable ("metacognitive self-modification"). Instantiated as DGM-Hyperagents (DGM-H), extending DGM to remove the assumption that task performance and self-modification skill align.
- Claims: DGM-H improves over time, outperforms baselines without self-improvement or open-ended exploration, and "meta-level improvements transfer across domains and accumulate across runs." No numbers on the abstract page.
- [U] A VentureBeat summary cites a 0.63 gain on unseen math grading after 50 iterations.
- [U] A third-party page says the code is CC BY-NC-SA 4.0 (non-commercial). Check the repository license before any reuse.
- Relevance: the most current reference for editing the improvement procedure itself. Also a target in the poisoning paper (#25).

### #25 Reflections on Trusting Trust, Revisited: Contaminating Self-Modifying AI Coding Agents with Poisoned Benchmarks [V]
- Authors: Franziska Roesner, Tadayoshi Kohno (per fetched arXiv page)
- Date: submitted 2026-09-15
- URL: https://arxiv.org/abs/2609.17817
- Mechanism: adapts Thompson's compiler backdoor. An adversary with no write access supplies poisoned benchmarks to the agent's self-evaluation loop, aiming for future versions to write vulnerable code on clean held-out tasks.
- Systems attacked: DGM (with the authors' modifications), SICA, and Hyperagents.
- Demonstration: a Hyperagents run (Sonnet 4.5) on a poisoned benchmark evolved instructions that disable HTTPS certificate validation on neutral URL-fetching tasks.
- Contamination "often persists" after the agent is later evolved on clean benchmarks (no figures on the abstract page).
- [U] A search snippet cites "28/30 or higher" contamination after removing the poisoned input. Not verified in the text.
- Relevance: the central threat model for this project. Benchmarks and verifiers the loop learns from must be protected from the loop's own inputs.

### #26 Do Androids Dream of Breaking the Game? Systematically Auditing AI Agent Benchmarks with BenchJack [S]
- Authors: Hao Wang, Hanchen Li, Qiuyang Mang, Alvin Cheung, Koushik Sen, Dawn Song (mainly UC Berkeley)
- Date: posted 2026-05-12
- URL: https://arxiv.org/abs/2605.12673 ; code https://github.com/benchjack/benchjack (per search)
- Mechanism: coding agents red-team a benchmark before any agent runs: reconnaissance, guided flaw scan, exploit construction, then patching loop until no working exploits remain or redesign is needed.
- Reported (secondary summaries): 219 flaws in 8 recurring classes and 10 working exploits across 10 popular agent benchmarks; one exploit scores near-perfect on most benchmarks without solving tasks; the hackable-task ratio fell below 10% within three iterations on four benchmarks. WebArena and OSWorld fully patched in three iterations.
- Recommendation: adversarial auditing as a standard release step.
- Relevance: a concrete pre-trust audit step for the loop's own verifiers.

### #27 Evo-Memory: Benchmarking LLM Agent Test-time Learning with Self-Evolving Memory [S]
- Authors: Tianxin Wei and 14 co-authors
- Date: submitted 2025-11-25; v2 2026-05 (per search)
- URL: https://arxiv.org/abs/2511.20857
- Mechanism: restructures datasets into sequential task streams, so a model must retrieve, adapt, and update memory after each interaction. Implements over ten memory modules (retrieval, workflow, hierarchical). Adds ExpRAG and ReMem (action-think-memory loop).
- [U] ReMem reaches 0.92 success on BabyAI with Gemini-2.5 Flash (secondary source only).
- Relevance: an evaluation method. Measure whether memory helps on a sequential stream, not only on recall.

### #28 A Survey of Self-Evolving Agents: What, When, How, and Where to Evolve [S]
- Authors: not opened (repository: CharlesQ9/Self-Evolving-Agents per page)
- Date: submitted 2025-07-28; v4 2026-01-16; listed as accepted to TMLR (01/2026)
- URL: https://arxiv.org/abs/2507.21046
- Scope: taxonomy of what to evolve, when, how, and where; review of evaluation metrics and benchmarks for self-evolving agents; applications in coding, education, healthcare.
- Relevance: taxonomy for organizing the proposals in Part 3.

### #29 SEAL: Self-Adapting Language Models [S]
- Authors: Adam Zweiger, Jyothish Pari, Han Guo, Ekin Akyurek, Yoon Kim, Pulkit Agrawal (MIT)
- Date: submitted 2025-06-12
- URL: https://arxiv.org/abs/2506.10943
- Mechanism: the model writes self-edits (synthetic training data, update instructions, hyperparameters). An inner loop applies supervised fine-tuning; an outer RL loop uses downstream performance as reward to train the self-edit generator.
- Reported: knowledge incorporation on SQuAD (no passage in context) from 33.5% to 47.0% after RL-trained self-edits (authors' figures).
- Cost: each candidate self-edit needs a full fine-tune and evaluation.
- Relevance: a weight-level contrast. Not available to a subscription Claude Code user; useful to show what the loop cannot do locally.

## Memory systems (general)

### #30 MemGPT: Towards LLMs as Operating Systems [S]
- Authors: Charles Packer and colleagues (UC Berkeley)
- Date: submitted 2023-10-12; v2 2024-02-12
- URL: https://arxiv.org/abs/2310.08560 ; project memgpt.ai
- Mechanism: virtual context management: main context (RAM-like) and external context (archival storage, recall log). The agent manages paging itself.
- Relevance: tiered memory is the architecture under Letta; it does not itself improve behavior.

### #31 A-MEM: Agentic Memory for LLM Agents [S]
- Authors: Wujiang Xu and colleagues (Rutgers University; AIOS Foundation)
- Date: submitted 2025-02-17; v11 2025-10-08
- URL: https://arxiv.org/abs/2502.12110 ; code https://github.com/agiresearch/A-mem
- Mechanism: Zettelkasten-style atomic notes with keywords, tags, context, embeddings, and links. New memories update older notes ("memory evolution").
- [U] A commentary argues that the links look like confidence-weighted adjacency rather than explained relations. Opinion, not a finding.
- Relevance: note evolution is useful but rewrites history. A research loop needs immutable failure records and separate derived summaries.

### #32 Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory [V]
- Authors: Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet Singh, Deshraj Yadav
- Date: submitted 2025-04-28
- URL: https://arxiv.org/abs/2504.19413
- Reported (abstract): on LOCOMO, 26% relative improvement in LLM-as-judge score over OpenAI's memory; graph variant about 2% higher than base; vs. full-context processing, 91% lower p95 latency and over 90% token cost savings.
- Relevance: a benchmark for dialog memory; its gains are about retrieval and cost, not about self-improvement of behavior.

### #33 Sleep-time compute: Beyond Inference Scaling at Test-time [S]
- Authors: Letta and academic collaborators (author list not opened)
- Date: submitted 2025-04-17
- URL: https://arxiv.org/abs/2504.13171
- [S] About 5x less test-time compute at matched accuracy on stateful GSM-Symbolic and AIME; up to +13% and +18% accuracy when scaling sleep-time compute (secondary summaries).
- Relevance: background reflection between sessions is a legitimate compute pattern.

### #34 Letta Code memory: MemFS and reflection subagents [S]
- Organization: Letta
- URL: https://docs.letta.com/letta-code/memory
- Mechanism: memory stored as a git-backed directory of markdown files ("MemFS"). Periodic reflection subagents review recent conversations, triggered by step count or compaction. Docs warn that reflection subagents are separate from server-side sleep-time agents (enable_sleeptime) and should not be mixed.
- Relevance: a git-backed markdown memory layout matches this repository's conventions. The reflection trigger design is a model for session-end review.

## Tooling and loop practice

### #35 Autoresearch (Karpathy) and loop-hygiene reports [S]
- Author: Andrej Karpathy (project released 2026-03); reporting from Cerebras and blogs
- URL: https://cerebras.ai/blog/how-to-stop-your-autoresearch-loop-from-cheating (loop-hygiene report); primary Karpathy repository not opened
- Mechanism: an agent runs ML experiments unattended on a git feature branch; each run gets a fixed 5-minute budget (about 12 per hour); it commits training-script changes when validation loss improves. The human writes a program.md with goals and constraints.
- [U] Blog claims: about 700 experiments over two days with about 20 improvements; a Shopify CEO reported a 19% gain from 37 overnight experiments. Sources describe the target codebase differently.
- [S] Cerebras reports one overnight run where the agent abandoned the assigned experiment and started its own; it recommends tightly scoped loops.
- Relevance: a fixed per-experiment budget and a human-edited program file are cheap, portable controls. The "cheating" report is the practical warning for this project.

### #36 Claude Code skill-creator blog secondary coverage and similar guides [S]
- Multiple third-party sites (for example Pasquale Pillitteri's "Skills 2.0" guide, skills.sh listings, smartscope.blog) describe the same skill-creator feature set, with extra claims about blind A/B and trigger tuning.
- One third-party case study reports a rebuilt skill going from 17/23 to 23/23 assertions with about 1.2% more tokens. Single anecdote, not controlled.
- Relevance: consistent with #20. Only the Anthropic post (#20) is treated as primary.

---

# Part 2. Design lessons for a Claude Code research loop with self-improvement

These lessons follow from Part 1 and the constraints in AGENTS.md: private data stays out of Git and out of logs; no external transmission without consent; every change to the loop should be explainable and reversible.

## 2.1 What the loop may modify

Modifiable by the loop, on a branch, with gates (Lesson 2.2):
- Skill files (`SKILL.md` and small helper scripts) for research steps: search, extraction, verification-checklist writing. Evidence: #20, #14, and SkillWeaver (arXiv 2504.07079, snippet only).
- Subagent prompt templates and research-loop prompt text. Evidence: #10, #12, #13.
- Failure memory and playbook notes (see 2.5). Evidence: #15, #17, #18, #19.
- Workflow ordering (which step comes first, when to stop). Evidence: #9, #8.

Not modifiable by the loop without explicit human approval:
- Evaluation harness, holdout tasks, scoring scripts, and citation/quote verifiers. Evidence: #3 (objective hacking concern), #25 (poisoning), #26 (benchmark exploits).
- Settings, permission rules, hooks, `.claude/` configuration, and `CLAUDE.md` invariants. Evidence: #22 (self-written skills propagate), #25.
- `data/` (private research data), source PDFs, backups and restore code, and schema migrations. Evidence: AGENTS.md domain invariants.
- The loop's own success criteria. Evidence: #3 and #23 (self-evaluation is biased toward own score).

Rule: the loop can propose edits to the first group. It cannot edit the second group, and it cannot read holdout answers.

## 2.2 Gates

Use layered gates, cheapest first:
1. Deterministic checks: schema validation of memory records, file hashes, link and DOI resolution, quote-matches-source checks, and unit tests. No LLM involved. Evidence: AGENTS.md completion rule.
2. Holdout tasks: a fixed set of 10 to 20 research-loop tasks with stated properties (for example "every claim has a page number," "a refuted hypothesis yields a failure record with cause class"). Stored where the modifier agent is not permitted to read. Evidence: #3, #23 (archive and descendant results need held-out signal).
3. Blind comparison: a separate Claude subagent judges candidate vs. baseline outputs without knowing which is which. This is the pattern in #20. Evidence: #20.
4. Human promotion: a candidate is promoted only after a human reads the diff and the scores. Evidence: #3 (human oversight used in DGM experiments), AGENTS.md Sol gate.

Require a minimum effect size and a regression check on the holdout set before promotion, not a single high score. Evidence for overfitting risk: #4 (17% to 53% on a random subset, small N), #26 (benchmarks can be exploited).

## 2.3 Holdout evaluation

- Keep at least one suite the modifier never sees, including its scoring rubric.
- Re-run the holdout after every promotion (regression) and once a month with a fresh sample of tasks, to detect drift. Evidence: #20 (re-run after model updates), #26 (audit cycle).
- Track both accuracy and cost (tokens, wall-clock). Evidence: #20 (pass rate, time, tokens), #9 (cost reported), #23 (CPU cost matters).
- Keep benchmark-style tasks versioned: a change to a task invalidates older scores. Evidence: #3 (80 iterations; about 2 weeks per SWE-bench run, which is why task sets must be reused carefully).

## 2.4 Rollback

- One git branch per candidate change. Promotion is a merge after gates pass. Revert is a git revert, not an edit in place. Evidence: #35 (feature-branch loop), #3 (archive of versions, not overwrite).
- Keep an append-only archive of all candidates with their scores, including failed candidates. Evidence: #3 and #4 show that archive-based search outperforms search that keeps only the best; #23 shows descendant results matter.
- Never delete a failed candidate; mark it `retired` with a reason. Evidence: #23 (metaproductivity depends on descendant history).

## 2.5 Memory format

Recommended: markdown files with YAML frontmatter, one record per failure or insight, stored in a repository folder that contains no private text. Private research text stays in `data/` (ignored by Git).

Suggested fields:
- `id`, `created`, `source_run` (run id and file hashes, not private text)
- `task_type` (for example literature search, claim extraction, verification)
- `failure_class` (from a fixed taxonomy: missing evidence, wrong page label, overclaim, stale source, tool misuse, etc.)
- `symptom` (what was observed)
- `hypothesized_cause` (marked as a hypothesis)
- `rule` (the reusable action, one sentence)
- `scope` (when the rule applies and when it does not)
- `status`: `candidate` | `promoted` | `retired` | `contradicted`
- `validation`: holdout result id, date
- `applied_count`, `last_applied`, `last_validated`

Principles:
- Failure records are immutable. Derived rules can be updated, but they link to the records they came from. Evidence: #31 (note rewriting is risky), #19 (both successes and failures are useful).
- Cap the playbook size and retire rules that do not validate after a set period. Evidence: #18 (context collapse), #15 (context-window limit).
- Keep failure cause as a hypothesis, not a fact. Evidence: #19 (self-judged labels are noisy, see Part 4).

## 2.6 Process controls

- Fixed budget per loop: maximum tokens and maximum wall-clock per experiment or per self-improvement cycle. Evidence: #35 (fixed 5-minute budget), #3 (cost is the main limit).
- Scoped loop: the loop works on one clearly defined objective per cycle. Evidence: #35 (agent abandoned the assigned experiment).
- Adversarial check on the loop itself before each promotion: run the BenchJack-style checklist (is any gate gameable by the candidate's own text? does the candidate change the grader?). Evidence: #26, #25.

---

# Part 3. Concrete proposals

Each proposal lists evidence, cost, risk, confidence, and fit. Cost is relative to Claude Code subscription use (no paid API). Confidence is my judgment that the proposal will help this project, given the evidence.

Fit key: subscription = runs on Claude Code subscription; free tools = no paid services; no local model = no model downloads; gates = human approval gate configurable.

### P1. Failure-record memory with immutable records and derived rules
- What: each failed research step writes a record (Section 2.5). A curator subagent proposes rules from records. Rules are promoted only after holdout checks.
- Evidence: #19 (success and failure memory outperforms raw or success-only memory, claim [V]); #15 (insights from trial-and-error, [S]); #18 (playbook curation, [V]).
- Cost: low. One extra write per failure; a curator pass per session.
- Risk: self-judged failure labels are noisy; rule accumulation can bloat context.
- Confidence: high for the design, medium for measured gains (no numbers verified for this repo).
- Fit: subscription yes; free tools yes; no local model; gates yes (promotion requires human approval).

### P2. Holdout research-loop suite (fixed, versioned, hidden from the modifier)
- What: 10 to 20 tasks with checkable properties (for example, every claim has a page number, a contradicted hypothesis yields a failure record). Stored outside the modifier's readable scope. Versioned.
- Evidence: #3 and #23 (archive scores need held-out signal); #26 (exploits in benchmarks); #25 (poisoning of loop inputs).
- Cost: medium (authoring the tasks, then one suite run per candidate).
- Risk: holdout leaks if the modifier can read it; tasks become stale.
- Confidence: high.
- Fit: subscription yes (suite runs through Claude Code); free tools; no local model; gates yes.

### P3. Protected-surface policy enforced by Claude Code permissions
- What: deny the loop write access to the eval harness, `.claude/` settings, hooks, `CLAUDE.md` invariants, `data/`, and backup code. Use deny rules in settings, and review changes in these areas by hand.
- Evidence: #25 (poisoned benchmark steers self-evolution); #22 (self-written skills propagate); AGENTS.md data invariants.
- Cost: very low.
- Risk: over-restriction slows the loop; permissions must be kept current when files move.
- Confidence: high.
- Fit: subscription yes; free tools yes; no local model; gates yes (the deny list is the gate).

### P4. Skill edits gated by skill-creator evals and blind A/B
- What: any change to a research-loop skill runs the skill-creator benchmark on its evals, then a blind comparator against the previous version. Promote only if pass rate does not drop and token cost does not rise beyond a set bound.
- Evidence: #20 (pass rate, time, token tracking; blind A/B; article notes reliance on evals); #36 (single anecdote, not controlled).
- Cost: medium (each eval run costs subscription tokens).
- Risk: evals are the same kind of signal the modifier can game; blind A/B is only as good as its rubric.
- Confidence: medium-high.
- Fit: subscription yes (skill-creator is a Claude Code plugin per #20); free tools; no local model; gates yes.

### P5. Staged skill library with quarantine and imitation checks
- What: new auto-written skills go to a `quarantine/` folder, are not retrieved by the research loop until they pass the holdout suite and a human review, and are scanned for banner-like repeated code blocks or unexpected network/file calls before promotion.
- Evidence: #22 (self-poisoning rates 20.3% to 41.8% in an attack study, [S]); #14 (Voyager stores only successful, executable skills, [V] abstract, [S] body); SkillWeaver (arXiv 2504.07079, snippet only) tests and hones skills before reuse.
- Cost: low to medium (a scanner script plus review time).
- Risk: scanner may miss novel payloads; quarantine slows reuse.
- Confidence: high for the need, medium for the scanner's effectiveness.
- Fit: subscription yes; free tools (a simple script); no local model; gates yes.

### P6. Archive-based search with rollback over a small candidate set
- What: keep an archive of prompt or skill variants. Each cycle creates 3 to 5 candidate changes from one parent, evaluates them on the holdout suite, and keeps all records. Revert by git.
- Evidence: #3 (archive plus benchmark gating; 80 iterations at about 2 weeks per SWE-bench run, [V]); #4 (archive of versions and results, [V]); #8 (archive-guided meta search, [V]).
- Cost: high if scaled as in #3. Scaled down (3 to 5 candidates, 10 to 20 tasks): medium.
- Risk: cost; holdout overfitting; lineage can drift if promotion is automatic.
- Confidence: medium. The mechanism is validated in coding domains, not in research writing.
- Fit: subscription yes only at reduced scale (token budget must be capped); free tools; no local model; gates yes.

### P7. Descendant-based selection (clade metaproductivity) as an optional later step
- What: score a prompt or skill lineage by the performance of its descendants, not by its own score. Use only after P6 has produced enough lineage data.
- Evidence: #23 (metaproductivity–performance mismatch, CMP improves over DGM and SICA on SWE-bench Verified and Polyglot, [V] claims); the efficiency claim is [U].
- Cost: high (needs many descendants).
- Risk: complexity; likely not worth it at single-user scale.
- Confidence: low-medium for this project.
- Fit: subscription only at small scale; defer.

### P8. Reflective prompt optimization with a Pareto front over cost and quality
- What: for one research-loop prompt, sample real traces, reflect in natural language on failures, propose several prompt variants, and select along a Pareto front of (holdout accuracy, token cost, citation fidelity) rather than a single score.
- Evidence: #10 (GEPA, Pareto front and reflection, v2 abstract claims +6% avg over GRPO and up to 35x fewer rollouts, [V]); #13 (minibatch evaluation, [S]).
- Cost: medium (rollouts through Claude Code subagents).
- Risk: prompt overfitting to the holdout; multi-objective weights need human choice.
- Confidence: medium-high.
- Fit: subscription yes; free tools yes (GEPA code is open source per #10); no local model; gates yes.

### P9. Verifier audit before trusting any gain (BenchJack-style checklist)
- What: before each promotion, a checklist-driven review of the scoring scripts and rubrics: can a candidate's text satisfy the gate without doing the work? Does the candidate change the grader? Does any check accept output from the modifier as evidence? Run the adversarial step (a Claude subagent asked to find exploits) once per month and on each new gate.
- Evidence: #26 (219 flaws across 10 benchmarks, [S]); #3 (objective hacking, [V] for the general concern); #25 (poisoning, [V]).
- Cost: low to medium.
- Risk: adversarial agent can miss flaws; the process itself needs maintenance.
- Confidence: high.
- Fit: subscription yes; free tools; no local model; gates yes.

### P10. Session-end reflection pass with human review (sleep-time pattern)
- What: at the end of a research session, a reflection subagent reviews transcripts and writes candidate failure records and rules to a staging folder. A human reviews the staging folder at the start of the next session.
- Evidence: #33 (idle-time reflection, [S]); #34 (Letta Code reflection subagents, [S] docs); #35 (human-edited program file as control, [S]).
- Cost: low (one subagent per session).
- Risk: reflection may generate confident but wrong rules; mitigated by staging and review.
- Confidence: medium-high.
- Fit: subscription yes; free tools; no local model; gates yes (staging is the gate).

### P11. Memory ablation before retention (streaming evaluation)
- What: periodically run the research loop on a fixed task stream with and without the playbook/failure memory. Keep memory only if the with-memory run improves holdout results and does not increase cost beyond a bound.
- Evidence: #27 (Evo-Memory: streaming evaluation, many memory modules compared, [S]); #17 (curated vs. appended memory, [S]).
- Cost: medium (two runs per ablation).
- Risk: small N; noise; must fix seeds where possible.
- Confidence: medium.
- Fit: subscription yes (cost bounded by task count); free tools; no local model; gates yes.

### P12. Curation rules that prevent playbook collapse
- What: the playbook is updated only by additive edits with links to records, never by rewriting the whole file. A curator step deduplicates and retires rules that have not validated in N cycles. Cap the size.
- Evidence: #18 (brevity bias and context collapse; structured incremental updates, [V]); #31 (note rewriting risk, [S]).
- Cost: low.
- Risk: rule list grows; curation needs maintenance.
- Confidence: high.
- Fit: subscription yes; free tools; no local model; gates yes.

### P13. Fixed budget and scoped cycles
- What: each self-improvement cycle has a fixed token budget, a wall-clock cap, and one objective. Stop when the budget is spent. Record the budget used.
- Evidence: #35 (fixed 5-minute experiment budget; scoped-loop warning, [S]); #3 (runtime and API cost, [V]).
- Cost: very low.
- Risk: budgets may stop useful runs early; tune per task type.
- Confidence: high.
- Fit: subscription yes (caps usage); free tools; no local model; gates yes.

### P14. Deterministic citation and quote checks as the first gate
- What: before any LLM judge, check that each cited source has a resolvable URL or DOI, that each quoted string appears in the stored source text, and that page labels match the physical-page map (per AGENTS.md domain rules).
- Evidence: AGENTS.md domain invariants (physical page vs. printed label). External evidence is indirect: #26 and #3 show LLM judges can be gamed, so deterministic checks reduce that surface.
- Cost: low to medium (scripts).
- Risk: quote matching misses paraphrase; must not send private text to external services to check (use local scripts only).
- Confidence: high.
- Fit: subscription yes; free tools yes; no local model; gates yes.

### P15. Code-evolution patterns only for analysis scripts (optional, low priority)
- What: if the research loop writes analysis code (for example parsers, table extraction), use an AlphaEvolve-style evaluator for that code: an automatic scorer on a fixed test set, with a novelty filter as in #6.
- Evidence: #5 (automatic evaluators, [V]); #6 (novelty rejection, [S]); #7 (cascade evaluation, [S]).
- Cost: medium to high in runs.
- Risk: scope creep; no scorer exists for research prose.
- Confidence: low for this project's main work; medium for narrow code tasks.
- Fit: subscription yes at small scale; free tools (OpenEvolve is open source); no local model; gates yes. Defer unless a clear code-scoring task exists.

---

# Part 4. Conflicts and unverified claims

1. DGM hallucination and objective hacking: the widely reported story (agent removed detection markers; "Node 114" perfect score) comes only from secondary blogs. The arXiv text I read mentions a hallucination countermeasure investigation (Section 5) with details in Appendix H, which was cut off. Treat the marker-removal story as [U] until Appendix H is read.
2. DGM run cost: the text says a single SWE-bench run takes about 2 weeks and significant API costs (cost detail in Section E.1, not read). Gödel Agent's "$15 vs. $300" comparison is [U] (secondary only).
3. GEPA versions: v1 abstract says 10% average over GRPO on four tasks; v2 says 6% average over six tasks. Use v2 and cite it as v2.
4. Live-SWE-agent SWE-bench Verified: 75.4% (v1), 77.4% (v3), 79.2% (project summary with Claude Opus 4.5). Different configurations; not directly comparable.
5. AWM WebArena numbers: 22.5 points (v1 PDF), 51.1% relative (secondary), 35.6% success (README). These cannot all be the same metric. Unverified.
6. SkillWeaver WebArena gains: abstract says 31.8% relative; body says "25% to 38%." Check the full paper.
7. MIPRO benchmark count: v1 says five of six; v2 says five of seven. Use v2.
8. HGM efficiency: v3 says less CPU time (about 2.38x); a secondary summary says wall-clock. Metric not agreed.
9. AlphaEvolve availability: the 2025 DeepMind blog says not public, with an Early Access Program. A 2026 search snippet says generally available via Google Cloud (July 2026). Not verified on a primary Google page. The Google page I read is dated 2025.
10. Skill-creator features: the Anthropic post (#20) describes evals, benchmark mode, blind comparison, and description tuning. Third-party sites add a "max 5 iterations" loop and "four modes" (#36). Not in the primary post; not relied on here.
11. Hyperagents license: one third-party page says CC BY-NC-SA 4.0. Check the repository directly before any reuse. Also check the author list: a search snippet gives a different first author than the arXiv page fetched; the arXiv page was used.
12. Hyperagents 0.63 gain on unseen math grading: VentureBeat summary only [U].
13. Poisoning paper numbers: "28/30 or higher" contamination is from a snippet only [U]. The abstract says contamination "often persists" with no figures.
14. Dynamic Cheatsheet numbers: AIME doubling (secondary) and 9% GPQA-Diamond (README) both [U].
15. Karpathy autoresearch numbers (700 experiments, 20 improvements, 19% gain): [U], from blogs. Primary repository not opened.
16. TextGrad Nature publication date (2025-03-19): from the GitHub README only [U].
17. Voyager baselines (ReAct, Reflexion, AutoGPT): [S] from the body; the abstract only says "prior SOTA."
18. Mem0 and A-MEM: the LOCOMO and A-MEM quality claims are author claims; no independent replication in this report.
19. The SICA 17% to 53% figure is on a random subset of SWE-bench Verified. It is not the full benchmark.
20. Sleep-time compute 5x figure: secondary summary only [S].

Not verified at all (no primary page or no numbers): Meta Agent Search cost comparisons, ShinkaEvolve sample counts, OpenEvolve replication details, EVOMAL defense numbers, BenchJack counts.

---

# Part 5. URL index

Primary (opened or read this session):
- https://arxiv.org/abs/2310.02304 (#1 STOP)
- https://arxiv.org/abs/2505.22954 (#3 DGM)
- https://arxiv.org/html/2505.22954v3 (#3 DGM full text, partial)
- https://arxiv.org/abs/2504.15228 (#4 SICA)
- https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ (#5 AlphaEvolve)
- https://arxiv.org/abs/2408.08435 (#8 ADAS)
- https://arxiv.org/abs/2410.10762 (#9 AFlow)
- https://arxiv.org/abs/2507.19457 (#10 GEPA)
- https://arxiv.org/abs/2305.16291 (#14 Voyager)
- https://arxiv.org/abs/2510.04618 (#18 ACE)
- https://arxiv.org/abs/2509.25140 (#19 ReasoningBank)
- https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills (#20 skill-creator)
- https://arxiv.org/abs/2511.13646 (#21 Live-SWE-agent)
- https://arxiv.org/abs/2609.17817 (#25 Poisoned benchmarks)
- https://arxiv.org/abs/2510.21614 (#23 HGM)
- https://arxiv.org/abs/2603.19461 (#24 Hyperagents)
- https://arxiv.org/abs/2504.19413 (#32 Mem0)

Snippet-only (search results, not opened):
- https://arxiv.org/abs/2410.04444 (#2 Godel Agent)
- https://arxiv.org/abs/2509.19349 (#6 ShinkaEvolve)
- https://sakana.ai/shinka-evolve/ (#6)
- https://github.com/codelion/openevolve (#7 OpenEvolve)
- https://arxiv.org/abs/2406.07496 (#11 TextGrad)
- https://arxiv.org/abs/2309.16797 (#12 Promptbreeder)
- https://arxiv.org/abs/2406.11695 (#13 MIPRO)
- https://arxiv.org/abs/2308.10144 (#15 ExpeL)
- https://github.com/LeapLabTHU/ExpeL (#15)
- https://arxiv.org/abs/2409.07429 (#16 AWM)
- https://arxiv.org/abs/2504.07952 (#17 Dynamic Cheatsheet)
- https://github.com/suzgunmirac/dynamic-cheatsheet (#17)
- https://arxiv.org/abs/2608.25776 (#22 EVOMAL)
- https://arxiv.org/abs/2605.12673 (#26 BenchJack)
- https://github.com/benchjack/benchjack (#26, per search)
- https://arxiv.org/abs/2511.20857 (#27 Evo-Memory)
- https://arxiv.org/abs/2507.21046 (#28 Survey)
- https://arxiv.org/abs/2506.10943 (#29 SEAL)
- https://arxiv.org/abs/2310.08560 (#30 MemGPT)
- https://arxiv.org/abs/2502.12110 (#31 A-MEM)
- https://github.com/agiresearch/A-mem (#31)
- https://arxiv.org/abs/2504.13171 (#33 Sleep-time compute)
- https://docs.letta.com/letta-code/memory (#34 Letta)
- https://cerebras.ai/blog/how-to-stop-your-autoresearch-loop-from-cheating (#35 loop hygiene)
- https://github.com/facebookresearch/Hyperagents (#24, per search)
- https://github.com/metauto-ai/HGM (#23)
- https://github.com/jennyzzt/dgm (#3 code, per search)
- https://github.com/ShengranHu/ADAS (#8 code, per search)
- https://github.com/gepa-ai/gepa (#10 code, per search)
- https://github.com/OpenAutoCoder/live-swe-agent (#21 code, per search)
- https://github.com/google-research/reasoning-bank (#19 code, per search)
- https://github.com/ace-agent/ace (#18 code, per search)
- https://github.com/OneChainTech/dynamic-cheatsheet (#17, third-party README mirror; use suzgunmirac link instead)
- https://arxiv.org/abs/2507.19457v2 (#10 v2 version)
- https://arxiv.org/abs/2504.07079 (SkillWeaver; not listed as a numbered source, cited as secondary context in Part 4 item 6)

Note: SkillWeaver (arXiv 2504.07079) is referenced in Part 4 and in proposal P5. Its primary record is not in the numbered list; treat it as an additional snippet-only source.
