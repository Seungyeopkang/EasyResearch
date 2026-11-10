# O. Stopping, Replanning, and Full-Text Acquisition for the Autonomous Research Loop

- Date: 2026-11-10
- Scope: Hole A (termination, replanning, budgets, not-found report) and Hole B (full text for papers found through OpenAlex)
- Design context: `docs/exec-plans/active/006-claude-code-research-system.md` (cycle steps ①–⑧, backtrack caps 2 per hypothesis / 10 per cycle, verifier auto-reject A1–A6, failure ledger)
- Status: research note. Not an ExecPlan. Proposed rules in Parts 2 and 3 need Sol review and an acceptance check before they become requirements.

## Legend

- **[V]** Verified: a primary page or paper was fetched in this session and the figure was extracted. Extraction was done by WebFetch with a small model, so exact wording should be re-checked before quoting in a paper. Where a PDF did not parse, the HTML version was used instead.
- **[S]** Secondary: a search snippet, a third-party summary, or a mirror. Use only as a pointer to the primary source.
- **[U]** Unverified: the primary page could not be read (403, redirect, or empty render), or the claim comes only from search titles. Do not build a requirement on a [U] item without checking it.
- Numbers in Parts 2–3 marked "proposal" are my design derivations, not figures from a source.

---

## Part 1. Source records

### Hole A: stopping and replanning

**1. The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search**
- Org: Sakana AI (Yamada, Lange, Lu, et al.)
- Date: 2025-04 (arXiv 2504.08066)
- URL: https://arxiv.org/abs/2504.08066 ; HTML: https://arxiv.org/html/2504.08066v1
- Tag: [V] for the HTML numbers (Appendix A, §3.2.1); abstract [V]
- Facts:
  - Appendix A, Table 3: maximum experiment runtime per node is 1 hour; node allocation is 21 (Stage 1), then 12, 12, 12 for Stages 2–4.
  - The appendix states a total runtime limit of "a maximum of 15 hours."
  - Four stages. Stage 1 stops when "a basic working prototype is successfully executed." Stage 2 stops when experiments stabilize across "at least two datasets." Stages 3–4 stop when the computational budget is exhausted.
  - Debug probability 1.0 and maximum debug depth 3 (Table 3).
  - Three manuscripts were submitted; one passed the workshop bar (abstract [V]).
- Relevance: the clearest example of a staged, budget-capped tree search with explicit per-stage stop conditions. Its stage-exit rules are a good template for our "found / not found" gates. It has no adaptive stop based on novelty.

**2. The AI Scientist: Agent Laboratory (Using LLM Agents as Research Assistants)**
- Org: Schmidgall et al.
- Date: 2025-01 (arXiv 2501.04227; v2 2025-06)
- URL: https://arxiv.org/abs/2501.04227 ; HTML: https://arxiv.org/html/2501.04227v2
- Tag: [V] (HTML, §3–§5)
- Facts:
  - Three stages: literature review, experimentation, report writing. Human feedback is a checkpoint at the end of each subtask in co-pilot mode.
  - Literature review retrieves abstracts of the "top 20 papers" per query; finalized when N = max relevant texts are added (N value not given).
  - Code repair: N_rep = 3 tries in experiments.
  - Failure mode (§5.2): a paper-search agent could run up to 100 searches before a time limit was enforced; the limit was then set to 5.
  - Cost: gpt-4o averaged $2.33 per workflow versus roughly $15 for previous autonomous workflows (§4.3).
- Relevance: concrete retry caps (3 repair tries) and a documented runaway-search failure that justifies a hard search-call cap per query family.

**3. Kosmos: An AI Scientist for Autonomous Discovery**
- Org: Mitchener, White, et al. (author list from search summary; affiliations not verified)
- Date: 2025-11-04 (arXiv 2511.02824)
- URL: https://arxiv.org/abs/2511.02824 ; HTML: https://arxiv.org/html/2511.02824v2
- Tag: [V]
- Facts:
  - "over 200 agent rollouts" per run; 166 data-analysis rollouts and 36 literature-review rollouts (Introduction).
  - Runs last "for up to 12 hours."
  - Per cycle the world model is updated with summaries; the system decides it has finished when it "believes it has completed the research objective" (§2.1). The world model does not decide the stop.
  - Terminal output is "three or four scientific reports."
  - 79.4% of statements in reports judged accurate by independent scientists (abstract).
  - Current implementation does not let scientists intervene in intermediate cycles (§3.2).
- Relevance: a two-axis budget (rollouts and wall-clock) with a self-judged stop. Lesson for us: self-judged "done" must not be the success condition; our verifier should be the gate.

**4. Magentic-One: A Generalist Multi-Agent System for Solving Complex Tasks**
- Org: Microsoft Research (Fourney et al.)
- Date: 2024-11 (arXiv 2411.04468)
- URL: https://arxiv.org/abs/2411.04468 ; HTML: https://arxiv.org/html/2411.04468v1
- Tag: [V] (HTML §4.1)
- Facts:
  - The Orchestrator keeps a stall counter that increments when "a loop is detected, or there is a lack of forward progress."
  - The counter must remain "below a threshold (≤2 in our experiments)." When it exceeds the threshold, the Orchestrator leaves the inner loop and runs an outer loop with a reflection step and plan revision.
  - No separate maximum replan count; overall termination is a "parameterized and configurable" limit (attempts or time).
- Relevance: the most direct model for our replan trigger ("three consecutive no-progress cycles → replan"). Note the semantic: threshold 2 means the third stall triggers the replan.
- Conflict: Microsoft Agent Framework's port uses a leaky counter with default max_stall_count 3, so the replan fires on the fourth bad round [S: https://startdebugging.net/2026/10/what-is-magentic-orchestration-in-microsoft-agent-framework/]. Do not copy framework defaults without checking.

