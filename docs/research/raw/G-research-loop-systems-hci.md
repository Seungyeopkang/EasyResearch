# G. Research-loop orchestration and HCI research-ideation tools (2024-2026)

- Date of research: 2026-11-10
- Scope: orchestration mechanics of AI-scientist and literature-agent systems; human intervention points; grounding; ranking; measured results. Plus HCI / mixed-initiative ideation tools and literature-search loops.
- Method: WebSearch (standard mode) for ~40 queries, then WebFetch on primary arXiv / vendor pages for 12 sources. Several secondary summaries (Emergent Mind, Moonlight, Liner, aitopics, bohrium, blogs) were used only to locate papers and are tagged [S] or [U]. No full-text PDFs were read end to end; claims that depend on paper bodies are tagged [S].
- Verification legend:
  - [V] = primary page opened (arXiv abstract/HTML or vendor blog) and the claim confirmed there.
  - [S] = search-result snippet or secondary summary only.
  - [U] = could not confirm (conflicting or missing).
- Limits: "Measured results" below are self-reported by the authors unless marked otherwise. Numbers quoted from snippets may be truncated or mis-attributed; check the source before citing externally.

---

## Part 1 - Source records

Numbering is used in all later parts. Quotes: none used; all findings are paraphrased.

### S1. Towards an AI co-scientist / "Accelerating scientific discovery with Co-Scientist"
- Authors/org: Juraj Gottweis, Vivek Natarajan et al. (51 authors), Google.
- Venue/date: arXiv:2502.18864, submitted 26 Feb 2025; v2 dated 29 Jun 2026; arXiv comment lists Nature (2026). Title differs between v1 and the current abstract page.
- URL: https://arxiv.org/abs/2502.18864 ; blog https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist
- Tag: [V] (abstract, version, journal reference). Agent details and Elo mechanics [S].
- Findings:
  - Multi-agent Gemini system: a supervisor-style planner assigns specialist agents (generation, reflection, ranking, proximity, evolution, meta-review) through an asynchronous task queue [S for agent list; V for "multi-agent, asynchronous task execution" in abstract].
  - Ranking is a tournament: hypotheses are pairwise-debated and given Elo-style ratings; "tournament evolution" improves hypotheses across rounds [V abstract for tournament; Elo mechanics [S]].
  - Authors state automated evaluation shows gains with more test-time compute [V abstract]; no figures in the abstract [V].
  - Validation: AML drug-repurposing candidates tested in vitro; KIRA6 cited as an example of reduced viability at clinically relevant concentrations [V abstract for AML validation; KIRA6 detail [S] from the blog].
  - Elo is an auto-evaluation not grounded in independent ground truth; the authors' claim that higher Elo correlates with correct GPQA answers is self-generated [S].
  - Human expert comparison was small (about 11 research goals) per the blog [S].
  - Human role: scientists supply objectives and run wet-lab validation; the abstract does not describe a human review gate inside the loop [V].
- Relevance to EasyResearch: Closest analogue to the ranking and evolution stages. The Elo-tournament design is an alternative to our 1-5 absolute critique scores (see Part 3, idea I2). Their "human only at the end" design matches O5 only loosely: our per-iteration pause is stronger.

### S2. Kosmos: An AI Scientist for Autonomous Discovery
- Authors/org: Edison Scientific (FutureHouse spin-out) and collaborators.
- Venue/date: arXiv:2511.02824 (Nov 2025); v2 is the version fetched.
- URL: https://arxiv.org/abs/2511.02824 ; https://edisonscientific.com/articles/announcing-kosmos
- Tag: [V] (abstract: rollouts, world model, citation statement, 79.4%, 20-cycle note).
- Findings:
  - A structured world model stores the outputs of parallel data-analysis and literature-search agents, and each cycle folds task summaries back into it [V for shared world model; S for "up to ten tasks per cycle"].
  - Reports cite every statement to code or primary literature (traceability) [V].
  - Independent scientists judged 79.4% of report statements accurate, so about one in five was inaccurate [V].
  - Scale: over 200 agent rollouts per run and up to 12 hours [V abstract]; snippet gives 166 data-analysis rollouts, 42,000 lines of code, 1,500 papers read [S]. Conflict, see Part 4.
  - Scaling of findings tested only up to 20 cycles [V].
  - Several headline discoveries reproduced earlier or unpublished human findings [V] (abstract caveat; the developers also say so [S]).
- Relevance to EasyResearch: The shared structured state across stages is a model for our per-iteration state. The 79.4% statement-accuracy figure argues strongly against trusting "evidence key present" as proof of support (O8, O11).

### S3. Language agents achieve superhuman synthesis of scientific knowledge (PaperQA2 / ContraCrow / WikiCrow)
- Authors/org: Skarlinski, Cox, Laurent, Braza, Hinks, Hammerling, Ponnapati, Rodriques, White (FutureHouse).
- Venue/date: arXiv:2409.13740 (v1 10 Sep 2024, v2 26 Sep 2024).
- URL: https://arxiv.org/abs/2409.13740 ; https://www.futurehouse.org/paperqa
- Tag: [V] for abstract (ContraCrow counts, "matches or exceeds" expert performance); tool/loop details [S].
- Findings:
  - Agent loop: paper search (keyword query), citation traversal (uses citation graph to add sources), per-chunk relevance summarization and reranking, then answer with citations [S for loop; the snippet describes RCS contextual summarization].
  - ContraCrow: flagged 2.34 +/- 1.99 contradictions per paper on a random biology subset; about 70% validated by human experts [V abstract; sample of 93 papers per search snippet [S]].
  - LitQA2 (248 MC questions): reported 85.2% precision vs 73.8% for PhD experts, accuracy 66.0% vs 67.7% [S; abstract claims superhuman but this detail is from snippet].
  - WikiCrow summaries judged more accurate than human-written Wikipedia articles [V abstract].
- Relevance to EasyResearch: Citation traversal (forward/backward) is a cheap recall lever our search stage lacks (idea I4). Per-chunk relevance scoring with an LLM is a grounding pattern we do not use; our term-overlap screen is weaker.

### S4. Robin: A multi-agent system for automating scientific discovery
- Authors/org: FutureHouse and collaborators.
- Venue/date: arXiv:2505.13400 (May 2025).
- URL: https://arxiv.org/pdf/2505.13400
- Tag: [S].
- Findings:
  - Loop: hypothesis generation, experiment proposal, result interpretation, hypothesis revision. Crow and Falcon are PaperQA2-based literature agents; Finch is a data-analysis agent [S].
  - Dry AMD: ripasudil proposed and validated; second-round wet-lab data show a large fold change [S; the snippet gives 7.5x and 1.75x from different analyses, see Part 4].
  - Mechanism follow-up: RNA-seq suggested ABCA1 involvement [S].
  - A critical reading notes the paper does not report how many false-positive candidates were generated before the validated one [S].
- Relevance to EasyResearch: Shows a human-in-the-loop experimental gate at the end of an agent loop. We could add a "what would falsify this" field to each problem (idea I9).

### S5. The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search
- Authors/org: Yamada, Lange, Lu, Hu, Lu, Foerster, Clune, Ha (Sakana AI and collaborators).
- Venue/date: arXiv:2504.08066, 10 Apr 2025.
- URL: https://arxiv.org/pdf/2504.08066 ; https://github.com/SakanaAI/AI-Scientist-v2
- Tag: [S] (search snippets; arXiv page not fetched).
- Findings:
  - Removes human code templates; progressive agentic tree search managed by an experiment-manager agent [S].
  - Three autonomous manuscripts submitted to an ICLR 2025 workshop; average reviewer score 6.33/10 reported; one accepted, with origin disclosed to the program committee [S].
  - Tree search means many branches are explored and pruned, the opposite of our single linear loop [S].
- Relevance to EasyResearch: Tree search with an experiment manager is a larger design than we need. The useful piece is branch pruning by a score and an explicit record of branches (idea I1).

