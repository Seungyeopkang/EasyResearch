# Autonomous / automated scientific research agent systems: scout report

Date of research: 2026-11-10. About 24 web searches and 20 page fetches were run. Items marked **UNVERIFIED** could not be checked against a primary source. Star counts are snapshots from the fetch date and vary across third-party sources.

## 1. System survey

### 1.1 Sakana AI Scientist v1
- Links: https://github.com/SakanaAI/AI-Scientist ; Sakana blog/paper referenced from the repo.
- Pipeline: idea generation (Semantic Scholar novelty check), experiments run through human-written code templates (NanoGPT, 2D Diffusion, Grokking; other templates are community-maintained), write-up via `launch_scientist.py`, LLM review (repo example uses gpt-4o-2024-05-13). Source: https://github.com/SakanaAI/AI-Scientist
- Loop: linear template-based experiments with reviewer feedback; no tree search.
- Human checkpoints: user launches runs, chooses models and experiments, runs `run_0` baseline per machine, and must disclose AI use in any manuscript. Source: same repo.
- Grounding: Semantic Scholar (or OpenAlex experimental) for literature and citation collection. Source: same repo.
- Failure modes (repo): "This codebase will execute LLM-written code"; reviewer models show positivity bias; success depends on template, model and idea complexity. Source: same repo.
- Cost claim: under $15 per paper with Claude Sonnet 3.5 (repo claim). Source: same repo.
- License: "The AI Scientist Source Code License" (Responsible-AI-License derivative). Stars about 15.0k, forks 2.1k (fetched).

### 1.2 Sakana AI Scientist v2 (arXiv 2504.08066)
- Links: https://arxiv.org/abs/2504.08066 ; https://github.com/SakanaAI/AI-Scientist-v2
- Paper: "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search" (Yamada, Lange, Lu, Hu, Lu, Foerster, Clune, Ha). Source: https://huggingface.co/papers/2504.08066
- Pipeline: ideation, then experiments via best-first tree search (BFTS), write-up, VLM feedback loop on figures. No human-written templates. Source: https://github.com/SakanaAI/AI-Scientist-v2 and https://huggingface.co/papers/2504.08066
- Loop engineering (repo `bfts_config.yaml`): `num_workers` parallel paths, `steps` cap on nodes, `num_drafts` independent root trees, `max_debug_depth` and `debug_prob` for debugging failing nodes. An experiment manager agent guides the search. Built on AIDE. Source: https://github.com/SakanaAI/AI-Scientist-v2
- Stopping: node/step budget. Cost about $15–20 per experiment run plus about $5 for write-up (repo, Claude 3.5 Sonnet). Source: same.
- Human checkpoints: topic file, config, running scripts, reviewing the tree visualization (`unified_tree_viz.html`). No approval gates documented. Source: same.
- Grounding: Semantic Scholar novelty check; rate limits reduce checking without an API key. Source: same.
- Evaluation: three fully autonomous manuscripts sent to an ICLR 2025 workshop; one exceeded the average human acceptance threshold per the authors. Source: https://huggingface.co/papers/2504.08066
- Failure modes (repo): lower paper-generation success than v1; some runs produce no PDF or review; Linux + NVIDIA GPU + CUDA required; run in a sandbox (Docker) because it executes LLM code. Source: https://github.com/SakanaAI/AI-Scientist-v2
- Workshop-experiment context: Sakana says the experiment was run with organizers' knowledge and UBC IRB approval; reviewer consent is not addressed in the source. Source: https://www.casrai.org/news/fully-ai-generated-papers-passing-peer-review-zochi-sakana
- License: the search summary said MIT, but the repo fetch did not confirm this, so it is **UNVERIFIED**. Stars about 7.5k, forks 1.0k (fetched).