**5. Towards an AI co-scientist**
- Org: Google DeepMind (Gottweis et al.)
- Date: 2025-02 (arXiv 2502.18864)
- URL: https://arxiv.org/abs/2502.18864 ; HTML: https://arxiv.org/html/2502.18864v1
- Tag: [V] for Elo initial value and correlation claim (first 100k characters of HTML only)
- Facts:
  - New hypotheses enter the Elo tournament with an initial rating of 1200.
  - Elo correlates with averaged accuracy of generated results; the top-rated result per question reaches a top-1 accuracy of 78.4%.
  - Termination: the Supervisor agent decides "whether a terminal state for the overall computation has been reached." No numeric stop rule was found in the portion read.
  - Tournament size, match count, and time budget: not found in the portion read [U].
- Relevance: pairwise ranking can drive "which direction to keep" without a numeric score. Elo is an auto-evaluation, not ground truth, so it is a prioritization signal, never a success signal.

**6. Robin: A multi-agent system for automating scientific discovery**
- Org: FutureHouse (Ghareeb et al.)
- Date: 2025-05 (arXiv 2505.13400)
- URL: https://arxiv.org/pdf/2505.13400
- Tag: [S] (search summary only)
- Facts:
  - Iterative loop: hypothesis generation, experiment design, data analysis, then refinement that feeds the next round.
  - Two rounds of candidate testing in the dry AMD case study; round 2 used round 1 data.
- Relevance: a closed loop where analysis results change the next hypothesis set. Stopping rule not described in the summary [U].

**7. DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively**
- Org: Weng, Zhu, Xie, Sun, Lin, Liu, Zhang
- Date: 2025-09-30 (arXiv 2509.26603)
- URL: https://arxiv.org/abs/2509.26603 ; HTML: https://arxiv.org/html/2509.26603v1
- Tag: [V] (abstract)
- Facts:
  - About 5,000 unique ideas generated; about 1,100 validated; over 20,000 GPU hours.
  - Improvements over human SOTA: 183.7%, 1.9%, and 7.9% on three frontier tasks (abstract).
  - The abstract describes "month-long timelines."
  - Framing: discovery as Bayesian optimization with a cumulative "Findings Memory" that balances deepening promising directions against exploring new ones (secondary summaries [S]).
- Relevance: explicit exploitation vs exploration over a findings memory. The memory design (store failures and dead ends) matches our failure ledger.
- Conflict: timeline wording ("two weeks" in one summary, "month-long" in the abstract). Use the abstract.

**8. AI-Researcher: Autonomous Scientific Innovation**
- Org: HKUDS (Tang, Xia, Li, Huang)
- Date: 2025-05 (arXiv 2505.18705; NeurIPS 2025)
- URL: https://arxiv.org/abs/2505.18705 ; HTML: https://arxiv.org/html/2505.18705v1
- Tag: [S]
- Facts:
  - Full pipeline: literature review, idea generation, implementation, experiments, paper writing.
  - Scientist-Bench evaluation on 22 benchmark papers with multiple LLM evaluators.
  - Authors report better performance in open-ended exploration than in guided implementation.
- Relevance: a benchmark-style check of the whole loop. Quality claims are self-reported; no independent replication found.

**9. Nova: An Iterative Planning and Search Approach to Enhance Novelty and Diversity of LLM Generated Ideas**
- Org: Hu et al.
- Date: 2024-10 (arXiv 2410.14255; v2 revised 2024-10-27)
- URL: https://arxiv.org/abs/2410.14255 ; HTML: https://arxiv.org/html/2410.14255v2
- Tag: [V] (HTML §4.1, §4.3, §6)
- Facts:
  - Limitations (§6): "we do not see a continuous increment in generating new ideas after 3 rounds of iteration."
  - Iteration step 3, starting from 15 seed ideas; pool reaches 405 seed ideas, clustered by k-means into 100 clusters.
  - Each iteration generates 10 new seed ideas; self-reflection keeps 3.
  - Ablation: without planning, unique ideas rise only from 42.4 (step 2) to 44.1 (step 3).
  - Stopping rule: none adaptive; fixed three steps. Authors' own statement is the plateau evidence.
- Relevance: the only source here with an explicit plateau number. Supports a cap of 3 idea-generation rounds per direction, with a novelty-gain check after each round.

**10. PaperQA2 / Language agents achieve superhuman synthesis of scientific knowledge**
- Org: FutureHouse (Skarlinski, Cox, Laurent, et al.)
- Date: 2024-09 (arXiv 2409.13740; v2 2024-09-26)
- URL: https://arxiv.org/abs/2409.13740 ; HTML: https://arxiv.org/html/2409.13740v2
- Tag: [V] (abstract); HTML not read
- Facts:
  - LitQA2 benchmark, 248 questions whose answers are in the main text of papers, not abstracts (search summary [S]).
  - Contradiction detection: 2.34 ± 1.99 contradictions per paper (N = 93 biology papers); about 70% validated by experts.
  - Retrieval uses Grobid parsing and chunking of full text.
- Relevance: the strongest argument in this set that full text, not abstracts, is needed for claim-level accuracy. Supports our rule that quote-level claims require full text.

**11. OpenScholar: Synthesizing Scientific Literature with Retrieval-augmented LMs**
- Org: Asai et al.
- Date: 2024-11 (arXiv 2411.14199)
- URL: https://arxiv.org/abs/2411.14199 ; HTML: https://arxiv.org/html/2411.14199v1
- Tag: [S]
- Facts:
  - Datastore of 45 million open-access papers; ScholarQABench with 2,967 queries and 208 long-form answers.
  - Iterative self-feedback at inference time.
  - Authors report GPT-4o hallucinated citations 78–90% of the time in their tests.
- Relevance: the datastore is open-access full text and abstracts, so it shows the open-access-only corpus approach. Figures are authors' claims.