### S6. Agent Laboratory: Using LLM Agents as Research Assistants
- Authors/org: Schmidgall et al. (AMD and Johns Hopkins).
- Venue/date: arXiv:2501.04227 (Jan 2025).
- URL: https://arxiv.org/pdf/2501.04227
- Tag: [S].
- Findings:
  - Co-pilot mode (human provides input at literature review, experiment plan, and report draft) scored higher than fully autonomous mode on most metrics [S].
  - Autonomous outputs showed weak clarity and soundness when judged against expert expectations [S].
  - Quality varied by backend; one blog reports gpt-4o averaging 2.6/5 on experimental quality [S; unverified secondary].
  - Human raters found co-pilot useful and most continued using it [S].
- Relevance to EasyResearch: Direct evidence for O5 (human review at stage boundaries beats autonomy).

### S7. AI-Researcher: Autonomous Scientific Innovation (HKUDS)
- Authors/org: Jiabin Tang, Lianghao Xia, Zhonghang Li, Chao Huang (HKUDS).
- Venue/date: arXiv:2505.18705 (24 May 2025).
- URL: https://arxiv.org/abs/2505.18705 ; https://github.com/HKUDS/AI-Researcher
- Tag: [S].
- Findings:
  - Pipeline: literature review, idea generation, implementation, validation, manuscript writing [S].
  - Scientist-Bench has guided-innovation (Level 1 implementation) and open-ended tasks, with peer-reviewed reference papers [S].
  - Self-reported quality "approaches human level" [S]; a third-party re-review gives it 3.25 vs Jr. AI Scientist 5.75 in the latter's table [S].
- Relevance to EasyResearch: A full-pipeline baseline for comparison; its quality claims are self-reported.

### S8. DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively
- Authors/org: Weng et al.
- Venue/date: arXiv:2509.26603 (30 Sep 2025); ICLR 2026 poster listed.
- URL: https://arxiv.org/html/2509.26603v1 ; https://github.com/ResearAI/DeepScientist
- Tag: [S].
- Findings:
  - Frames discovery as goal-driven Bayesian optimization; a growing "Findings Memory" stores unverified hypotheses and validated results so dead ends are not re-explored [S].
  - Reported ~5,000 unique ideas, ~1,100 experimentally validated, and gains over human SOTA on three tasks (agent failure attribution, LLM inference acceleration, AI text detection) [S; the percentage figures conflict across snippets, see Part 4].
- Relevance to EasyResearch: The findings-memory concept (idea I1) maps directly onto our per-iteration feedback carry-over.

### S9. InternAgent (formerly NovelSeek): When Agent Becomes the Scientist
- Authors/org: Shanghai AI Laboratory.
- Venue/date: arXiv:2505.16938 (22 May 2025); v3 Jul 2025 renamed InternAgent.
- URL: https://arxiv.org/abs/2505.16938v3
- Tag: [S].
- Findings:
  - Closed loop: idea generation, method, execution, feedback; 12 tasks reported [S].
  - Reaction yield 27.6% to 35.4% in 12 hours; 2D segmentation precision 78.8% to 81.0% in 30 hours [S; secondary listing].
  - InternAgent-1.5 claims wet-lab coordination; not verified [U].
- Relevance to EasyResearch: Mainly evidence that closed loops need an executable evaluator; we have none, so our loop is necessarily a proposal loop.

### S10. AlphaResearch: Accelerating New Algorithm Discovery with Language Models
- Authors/org: Yu, Feng, Zhao, He, Zhang, Cohan.
- Venue/date: arXiv:2511.08522 (11 Nov 2025).
- URL: https://arxiv.org/abs/2511.08522
- Tag: [S].
- Findings:
  - "Dual research environment": a reward model screens proposals before any code is written; proposals below a threshold (reported 5.5/10) are dropped to save compute [S].
  - Reward model reported 72% accuracy on unseen ICLR 2025 papers vs 53% for GPT-5 (medium) and 65% for human annotators [S].
  - Companion benchmark AlphaResearchComp; authors say beating experts on open-ended problems remains a challenge [S].
- Relevance to EasyResearch: A pre-filter gate before expensive stages is an idea we can reuse cheaply (I3). The reward model itself would be a new model: rule out under our constraints.

### S11. Jr. AI Scientist and Its Risk Report
- Authors/org: Atsuyuki Miyai et al. (University of Tokyo).
- Venue/date: arXiv:2511.04583 (Nov 2025); TMLR 02/2026 per listing.
- URL: https://arxiv.org/abs/2511.04583
- Tag: [S].
- Findings:
  - Starts from a baseline paper with its code and LaTeX, identifies limitations, proposes and tests an extension, writes a paper [S].
  - Review-score table: AI-Researcher 3.25 vs Jr. AI Scientist 5.75 [S].
  - The authors' own risk report: on raw outputs they found fabricated auxiliary results, mis-citation, method overfitting, and superficial science [S].
- Relevance to EasyResearch: Explicit risk taxonomy for an automated loop; supports logging and per-claim checks (I7, I11).

### S12. The More You Automate, the Less You See: Hidden Pitfalls of AI Scientist Systems
- Authors/org: Ziming Luo, Atoosa Kasirzadeh, Nihar B. Shah (CMU).
- Venue/date: arXiv:2509.08713 (Sep 2025; v2 Dec 2025); NeurIPS 2025 AI4Science spotlight per search [S].
- URL: https://arxiv.org/abs/2509.08713
- Tag: [V] (abstract and HTML).
- Findings:
  - Four failure modes: inappropriate benchmark selection, data leakage, metric misuse, post-hoc selection bias [V].
  - Tested two open-source systems (named as Agent Laboratory and The AI Scientist v2 in secondary summaries [S]); failures include silent synthetic-data creation or subsampling not disclosed in the paper [S].
  - Trace logs and generated code reveal failures that the final paper hides; they recommend mandating those artifacts [V].
  - No failure counts are given in the abstract [V].
- Relevance to EasyResearch: Strongest argument for a full audit trail per iteration (I11) and for a "source of every number" check.

### S13. Evaluating Sakana's AI Scientist: Bold Claims, Mixed Results, and a Promising Future?
- Authors/org: Joeran Beel, Min-Yen Kan, Moritz Baumgart.
- Venue/date: arXiv:2502.14297 (Feb 2025; v3 Oct 2025); SIGIR Forum 2025 [S].
- URL: https://arxiv.org/abs/2502.14297
- Tag: [S].
- Findings:
  - Generated papers averaged about five citations each, mostly old (5 of 34 cited works from 2020 or later) [S].
  - Cost roughly $6-15 per paper with about 3.5 hours of human involvement [S].
  - 5 of 12 proposed experiments (42%) failed due to coding errors; some that ran gave misleading results [S].
  - Novelty checks were unreliable: established ideas (e.g., micro-batching for SGD) were labeled novel [S].
- Relevance to EasyResearch: Concrete failure numbers for LLM novelty labels (O7) and for citation quality (O8).

### S14. Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers
- Authors/org: Chenglei Si, Diyi Yang, Tatsunori Hashimoto (Stanford).
- Venue/date: arXiv:2409.04109 (6 Sep 2024); ICLR 2025 poster [S].
- URL: https://arxiv.org/abs/2409.04109
- Tag: [V] (abstract).
- Findings:
  - Over 100 NLP researchers wrote and blindly reviewed ideas; AI ideas judged more novel than expert ideas (p < 0.05) and slightly weaker on feasibility [V].
  - Authors name LLM self-evaluation failure and lack of generation diversity as open problems; they note LLM reviewers agreed with humans less than humans agreed with each other [V abstract for the first two; the agreement point [S]].
  - Proposed follow-up: have researchers actually execute ideas [V].
  - Search snippets give 79 experts and 49 ideas per condition; not verified in the abstract [U].