### 1.3 Sakana AI "Agentic Scientist" / AI-Scientist-v3 (2026)
- Links: https://aiweekly.co/alerts/sakana-ai-open-sources-agentic-scientist-v3-with-alife-2026-paper ; arXiv 2610.18933 (per that article; **UNVERIFIED** directly).
- Claims: Apache 2.0; orchestrates Claude, Codex, Cursor, OpenCode, Gemini and Pi via headless CLI; six phases (task drafting, investigation, ablations, final evaluation, post-hoc analysis, paper generation); one paper accepted at ALIFE 2026. Source: same article.
- Key claim: cross-agent orchestration layer matters more than base model capability (ablations). No head-to-head benchmark against v1/v2 published in the sources. Source: same article.
- Caveat: article is a secondary aggregator, so license and paper need checking on GitHub and arXiv.

### 1.4 Agent Laboratory (Schmidgall)
- Links: https://github.com/SamuelSchmidgall/AgentLaboratory ; arXiv 2501.04227 (https://arxiv.org/abs/2501.04227v1).
- Pipeline: three phases, literature review, experimentation, report writing, with specialized LLM agents. Source: repo fetch above.
- Loop: linear phases with checkpointing in `state_saves` for resume. No tree search. Source: repo fetch.
- Human checkpoints: "Co-Pilot mode" toggled by a YAML flag. Source: repo fetch.
- Grounding: README says agents use arXiv, Hugging Face, Python and LaTeX; the specific literature API is **UNVERIFIED**. Source: repo fetch.
- Models: OpenAI (o1, o1-preview, o1-mini, gpt-4o, o3-mini) and DeepSeek. Source: repo fetch.
- Claimed results: o1-preview best; 84% cost reduction vs prior methods (preprint claim). Source: https://infodocket.com/?p=165076
- Limitations (README): pdflatex needed; "a lot of room to improve"; not studied in other languages. Source: repo fetch.
- License: MIT. Stars about 5k per a third-party tracker (**UNVERIFIED** on GitHub). Source: https://www.sourcepulse.org/projects/1833580