**12. Co-STORM / Into the Unknown Unknowns (STORM extension)**
- Org: Stanford OVAL (Jiang et al.)
- Date: 2024-08 (arXiv 2408.15232; EMNLP 2024 main)
- URL: https://arxiv.org/abs/2408.15232
- Tag: [V] (abstract)
- Facts:
  - A moderator turn generates new questions from unused information and the mind map to steer the discourse.
  - Mixed initiative: the user can take a turn at any time.
  - Human evaluation: 70% preferred Co-STORM over a search engine; 78% over a RAG chatbot.
  - No numeric turn budget or stop rule found in the abstract [U].
- Relevance: "saturation" is driven by an unused-information pool. A pool that stops producing unused information is a usable stop signal.

**13. Anthropic: How we built our multi-agent research system**
- Org: Anthropic (engineering blog)
- Date: undated on fetch [U]
- URL: https://www.anthropic.com/engineering/multi-agent-research-system
- Tag: [V]
- Facts:
  - Effort scaling guidance: simple fact-finding 1 agent with 3–10 tool calls; direct comparisons 2–4 subagents with 10–15 calls each; complex research more than 10 subagents.
  - Lead agent launches 3–5 subagents in parallel.
  - Failure modes: spawning 50 subagents for simple queries; subagents kept searching after they "already had sufficient results."
  - Token usage: agents about 4× chat; multi-agent about 15× chat. Token usage alone explains 80% of variance on BrowseComp.
- Relevance: the only source here with explicit tool-call tiers and an over-search failure. Use as a prior for per-stage tool-call budgets.

**14. The SAFE procedure: a practical stopping heuristic for active learning-based screening in systematic reviews and meta-analyses**
- Org: Boetje and van de Schoot (ASReview ecosystem)
- Date: 2024 (Systematic Reviews)
- URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC10908130/
- Tag: [V]
- Facts:
  - Phase 1 random set about 1% of records; stop once at least one relevant record is found (plus a minimum count).
  - Phase 2 active learning stops only if all hold: all key papers marked relevant; at least 2 × RR_T records screened (RR_T = estimated relevant count); at least 10% of the dataset screened; no relevant records in the last 50 records.
  - Phase 3 (second model, e.g., sBERT) and Phase 4 (quality check, Naive Bayes with TF-IDF on the top and bottom 10 records): stop if no extra relevant records in the last 50 records.
  - Humans typically miss around 10% of relevant records (cited in the article).
  - The authors say the numbers are examples, not fixed rules.
- Relevance: a multi-condition stop with a "last 50 records" window. Adapt it to "last 50 candidate papers screened" for search saturation.

**15. Statistical stopping criteria for automated screening in systematic reviews**
- Org: Callaghan and Müller-Hansen
- Date: 2020 (Systematic Reviews)
- URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC7700715/
- Tag: [V]
- Facts:
  - Setup: recall target 95%, confidence 95%, 20 datasets, 100 iterations each.
  - Ranked quasi-sampling (proposed): mean work saved 17%; target missed in 0.95% of cases.
  - Random sampling (proposed): 15% saved; missed 3.29%.
  - Baseline sampling (Shemilt et al.): most common saving 0%; target missed 39.67%.
  - Heuristic "50 irrelevant in a row" (IH50): 41% saved but target missed in 39% of cases.
  - Heuristic with 200 irrelevant in a row: described as performing unreliably.
- Relevance: the key evidence that a simple "N irrelevant in a row" rule misses the target often (39% for N = 50). Our rule must be a floor combined with a statistical estimate, not the only test.

**16. Computer-assisted screening in systematic evidence synthesis requires robust and well-evaluated stopping criteria**
- Org: Multi-author commentary (includes Wojciech Kusa per search summary)
- Date: 2024 (Systematic Reviews)
- URL: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11583672/
- Tag: [S]
- Facts: argues stopping rules must make the risk of missing relevant studies explicit and reported.
- Relevance: supports writing the miss risk into the not-found report.

**17. Undermind (whitepaper and product claims)**
- Org: Undermind
- Date: 2024-01 (whitepaper)
- URL: https://www.undermind.ai/whitepaper.pdf ; product: https://undermind.ai/
- Tag: [S]
- Facts:
  - Vendor claims the search can tell when it is complete and that convergence finds "virtually every relevant paper."
  - Classifier: about 2% chance a highly relevant paper (per humans) is judged not relevant.
  - Corpus moved to Semantic Scholar (about 200M records), titles and abstracts only.
  - The exact convergence criterion was not found in search snippets [U].
- Relevance: a product claim of convergence stop. Use only as a reason to define our own saturation test and to report the classifier miss rate.

**18. Novelty-guided UCT and epistemic-uncertainty search (group of papers)**
- Org: multiple (arXiv 2603.16250 Visual Prompt Discovery; arXiv 2605.11328 Epistemic Uncertainty for Test-Time Discovery)
- Date: 2026 (arXiv IDs)
- URLs: https://arxiv.org/pdf/2603.16250 ; https://arxiv.org/pdf/2605.11328
- Tag: [S]
- Facts:
  - Novelty-guided UCT scores an unexecuted node by its novelty against siblings and the count of executed siblings as a saturation proxy of the parent.
  - Epistemic-uncertainty paper: maximum reward tends to plateau when systems optimize expected reward; proposes disagreement across hypotheses as the push-past signal.
  - One planner paper uses UCB scores from MCGS to rank experiments, then assigns non-overlapping directions.
- Relevance: supplies the UCB-plus-novelty form for direction selection. No paper found that uses plateau detection as a bandit-level switch trigger [U]; that part must be designed.

**19. Scientific discovery as meta-optimization and Heuresis (group of 2026 papers)**
- URLs: https://arxiv.org/pdf/2606.26728 ; https://icml.cc/virtual/2026/73443 (novelty ceiling / PAC-style bound title)
- Tag: [U] (titles and snippets only, not read)
- Relevance: candidate sources for a formal saturation or oversight-rate bound. Not used for numbers in this note.