- Relevance to EasyResearch: Justifies O7 (don't label novelty as a verdict) and O1's "critique" step as weak.

### S15. The Ideation-Execution Gap: Execution Outcomes of LLM-Generated versus Human Research Ideas
- Authors/org: Chenglei Si, Tatsunori Hashimoto, Diyi Yang (Stanford).
- Venue/date: arXiv:2506.20803 (25 Jun 2025).
- URL: https://arxiv.org/abs/2506.20803
- Tag: [V].
- Findings:
  - 43 expert researchers executed randomly assigned ideas (expert-written or LLM-generated); each spent over 100 hours and wrote a 4-page paper [V].
  - After execution, LLM ideas dropped significantly more than human ideas on novelty, excitement, effectiveness, and overall score (all four p < 0.05 as reported) [V; effect sizes not in abstract].
  - Ranking flips: human ideas often scored higher after execution [S/V summary].
- Relevance to EasyResearch: The single most important caveat for O1's "contributions" stage. Ideas that look good on paper before execution are not reliable. Supports a feasibility checklist (I8) and a "smallest test" field.

### S16. Holzner et al., meta-analysis on human-GenAI collaboration and idea diversity
- Authors/org: Holzner et al.
- Venue/date: arXiv:2505.17241 (2025).
- URL: https://arxiv.org/abs/2505.17241
- Tag: [S].
- Findings: Pooled Hedges' g of about -0.86 for diversity reduction under human-GenAI collaboration; six observations from four studies; heterogeneous and mostly text tasks with GPT-4 [S].
- Relevance: Warning that AI-assisted ideation can narrow the idea space; supports diversity checks (I9).

### S17. Deng, Brucks, Toubia: LLM idea fixation and knowledge partitioning
- Venue/date: arXiv:2602.20408 (Feb 2026).
- URL: https://arxiv.org/abs/2602.20408
- Tag: [S].
- Findings: LLMs fixate on early outputs and pool knowledge into one distribution; CoT reduces fixation; personas help partition knowledge; combining both gave the highest diversity, above humans in their test [S]. Repeated independent sessions converge on similar themes [S].
- Relevance: Cheap diversity levers that need no new model (I9).

### S18. OpenNovelty: LLM-powered agentic system for verifiable scholarly novelty assessment
- Venue/date: arXiv:2601.01576 (Jan 2026).
- URL: https://arxiv.org/abs/2601.01576
- Tag: [S].
- Findings: Retrieves real prior papers, requires verbatim quotes from both papers for any refutation; run on 500+ ICLR 2026 submissions as "preliminary analysis" with no established accuracy [S].
- Relevance: Shows the verbatim-evidence pattern for novelty; reinforces O7 (show evidence, not a verdict).

### S19. SchNovel / RAG-based novelty benchmark (Lin, Peng, Fang, 2025)
- Venue/date: 2025 (aclanthology preprint setup 2025.aisd-main.5 as "Evaluating and Enhancing LLMs for Novelty Assessment in Scholarly Publications") [S].
- URL: https://arxiv.org/pdf/2409.16605
- Tag: [S].
- Findings: Benchmark of 15,000 arXiv pairs where newer = more novel (weak proxy); RAG method reported to beat baselines [S].
- Relevance: Shows the field lacks a reliable novelty ground truth; the proxy is weak.

### S20. Originality study with graph-based retrieval (Mostafa et al.)
- Venue/date: arXiv:2602.06054v3 (May 2026) [S].
- URL: https://arxiv.org/html/2602.06054v3
- Tag: [U] (results not read).
- Relevance: Candidate reading for O7 reliability numbers.

### S21. ResearchAgent: Iterative Research Idea Generation over Scientific Literature with LLMs
- Authors/org: Jinheon Baek, Sujay Kumar Jauhar, Silviu Cucerzan, Sung Ju Hwang.
- Venue/date: arXiv:2404.07738 (Apr 2024; rev. Feb 2025); NAACL 2025 Long [S].
- URL: https://arxiv.org/abs/2404.07738
- Tag: [V] (abstract).
- Findings:
  - Starts from a core paper; expands via an academic graph; adds concepts from an entity-centric knowledge store [V].
  - Multiple LLM reviewing agents give feedback on problem, method, and experiment design; ideas are revised iteratively [V].
  - Reviewer criteria are elicited from human judgments by prompting and the reviewers are human-preference aligned [V].
  - Evaluation: novelty, clarity, validity judged by humans and models across disciplines; no numbers in abstract [V]; diminishing returns after a few cycles [S].
- Relevance to EasyResearch: Closest published match to our iterate-with-critique design. Their criteria are human-elicited; ours are not, which is a gap to fix (I5).

### S22. SciMON: Scientific Inspiration Machines Optimized for Novelty
- Authors/org: Qingyun Wang, Doug Downey, Heng Ji, Tom Hope. ACL 2024.
- URL: https://arxiv.org/abs/2305.14259 (v5)
- Tag: [S].
- Findings: Retrieves inspirations from related papers and loops on novelty: compares ideas to prior papers and updates until novel enough [S]. Human comparison: ground-truth ideas rated higher in technical level and novelty in 85% of comparisons [S].
- Relevance: Explicit novelty-optimization loop against retrieved prior work (the same mechanism as our contribution-vs-prior-work step).

### S23. Chain of Ideas (CoI): Revolutionizing Research via Novel Idea Development with LLM Agents
- Authors/org: Long Li et al. (Alibaba DAMO Academy).
- Venue/date: arXiv:2410.13185 (Oct 2024; v5 Oct 2024 per fetch); ICLR 2025 / EMNLP 2025 Findings noted [S/U].
- URL: https://arxiv.org/abs/2410.13185 ; code https://github.com/DAMO-NLP-SG/CoI-Agent
- Tag: [V] (abstract: chain structure; cost; "consistently outperforms"); construction details [S].
- Findings:
  - Organizes retrieved literature into chains that follow a field's progression; several chains from different perspectives [S].
  - An LLM predicts future directions; a novelty-checker agent compares drafts with literature and revises [S].
  - Idea Arena evaluation protocol claimed to align with human preference; no numbers in abstract [V].
  - Minimum cost of about $0.50 per candidate idea with experiment design [V].
- Relevance: Shows chain-of-literature construction as a grounding device for problems (I4). Cost reference for a cloud-LLM budget.

### S24. Nova: An Iterative Planning and Search Approach to Enhance Novelty and Diversity of LLM Generated Ideas
- Authors/org: Xiang Hu, Hongyu Fu, et al. (incl. Zhenzhong Lan).
- Venue/date: arXiv:2410.14255 (Oct 2024); Findings of ACL 2025 as "NOVA" [S].
- URL: https://arxiv.org/abs/2410.14255
- Tag: [V] (abstract numbers) and [S] (3-round limit from snippet quoting the paper).
- Findings:
  - Iterative planning of which external knowledge to retrieve next; 3.4x as many unique novel ideas vs no-planning baseline; at least 2.5x more top-rated ideas vs prior SOTA in a Swiss-tournament evaluation over 170 seed papers [V].
  - Pipeline: generation, iterative refinement, completion [S].
  - No further gain after about 3 iterations; no reward function in planning [S].
- Relevance: Direct evidence for the iteration cap (O5, max 3) and for planning retrieval instead of only generating ideas (I4, I6).

### S25. MOOSE-Chem: Large Language Models for Rediscovering Unseen Chemistry Scientific Hypotheses
- Authors/org: Zonglin Yang et al.
- Venue/date: arXiv:2410.07076 (Oct 2024; v6 Oct 2025); ICLR 2025 [S].
- URL: https://arxiv.org/abs/2410.07076 ; code https://github.com/ZonglinY/MOOSE-Chem
- Tag: [S].
- Findings: Three subtasks: retrieve inspirations, compose hypotheses from them, rank hypotheses. 51 post-2024 chemistry papers as a benchmark with PhD-annotated hypotheses; claims rediscovery with high similarity to ground truth; uses pre-2024 knowledge cutoff to limit contamination [S].
- Relevance: The retrieve-compose-rank decomposition maps to our stages; the contamination argument is a useful evaluation idea.

### S26. Scideator: Human-LLM Compound System for Scientific Ideation through Facet Recombination and Novelty Evaluation
- Authors/org: Marissa Radensky, Simra Shahid, et al. (incl. Tom Hope, Daniel S. Weld).
- Venue/date: arXiv:2409.14634 (first 23 Sep 2024; v7 16 May 2026 per fetch). Earlier title "Scideator: Human-LLM Scientific Idea Generation Grounded in Research-Paper Facet Recombination".
- URL: https://arxiv.org/abs/2409.14634
- Tag: [V] (abstract, v7 date, retrieve-then-rerank, facet-grounded classifier, creativity-support result).
- Findings:
  - Extracts purposes, mechanisms, and evaluations facets from user-supplied papers; users recombine facets; generation grounded in those facets [V].
  - Novelty checker: retrieve-then-rerank over facets; classifier gives a verdict with explanation and facet-level suggestions for improvement [V/S].
  - Within-subjects user study (22 CS researchers per snippet) found significantly more creativity support than a same-backbone baseline without facet modules [V for significance; N from snippet [S]].
  - Snippet reports the checker agrees with human novelty ratings much better than a prior LLM-based method (more than 10x on one measure, about 13% higher on another) [S; not in fetched abstract].
- Relevance: The facet structure (I7) is directly reusable without a new model. Their verdict-style novelty checker conflicts with O7, but they pair it with explanations and facet-level suggestions, which we can copy without giving a score.

### S27. IdeaSynth: Iterative Research Idea Development Through Evolving and Composing Idea Facets with Literature-Grounded Feedback
- Authors/org: Kevin Pu, K. J. Kevin Feng, Tovi Grossman, et al. (Allen AI collaborators).
- Venue/date: CHI 2025 (DOI 10.1145/3706598.3714057); arXiv:2410.04025 (v2 Jul 2025).
- URL: https://arxiv.org/abs/2410.04025 ; https://kevinpjk.github.io/assets/pdf/ideasynth_chi_2025.pdf
- Tag: [V] (abstract: N=20 lab, N=7 field, more alternatives and more detail vs baseline).
- Findings:
  - Ideas are facets (problem, method, evaluation, contribution) shown as canvas nodes; users branch, vary, and compose them [V].
  - Lab study (20 participants: 12 HCI, 8 NLP) vs strong LLM baseline: participants explored more alternatives and added more detail [V].
  - Field deployment (7 participants) on real projects at varied stages; no quantitative deployment result [V].
  - LLM feedback is literature-grounded on user-supplied papers [V abstract; mechanism [U]].
- Relevance: Strongest HCI evidence for facet-based human control over LLM drafting; supports the idea of a human-editable facet view between stages.

### S28. CoQuest: Exploring Research Question Co-Creation with an LLM-based Agent
- Authors/org: Yiren Liu et al. (UIUC/collaborators).
- Venue/date: CHI 2024 (DOI 10.1145/3613904.3642698); arXiv:2310.06155.
- URL: https://arxiv.org/abs/2310.06155 ; code https://github.com/yiren-liu/coquest
- Tag: [S].
- Findings:
  - Three-panel interface (RQ flow editor, paper graph visualizer, AI thoughts) [S].
  - Breadth-first vs depth-first agent initiative (within-subject, 20 HCI researchers): breadth-first judged more creative and trustworthy at task end; depth-first RQs rated more creative during the task [S].
  - Effect on experience varied with researcher background [S].
- Relevance: Directly informs a "breadth vs depth" toggle at the review point (I8).

### S29. Synergi: A Mixed-Initiative System for Scholarly Synthesis and Sensemaking
- Venue/date: arXiv:2308.07517 (2023).
- URL: https://arxiv.org/pdf/2308.07517
- Tag: [S].
- Findings: Builds on user-curated threads; uses citation graphs and GPT-4 to expand threads and generate outlines; domain experts rated Synergi outlines most helpful vs Threddy and a ChatGPT-4 baseline [S].
- Relevance: Evidence that user-curated seeds plus citation expansion beat plain LLM chat for outlines.

### S30. Threddy / Relatedly / PaperWeaver (HCI literature-review tools)
- Threddy: Kang, Chang, Kim, Kittur (arXiv:2208.03455, 2022). Within-subject, 8 participants vs Google Docs. Saved clips into threads; recommended articles from threads [S].
- Relatedly: Palani et al., CHI 2023 (arXiv:2302.06754). Within-subject, 15 participants. Experts rated Relatedly outlines higher; users opened significantly more paragraphs and papers with same time and papers [S]. Re-ranks paragraphs as users read and highlights unexplored dissimilar content [S].
- PaperWeaver: Lee, Kang, Chang, Siangliulue, CHI 2024 (arXiv:2403.02939). LLM infers interests from collected papers and explains relevance of recommendations; 15 participants; better understanding and triage [S].
- Relevance: Consistent theme: explain why a paper is relevant to the user's own collection. Supports showing the link to seed papers for each suggested item.

### S31. Scim: Intelligent Skimming Support for Scientific Papers
- Authors/org: Raymond Fok, Hita Kambhamettu, Luca Soldaini, Jonathan Bragg, Kyle Lo, Andrew Head, Marti Hearst, Daniel Weld (IUI 2022).
- URL: https://arxiv.org/pdf/2205.04561
- Tag: [S].
- Findings: Pre-LLM; highlights salient sentences by rhetorical facet; 12-participant diary study with NLP-experienced readers over about nine days [S].
- Relevance: Highlights salient sentences by facet. Pattern usable for our evidence sentence selection (I6) instead of term overlap. Not an LLM study. The user's query mentioned Scim as an LLM-era tool; the search did not find one [U].

### S32. OpenScholar: Synthesizing Scientific Literature with Retrieval-augmented LMs
- Authors/org: Akari Asai et al. (25 authors), Allen AI / UW.
- Venue/date: arXiv:2411.14199 (21 Nov 2024).
- URL: https://arxiv.org/abs/2411.14199 ; https://openscholar.allen.ai/paper
- Tag: [V] (abstract and listed results).
- Findings:
  - Datastore of 45M open-access papers with trained retrievers and an 8B LM; iterative self-feedback to refine drafts; loop round count not in abstract [V].
  - ScholarQABench: OpenScholar-8B beats GPT-4o by 5% and PaperQA2 by 7% on correctness; adding the datastore and loop raises GPT-4o correctness by 12% [V].
  - GPT-4o hallucinated citations 78-90% of the time vs OpenScholar citation accuracy said to match human experts [V].
  - Experts preferred OpenScholar-8B responses over expert-written ones 51% of the time, and OpenScholar-GPT4o 70% [V].
- Relevance: Strongest measured evidence that unverified LLM citations fail badly and that a retrieval-grounded self-feedback loop can fix a lot of it (O8, O11). Their datastore approach is not free to replicate; the loop pattern is.

### S33. STORM and Co-STORM (Stanford OVAL)
- Venue/date: STORM arXiv:2402.14207 (2024); Co-STORM arXiv:2408.15232 (Aug 2024) [S for STORM ID].
- URL: https://arxiv.org/abs/2408.15232 ; https://github.com/stanford-oval/storm
- Tag: [V] (Co-STORM abstract).
- Findings:
  - Co-STORM: LM agents discuss a topic while the user observes or steers; a dynamic mind map organizes gathered information; a cited report is produced from the discourse [V].
  - Co-STORM beat baselines on discourse and report quality; human evaluation: 70% of participants preferred it over search engine, 78% over RAG chatbot [V].
  - STORM's perspective-guided question asking uses survey of similar articles to diversify questions [S].
- Relevance: Human steering during the loop (not just at the end) and a visible shared map of what the system has found (I6, I9).

### S34. AstaBench / Asta agents (Ai2)
- Authors/org: Allen Institute for AI.
- Venue/date: Ai2 blog and arXiv paper (2025); astabench 0.3.1 update noted.
- URL: https://allenai.org/blog/astabench
- Tag: [V] (blog).
- Findings:
  - Over 2,400 problems across literature understanding, code/execution, data analysis, end-to-end discovery [V].
  - Asta v0 scored 53.0%; ReAct with gpt-5 scored 43.3%; budget ReAct (claude-3-5-haiku) 20% at about $0.03 per problem; data analysis: no agent above 34% [V].
  - ScholarQA-CS2: Asta Scholar QA, Elicit, SciSpace Deep Review each about 85% or higher [V].
  - Paper Finder more than double ReAct on PaperFindingBench [V].
  - 57 agents across 22 classes evaluated [V].
- Relevance: Cost-per-problem and per-task reporting is a model for us to measure our own loop (I10). Confirms that end-to-end discovery remains weak.

### S35. Undermind (iterative search with citation trails)
- Venue/date: product; secondary reviews 2024-2025.
- URL: https://aarontay.substack.com/p/undermindai-different-type-of-ai-agent (blog; secondary); library reviews in PMC12352444.
- Tag: [S] / [U] for accuracy numbers.
- Findings: Successive searches over Semantic Scholar with citation-trail reading; company claims about 2% miss rate for relevant papers; librarian reviews report a completeness estimate of 87-100% and an estimate of 93% recall after 144 papers analysed; no independent benchmark found; the main limit is non-reproducible search strategy [S/U].
- Relevance: Iterative recall-oriented search with citation snowballing. The reproducibility criticism matters for our trace design (I11).

### S36. LitSearch: A Retrieval Benchmark for Scientific Literature Search
- Authors/org: Ajith et al. (Princeton).
- Venue/date: EMNLP 2024 main (arXiv:2407.18940).
- URL: https://arxiv.org/abs/2407.18940
- Tag: [S].
- Findings: 597 queries; BM25 vs dense retrievers: 24.8 absolute recall@5 gap; LLM reranking adds 4.4% to best dense retriever; commercial search tools lag best dense retriever by about 32 points [S].
- Relevance: Our term-overlap screen behaves like BM25 at best; the gap suggests better retrieval is worth more than better abstract sentence selection (I6).

### S37. DeepResearch Bench
- Authors/org: Mingxuan Du et al. (USTC et al.).
- Venue/date: arXiv:2506.11763 (Jun 2025); ICLR 2026 poster [S].
- URL: https://arxiv.org/abs/2506.11763 ; https://github.com/Ayanami0730/deep_research_bench
- Tag: [S].
- Findings: 100 expert-written tasks across 22 fields (50 English, 50 Chinese); RACE (reference-based report quality) and FACT (citation count and accuracy); claimed human-agreement numbers from a secondary summary [S/U].
- Relevance: Ready-made citation-accuracy metric (FACT) for evaluating our evidence keys.

### S38. Systematic-review LLM screening evidence (SESR-Eval and related 2025 studies)
- Venue/date: SESR-Eval arXiv:2507.19027 (Jul 2025); other 2025 preprints [S].
- URL: https://arxiv.org/pdf/2507.19027
- Tag: [S].
- Findings: SESR-Eval targets about 0.95 recall with about 0.50 precision (reviewers check about half of included papers); a 2024 GPT-3.5/4 study reported F1 0.60, precision 0.69, recall 0.76 [S]; recall is usually high, precision is the cost; a 2025 ISPOR poster reported 83% recall at 56% precision with a fine-tuned GPT-4o [S, conference abstract]. Chain-of-thought with few-shot examples gave the best precision-recall balance in one 2025 prompting study [S].
- Relevance: Recall-first screening with human sign-off on the rest; supports a tunable threshold (I10) rather than a fixed top-k.

### S39. Elicit systematic-review evaluations (vendor and independent)
- URL: https://elicit.com/blog/how-we-evaluated-elicit-systematic-review ; medRxiv 2026.02.25.26347053 (non-peer-reviewed noninferiority study) [S].
- Tag: [S].
- Findings: Vendor reports 94-99% extraction accuracy vs manual and 96.9% sensitivity / 92.5% specificity for abstract screening; another Elicit page shows 93.6% recall, 62.8% specificity [S, inconsistent]. Independent 2025 preprint: high-accuracy mode lowered value matches to 77% [S]. A 2026 medRxiv noninferiority study: AI-assisted extraction noninferior and about 25 minutes faster [S]. Secondhand report of Lau et al. (2025): sensitivity fell to 37.9% with real systematic-review queries [U].
- Relevance: Evidence that human second review remains needed; supports a per-stage "accept/verify" gate.

### S40. Literature-grounded hypothesis and idea generation (other 2025-2026 items found)
- Note: These were located only in search snippets and are listed for follow-up. Not used for verdicts.
  - Google/Edison/FutureHouse "Robin" (S4) and "Kosmos" (S2) covered above.
  - Holzner et al. (S16), Deng et al. (S17), OpenNovelty (S18) covered above.
  - Hypothesis generation with novelty loops (SciMON, S22) covered above.
  - Undermind (S35) covered above.
- Tag: [S].

---

## Part 2 - Verdicts on O1, O5, O7, O8, O11

### O1. Fixed stage order: plan_queries -> search -> screen -> problems -> methods -> contributions -> critique
**Verdict: Partly supported.**

Evidence for:
- Staged decomposition is common and works. MOOSE-Chem uses three subtasks (retrieve inspirations, compose, rank) [S25]. Nova uses three stages and plans retrieval iteratively [S24]. ResearchAgent refines problem, method, and experiment in a loop with reviewing agents [S21]. Chain of Ideas builds chains then drafts ideas and checks novelty [S23].
- Planning retrieval is a useful stage on its own: Nova's iterative retrieval planning produced 3.4x more unique novel ideas than its no-planning baseline [S24].

Evidence against or limiting:
- The better-performing systems in 2025 do not use a single fixed linear order. Co-scientist uses a supervisor with asynchronous agents and a tournament [S1]. Kosmos uses parallel agents writing to a shared world model [S2]. AI Scientist-v2 uses tree search with pruning [S5]. DeepScientist uses a memory of findings across cycles [S8]. So the fixed order is simpler, not state of the art.
- Errors are not recoverable in a fixed order. If queries are poor, every later stage inherits the miss. Undermind and PaperQA2 both use citation traversal during search, which our search lacks [S3, S35].
- The critique stage is last, so it cannot cause re-search except via next queries. Luo et al. show that failures cluster in benchmark choice, leakage, metric misuse, and post-hoc selection [S12]: our stage list has no step that checks these for contributions.
- The "screen" step with term overlap is weaker than BM25-level retrieval per LitSearch (24.8 points recall gap between BM25 and dense retrieval) [S36].

Risks: a 7-stage local-8B chain has many failure points; an error in problems (stage 4) can drop all downstream output silently. Recommend stage-level checks that return a reason (e.g., "0 valid evidence keys") rather than silently dropping problems.

### O5. Human review pause after each iteration; feedback carries forward; max 3 iterations; human decides what to save
**Verdict: Supported.**

Evidence for:
- Co-pilot beats autonomy in Agent Laboratory (human input at literature, plan, report stages) [S6].
- Co-STORM lets users steer during the discussion and reports a 70% / 78% preference over search and RAG chat [S33].
- CoQuest and IdeaSynth show that human control over the breadth/depth and facet level improves perceived creativity and idea expansion [S27, S28].
- Luo et al. recommend trace logs for human review, implying review points should show the process, not only outputs [S12].
- Iteration cap: Nova reports no continued gain after about 3 rounds [S24]; ResearchAgent reports diminishing returns after a few cycles [S21]. A cap of 3 is consistent with the literature.

Evidence against or limiting:
- The "human decides what to save" rule is supported by Beel et al.'s finding that generated papers are not reliably distinguishable from human work and that novelty labels are unreliable [S13].
- Human review at a pause can still be superficial; Kosmos found 20.6% of statements inaccurate even with traceability [S2]. A review UI should show evidence sentences next to each claim, not only the claim.
- No source measures the effect of a per-iteration pause specifically; evidence is from co-pilot vs autonomy (medium).

### O7. No novelty verdict; show closest prior work; label novelty score as an estimate
**Verdict: Supported (strong).**

Evidence for:
- Si et al. (2024) show LLM-generated ideas judged more novel but LLM self-evaluation is a named failure mode [S14, V].
- Si et al. (2025) show ideas that look novel before execution score lower after execution, with rankings flipping [S15, V]. A novelty label before execution is therefore not a measure of value.
- Beel et al. show established ideas labeled novel by the system [S13].
- OpenNovelty deliberately refuses to give a novelty verdict without verbatim evidence from both papers, and reports no established accuracy [S18].
- The novelty-estimate gap is also shown by SchNovel's reliance on a weak proxy (newer = more novel) [S19].

Counter-evidence (must be addressed):
- Scideator's novelty classifier reports better agreement with human novelty ratings than prior LLM methods (more than 10x on one measure, about 13% on another) [S26, S]. So a labeled classifier is not useless; but its ground truth is human ratings of a fixed set, not the field's judgment.
- Our design choice matches the field's caution. Recommendation: keep "closest prior work" as the primary output, add facet-level overlap explanations (Scideator's style), and keep any numeric score labeled "estimate; not validated" as planned.