### 1.5 AgentRxiv
- Link: https://arxiv.org/html/2503.18102v1 ; project site https://agentrxiv.github.io
- Design: a shared preprint server where Agent Laboratory instances upload and retrieve reports; similarity-based search over prior work. Source: arXiv abstract and project site.
- Result: three parallel labs reached 79.8% on MATH-500 (authors' claim). Source: arXiv.
- Relevance to a personal workspace: an explicit "prior work memory" pattern, with uploads to a shared archive.
- No separate repo found; code is in the Agent Laboratory repo.

### 1.6 AI-Researcher (HKUDS)
- Links: https://github.com/HKUDS/AI-Researcher ; arXiv https://arxiv.org/html/2505.18705v1 ; NeurIPS 2025 paper https://papers.nips.cc/paper_files/paper/2025/file/0d904d300a105809a2114d727851e759-Paper-Conference.pdf
- Pipeline (repo fetch): Resource Collector, Resource Filter, Idea Generator; Design, Implementation, Validation, Refinement phases; Writer Agent drafts hierarchically.
- Literature sources: arXiv, IEEE Xplore, ACM DL, Google Scholar, GitHub, Hugging Face (Semantic Scholar not mentioned). Source: repo fetch.
- Human-in-the-loop: not described. User gives an idea (Level 1) or reference papers (Level 2); no approval gates mentioned. Gradio GUI available. Source: repo fetch.
- Evaluation: Scientist-Bench, with evaluator agents scoring novelty, comprehensiveness, theoretical foundation, result analysis, writing. Source: repo fetch.
- Warnings (repo): a hardcoded API key in an example script; the technical report is forthcoming. Source: repo fetch.
- Venue: NeurIPS 2025 Spotlight (third-party blog; proceedings PDF appears in search). Source: https://blog.brightcoding.dev/2026/05/31/neurips-2025-spotlight-ai-researcher-cuts-research-time-from-months-to-hours
- License: not stated in repo page. Stars about 5.9k, forks 729 (fetched).

### 1.7 Google AI co-scientist
- Links: https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/ ; DeepMind post https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/
- Architecture (fetched): built on Gemini 2.0; supervisor agent plus Generation, Reflection, Ranking, Evolution, Proximity, Meta-review agents. Source: research.google blog.
- Loop: generate, review, rank by Elo-based pairwise tournament, evolve top candidates back into the tournament; Proximity agent clusters similar ideas. Source: research.google blog and search summaries.
- Elo: correlated with GPQA-diamond accuracy (authors). The authors themselves call Elo an auto-evaluation metric, not ground truth. Source: research.google blog.
- Human checkpoints: scientists supply seed ideas or natural-language feedback. Source: research.google blog.
- Grounding: web search tools; authors name better literature review and factuality checking as needs. Source: research.google blog.
- Validation: AML drug repurposing (KIRA6 reduced viability in one cell line), liver fibrosis organoid results, a cf-PICI re-discovery. Small expert study (11 goals). Source: research.google blog.
- Status: a May 2026 DeepMind post says the work was published in Nature and offered as "Hypothesis Generation" (**UNVERIFIED** beyond the search summary). Source: https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/
- Closed system; no OSS repo.

### 1.8 FutureHouse / Edison Kosmos
- Links: https://arxiv.org/abs/2511.02824 ; https://edisonscientific.com/articles/announcing-kosmos ; https://www.hpcwire.com/aiwire/2025/11/07/futurehouse-spins-out-edison-scientific-launches-kosmos-ai-for-research/
- Pipeline (abstract, fetched): cycles of parallel data analysis, literature search, hypothesis generation; synthesis into reports. Averages 200 rollouts, about 42,000 lines of code and 1,500 papers per run.
- Loop engineering: structured world model shared between data-analysis and literature agents; runs up to 12 hours or 20 cycles. Source: arXiv abstract.
- Grounding: every report statement cited to code or primary literature. Source: arXiv abstract.
- Accuracy: 79.4% of statements judged accurate by independent scientists, so about 20.6% were judged inaccurate. Source: arXiv abstract.
- Claimed value: collaborators estimated a 20-cycle run equals about 6 months of their own work (estimate). Source: arXiv abstract.
- Discoveries: seven highlighted; three reproduce unpublished or preprint findings the system did not access at runtime. Source: arXiv abstract.
- Commercial: via Edison Scientific; reported at $200/run (secondary news, **UNVERIFIED**). Source: https://www.hpcwire.com/aiwire/2025/11/07/futurehouse-spins-out-edison-scientific-launches-kosmos-ai-for-research/
- Closed system.

### 1.9 Robin (FutureHouse)
- Not verified in this session. Searches did not return a primary source. **UNVERIFIED**; mention only as a prior FutureHouse system.

### 1.10 Denario
- Links: https://github.com/AstroPilot-AI/Denario ; arXiv 2510.26887 (https://huggingface.co/papers/2510.26887)
- Pipeline (repo fetch): `set_data_description` → `get_idea` → `get_method` → `get_results` → `get_paper(journal=...)`, with LaTeX output in a journal style. Built on AG2 and LangGraph, with cmbagent as research backend.
- Human checkpoints: `set_idea`, `set_method`, `set_results` let the user supply intermediate content. Source: repo fetch.
- Grounding: not detailed in the fetched content; **UNVERIFIED** beyond "literature checks" in the paper summary.
- Limitations: depends on external LLM APIs; no dedicated limitations section. Source: repo fetch.
- License: GPL-3.0. Stars about 620 (fetched).

### 1.11 data-to-paper (Technion Kishony lab)
- Links: https://github.com/Technion-Kishony-lab/data-to-paper ; arXiv 2404.17605 (per search summary; **UNVERIFIED** in full).
- Pipeline: data exploration, literature search and ideation, analysis and interpretation, step-by-step writing. Source: repo fetch.
- Human-in-the-loop: Autopilot or Copilot App; Copilot lets users set goals, request reviews, rewind to earlier steps, record and replay runs. Source: repo fetch.
- Traceability: "data-chaining" lets numeric values in the manuscript be click-traced to the code lines that produced them. This is the strongest anti-hallucination mechanism in the surveyed set. Source: repo fetch.
- Limitations: "NOT error-proof"; simple goals and datasets only; code runs on the user's machine. Source: repo fetch.
- License: MIT. Stars about 834 (fetched).

### 1.12 MLR-Copilot
- Not verified in this session. **UNVERIFIED**; no source fetched.

### 1.13 CycleResearcher / CycleReviewer (Weng, Zhu et al., ICLR 2025)
- Links: https://arxiv.org/pdf/2411.00816 ; https://iclr.cc/virtual/2025/poster/32074 ; project page https://wengsyx.github.io/Researcher (sources disagree on the code URL; the arXiv abstract's URL is malformed).
- Design: RL policy model (CycleResearcher) with a reward model (CycleReviewer) that simulates peer review; models from 12B to 123B. Source: arXiv.
- Results: CycleReviewer reduced MAE in predicting scores by 26.89% vs individual humans (authors). Generated papers scored 5.36 in simulated review vs 5.24 for human preprints and 5.69 for accepted papers. Source: arXiv.
- Key caveat: the paper states its generated experimental results are fabricated and do not reflect real experiments. Source: arXiv.
- Relevance: reviewer-as-reward is a risk; a self-graded loop can overfit to the reviewer model.
- License and stars: **UNVERIFIED**.

### 1.14 DeepScientist (Weng, Zhu et al., arXiv 2509.26603)
- Links: https://arxiv.org/abs/2509.26603 ; ICLR 2026 poster https://iclr.cc/virtual/2026/poster/10008492
- Design: frames search as Bayesian optimization with a cumulative "Findings Memory" balancing exploration and exploitation; multi-agent; synthesis agent writes the paper. Source: arXiv summary via search.
- Scale: over 20,000 GPU hours; about 5,000 ideas, about 1,100 validated experimentally. Three frontier AI tasks (agent failure attribution, LLM inference acceleration, AI text detection). Source: ICLR poster listing (search summary).
- Claims: surpasses human SOTA by 183.7% and 1.9% on two tasks (listing truncated). Authors' claims; no independent evaluation found.
- Bottleneck (paper): low success rate of implementation and verification.
- Code release: promised; status **UNVERIFIED**.

### 1.15 AlphaEvolve (DeepMind) and OpenEvolve
- AlphaEvolve paper: "Mathematical exploration and discovery at scale," arXiv 2511.02864 (Nov 2025), 67 problems; rediscovered best-known in most, improved several. Source: https://www.alphaxiv.org/abs/2511.02864v1 and https://spectrum.ieee.org/deepmind-alphaevolve
- Hit rates differ across sources (IEEE: 20% new best, 5% worse than known). Treat as **UNVERIFIED** until checking the paper.
- OpenEvolve (community): https://github.com/codelion/openevolve ; Apache-2.0; about 7.7k stars (fetched). MAP-Elites plus island populations; LLM ensemble; errors fed back to next prompts; seeded for reproducibility. Source: repo fetch.
- OpenEvolve warnings: no sandbox or human-review step documented; evaluator code is user-supplied and its isolation is not described. Source: repo fetch.

### 1.16 ShinkaEvolve (Sakana)
- Links: https://github.com/SakanaAI/ShinkaEvolve ; https://arxiv.org/abs/2509.19349 ; https://sakana.ai/shinka-evolve/
- Components (repo fetch): weighted parent selection with islands (2 islands, migration every 10 generations); code-novelty rejection sampling with embedding similarity threshold 0.99 (up to 3 attempts); UCB bandit LLM ensemble with cost-aware coefficient. Source: repo fetch.
- Results: circle packing with 150 samples (authors). Source: arXiv via search.
- Safety: Docker or SLURM only for isolation; `max_api_costs` cap; headless mode fetches a package via npx at runtime. Source: repo fetch.
- License: Apache-2.0. Stars about 1.5k (fetched). Accepted ICLR 2026 (search summary).

### 1.17 NovelSeek / InternAgent (Shanghai AI Lab)
- Links: https://arxiv.org/html/2505.16938v3 ; https://github.com/Alpha-Innovator/InternAgent (partial release per HF news).
- Design: specialized agents (survey, coding, idea innovation, assessment); closed loop from idea to experiment to feedback; 12 scientific tasks. Source: arXiv via search.
- Claims: beats DOLPHIN on all evaluated tasks (authors). Newer InternAgent-1.5 mentioned; code status **UNVERIFIED**.

### 1.18 freephdlabor (Yale, ltjed)
- Links: https://github.com/ltjed/freephdlabor ; arXiv 2510.15624
- Architecture (repo fetch): ManagerAgent orchestrates IdeationAgent, ExperimentationAgent, WriteupAgent, ReviewerAgent, ProofreadingAgent; file-based workspace shared among agents; ReAct-style, agents choose next step; `--resume` restarts from saved workspace; all LLM calls logged to JSONL.
- Human checkpoints: callback server; user types `interrupt`, then instructions that either modify the current task or start a new one. Non-blocking. Source: repo fetch.
- Security warnings (repo): `.env` with keys in file listing; callback server with no auth, and the README suggests binding to 0.0.0.0. Source: repo fetch.
- Claim "first multi-agent system to produce peer-reviewed research end-to-end" is unsubstantiated on the page. Source: repo fetch.
- License: MIT. Stars about 720 (fetched).

### 1.19 AIDE / AIDE ML (Weco AI)
- Links: https://arxiv.org/abs/2502.13138 ; https://github.com/WecoAI/aideml
- Loop: code solution tree; drafts, improve, debug; metric feedback prunes. Defaults: 20 steps, 5 drafts. Source: repo fetch.
- Results: "Exceeds % of humans" 51.38% on tabular Kaggle tasks (paper, via search). Source: search summary of arXiv.
- Warnings: model IDs not validated; transient errors retried up to five times. Source: repo fetch.
- License: MIT. Stars about 1.6k (fetched).
- Used by AI-Scientist-v2 as its tree search base.

### 1.20 Zochi (Intology)
- Links: https://www.casrai.org/news/fully-ai-generated-papers-passing-peer-review-zochi-sakana ; https://rayscuration.blogspot.com/2025/06/zochi-achieves-main-conference.html (blog, secondary)
- Claim: "Tempest: Automatic Multi-Turn Jailbreaking of LLMs with Tree Search" accepted to ACL 2025 main proceedings, meta-review 4/5, top 8.2% (Intology writeup). Source: casrai page and search summary.
- Human role: figures, citation formatting, minor fixes, rebuttals written by humans; humans are authors of record. Source: casrai page.
- Controversy: one search summary reports criticism of workshop submissions without disclosure; the fetched article does not confirm this. Treat as **UNVERIFIED**.
- Closed system.

### 1.21 Agents4Science 2025
- Links: https://arxiv.org/abs/2511.15534 ; https://agents4science.stanford.edu ; Science News article https://www.sciencenews.org/article/science-conference-test-ai-agents
- Setup: Oct 22, 2025 virtual conference; AI agents as primary authors and reviewers; humans as co-authors and co-reviewers. Source: arXiv abstract.
- Numbers: 314 submitted, 48 accepted (about 15%) per Science News; the organizers' paper reports 315 / 48 per search summary. Source: Science News.
- Failures reported: hallucinated references, needs heavy oversight (search summary); a repeated wrong date for a fee waiver caught by a human. Source: Science News. Hallucinated references is supported only by search summary: **UNVERIFIED** in the primary paper.
- Quote: a reviewer said papers were technically correct but neither interesting nor important, and technical skill can mask weak judgment. Source: Science News.
- Requirement: each accepted paper must describe human-AI collaboration per stage. Source: Science News.

### 1.22 PaperBench (OpenAI)
- Links: https://openai.com/index/paperbench ; https://proceedings.mlr.press/v267/starace25a.html ; code https://github.com/openai/preparedness (per paper footnote)
- Task: replicate 20 ICML 2024 Spotlight/Oral papers; 8,316 rubric items; LLM judge. Source: ICML PMLR page and search summary.
- Result: best 21.0% with Claude 3.5 Sonnet and open-source scaffolding (search summary). Source: search summary of OpenAI paper.
- ICML 2025 published. Source: PMLR.

### 1.23 MLE-bench (OpenAI)
- Links: https://arxiv.org/abs/2410.07095 ; https://github.com/openai/mle-bench
- 75 offline Kaggle competitions; o1-preview with AIDE gets at least bronze in 16.9%. Autonomous runs up to 24 hours. Source: arXiv summary via search.
- Includes plagiarism/cheating monitoring. Source: arXiv summary.

### 1.24 ScienceAgentBench (OSU)
- Links: https://arxiv.org/abs/2410.05080 ; https://osu-nlp-group.github.io/ScienceAgentBench
- 102 tasks from 44 peer-reviewed papers across four disciplines; ICLR 2025. Agents not ready for end-to-end automation. Source: arXiv summary via search.
- Contamination control: annotations only on Hugging Face; evaluation harness added to OpenHands. Source: same.

### 1.25 ResearchBench
- Links: https://arxiv.org/abs/2503.21248 (v2 HTML at https://arxiv.org/html/2503.21248v2)
- Three sub-tasks: inspiration retrieval, hypothesis composition, hypothesis ranking; 1,386 papers, 2024 only. LLMs strong at inspiration retrieval (GPT-4o included ground-truth inspiration in top 4% 45.7% of the time). Source: arXiv via search.
- Findings Mode accepted to ACL 2026 Findings (search summary).

### 1.26 OpenAGS, OpenResearch (alphaXiv), BioAgents, AutoScientists, EvoScientist
- Mentioned in 2026 aggregator pages only. All **UNVERIFIED** at primary-source level.
- OpenResearch (alphaXiv): framework that turns coding agents into research agents, GitHub Trending Sept 2026. Source: https://aitoolly.com/ai-news/article/2026-09-19-alphaxiv-launches-openresearch-on-github-trending-to-transform-ai-coding-agents-into-research-assist
- AutoScientists (mims-harvard, Harvard): shared global state recording proposals, experiments, results, failures and the current best. Source: https://www.besthub.dev/articles/autoscientists-open-source-harvard-s-self-organizing-agents-enable-long-term-autonomous-research-c6516f82cdd0
- BioAgents (bio-xyz): semi-autonomous and fully autonomous modes; some sub-agents unreleased. Source: https://scripps-ai-enablement.github.io/sci-ai-enabler/autonomous-science/systems/deep-research-bioagents.html

### 1.27 Not checked
- Robin, MLR-Copilot, AgentRxiv standalone repo, Sakana v1 Nature paper, AI co-scientist Nature paper text.

## 2. Cross-cutting failure modes (evidence)

1. **Coding failures dominate.** 42% of AI Scientist v1 experiments failed from coding errors (Beel et al.). https://arxiv.org/abs/2502.14297
2. **Hallucinated numbers.** Some manuscripts contained numbers that did not match the actual experiment outcomes. Same source.
3. **Novelty checks are weak.** Established ideas (micro-batching for SGD) were labeled novel. Same source.
4. **Citations are thin and old.** Median 5 citations per paper; only 5 of 34 from 2020 or later. Same source.
5. **Structural errors.** Missing figures, repeated sections, placeholder text ("Conclusions Here"). Same source.
6. **Self-grading is not validation.** Beel et al. say the system cannot detect errors in its own results. Same source. Google also notes Elo is an automated metric, not ground truth. https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/
7. **Reviewer-model bias.** Sakana notes LLM reviewers show positivity bias. https://github.com/SakanaAI/AI-Scientist
8. **Conference results mixed.** Agents4Science: fabricated references and "technically correct but not important" feedback. https://www.sciencenews.org/article/science-conference-test-ai-agents
9. **Code execution risk.** Multiple repos require sandboxing (AI-Scientist, AI-Scientist-v2, data-to-paper, ShinkaEvolve, freephdlabor).
10. **Secrets in repos.** AI-Researcher has a hardcoded key in an example; freephdlabor's `.env` appears in the listing. https://github.com/HKUDS/AI-Researcher ; https://github.com/ltjed/freephdlabor
11. **Overstated claims.** CycleResearcher's paper says its experimental results are fabricated (https://arxiv.org/pdf/2411.00816), and the freephdlabor "first peer-reviewed end-to-end" claim is not substantiated (https://github.com/ltjed/freephdlabor).

## 3. Design lessons for a personal research workspace

Target loop: topic -> evidence search -> iterative problem finding -> method improvement -> contribution statement.

### 3.1 Stage design
- **Topic and scoping:** human-gated. Systems that start from a human-written topic file (AI-Scientist-v2) or a dataset plus objective (Kosmos, data-to-paper) show that the scope decision is where human input matters most.
- **Evidence search:** automate retrieval, but store every hit with ID, source and query. Kosmos ties each claim to a citation; data-to-paper ties each number to code. Copy that pattern: each claim in the workspace has a source pointer or is marked hypothesis.
- **Iterative problem finding:** automate with a bounded budget. Use an idea tournament (Google co-scientist) or Bayesian-style memory of failed and promising branches (DeepScientist). Store negative results, since they prevent re-exploring dead ends.
- **Method improvement:** automate inside a sandbox with a fixed evaluator and a node/step budget (AIDE defaults: 20 steps, 5 drafts; AI-Scientist-v2 uses `steps`, `num_workers`, debug depth). Keep the evaluator and data out of the agent's write access.
- **Contribution statement:** human-gated. Every system that produces papers still needs a human to decide the claim. The Agents4Science and Beel et al. results both point here.
- **Write-up:** automate drafting only after numbers are frozen and traceable.

### 3.2 Automate vs gate
| Stage | Automate | Human gate |
|---|---|---|
| Topic/scope | suggest | decide |
| Literature search | retrieve, dedupe, extract claims | verify top claims |
| Idea generation | generate many, rank | pick directions |
| Method/experiment | run in sandbox with budget | approve before compute spend, approve code changes touching data |
| Results | compute, plot, log | interpret |
| Contribution | draft candidates | final wording and novelty claim |
| Write-up | draft from frozen results | edit and cite-check |

### 3.3 Avoiding hallucinated novelty
1. **Novelty must be an explicit search, not a model judgment.** Record the exact queries and the papers returned; require at least one "closest prior work" entry with a link before any novelty claim. Beel et al. show this is the failure that gets through.
2. **Use the citation graph, not only a search query.** Pull references and citing papers of the closest 5-10 works (Semantic Scholar or OpenAlex). Flag claims whose key phrase appears in a retrieved abstract.
3. **Require a contradiction check.** Ask the model to find the strongest prior work that contradicts the idea, and store the result even when it is negative.
4. **Traceability per number.** Adopt data-to-paper's data-chaining: each reported value links to code and a raw output file. Refuse to export a number without a link.
5. **Never let an LLM reviewer be the only gate.** CycleReviewer-style reward loops can optimize for the reviewer. Use reviewers as triage, and require a human decision on the contribution statement.
6. **Keep a record of failures.** Negative results and failed runs are evidence for the novelty check and prevent re-exploration.
7. **Pin the evaluation.** Do not let the agent modify the evaluator or its data (ShinkaEvolve and OpenEvolve both depend on a user-supplied evaluator for scoring).

### 3.4 Engineering takeaways
- Budget everything: steps, drafts, cost cap (ShinkaEvolve `max_api_costs`), wall-clock (Kosmos 12 h).
- Checkpoint and resume (Agent Laboratory `state_saves`, freephdlabor `--resume`).
- Non-blocking human interrupts with an audit log (freephdlabor callback; data-to-paper Copilot rewind/replay).
- Log every LLM call (freephdlabor `agent_llm_calls.jsonl`).
- Shared workspace as memory (freephdlabor, AgentRxiv, AutoScientists).
- Run generated code in Docker, restrict network, store API keys outside repos.

## 4. Summary table (stars are approximate, fetched on 2026-11-10 unless noted)

| System | Link | License | Stars | Loop | Human gate | Main failure evidence |
|---|---|---|---|---|---|---|
| AI Scientist v1 | github.com/SakanaAI/AI-Scientist | AI Scientist Source Code License | ~15.0k | linear, templates | launch, disclose | 42% coding failures (arXiv 2502.14297) |
| AI Scientist v2 | github.com/SakanaAI/AI-Scientist-v2 | UNVERIFIED (search said MIT; repo says the AI Scientist license family) | ~7.5k | BFTS | config, review | lower success than v1 |
| Agentic Scientist v3 | aiweekly article | Apache 2.0 (secondary) | UNVERIFIED | 6 phases | UNVERIFIED | none published |
| Agent Laboratory | github.com/SamuelSchmidgall/AgentLaboratory | MIT | ~5k (UNVERIFIED) | 3 phases, checkpoints | Co-Pilot flag | "room to improve" |
| AgentRxiv | arxiv 2503.18102 | in Agent Lab repo | in Agent Lab | shared archive | none | UNVERIFIED |
| AI-Researcher | github.com/HKUDS/AI-Researcher | not stated | ~5.9k | idea-design-impl-validate-refine | none | hardcoded key in example |
| Google AI co-scientist | research.google blog | closed | n/a | Elo tournament, evolution | seed/feedback | auto-eval only |
| Kosmos | arxiv 2511.02824 | closed | n/a | cycles, world model | not described | 20.6% statements inaccurate |
| Denario | github.com/AstroPilot-AI/Denario | GPL-3.0 | ~620 | staged API | set_* overrides | depends on LLM APIs |
| data-to-paper | github.com/Technion-Kishony-lab/data-to-paper | MIT | ~834 | autopilot / copilot | copilot rewind | "NOT error-proof" |
| CycleResearcher | arxiv 2411.00816 | UNVERIFIED | UNVERIFIED | RL vs reviewer | none | fabricated experimental results (own paper) |
| DeepScientist | arxiv 2509.26603 | promised | UNVERIFIED | Bayesian memory | none | implementation success low |
| OpenEvolve | github.com/codelion/openevolve | Apache-2.0 | ~7.7k | MAP-Elites islands | none | evaluator isolation undocumented |
| ShinkaEvolve | github.com/SakanaAI/ShinkaEvolve | Apache-2.0 | ~1.5k | islands, UCB ensemble | none | network fetch at runtime |
| InternAgent (NovelSeek) | github.com/Alpha-Innovator/InternAgent | UNVERIFIED | UNVERIFIED | closed loop | UNVERIFIED | partial open source |
| freephdlabor | github.com/ltjed/freephdlabor | MIT | ~720 | ManagerAgent | interrupt callback | unauth callback server |
| AIDE ML | github.com/WecoAI/aideml | MIT | ~1.6k | solution tree | none | model ID not validated |
| Zochi | casrai article | closed | n/a | UNVERIFIED | human rebuttals | disclosure dispute (UNVERIFIED) |
| Agents4Science | arxiv 2511.15534 | n/a | n/a | AI authors/reviewers | co-author/co-reviewer | hallucinated references (UNVERIFIED in primary) |
| PaperBench | openai.com/index/paperbench | see openai/preparedness | n/a | replication | none | best 21.0% |
| MLE-bench | github.com/openai/mle-bench | see repo | n/a | benchmark | none | 16.9% bronze |
| ScienceAgentBench | arxiv 2410.05080 | OSU-NLP repo | n/a | benchmark | none | agents not ready end-to-end |
| ResearchBench | arxiv 2503.21248 | n/a | n/a | benchmark | none | UNVERIFIED |

## 5. Not verified / open items
- Robin, MLR-Copilot, AgentRxiv standalone repo: no primary source.
- Sakana AI-Scientist-v3 paper (arXiv 2610.18933) and license: secondary source only.
- Agents4Science hallucinated-reference claim: the Science News article supports fabricated references in one line only; the organizers' paper was not fetched in full.
- AlphaEvolve hit rates differ between sources.
- Google co-scientist Nature publication date and details: UNVERIFIED beyond a DeepMind blog summary.
- Zochi controversy: the search summary and the fetched article disagree.
- Kosmos pricing: secondary source.