**20. Don't Stop Early: Scalable Enterprise Deep Research with Controlled Information Flow and Evidence-Aware Termination**
- URL: https://arxiv.org/pdf/2604.24978
- Tag: [U] (title only in search; not read)
- Relevance: a named "evidence-aware termination" design for deep research. Read before finalizing Part 2 stop logic.

**21. OpenAI and Google deep research stopping rules**
- Status: not found. Searches returned only the OpenAI Deep Research system-card snapshot (no stop logic) and plan quotas. No Gemini deep research stop rule found.
- Tag: gap [U]

### Hole B: full text

**22. OpenAlex: Full-text PDFs (download all data)**
- Org: OpenAlex (OurResearch)
- Date: undated (accessed 2026-11-10)
- URL: https://help.openalex.org/download-all-data/full-text-pdfs (redirects from docs.openalex.org)
- Tag: [V]
- Facts:
  - Per-file downloads use the API key at $0.01/file.
  - Public bucket is free and anonymous; no AWS account needed.
  - Full-archive sync is an add-on to the Member+ or Partner plan.
  - Coverage count, re-download cost, and licensing note not on this page; the bucket root has a LICENSE.txt [V: page says so].
- Relevance: the bulk path. Shows cost is per file and the bucket is free to read.

**23. OpenAlex: Fulltext access**
- URL: https://help.openalex.org/access/fulltext/
- Tag: [V]
- Facts:
  - Cached full text for more than 60 million open-access works, as PDF and TEI XML.
  - Table file counts: PDF about 73M (about 113 TB); TEI XML about 71M (about 1.5 TB).
  - Check `has_content.pdf` before requesting.
  - A HEAD request is free.
  - "The PDFs retain their original copyright." OpenAlex grants no additional rights.
  - Check license via `best_oa_location.license` (for example, cc-by).
- Relevance: the legal boundary. Stored PDFs keep their own license; our use is research-local.

**24. OpenAlex: Example costs**
- URL: https://help.openalex.org/access/example-costs/
- Tag: [V]
- Facts:
  - Search $1 per 1,000 calls; singleton lookup free; content download $10 per 1,000 calls.
  - A free key multiplies the no-key budget by 10, giving $1 of usage per day, which covers up to 1,000 search calls or 100 PDF downloads.
- Conflict: a search snippet said a free key gets 100,000 credits per day (about 1,000 downloads at 100 credits each). The example-costs page implies 100 PDF downloads per day. Treat 100 downloads/day as the conservative planning number until the current pricing page is rechecked.

**25. OpenAlex: Locations and best OA location**
- URLs: https://docs.openalex.org/api-entities/works/work-object/location-object ; https://help.openalex.org/data/locations/ ; https://help.openalex.org/hc/en-us/articles/41193798112151-How-is-the-best-OA-location-determined
- Tag: [S] (search snippets of current help pages; the location page itself was not fetched in full)
- Facts:
  - `best_oa_location` is the best freely readable copy or null.
  - Ranking: OA first; publisher-hosted above repository-hosted; publishedVersion above acceptedVersion above submittedVersion; a direct `pdf_url` ranks above a landing page.
  - `pdf_url` is null when only a landing page is known.
  - Older help articles use Unpaywall-style names (`host_type`, `url_for_pdf`, `is_best`). Current OpenAlex docs govern.
- Relevance: the first lookup for a PDF URL. Always validate that the URL returns a PDF.

**26. OpenAlex: Open access status values**
- URL: https://help.openalex.org/data/works/open-access/
- Tag: [V]
- Facts:
  - `gold`: fully OA journal. `green`: toll-access on publisher page, free copy in an OA repository. `hybrid`: free under an open license in a toll-access journal. `bronze`: free to read on publisher page without an identifiable open license. `diamond`: fully OA with no APC. `closed`: everything else.
  - `is_oa`: whether any free, legal full-text copy exists. `oa_url`: best full-text link OpenAlex found.
- Relevance: bronze means readable but not licensed for reuse. Keep local, do not redistribute, and label it.

**27. arXiv Terms of Use for arXiv APIs**
- URL: https://info.arxiv.org/help/api/tou.html
- Tag: [V]
- Facts:
  - Legacy APIs (OAI-PMH, RSS, arXiv API): "make no more than one request every three seconds."
  - "limit requests to a single connection at a time."
  - Limits apply "to all of the machines under your control as a whole."
  - Metadata: free to retrieve, store, transform, and share descriptive metadata under CC0 1.0.
  - Bulk data is a covered service; the page links to a separate S3 bulk page.
- Conflict: a secondary site reports 3 requests per second and HTTP 503 on excess; a 2026 Google Groups thread reports 429 errors below the 3-second spacing; a secondary blog reports an October 2026 policy change. None verified on arXiv pages [U].
- Relevance: the arXiv direct-PDF rate limit is one request per 3 seconds on one connection, shared across our machines.