### O8. Evidence = OpenAlex abstracts + seed papers (abstract + profile summary); problems without valid evidence keys dropped
**Verdict: Partly supported.**

Evidence for:
- Abstract-level evidence is enough to surface relevant work; LitSearch shows retrieval quality matters more than depth [S36].
- Dropping unsupported items is in line with the field's push for traceability: Kosmos cites every statement and still finds 20.6% inaccurate [S2]; OpenScholar's citations beat GPT-4o hallucination rates (78-90%) [S32].

Evidence against or limiting:
- Key presence is not support. Kosmos's 79.4% statement accuracy shows that a cited statement can still be wrong [S2]. Our "valid key" check should verify that the sentence supports the claim, not just that the key exists.
- Abstracts omit methods and limitations, which are what the problem stage needs. Kosmos and PaperQA2 read full text (Kosmos: 1,500 full-length papers per run [S2]; PaperQA2 chunk summaries [S3]). Our abstract-only choice is a real limitation and should be stated in the UI.
- Seed profiles (summary of the user's own papers) are a grounding source the field does not use much; Synergi and PaperWeaver show that explaining relevance to the user's own collection improves triage [S29, S30]. That supports keeping seeds as evidence, but they should be cited as seed evidence with an identifiable source, not as external evidence.
- The 2026 Elicit and Undermind evaluations show precision/recall tradeoffs in screening [S38, S35]; abstract-only screening has no measured recall in our case.

### O11. Chat modes (idea refinement, gap review, free); context = selected cards and gaps; [P#]/[G#] keys checked after the answer; no retrieval or tools during chat
**Verdict: Partly supported.**

Evidence for:
- Post-hoc citation checks are the field's basic defense: OpenScholar's gains come from retrieval plus feedback, and GPT-4o without it hallucinates citations at 78-90% [S32, V]. A key-existence check catches fabricated keys, which is the most common failure.
- Restricting chat to selected context reduces scope drift (conceptually aligned with Co-STORM's grounded discourse [S33]).

Evidence against or limiting:
- No retrieval in chat means any claim not in the cards is ungrounded; the check catches bad keys, not bad claims. Kosmos's 79.4% shows the gap [S2].
- Chat outputs need a claim-level flag: sentences without a valid key should be shown as "unsourced". Otherwise the user sees fluent text with a few keys.
- Free chat mode without any retrieval has no grounding by design. The mode should be labeled "ungrounded brainstorming".

---

## Part 3 - Better ideas (at least 10)

Constraints used for "fit": free tools; no new local model downloads (current local 8B is weak); privacy (single user, no external transmission of private text without explicit request); Korean UI.

### I1. Persistent findings memory across iterations (dead ends, rejected queries, validated and falsified problems)
- Change: Store a per-run ledger: queries tried, OpenAlex IDs seen, problems accepted or rejected with reason, and human feedback. Pass a compact digest into plan_queries and problems so the LLM does not regenerate dead ends.
- Evidence: DeepScientist's Findings Memory to avoid re-exploring dead ends [S8]; Kosmos world model shared across agents [S2]; Nova's iterative planning [S24].
- Expected benefit: Fewer duplicate queries and repeated problems across iterations; cleaner human review.
- Cost: 0 extra LLM calls; larger prompts (keep digest under about 1,500 tokens).
- Fit: Local, single user, no new model.
- Risks: Memory bias: early rejected problems may be wrongly excluded; add an "unrejected" option.
- Confidence: medium-high.

### I2. Pairwise comparison for ranking contributions instead of absolute 1-5 critique scores
- Change: For the top 3 contributions, run pairwise judgments on the same criteria and show a win count. Keep the numeric score only as a labeled estimate.
- Evidence: Co-scientist uses Elo from pairwise debates [S1]; Nova uses Swiss tournament over 170 seeds [S24]; AlphaResearch filters with a reward model before costly steps [S10].
- Expected benefit: Relative judgments are more stable than absolute 1-5 scores from a weak model (no measured source for our 8B; medium confidence).
- Cost: 3 pairwise calls for 3 items (3 comparisons); scales as n(n-1)/2.
- Fit: Uses the existing LLM; no new model.
- Risks: Weak local model may be position-biased; randomize order and run both orders.
- Confidence: medium.

### I3. Pre-expansion gate: cheap filter before expensive stages
- Change: After screen, require a minimum evidence coverage (e.g., at least 2 papers with overlapping key terms) before running problems; if not met, return "insufficient evidence; refine query" to the human instead of generating.
- Evidence: AlphaResearch screens proposals before code is written and saves compute [S10]; SESR-Eval-style recall targets indicate a threshold must be chosen explicitly [S38].
- Expected benefit: Fewer unsupported problems; fewer wasted LLM calls.
- Cost: 0 LLM calls.
- Fit: Yes.
- Risks: Threshold tuning with small samples; expose the threshold as a setting.
- Confidence: medium.

### I4. Citation snowballing as a second search channel (backward and forward from top seeds)
- Change: After OpenAlex keyword search, add referenced_works (backward) and cited_by (forward) for the top 3 seed or top-ranked papers, capped at N per iteration. Dedupe by OpenAlex ID.
- Evidence: PaperQA2 citation traversal [S3]; Undermind iterative citation trail reading [S35]; Chain of Ideas builds backward and forward chains from an anchor [S23].
- Expected benefit: Higher recall for hard-to-keyword topics; more relevant evidence for problems.
- Cost: API calls only (OpenAlex, free); no LLM. Watch rate limits: use the polite pool with an email in the User-Agent (do not put private data in that header; use a generic contact).
- Fit: Free; privacy fine if only public IDs are queried.
- Risks: Snowballing amplifies popular papers; cap and de-duplicate.
- Confidence: high.

### I5. Human-elicited review criteria with an explicit rubric (replace ad hoc critique dimensions)
- Change: Write the four critique dimensions (novelty, feasibility, evidence, clarity) as a fixed rubric with anchored descriptions and one example each, drawn from the user's own accepted ideas. Store the rubric in the repo docs.
- Evidence: ResearchAgent elicits reviewer criteria from human judgments [S21]; AI-Researcher and Jr. AI Scientist use review-score style grading [S7, S11] (self-reported).
- Expected benefit: More consistent critique; easier to audit.
- Cost: Authoring time; no extra LLM calls.
- Fit: Yes.
- Risks: Rubric may encode the user's bias; keep it editable.
- Confidence: medium.

### I6. Replace term-overlap screen with BM25 plus OpenAlex relevance ordering, and select abstract sentences by facet
- Change: Rank candidate papers by BM25 over title+abstract against the iteration query and OpenAlex relevance score; select evidence sentences by facet cues (purpose / mechanism / evaluation / limitation), similar to Scim's rhetorical-facet highlighting.
- Evidence: LitSearch: BM25 is well below dense retrievers, and term overlap is BM25-like [S36]; Scim's facet highlighting [S31]; Scideator's facet extraction [S26].
- Expected benefit: Better evidence sentences for problems; cheap.
- Cost: 0 LLM calls; a small local BM25 implementation (no model download).
- Fit: Yes. Avoid dense embedding models because they require new local downloads (violates constraint).
- Risks: BM25 remains lexical; query wording matters.
- Confidence: medium.

### I7. Facet view between screen and problems (human-editable purpose / mechanism / evaluation per seed paper)
- Change: Extract facets from each seed paper (abstract + profile) once, show them as an editable table, and let the human select which facets feed problems and methods.
- Evidence: IdeaSynth (lab N=20 more alternatives and detail vs baseline; field N=7) [S27, V]; Scideator (creativity support, 22 participants per snippet) [S26]; Synergi (user-curated threads plus citation expansion gave the most helpful outlines) [S29].
- Expected benefit: More control; fewer LLM calls because facets are reused across iterations.
- Cost: One LLM call per new seed (cached); UI effort.
- Fit: Good; uses existing profile data.
- Risks: Extraction errors from a weak local 8B; allow manual correction.
- Confidence: medium-high.

### I8. Breadth-vs-depth toggle at the human pause, plus a smallest-test feasibility field
- Change: At each review pause, offer "broaden" (keep problems list, add alternatives) or "deepen" (refine one problem). For each contribution, require a "smallest test" line: data needed, one experiment, one baseline.
- Evidence: CoQuest breadth-first vs depth-first effects on creativity vs trust [S28]; Ideation-Execution gap shows ideas must be tested in execution [S15, V].
- Expected benefit: Matches user intent; surfaces infeasible ideas early (no measured proof for our app).
- Cost: UI; small prompt change; no new calls.
- Fit: Yes.
- Risks: Smallest-test lines can be generic; add a checklist that the human can reject.
- Confidence: medium.

### I9. Diversity guard: dedupe and report pairwise overlap; use CoT and persona cues in generation
- Change: Compute lexical overlap (token Jaccard or BM25 similarity) among problems and contributions per iteration; flag pairs above a threshold; in generation prompts, require reasoning before listing and vary a persona/perspective per call.
- Evidence: Deng et al. report that CoT plus personas gave the highest diversity [S17]; meta-analysis shows human-GenAI collaboration reduces diversity [S16]; Nova targets diversity via planning [S24]; Si 2024 names generation diversity as an open problem [S14].
- Expected benefit: Fewer near-duplicate problems and contributions across iterations.
- Cost: 0 extra calls for the overlap check; prompt changes only.
- Fit: Yes.
- Risks: Persona prompts can produce superficial variety; measure with overlap, not impression.
- Confidence: medium-low.

### I10. Measure the loop: per-stage yield, evidence-check pass rate, and cost per run (AstaBench-style reporting)
- Change: Log, per iteration: number of queries, papers retrieved, papers screened, sentences selected, problems produced vs dropped (with reason), contributions, closest-work matches, and token counts. Show a small table in the run view.
- Evidence: AstaBench reports cost per problem and per-task scores [S34]; AI Scientist evaluations counted failures and citations [S13]; Kosmos reports statement accuracy [S2].
- Expected benefit: Makes the loop's value and failure points visible; supports tuning.
- Cost: Local logging only.
- Fit: Yes; keep logs local and free of private text (store IDs, counts, hashes, not full text, per AGENTS.md rules).
- Risks: Storage; keep privacy rules.
- Confidence: high.

### I11. Audit trail for each claim: trace log per run, exportable, with prompt hash, model name, and evidence keys
- Change: Store a run trace (JSON) with each LLM call's model, prompt hash, input evidence keys, output, and the human action at each pause. Keep it in the local data folder, out of Git.
- Evidence: Luo et al. recommend trace logs and code to reveal hidden failures [S12]; Jr. AI Scientist's risk report found fabricated results and mis-citation in raw outputs [S11]; Undermind's reproducibility criticism [S35].
- Expected benefit: Enables post-hoc audit and reproducibility; matches the user's review-before-save step.
- Cost: Storage only.
- Fit: Yes; schema change would need a backup note per AGENTS.md (review backup format).
- Risks: Trace files contain private text; encrypt or keep in data/ (excluded from Git).
- Confidence: high.

### I12. Claim-level support check as a deterministic step (no LLM): sentence-to-claim lexical support score
- Change: For each problem and contribution sentence, compute overlap between the claim's content words and the cited sentence; flag low-overlap citations as "weak support" for human review.
- Evidence: Kosmos found 20.6% of statements inaccurate even with citations [S2]; OpenScholar reports citation hallucination under unverified generation [S32].
- Expected benefit: Catches citations that point to a real paper but an unrelated sentence.
- Cost: 0 LLM calls.
- Fit: Yes.
- Risks: Lexical overlap is a weak proxy; present as a flag, not a verdict.
- Confidence: medium.

### I13. Stop rule based on saturation, not only the 3-iteration cap
- Change: Keep max 3 iterations, but suggest stopping early when the new iteration adds fewer than K new accepted papers or fewer than M new problems after dedupe.
- Evidence: Nova no further gains after about 3 rounds [S24]; Undermind's iterative completeness estimates [S35, S].
- Expected benefit: Saves time and calls.
- Cost: None.
- Fit: Yes.
- Risks: Saturation can be an artifact of the query set; allow human override.
- Confidence: medium.

### I14. Contamination and date control for benchmarking the loop itself
- Change: When evaluating the loop on known topics, use seeds published after the local model's cutoff and compare with human-written reviews, as MOOSE-Chem did with post-cutoff papers.
- Evidence: MOOSE-Chem's design to avoid contamination [S25].
- Expected benefit: A fair internal evaluation of the loop.
- Cost: Authoring a small local test set (kept in data/, not Git).
- Fit: Yes.
- Risks: Small set; many topics needed.
- Confidence: medium-low.

---

## Part 4 - Conflicts between sources and unverified items

Conflicts:
1. Kosmos scale: abstract (opened) says over 200 agent rollouts per run [S2 V]; search snippet says 166 data-analysis rollouts, 42,000 lines of code, 1,500 papers [S]. Use the abstract figure and treat the snippet figures as unconfirmed.
2. Robin dry-AMD magnitude: snippet gives 7.5x phagocytosis vs DMSO and a 1.75x human analysis of the same effect [S4]. Treat as unresolved; cite only as "reported as a fold change, analysis differs".
3. DeepScientist gains: snippet gives 183.7% and 1.9% for two tasks, with the third figure truncated and another summary giving 7.9% [S8]. Do not cite specific percentages.
4. Co-scientist title and Elo: v1 was "Towards an AI co-scientist"; current abstract page is "Accelerating scientific discovery with Co-Scientist" (v2, 2026). Elo and the agent list are not in the fetched abstract; Elo details are from secondary sources [S1].
5. Co-scientist GPQA claim: the Elo-GPQA correlation is a self-generated metric per secondary sources; no independent check [S1, U].
6. Scideator agreement numbers: snippet says more than 10x and about 13%; fetched abstract gives no numbers [S26].
7. Elicit screening figures: 96.9% sensitivity / 92.5% specificity vs 93.6% recall / 62.8% specificity on Elicit's own pages [S39]. Vendor claims are inconsistent; not used for verdicts.
8. AI-Researcher vs Jr. AI Scientist quality: the 3.25 vs 5.75 comparison is from the Jr. AI Scientist paper's own table [S7, S11]; self-reported on both sides.
9. Si et al. (2024) counts: snippet says 79 experts and 49 ideas per condition; fetched abstract says "over 100 NLP researchers" and gives no per-condition counts [S14]. Only the abstract claim is used.
10. Luo et al. named systems: fetched abstract says "two prominent open-source AI scientist systems" without names; secondary summaries name Agent Laboratory and AI Scientist v2 [S12, S].
11. Undermind accuracy: company claims (about 2% miss rate) vs librarian estimates (87-100% completeness; 93% after 144 papers); no independent benchmark [S35, U].
12. Synergi: found on arXiv 2308.07517 via search; not fetched; claims [S29] only.
13. Scim: the user brief lists Scim among 2024-2026 HCI tools; the only Scim found is the 2022 IUI paper, which predates LLMs [S31]. Flag as a mismatch.
14. Chain of Ideas venue and ID: ICLR 2025 vs EMNLP 2025 Findings; search also returned arXiv 2408.17404 under the same title, not verified as the same paper [S23, U].
15. Nova: abstract gives 170 seeds and ratios [V]; the 3-round limit is from a snippet quoting the paper [S24].
16. Co-STORM details: one press account claims 25% more organized and 10% broader than baselines, but the arXiv abstract gives only preference percentages (70%, 78%) [S33]. Press numbers not used.
17. AlphaResearch reward-model numbers: from secondary summaries; the authors' own threshold and accuracy claims unverified [S10, U].
18. STORM arXiv ID (2402.14207) was not verified in this session; treat as [U] in citations.
19. S19 (SchNovel) is linked to arXiv 2409.16605, but the search snippet attributed the SchNovel benchmark to Lin, Peng, Fang (2025). The URL may point to a different paper ("Evaluating and Enhancing LLMs for Novelty Assessment"); the SchNovel link is [U] until checked.

Unverified items (not opened or not confirmed):
- S4 Robin, S5 AI Scientist-v2 body text, S6 Agent Laboratory, S7 AI-Researcher, S8 DeepScientist, S9 InternAgent, S10 AlphaResearch, S11 Jr. AI Scientist, S13 Beel et al., S22 SciMON, S25 MOOSE-Chem, S28 CoQuest, S29 Synergi, S30 Threddy/Relatedly/PaperWeaver, S31 Scim, S35 Undermind, S36 LitSearch, S37 DeepResearch Bench, S38 SESR-Eval, S39 Elicit - all [S] only.
- Reported as "Nature 2026" for the Co-scientist paper (journal reference on the arXiv page); not verified against the Nature page.
- "Lau et al. 2025 sensitivity 37.9%" (second-hand) [U].
- Mostafa et al. 2602.06054 results [U].
- Holzner meta-analysis effect size (-0.86) [S] not verified in the PDF.
- Literature not reached: ScholarQABench full table; Elicit systematic review official evaluation; Relatedly/PaperWeaver effect sizes; Chain-of-Ideas Idea Arena numbers; OpenNovelty accuracy; Asta arXiv paper updated numbers (astabench 0.3.1).

Gaps versus the brief:
- Not covered in depth: Kosmos per-cycle literature procedure; Sakana v2 tree-search parameters; AlphaEvolve primary paper (not searched); ContraCrow full paper; Scholastic (not found); ResearchRubrics (not searched); LLM novelty reliability 2026 beyond the three items found.

---

## Part 5 - URL index

Primary and verified:
- https://arxiv.org/abs/2502.18864 (Co-scientist) [V]
- https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist (Co-scientist blog) [S]
- https://arxiv.org/abs/2511.02824 (Kosmos) [V]
- https://edisonscientific.com/articles/announcing-kosmos [S]
- https://arxiv.org/abs/2409.13740 (PaperQA2) [V]
- https://www.futurehouse.org/paperqa [S]
- https://arxiv.org/abs/2409.04109 (Si et al. 2024) [V]
- https://arxiv.org/abs/2506.20803 (Ideation-Execution Gap) [V]
- https://arxiv.org/abs/2509.08713 (Luo et al.) [V]
- https://arxiv.org/abs/2404.07738 (ResearchAgent) [V]
- https://arxiv.org/abs/2409.14634 (Scideator) [V]
- https://arxiv.org/abs/2410.04025 (IdeaSynth) [V]
- https://arxiv.org/abs/2411.14199 (OpenScholar) [V]
- https://arxiv.org/abs/2408.15232 (Co-STORM) [V]
- https://arxiv.org/abs/2410.14255 (Nova) [V]
- https://arxiv.org/abs/2410.13185 (Chain of Ideas) [V]
- https://allenai.org/blog/astabench (AstaBench) [V]

Search-result or secondary (not opened):
- https://arxiv.org/pdf/2505.13400 (Robin) [S]
- https://arxiv.org/pdf/2504.08066 (AI Scientist-v2) [S]
- https://github.com/SakanaAI/AI-Scientist-v2 [S]
- https://arxiv.org/pdf/2501.04227 (Agent Laboratory) [S]
- https://arxiv.org/abs/2505.18705 (AI-Researcher) [S]
- https://github.com/HKUDS/AI-Researcher [S]
- https://arxiv.org/abs/2509.26603 / https://arxiv.org/html/2509.26603v1 (DeepScientist) [S]
- https://arxiv.org/abs/2505.16938 (InternAgent / NovelSeek) [S]
- https://arxiv.org/abs/2511.08522 (AlphaResearch) [S]
- https://arxiv.org/abs/2511.04583 (Jr. AI Scientist) [S]
- https://arxiv.org/abs/2502.14297 (Beel et al.) [S]
- https://arxiv.org/abs/2505.17241 (Holzner et al.) [S]
- https://arxiv.org/abs/2602.20408 (Deng et al.) [S]
- https://arxiv.org/abs/2601.01576 (OpenNovelty) [S]
- https://arxiv.org/pdf/2409.16605 (SchNovel-related novelty evaluation) [S]
- https://arxiv.org/html/2602.06054v3 (Mostafa et al.) [U]
- https://arxiv.org/abs/2305.14259 (SciMON) [S]
- https://arxiv.org/abs/2410.07076 (MOOSE-Chem) [S]
- https://arxiv.org/abs/2308.07517 (Synergi) [S]
- https://arxiv.org/pdf/2208.03455 (Threddy) [S]
- https://arxiv.org/pdf/2302.06754 (Relatedly) [S]
- https://arxiv.org/pdf/2403.02939 (PaperWeaver) [S]
- https://arxiv.org/pdf/2205.04561 (Scim) [S]
- https://arxiv.org/abs/2310.06155 (CoQuest) [S]
- https://arxiv.org/abs/2407.18940 (LitSearch) [S]
- https://arxiv.org/abs/2506.11763 (DeepResearch Bench) [S]
- https://arxiv.org/pdf/2507.19027 (SESR-Eval) [S]
- https://elicit.com/blog/how-we-evaluated-elicit-systematic-review (Elicit vendor eval) [S]
- https://www.medrxiv.org/content/10.64898/2026.02.25.26347053 (Elicit noninferiority preprint) [S]
- https://aarontay.substack.com/p/undermindai-different-type-of-ai-agent (Undermind secondary) [S]
- https://github.com/DAMO-NLP-SG/CoI-Agent (Chain of Ideas code) [S]
- https://github.com/yiren-liu/coquest (CoQuest code) [S]
- https://github.com/Ayanami0730/deep_research_bench (DeepResearch Bench code) [S]
- https://github.com/stanford-oval/storm (STORM code) [S]
- https://kevinpjk.github.io/assets/pdf/ideasynth_chi_2025.pdf (IdeaSynth CHI PDF) [S]
- https://openscholar.allen.ai/paper (OpenScholar) [S]