**28. Unpaywall REST API**
- URL: https://unpaywall.org/api/v2
- Tag: [U] for the email and limit claims. The page fetch returned only the word "Unpaywall."
- Claims from search (unverified against the page):
  - Email is required as a query parameter.
  - Recommended ceiling of 100,000 calls per day; heavier users should use the database snapshot.
  - rOpenSci roadoi docs (https://docs.ropensci.org/roadoi/) say an email is required and 100k/day is suggested [S].
- Relevance: Unpaywall gives locations, not files. Use it as a second source for `oa_url` and for a license check, with email set to a project address (no personal details).

**29. Semantic Scholar Academic Graph API (openAccessPdf)**
- URL: https://api.semanticscholar.org/api-docs/ (overview only, fetched); Graph docs at https://api.semanticscholar.org/api-docs/graph
- Tag: [U] for field details; the overview page did not contain them.
- Claims from third-party tools [S]:
  - `openAccessPdf` is not in the default response; must be requested via `fields`.
  - Shape: object with `url`, `status`, `license`; `url` can be missing, so handle a null URL.
  - Works on search results as well as single-paper lookup.
  - New keys reportedly start at 1 request per second [S]; an API key is optional and raises limits.
- Relevance: a cheap second PDF-URL source, but treat `url` as optional.

**30. CORE API**
- URL: https://www.core.ac.uk/services/api ; docs https://core.ac.uk/documentation/api (403 on fetch)
- Tag: [S] for the services page; [U] for numbers
- Facts:
  - Free, no registration required, subject to rate limits; registered organisations get higher limits.
  - A third-party listing reports a free tier of 1 batch or 5 single requests per 10 seconds [U].
  - The CORE Dataset is a separate bulk download with eligibility limits [S].
- Relevance: a fallback full-text source with a repository-style license profile. Check the docs page directly before use.

**31. Europe PMC RESTful Web Service**
- URL: https://docs.ropensci.org/europepmc/ (client docs; official docs at europepmc.org/RestfulWebService not fetched)
- Tag: [S] for client behavior; [U] for licensing and key policy
- Facts:
  - The R client's `fullTextXML` retrieves full text deposited in PMC, which is not always available.
  - Some sources say no key is needed; one catalog says a key may be required. Conflict unresolved.
  - One aggregator says over 2.5 million full-text articles are freely reusable for text mining [S].
- Relevance: the biomedical full-text route. Use only for PMC-deposited articles; check the official reuse terms.

**32. Plan S / Coalition S open access analysis (Zenodo) and Piwowar et al. (PeerJ 2018)**
- URLs: https://zenodo.org/records/3543000/files/Open-access-potential-and-uptake-in-the-context-of-Plan-S-20191121.pdf ; https://peerj.com/articles/4375/ (403 on fetch)
- Tag: [U] for both; figures from search snippets
- Claims from snippets:
  - Piwowar et al. (2018): at least 28% of scholarly literature is OA (about 19M); 47% of articles viewed by Unpaywall users were OA; the most common route was Bronze.
  - Plan S report: per-field analysis using Unpaywall, DOAJ, Crossref, and SHERPA/RoMEO across four fields and 30 subdisciplines. Per-field figures not retrieved.
- Relevance: the only OA-rate figures found. They are old (2018 data) and not field-specific for CS. Replace with a live OpenAlex query before using in any report.

**33. OpenAlex OA share by discipline (2024 snapshot)**
- URL: https://tagteam.harvard.edu/hub_feeds/119/feed_items/13824690/about (pulse49 summary)
- Tag: [S]
- Facts: Life Sciences 52%, Health Sciences 49%, Social Sciences 41%, Physical Sciences 38% OA. Green OA 3–4% in most fields, 8% in Physical Sciences (possibly arXiv). Computer Science not broken out.
- Relevance: gives a field-level baseline, but CS is not reported separately. Compute the CS share directly from OpenAlex before setting any expectation.

**34. arXiv share in CS and open access in CS**
- Tag: gap [U]
- Facts found: a 2023 arXiv paper says OA rates are lower in engineering and CS; one journal study reports CS Born-OA journals at 64.9% but journal OA share at 16.2%. No verified CS arXiv share found.
- Relevance: do not assume a high arXiv share for CS. Measure it on our own query results and record the rate in the run log.

---

## Part 2. Proposed rules for Hole A

Numbers marked [src] are from Part 1. Numbers marked (proposal) are my derivation and need Sol review and a test run.

### 2.1 Success condition ("contribution found")

A cycle may end in FOUND only when all of the following hold. These are conjunctive, so any single failure keeps the cycle open or ends it NOT FOUND.

1. **Verifier gate.** The verifier returns PASS on C1–C7 (design §11.4), with a finding ID for each item. No REVISE is open.
2. **No auto-reject.** A1–A6 all clear (code-checked, not model-judged).
3. **Nearest-prior check.** At least 3 nearest prior works are listed, each with an explicit difference statement (C4). A search of at least 3 queries was run for the nearest prior works (A3).
4. **Reverse search.** At least one search for contrary results or "already done" evidence, with the query and result count recorded (design §11.4 反증 검색).
5. **Citation check.** Every claim citing a source has a `verify_quote` match. Abstract-only support cannot pass a quote-level claim (see Part 3.5).
6. **Stability.** The same verdict is reached on two consecutive verifier runs with different context (independent of the author). (proposal)
7. **Human gate.** Under the "꼼꼼히" and "보통" policies, the contribution is confirmed by a person (design §7). Under "대부분 자동" it is marked as auto-confirmed in the report.

Rationale: Kosmos's own statement of completion [V] is a self-judged stop, and the Anthropic blog notes agents over-search after they "already had sufficient results" [V]. Neither is a success condition for us. The verifier gate and the human gate are.

### 2.2 Saturation and plateau detection

Use three detectors. Each writes a reason code to the cycle log. Any one may trigger a replan or a not-found check; none alone declares success.

**(a) Search saturation (literature stage).** Adapted from SAFE [V].
- Maintain a queue of candidate papers in the order screened.
- Saturated when, all of the following hold:
  - At least 2 × (estimated relevant count) candidates screened. (SAFE uses this form; the estimate comes from the screener's first pass.)
  - At least 10% of the candidate pool screened, or 100 candidates, whichever is smaller. (proposal: the 100 floor avoids tiny pools; SAFE uses 10% [V].)
  - No new relevant candidate in the last 50 screened. (SAFE uses 50 [V].)
  - All key papers named in the plan marked as found.
- Caveat: IH50 (50 irrelevant in a row alone) missed the target in 39% of cases [V: Callaghan]. Never use the 50-window as the only stop. Record the expected miss rate in the not-found report.

**(b) Idea novelty plateau (hypothesis stage).** Adapted from Nova [V].
- After each idea-generation round, compute the count of new unique ideas (dedup by embedding or title similarity) that pass the novelty check.
- Stop the round loop after 3 rounds (Nova's stated plateau [V]), or earlier when the gain in new unique ideas between two rounds is below 5% of the previous round's count. (proposal: the 5% threshold is not from a source.)

**(c) Stall counter (cycle stage).** Adapted from Magentic-One [V].
- Increment the stall counter on a cycle step that yields no new evidence, no new candidate, no new verifier finding, or a repeated query.
- Reset on progress.
- Replan when the counter exceeds 2 (Magentic-One threshold ≤2 [V]), i.e., the third consecutive stall.

Note: the Magentic-One threshold value is from the HTML fetch of the paper's §4.1. Confirm with the PDF before citing as a number in a paper.

### 2.3 Direction selection (exploit vs explore)

- Score each open direction d with a UCB1-style value: score(d) = mean_reward(d) + c × sqrt(ln(N) / n(d)), with reward = verifier pass rate or novelty-gain proxy. (proposal: c = 1.0 as default; not tuned.)
- Add a saturation penalty from the novelty-guided UCT idea [S]: lower the score of a direction whose sibling ideas are all executed (parent saturated).
- Use the same score to pick which direction to replan into. Do not pick the highest mean alone.
- The UCB-plus-plateau combination is not found in a single paper [U] (Part 1 #18). Treat this as design, and check it with the M4 evaluation set.

### 2.4 Replan types and caps

Replan means changing the search or idea plan without restarting the cycle. Each replan must write a failure-ledger entry first (design §4).

| Replan type | What changes | Cap per topic run | Trigger |
|---|---|---|---|
| R1 narrow | Add a constraint (population, method family, year range) | 2 | Stall counter > 2 with a large candidate pool (more than 200 screened) |
| R2 broaden | Drop one constraint or add a synonym family | 1 | Saturation reached with fewer than 10 relevant candidates |
| R3 pivot | New sub-question via citation chase (`cites:`, `cited_by:`, `related_to:`) | 2 | Verifier REJECT with reason code C1 or C4 on every direction |
| R4 method-alternative | Change the idea family (design §4: alternative method 2–4) | 2 per hypothesis, matching the design cap | Verifier REJECT on C2, C5, or C6 |

- Total replans per topic run: 5 (proposal). The sum is capped to keep the run from drifting.
- Total backtracks per cycle: 10, and per hypothesis: 2 (design §4, unchanged).
- Basis for the caps: Agent Laboratory's 3 repair tries [V], Magentic-One's stall threshold ≤2 [V], Nova's 3-round plateau [V]. The 5-replan total is a proposal.

### 2.5 Budgets

Hard limits enforced in code, not by model judgment.

| Budget | Proposed cap | Basis |
|---|---|---|
| Wall clock per topic run | 12 hours | Kosmos runs up to 12 hours [V]; AI Scientist-v2 total cap 15 hours [V] |
| Tool calls per topic run | 200 rollouts equivalent (count every MCP call and subagent call) | Kosmos 200 rollouts [V] |
| Subagent spawns per cycle | 6 (one per agent role per round) | Anthropic prior: 3–5 subagents, avoid 50 for simple queries [V] |
| Tool calls per literature sub-task | 15 | Anthropic: 10–15 calls for direct comparison [V] |
| OpenAlex content downloads per run | 100 (conservative; see Part 3.4) | OpenAlex example-costs page [V] |
| Verifier runs per hypothesis | 3 | proposal; 2 debate rounds plus the final check (design §11.4) |
| Code repair tries per experiment | 3 | Agent Laboratory N_rep = 3 [V] |

At 80% of any budget, the loop must write a status event and begin wrap-up: no new direction, finish the current verification, go to the not-found or FOUND report.

### 2.6 Not-found report contents

When a cap is hit or saturation finds no contribution, the cycle ends NOT_FOUND and writes a report with:

1. **Status and reason code.** Which cap or detector ended the run (for example: `WALL_CLOCK`, `REPLAN_CAP`, `SATURATED_NO_CANDIDATE`, `VERIFIER_REJECT_ALL`).
2. **Search coverage.** Queries run (count and list), candidates screened, relevant candidates found, and the saturation test values at stop (the 50-window, the 2×RR and 10% checks).
3. **Expected miss rate.** State the stop rule used and cite its measured miss rate (for example, IH50 39% [V]; SAFE-type rules as the reference). Say the search may have missed relevant work.
4. **Idea trail.** Directions tried, with status (rejected, closed, or open), reason codes, and failure-ledger IDs.
5. **Closest candidates.** The top 3 nearest prior works and the closest near-miss idea, with the verifier's specific failing criterion.
6. **Budget used.** Time, tool calls, downloads, and replans against each cap.
7. **What would change the answer.** One or two concrete next steps (new data, a narrower question, a human judgment) stated as actions.
8. **Full-text coverage.** How many of the screened papers had full text vs abstract-only (Part 3.5).

Do not write "no prior work exists." The A6 rule already bans novelty certainty claims.

---

## Part 3. Proposed pipeline for Hole B (full text)

### 3.1 Source order

Run in this order and stop at the first source that returns a valid PDF or full-text XML for the work. Every attempt is logged with source, URL class (not the full URL if it contains a key), HTTP status, content type, and result.

1. **OpenAlex work record.** Read `best_oa_location` and `open_access` (`is_oa`, `oa_url`, `oa_status`) from the work already in hand. Free (singleton lookup free [V]).
2. **arXiv direct.** If the work has an arXiv ID (in `ids`, or in a location URL), fetch `https://arxiv.org/pdf/<id>`. Rate: one request per 3 seconds, one connection [V]. Store the PDF with its SHA-256.
3. **OpenAlex content (paid, per file).** `has_content.pdf: true` then request the content. Cost $0.01 per file [V]. Free-key allowance is 100 PDF downloads per day on the example-costs page [V]; see the conflict in Part 4.
4. **Other OA locations.** Try the `pdf_url` of other locations, in OpenAlex rank order, and the Unpaywall `oa_url` as a cross-check [U]. Unpaywall requires an email parameter and suggests 100k calls per day [U].
5. **Semantic Scholar `openAccessPdf`.** Request the field; handle a null `url` [U for field details].
6. **CORE.** Use only by DOI or title match with a confidence check; respect its rate limits (verify first) [U].
7. **Europe PMC full text.** For PMC-deposited biomedical work only [S].
8. **Abstract-only fallback.** Use the OpenAlex abstract (or the abstract from the first source that returns one). Label it (Part 3.5).

Do not use any site whose main purpose is access to paywalled copies. This matches the design rule excluding Sci-Hub-style options (design §11.2).

### 3.2 Caps

| Item | Cap | Basis |
|---|---|---|
| arXiv requests | 1 per 3 seconds, 1 connection, shared across all of our machines | arXiv TOU [V] |
| OpenAlex content downloads | 100 per day (planning cap), 1 per run is the minimum for any PDF | Example-costs page [V] |
| Unpaywall requests | 100k per day maximum, recommended; use a low internal cap (proposal: 1,000 per run) | [U] |
| Per-host concurrency | 1 for any publisher or repository host | proposal |
| Retry on 429 or 503 | up to 3, exponential backoff starting at 30 seconds (proposal) | proposal |
| Max PDF size | 50 MB (proposal; check outliers) | proposal |

### 3.3 Legality and terms checks

Run before storing any file.

1. **License check.** Read `best_oa_location.license` or the `open_access` license (for example `cc-by`). Record it with the file.
   - `gold`, `diamond`, `hybrid` with an open license: store and use with attribution.
   - `green`: free copy in a repository; store locally; redistribution depends on the repository's license (check the field).
   - `bronze`: readable but no identifiable license. Store only for private research use. Do not redistribute, do not add to shared corpora. Mark `license: unknown`.
   - `closed`: no file.
2. **Terms check per host.** Confirm each host's terms allow automated access before enabling it (arXiv TOU [V]; publisher terms [U, not checked]). Disable any host whose terms are not checked.
3. **Robots and automation.** Respect robots.txt where a host publishes one (best practice; not verified for any host here [U]).
4. **No credential handling.** Never enter a login, token, or institutional credential into a page. A login wall is a stop, not a step.
5. **No captcha bypass.** A captcha or bot challenge is a failure state (Part 3.4).
6. **Data handling.** Files stay in the private research folder (`data/`, excluded from git per repository invariants). Do not send full text to an external service without the design's explicit consent step (design §7, "서재 내용을 Claude로 보내기").

### 3.4 Failure modes and handling

| Failure | Detection | Handling |
|---|---|---|
| Landing page instead of PDF | Content type `text/html`, or first bytes not `%PDF-` | Mark `pdf_url` invalid; try next location; never save HTML as a PDF |
| Captcha or bot challenge | Response body or redirect matches a challenge page | Stop that host for the run; log; move to next source |
| Paywall | 401/403, or preview-only PDF (short page count, "subscribe" text) | Mark closed for this source; try next source |
| 429 / rate limit | HTTP 429 or 503 | Backoff; after 3 tries, disable host for the run |
| Broken or expired link | 404, DNS error | Try next location |
| Corrupt PDF | Parser fails or zero pages | Keep the file as evidence (do not delete); mark parse failed; use abstract fallback |
| Wrong work | Title similarity below threshold after download | Quarantine; do not cite |

Never overwrite a source PDF. Keep the file hash and the physical page count, and record printed page labels separately (repository invariant).

### 3.5 Evidence-strength labels

Each claim in a hypothesis card carries one label. The verifier reads the label.

| Label | Meaning | Allowed use |
|---|---|---|
| **F1** | Full text parsed; quote verified by `verify_quote` on the physical page | Quote-level and method-level claims; can support PASS |
| **F2** | Full text parsed, but page mapping or extraction is partial | Claims at paragraph level; needs a second check before PASS |
| **A1** | Abstract only | Topic-level or background claims only; cannot support C2 (contribution), C3 (quote), or C4 (nearest prior difference) |
| **M** | Metadata only (title, venue, year) | Existence and citation only; no content claims |

Rules:
- A hypothesis whose contribution rests on A1 or M support cannot PASS (proposal). It can be REVISE with a request for full text.
- The not-found report must state the F1/F2/A1/M count for the screened set (Part 2.6 item 8).
- Abstract-only support is weaker. PaperQA2 [V] argues that answers in the main text need full text, so do not treat abstracts as equal evidence.

### 3.6 Expected coverage (to measure, not assume)

Open-access rates in Part 1 are from 2018–2024 data and are not CS-specific. Measure these on our own query results:
- Share of candidate works with `is_oa: true`, by `oa_status`.
- Share with a valid PDF after step 1–5 of Part 3.1.
- Share with arXiv ID among CS candidates.

Record the four numbers in each run's log so the next run can compare. Do not set an expected coverage target until at least one real run has been logged.

---

## Part 4. Conflicts and unverified items

### Conflicts

1. **OpenAlex free-key allowance.** Search snippet: 100,000 credits/day, about 1,000 downloads at 100 credits each. Example-costs page: $1/day, which covers 100 PDF downloads. The $10 per 1,000 content calls price implies 100 downloads = $1. Resolution: use 100 downloads/day as the planning cap and confirm the current pricing page before enabling bulk downloads.
2. **arXiv rate limit.** TOU [V]: one request per 3 seconds, one connection. Secondary sites: 3 requests per second with HTTP 503 on excess. 2026 user report: 429 errors below 3-second spacing. Secondary blogs: a policy change on 2026-10-01. Resolution: follow the TOU's 3-second rule now and re-read the live arXiv bulk and API pages before any bulk run.
3. **Magentic-One stall threshold.** Paper HTML [V]: counter must stay below ≤2, and the replan follows when exceeded. Microsoft Agent Framework port: leaky counter, default 3, replan on the fourth bad round [S]. Resolution: use the paper's semantics; confirm the threshold from the PDF's text layer (PDF did not parse in this session).
4. **DeepScientist timeline.** One summary says two weeks; the abstract says "month-long timelines" [V]. Resolution: cite the abstract.
5. **Co-Scientist.** Elo correlation and initial rating read from the first 100k characters of HTML; tournament size and budget not found. Resolution: read the remaining text before citing any tournament parameter.
6. **Unpaywall email and daily limit.** Search snippets say email required and 100k/day recommended; the page fetch returned no text. Resolution: fetch the Unpaywall documentation via another route before the first call.

### Unverified or gaps

- OpenAI and Gemini deep research stopping rules: not found in primary sources.
- Undermind convergence criterion: not found; only vendor claims [S].
- STORM (non-Co-STORM) turn budgets: not read.
- Knee method (Cormack and Grossman 2016): mentioned in summaries only [S]; primary not read. Do not cite the knee method's numbers.
- Unpaywall per-field OA rates: not found. Plan S per-field report not read.
- Arxiv share of CS papers: not found.
- Semantic Scholar field details and rate-limit numbers: docs overview only [U].
- CORE rate limits: docs page returned 403 [U].
- Europe PMC licensing: official docs not read [U].
- Publisher terms and robots.txt: not checked for any host.
- Several 2026 arXiv items (IDs 2603–2606) are from search titles or summaries only [S/U]; they are useful pointers, not evidence.
- The recursive-improvement references in design §6 (ACE, ReasoningBank) are outside this note's scope.

### Method notes

- PDF extraction failed for three primary PDFs in this session (AI Scientist-v2, Magentic-One, Co-Scientist PDFs returned compressed binary). HTML versions were used instead. Kosmos and Agent Laboratory were read from HTML. Figures were extracted by a small model from the page text, so re-verify exact numbers before quoting them in a paper.
- Some fetches were redirected or returned 403 (OpenAlex docs redirect, PMC redirect, Piwowar PeerJ 403, CORE 403, Anthropic blog was fetched). The URLs in Part 5 are the ones to check.

---

## Part 5. URL index

Primary and verified:
- https://arxiv.org/abs/2504.08066 (AI Scientist-v2)
- https://arxiv.org/html/2504.08066v1
- https://arxiv.org/html/2501.04227v2 (Agent Laboratory)
- https://arxiv.org/abs/2501.04227
- https://arxiv.org/abs/2511.02824 (Kosmos)
- https://arxiv.org/html/2511.02824v2
- https://arxiv.org/abs/2411.04468 (Magentic-One)
- https://arxiv.org/html/2411.04468v1
- https://arxiv.org/abs/2502.18864 (Co-Scientist)
- https://arxiv.org/html/2502.18864v1
- https://arxiv.org/abs/2509.26603 (DeepScientist)
- https://arxiv.org/html/2410.14255v2 (Nova)
- https://arxiv.org/abs/2410.14255
- https://arxiv.org/abs/2409.13740 (PaperQA2)
- https://arxiv.org/abs/2408.15232 (Co-STORM)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10908130/ (SAFE)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC7700715/ (Callaghan and Müller-Hansen)
- https://www.anthropic.com/engineering/multi-agent-research-system
- https://help.openalex.org/download-all-data/full-text-pdfs
- https://help.openalex.org/access/fulltext/
- https://help.openalex.org/access/example-costs/
- https://help.openalex.org/data/works/open-access/
- https://info.arxiv.org/help/api/tou.html

Secondary (search or summary):
- https://arxiv.org/pdf/2505.13400 (Robin)
- https://arxiv.org/abs/2505.18705 (AI-Researcher)
- https://arxiv.org/html/2505.18705v1
- https://arxiv.org/abs/2411.14199 (OpenScholar)
- https://arxiv.org/html/2411.14199v1
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11583672/ (commentary on stopping rules)
- https://www.undermind.ai/whitepaper.pdf
- https://undermind.ai/
- https://arxiv.org/pdf/2603.16250 (Novelty-guided UCT, visual prompt discovery)
- https://arxiv.org/pdf/2605.11328 (epistemic uncertainty, test-time discovery)
- https://arxiv.org/pdf/2606.26728 (meta-optimization; title only)
- https://icml.cc/virtual/2026/73443 (title only)
- https://arxiv.org/pdf/2604.24978 (evidence-aware termination; title only)
- https://startdebugging.net/2026/10/what-is-magentic-orchestration-in-microsoft-agent-framework/
- https://docs.openalex.org/api-entities/works/work-object/location-object
- https://help.openalex.org/data/locations/
- https://help.openalex.org/hc/en-us/articles/41193798112151-How-is-the-best-OA-location-determined
- https://tagteam.harvard.edu/hub_feeds/119/feed_items/13824690/about (OpenAlex 2024 OA by discipline)
- https://docs.ropensci.org/roadoi/ (Unpaywall client docs)
- https://www.core.ac.uk/services/api (CORE services)
- https://docs.ropensci.org/europepmc/ (Europe PMC client docs)

Unverified (fetch failed or not read):
- https://unpaywall.org/api/v2 (fetch returned no content)
- https://api.semanticscholar.org/api-docs/ (overview only)
- https://api.semanticscholar.org/api-docs/graph (not read)
- https://core.ac.uk/documentation/api (403)
- https://europepmc.org/RestfulWebService (not read)
- https://peerj.com/articles/4375/ (403; Piwowar et al. 2018)
- https://zenodo.org/records/3543000/files/Open-access-potential-and-uptake-in-the-context-of-Plan-S-20191121.pdf (not read)
- https://arxiv.org/pdf/2409.13740 (not read)
- https://arxiv.org/abs/2505.13400 (not read)
- https://github.com/ResearAI/DeepScientist (not read)
- https://github.com/HKUDS/AI-Researcher (not read)
- https://github.com/sakanaai/ai-scientist-v2 (not read)
- https://github.com/SakanaAI/AI-Scientist-v2 (not read)
- https://openscholar.allen.ai (not read)
- https://www.arxiv.org/pdf/2601.03267 (not read; out of scope)
- Cormack and Grossman (2016), knee method: primary not located in this session.
