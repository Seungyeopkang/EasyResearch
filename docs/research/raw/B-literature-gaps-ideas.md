# Research B: Literature Tools, Structured Summaries, Paper Links, Gap Finding, Idea Generation

Date of research: 2026-11-10. Scope: tools and papers for (1) structured paper profiles with grounded quotes, (2) paper-to-paper linking and literature graphs, (3) research gap finding for one or many papers, (4) idea generation and refinement by chat.

Verification legend: **VERIFIED** = read on the primary page or a primary-source fetch in this session. **SEARCH-ONLY** = seen in search-result snippets or secondary sources, not opened. **UNVERIFIED** = could not confirm, or only an aggregator claimed it.

Method note: about 40 WebSearch calls and 11 WebFetch calls. Several primary pages (Semantic Scholar API docs, NotebookLM help, Consensus, Undermind white paper, Litmaps/ResearchRabbit/Inciteful official sites) did not yield usable text, so those rows rely on secondary sources.

---

## Part 1. Source records

### 1.1 Structured summarization and literature QA

**PaperQA2 (FutureHouse)**
- Link: https://arxiv.org/abs/2409.13740 (paper, "Language Agents Achieve Superhuman Synthesis of Scientific Knowledge"); https://www.futurehouse.org/paperqa (product page) (VERIFIED for arXiv abstract, SEARCH-ONLY for product page)
- What it does: RAG agent for scientific literature. Produces cited, Wikipedia-style summaries; WikiCrow was built on it; ContraCrow finds contradictions between papers. (https://arxiv.org/abs/2409.13740)
- Data model / pipeline (VERIFIED from arXiv HTML v2, https://arxiv.org/html/2409.13740v2):
  - Paper Search: LLM turns the request into keyword queries; default 12 candidate papers, parsed and chunked.
  - Gather Evidence: embeds chunks, top-k vector ranking (default k=30); an LLM writes a 200-400 token contextual summary per chunk plus an integer relevance score out of 10 (returned as JSON); top summaries kept.
  - Generate Answer: top evidence summaries (default 15; 5 gave best accuracy) passed to an LLM.
  - Citation Traversal: follows one degree of citers/references from high-scoring papers (min score 8), keeps candidates overlapping across source papers, caps at 12.
- Grounding: citation keys appended to sentences, e.g. `(Example2012Example pages 3-4)`; the model is instructed to cite only keys present in its context. Grounding is at the passage-summary level, with page ranges. Contradiction step: 2.34 +/- 1.99 contradictions per paper, 70% validated by experts (https://arxiv.org/abs/2409.13740).
- Gap/idea generation: not its purpose. ContraCrow (contradictions) is the nearest analogue to gap finding.
- Evaluation (VERIFIED, https://arxiv.org/html/2409.13740v2): LitQA2 (248 MCQ): accuracy 66.0% +/- 1.2, precision 85.2%, "insufficient information" 21.9%. Human accuracy 67.7% +/- 11.9. Original PaperQA: 36.7% accuracy. WikiCrow vs Wikipedia (375 statements): "cited and unsupported" 13.5% vs 24.9%; precision 86.1% vs 71.2%. Cost about $4.48 per article.
- Open source: code on GitHub as `paper-qa`, pip installable (SEARCH-ONLY: https://awesome.ecosyste.ms/projects/github.com%2Fwhitead%2Fpaper-qa). Exact repo URL UNVERIFIED.

**STORM / Co-STORM (Stanford OVAL)**
- Links: STORM arXiv 2402.14207 (cited in the task; not opened). Co-STORM arXiv 2408.15232: https://arxiv.org/pdf/2408.15232v1.pdf (SEARCH-ONLY). Code: https://awesome.ecosyste.ms/projects/github.com%2Fstanford-oval%2Fstorm (SEARCH-ONLY; repo is github.com/stanford-oval/storm per that listing). Demo storm.genie.stanford.edu is UNVERIFIED.
- What it does: STORM writes Wikipedia-style articles from web search by simulating multi-perspective question asking and conversations, then outlining, then drafting. Co-STORM adds an interactive discourse among LM agents with a shared mind map, letting the user steer. (SEARCH-ONLY, https://www.edtechinnovationhub.com/news/pn7fo3f7xehe5gfj24mcjuntt7ormz)
- Data model: outline/section hierarchy; Co-STORM uses a hierarchical concept mind map (SEARCH-ONLY).
- Grounding: cited sources from search; reported as fact-checked with citations (secondary).
- Gap/idea generation: not primary. The mind map is a concept-structure tool, relevant to "concept graph" design.
- Evaluation (SEARCH-ONLY): FreshWiki dataset; Co-STORM 70% preference over search engine, 78% over RAG chatbot. The "25%/10%" coverage numbers come from a secondary news article and are UNVERIFIED.
- Open source: yes (SEARCH-ONLY). Developers position it as a pre-writing tool, not a publishable article generator (SEARCH-ONLY, https://brajeshwar.com/2025/storm.md).

**OpenScholar (UW / Ai2)**
- Link: https://arxiv.org/abs/2411.14199 (SEARCH-ONLY; abstract/index pages).
- What it does: retrieves passages from a 45M open-access paper datastore and writes citation-backed long-form answers, with iterative self-feedback.
- Data model: passage-level retrieval over open-access papers; no structured profile fields.
- Grounding: citation-backed answers; the authors claim GPT-4o hallucinated citations 78-90% of the time vs OpenScholar citation accuracy comparable to experts (authors' claim, SEARCH-ONLY).
- Gap/idea generation: none.
- Evaluation (authors' own, SEARCH-ONLY): ScholarQABench with 2,967 queries and 208 long-form answers across CS, physics, neuroscience, biomedicine. The 8B model beats GPT-4o by 5% and PaperQA2 by 7% on correctness. Experts preferred OpenScholar answers over expert-written ones 51% of the time.
- Open source: code, models, datastore, and demo released (SEARCH-ONLY). Journal version Feb 2026 (SEARCH-ONLY, aggregator).

**GPT Researcher (assafelovic)**
- Link: https://github.com/assafelovic/gpt-researcher (SEARCH-ONLY; README snippets).
- What it does: open-source deep research agent for web and local documents; produces cited reports; has a "Deep Research" recursive workflow; supports MCP data sources and installation as a Claude Skill (`npx skills add assafelovic/gpt-researcher`) (SEARCH-ONLY).
- Data model: free-text report with citations; no structured paper profile.
- Grounding: web-source citations.
- Gap/idea generation: none explicit.
- Evaluation: none found.
- Open source: Apache-2.0 (SEARCH-ONLY). Star counts differ by snapshot (27.7k to 28.1k); treat as approximate.

**LangChain open_deep_research**
- Link: https://github.com/langchain-ai/open_deep_research (VERIFIED, fetched).
- Architecture (VERIFIED from the repo page): run with LangGraph server (`langgraph dev`, port 2024); four LLM roles: summarization (default `openai:gpt-4.1-mini`), research, compression, final report (defaults `openai:gpt-4.1`). Search backend default is Tavily; MCP supported; native web search for Anthropic and OpenAI. Legacy `legacy/multi_agent.py` contains the supervisor-researcher pattern with parallel researchers; `legacy/graph.py` is plan-and-execute. License MIT. Evaluation via `tests/run_evaluate.py`.
- Note: the search summaries described a clarify, brief, supervisor, final-report flow in the current graph (SEARCH-ONLY, aggregator). Not confirmed on the repo page.
- Data model: free-text report; no paper profile.
- Grounding: web sources.
- Gap/idea generation: none.
- Evaluation: repo has an evaluation script; results UNVERIFIED.

**Elicit (systematic review extraction columns)**
- Links: https://support.elicit.com/en/articles/4267649 (Steps 4-5: data extraction and final report) and https://support.elicit.com/en/articles/14758162 (SEARCH-ONLY; search snippets from official help center).
- Data model (SEARCH-ONLY, official help snippets): a table where each column = a short name phrase plus free-text instructions. Yes/no/maybe and multiple-choice column types exist. Columns can be duplicated and tuned on a 10-paper pilot set, saved as presets, and exported to CSV.
- Grounding: clicking a cell shows the supporting quotes (SEARCH-ONLY). This is the closest commercial pattern to "verifiable page quotes per extracted field."
- Gap/idea generation: none directly; the user creates columns such as limitations.
- Evaluation: none found in this session.
- Open source: no. Systematic Reviews on Pro, Scale, Enterprise plans (SEARCH-ONLY).

**Undermind**
- Link: https://undermind.ai/ (SEARCH-ONLY; homepage not fetched).
- What it does: multi-round adaptive search for literature. Asks clarifying questions first, then runs a Deep Search, then writes annotated reports with inline citations (SEARCH-ONLY; CASRAI guide https://www.casrai.org/guides/undermind-ai).
- Data model: ranked paper list with annotations; no facet schema found.
- Grounding: inline citations.
- Relevance judgement: an LLM classifies papers into high/close/ignorable (SEARCH-ONLY, aggregator). The 96% recall figure from a 2024 blog (https://aarontay.substack.com/p/undermindai-different-type-of-ai-agent) was inferred by the blogger to use an Elicit custom column; UNVERIFIED.
- Corpus: moved to Semantic Scholar corpus (about 200M papers, titles and abstracts) per the 2024 blog (SEARCH-ONLY).
- Evaluation: vendor-only (2x recall vs AI web search). No independent replication found.
- Open source: no.

**Consensus**
- Links: https://casrai.org/guides/consensus-ai-search-engine-guide (SEARCH-ONLY); https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises (SEARCH-ONLY). Official site consensus.app not opened.
- What it does: peer-reviewed-paper AI search. Hybrid search, quality-signal re-ranking, and AI synthesis with inline citations over about 200-220M papers (sources disagree).
- Consensus Meter: summarizes the distribution of findings for yes/no questions; the guides warn that vote-counting across studies can mislead.
- Data model: per-paper quality signals (SEARCH-ONLY, not itemized).
- Evaluation: none found.
- Open source: no.

**SciSpace (table extraction)**
- Links: https://stagecf.scispace.com/extract-data (SEARCH-ONLY); https://library.smu.edu.sg/topics-insights/scispace-yet-another-academic-search-powered-generative-ai (SEARCH-ONLY).
- Data model (SEARCH-ONLY): literature review table with columns that have custom instructions (e.g. "classify discipline into 4 areas"); suggested columns include conclusions, results, limitations, literature survey, study context, participants. Export CSV, XLSX, BibTeX.
- Grounding: "Locate in PDF" for citations and extracted values (SEARCH-ONLY, library guide).
- Column caps and plan limits conflict across sources (50 columns vs 5 columns on free tier). UNVERIFIED for current limits.
- Gap finding: none found.
- Open source: no.

**NotebookLM (Google)**
- Links: no official Google help page was retrieved. Secondary: https://www.emergentmind.com/topics/notebooklm (SEARCH-ONLY). Treat the following as UNVERIFIED.
- What it does: source-grounded Q&A over uploaded sources; answers carry numbered citations that link to the source passage (secondary).
- Limits claimed (UNVERIFIED): free tier 50 sources per notebook; per-source cap 500k words or 200 MB.
- Grounding: says when info is not in sources; citations point at passages.
- Open source: no.

### 1.2 Literature graphs and paper linking

**Connected Papers**
- Link: https://www.connectedpapers.com/about (SEARCH-ONLY; About page cited by secondary sources).
- What it does: builds a similarity graph of a seed paper's neighborhood. Similarity = co-citation and bibliographic coupling (SEARCH-ONLY, https://casrai.org/guides/connected-papers).
- Data model: nodes = papers (size = citation count, color = year). Edges are implicit similarity weights, not typed relations. Prior Works (common ancestors) and Derivative Works (common descendants) lists (SEARCH-ONLY).
- Corpus: Semantic Scholar; about 50,000 papers analyzed per graph, a few dozen shown (SEARCH-ONLY, university blog).
- Grounding: none; it is a graph of metadata.
- Gap/idea generation: none. Useful as a "neighborhood" view for gap comparison.
- Limits: bias toward highly cited papers and Semantic Scholar coverage gaps (SEARCH-ONLY, library guide).
- Open source: no.

**Litmaps**
- Links: https://paperguide.ai/blog/litmaps-vs-researchrabbit/ (SEARCH-ONLY, comparison blog); official litmaps.com not opened.
- What it does: citation map with a timeline view (publication time vs citation count). Two-way Zotero sync on Pro; alerts for new papers in a saved map (SEARCH-ONLY).
- Data model: citation edges plus date and citation count.
- Open source: no.

**ResearchRabbit**
- Links: https://paperguide.ai/blog/litmaps-vs-researchrabbit/ (SEARCH-ONLY); official site not opened.
- What it does: citation and similarity-based discovery from seed papers/collections. Free tier with 310M+ articles and up to 50 seeds; RR+ from about $10/month (SEARCH-ONLY, listing; UNVERIFIED pricing).
- Head-to-head anecdote: matched a DOI first while Litmaps ranked it second (one blog, not a benchmark).
- Note: one source says Litmaps and ResearchRabbit share an owner (UNVERIFIED).
- Open source: no.

**Inciteful**
- Links: https://intuitionlabs.ai/articles/ai-literature-mapping-tools-guide (SEARCH-ONLY); official site not opened.
- What it does: free citation mapper; saves to Zotero and Mendeley (SEARCH-ONLY).
- Open source: no.

**Semantic Scholar (TLDR, API, recommendations, citation intents)**
- TLDR paper: https://arxiv.org/abs/2004.15011 (SEARCH-ONLY abstract). Cachola et al. 2020, "TLDR: Extreme Summarization of Scientific Documents"; CATTS (title as auxiliary signal) applied to BART; dataset of 5.4K TLDRs over 3.2K papers in v3 (v2 says 3.9K). Product page: https://www.semanticscholar.org/product/tldr (SEARCH-ONLY): TLDRs in beta for about 60M papers in CS, biology, medicine; available in the API.
- Datasets API (SEARCH-ONLY, release index https://api.semanticscholar.org/datasets/v1/release/latest): `citations` dataset with `isinfluential` (bool), `intents` (why cited), `contexts` (citing sentence text). ODC-BY license. About 2.4B records.
- Graph API paper and citation endpoints: field names confirmed in the datasets schema above. Endpoint paths and rate limits were NOT verified: the official API docs fetch returned navigation only (https://api.semanticscholar.org/api-docs/ and /api-docs/graph, VERIFIED-as-failed). Third-party scrapers claim `/graph/v1/paper/{id}/citations` returns intent and influence flags, and that the API key raises rate limits 10x (UNVERIFIED).
- Recommendations: client docs list `/recommendations/v1/papers/forpaper/{paper_id}` (single seed, `limit` <= 500, `pool_from` "recent" or "all-cs") and a multi-seed POST `/recommendations/v1/papers/` (SEARCH-ONLY, https://semanticscholar.readthedocs.io/en/latest/api.html). A scraper page says max 100 recommendations per source. The 500 vs 100 limit conflict is UNVERIFIED.
- Open source: API free; dataset release downloadable (SEARCH-ONLY).

**scite (Smart Citations)**
- Paper: Nicholson et al. 2021, "scite: A smart citation index that displays the context of citations and classifies their intent using deep learning," Quantitative Science Studies 2(3): https://doaj.org/article/81fa50fb3c294f6ba01cc597d41a974e (SEARCH-ONLY metadata).
- Data model: each citation labelled supporting / mentioning / contrasting, with citing-sentence context (SEARCH-ONLY).
- Accuracy (developers' figures via HKUST library, SEARCH-ONLY https://library.hkust.edu.hk/sc/?p=1704): 97% mentioning, 64% supporting, 59% contrasting. Library note: the three-way scheme oversimplifies.
- Grounding: the citing context sentence is shown.
- Open source: no (commercial). Verified claim status: SEARCH-ONLY.

**Zotero AI plugins**
- Zotero GPT (MuiseDestiny): https://github.com/muisedestiny/zotero-gpt (SEARCH-ONLY; 2023-era README; one-click summary; API key/model/URL settings). Note the search listed a second fork at https://github.com/WengMixin/zotero-gpt.
- Aria (lifan0127): https://awesome.ecosyste.ms/projects/github.com%2Flifan0127%2Fai-research-assistant (SEARCH-ONLY). It is a chat assistant for Zotero papers; separate Zotero 6 and 7 releases. A one-click summary was not confirmed.
- Zotero AI Butler (steven-jianhao-li): summary, analysis, and annotations saved as Zotero notes (SEARCH-ONLY, https://www.sourcepulse.org/projects/21844019).
- AI Summary for Zotero: https://forums.zotero.org/discussion/131505/plugin-ai-summary-for-zotero-save-ai-generated-paper-summaries (SEARCH-ONLY). Requires Zotero 9+, Poppler, Python 3.
- Maintenance status: UNVERIFIED for all of these.
- Grounding: mostly none. Notes saved in Zotero; no page-quote requirement.

**Obsidian Smart Connections**
- Repo: https://github.com/brianpetro/obsidian-smart-connections (SEARCH-ONLY via https://docsearch.algolia.com/mcp/docs/repo/brianpetro/obsidian-smart-connections); community page https://community.obsidian.md/plugins/smart-connections.
- What it does: local embeddings; Connections view (related notes) and Lookup view (semantic search); builds index automatically with a built-in local model (SEARCH-ONLY). v4 moved advanced features to Pro plugins; Core v4.7 requires Smart Environment v3.
- Data model: note-level embeddings; blocks are embedded in the index.
- Grounding: note links only; no quote-level grounding.
- Open source: core free and open-source (SEARCH-ONLY).
- Community MCP server: https://github.com/msdanyg/smart-connections-mcp (SEARCH-ONLY). A claim that it sends notes to a cloud service is UNVERIFIED; check the code before using it on private notes.
- Alternatives (SEARCH-ONLY): Open Connections, Vector Search (needs Ollama), Semantic Backlinks.

### 1.3 Idea generation and novelty

**ResearchAgent (Baek et al., KAIST / Microsoft Research / DeepAuto.ai)**
- Link: https://arxiv.org/abs/2404.07738 (SEARCH-ONLY; arXiv v2 Feb 2025; venue reported as NAACL by one aggregator, UNVERIFIED).
- What it does: starts from a core paper, adds related papers from an academic graph, plus entities from an entity-centric knowledge store built by entity co-occurrence across papers. Multiple reviewing LLM agents give iterative feedback aligned with criteria derived from human judgments (SEARCH-ONLY).
- Data model: idea = problem + method + experiment design; knowledge store = entity co-occurrence.
- Grounding: references from the seed and graph neighbours. Not quote-level.
- Gap/idea generation: problem-first. Reviewers score novelty, clarity, validity.
- Evaluation (SEARCH-ONLY): gains over LLM baselines in novelty, clarity, validity; ablation: relevant references matter most.
- Open source: UNVERIFIED.

**SciMON (Wang, Downey, Ji, Hope, 2023; ACL 2024)**
- Links: https://arxiv.org/abs/2305.14259 (SEARCH-ONLY); ACL Anthology https://aclanthology.org/2024.acl-long.18 (SEARCH-ONLY).
- What it does: retrieves inspirations from semantic similarity graphs, knowledge graphs, and citation networks given a background problem; iterative novelty boosting compares the ideas against prior work and revises them (SEARCH-ONLY).
- Data model: background problem, inspiration papers, generated idea text.
- Evaluation: authors report ideas tend to be incremental with thin detail (SEARCH-ONLY).
- Open source: UNVERIFIED.

**Chain of Ideas (CoI), Alibaba DAMO**
- Link: https://arxiv.org/abs/2410.13185 (VERIFIED abstract: cs.AI and cs.CL; v5 Oct 30, 2024). Code: https://github.com/DAMO-NLP-SG/CoI-Agent (SEARCH-ONLY; not confirmed on the arXiv page). ICLR 2025 (SEARCH-ONLY).
- What it does (VERIFIED abstract + SEARCH-ONLY summary): retrieves an anchor paper for a topic, builds a chain of literature backward and forward to mirror domain progression, asks an LLM to predict trends, and runs a novelty-checker that compares the draft against literature and refines it when similarity is high.
- Evaluation: Idea Arena (pairwise arena-style protocol). CoI beats the second-best baseline by 56 ELO in human evaluation (SEARCH-ONLY). Cost at least $0.50 per candidate idea plus experiment design (VERIFIED abstract).
- Aggregator arXiv IDs 2409.07578 and 2408.17404 are wrong; ignore them.

**Si, Yang, Hashimoto, "Can LLMs Generate Novel Research Ideas?"**
- Link: https://arxiv.org/abs/2409.04109v1 (SEARCH-ONLY); full text https://arxiv.org/html/2409.04109v1.
- Design (SEARCH-ONLY): 79 expert NLP researchers, blind review of 49 ideas per condition: expert ideas, AI ideas, AI ideas reranked by an expert. Testbed: prompting-based NLP.
- Result: AI ideas judged more novel (p<0.05), slightly weaker on feasibility.
- Limits (SEARCH-ONLY): LLM agents fail at self-evaluation, lose diversity at scale, and are not reliable evaluators. The study is NLP-only.
- Code and review scores released (SEARCH-ONLY).

**Scideator (UW / AI2)**
- Link: https://arxiv.org/abs/2409.14634 (VERIFIED abstract/search; latest version v5 per listing; CAIS 2026 listed as venue, SEARCH-ONLY).
- Data model (VERIFIED from arXiv abstract fetch): three facets per paper: purpose (problem), mechanism (method), evaluation (how it is checked). Facets extracted from input and analogous papers; GPT-4 extraction per a secondary review (SEARCH-ONLY, UNVERIFIED).
- Pipeline (VERIFIED): Analogous Paper Facet Finder (distance-controlled retrieval, uses Semantic Scholar API per SEARCH-ONLY); Faceted Idea Generator (user picks facets, LLM finds analogies across them); Idea Novelty Checker (facet-based retrieve-then-rerank; facet-grounded novelty classifier).
- Evaluation (VERIFIED from fetch): ablation: facet-based retrieve-then-rerank surfaces more relevant papers than standard retrieve+rerank; facet-grounded classifier beats one reasoning over unstructured text. User study (22 CS researchers, within-subjects): significantly more creativity support, especially exploration and expressiveness.
- Refinement loop: user adopts a suggestion, regenerates from Module 2, or changes facets in Module 1 (SEARCH-ONLY).
- Code: not linked on the arXiv abstract page (VERIFIED absence on that page).

**Nova (Hu, Fu et al., 2024; Findings of ACL 2025)**
- Link: https://arxiv.org/abs/2410.14255 (VERIFIED abstract; the ACL Findings version is https://aclanthology.org/2025.findings-acl.1099, SEARCH-ONLY). Code: https://github.com/hflyzju/Nova (SEARCH-ONLY).
- What it does (VERIFIED abstract): iterative planning and search. Seed ideas from an input paper; each round plans a search for papers in other fields to boost novelty and diversity.
- Evaluation: 3.4x more unique novel ideas vs no framework; at least 2.5x more top-rated ideas in Swiss Tournament across 170 seed papers vs state-of-the-art (VERIFIED abstract).
- Novelty definition: not stated on the abstract page (UNVERIFIED).

**IdeaBench (Guo et al., Oct 2024; KDD 2025 listed by a SUNY record)**
- Link: https://arxiv.org/abs/2411.02429 (SEARCH-ONLY).
- Data: 2,374 target biomedical papers and 29,408 reference papers. The LLM is given the references as context.
- Scoring: GPT-4o ranks ideas against quality indicators (novelty, feasibility, etc.); rankings turned into an "Insight Score" (SEARCH-ONLY).
- Author list conflicts across sources; verify. Open source: UNVERIFIED.

**LiveIdeaBench (Ruan et al., arXiv 2412.17596)**
- Link: https://arxiv.org/abs/2412.17596 (SEARCH-ONLY; latest HTML v4 at https://arxiv.org/html/2412.17596v4). Leaderboard https://liveideabench.com; dataset https://huggingface.co/datasets/6cf/liveideabench-v2 (SEARCH-ONLY).
- Design: single-keyword prompts over more than 1,000 scientific keywords; grounded in Guilford's divergent thinking. Minimal context on purpose.
- Scoring: a dynamic panel of LLM judges on originality, feasibility, fluency, flexibility, and clarity (SEARCH-ONLY, latest version). Early versions used originality and feasibility only.
- Finding: creative performance does not track general intelligence (SEARCH-ONLY).
- Relevance for us: useful as a judge-design reference; minimal-context prompting is the opposite of our grounded setting.

**Novelty assessment**
- SchNovel (Lin, Peng, Fang; AI and Scientific Discovery workshop, 2025): https://arxiv.org/html/2409.16605v1 (SEARCH-ONLY). 15,000 arXiv pairs over six fields; the more recent paper is treated as more novel. RAG-Novelty retrieves related papers. Code: https://github.com/ethannlin/SchNovel (SEARCH-ONLY). Assumption (newer = more novel) is a proxy, not ground truth.
- RINoBench (arXiv 2603.10303): https://arxiv.org/pdf/2603.10303 (SEARCH-ONLY). Argues many tools reduce novelty to binary judgments; LLM reasoning resembles human rationale but does not reliably produce accurate judgments.

### 1.4 Gap finding, limitations, and rhetorical structure

**BAGELS (arXiv 2505.18207)**: https://arxiv.org/pdf/2505.18207 (SEARCH-ONLY). Benchmark for extracting and generating limitations from scholarly text. Limitations often sit in Conclusion, Discussion, or Future Work, so a targeted section pipeline is used.

**FutureGen (arXiv 2503.16561)**: https://arxiv.org/html/2503.16561v1 (SEARCH-ONLY). RAG-based generation of future-work sections; author-written future work is often vague or too brief. Extraction step checked against human annotators.

**Research Gap Discovery Dataset (Mendeley Data)**: https://data.mendeley.com/datasets/px9xd7tw8n (SEARCH-ONLY). 3,326 recent arXiv CS papers, each with an LLM-written limitation, research-gap, and importance statement. Outputs are non-deterministic, so the pipeline is not exactly repeatable.

**Multi-agent gap discovery (SBC WESAAC)**: https://sol.sbc.org.br/index.php/wesaac/article/download/45243/45004/ (SEARCH-ONLY). Combines a concept co-occurrence graph with explicit limitation and future-work statements; ranks candidate gaps with traceable evidence and confidence; trades recall for precision.

**Limitation extraction reliability (TU Delft 2026 bachelor thesis)**: https://repository.tudelft.nl/record/uuid:bebea6a3-0921-440a-8a29-7aa7f55cac4e (SEARCH-ONLY). LLM found dedicated limitation sections with perfect accuracy; text extraction less reliable; main failure is drifting into future-work sentences.

**SciCite / Structural scaffolds (Cohan et al., NAACL 2019)**: https://arxiv.org/pdf/1904.01608 (SEARCH-ONLY); code and data https://github.com/allenai/scicite (SEARCH-ONLY). Citation intent classification with a multitask model (auxiliary: predict section title and whether a sentence needs a citation). SciCite is more than 5x larger than prior datasets. Figures from alphaXiv (11,020 instances, macro F1 84.0) are UNVERIFIED. Intent labels in SciCite: background, method, result comparison (verify against the paper).

**Argumentative Zoning (Teufel, 1999 thesis; Teufel and Moens, Computational Linguistics 2002)**: thesis abstract https://www.cl.cam.ac.uk/~sht25/thesis/abstract.html (SEARCH-ONLY). Sentence-level rhetorical roles built on Swales' CARS model. Original seven categories include AIM (research goal), BASIS (agreement or continuation), OTHER (neutral description of others' work), and OWN (new work). TEXTUAL (paper structure) is listed by a later source. Main journal version: Teufel and Moens 2002, Computational Linguistics 28(4): 409-446 (SEARCH-ONLY citation). Full category list: UNVERIFIED.
- Design relevance: AZ-style zoning gives a cheap, verifiable section-level label per sentence. This is a good grounding unit for profile fields such as "problem" and "limitation".

---

## Part 2. Cross-cutting findings

1. Grounding patterns in use:
   - Passage summaries with relevance scores, cited by page ranges (PaperQA2). Verified.
   - Per-cell quotes shown in a table (Elicit). SEARCH-ONLY.
   - Citing-sentence context with intent labels (scite, Semantic Scholar contexts). SEARCH-ONLY.
   - Source grounding in NotebookLM. UNVERIFIED on primary.
2. Gap generation methods:
   - Limitation and future-work extraction from sections, then aggregation (BAGELS, FutureGen, SBC system). Strongest signal is the explicit limitations section.
   - Contradiction detection between paper pairs (ContraCrow). Verified.
   - Comparison matrix empty cells: the Elicit/SciSpace table workflow implies it, but no paper was found that evaluates empty-cell gap detection. UNVERIFIED as a method.
3. Idea generation methods:
   - Problem-first retrieval plus iterative critique (ResearchAgent, SciMON).
   - Chain of prior work to predict next step (Chain of Ideas).
   - Facet recombination with novelty check (Scideator).
   - Search-plan rounds across fields for diversity (Nova).
4. Evaluation evidence is mostly authors' own. Independent evaluations are thin:
   - Si et al. (human study, 100+ NLP researchers; verified scope on search only).
   - Scideator (user study, 22 researchers).
   - LiveIdeaBench (judge-panel scoring).
   - Undermind, Consensus: vendor claims only.
5. Known weak spots reported by sources: LLM self-evaluation unreliable (Si et al.); diversity drops at scale (Si et al.); incremental ideas (SciMON); binary novelty reduction (RINoBench); newer-equals-more-novel proxy (SchNovel).

---

## Part 3. Design lessons for a local app

Target app: extracts a structured profile per paper with verifiable page quotes; links papers (citations plus shared problem/method); finds gaps for one or many papers; idea-refinement chat.

### L1. Store page-level evidence, not just text
PaperQA2 and Elicit both keep a snippet and the page it came from. Store every extracted value with at least one evidence span: physical PDF page index, printed page label, exact quote, and a hash of the source file. The user explicitly asked for this (AGENTS.md domain rule on physical vs printed pages and hashes). Reject any generated field whose quote cannot be found by exact or fuzzy match in the stored page text.

### L2. Use a fixed facet schema for profiles
Scideator's three facets (purpose, mechanism, evaluation) are the simplest proven reusable structure. Extend with data and metrics (from Elicit-style column design) and limitations (BAGELS, FutureGen show limitations need a dedicated slot). AZ roles (AIM, BASIS, OWN, OTHER) suggest a sentence-level label used as a section filter before LLM extraction.

### L3. Typed links, with citations as one signal
Semantic Scholar exposes citation intent and influence flags per citation (datasets schema, SEARCH-ONLY). scite shows supporting/mentioning/contrasting with context. So link records should carry type and evidence, not only a similarity score. Shared problem or method (facet match) is a separate relation type from citation. Connected Papers shows that co-citation and bibliographic coupling give a useful non-citation signal.

### L4. Gap records should cite the limitation or claim they come from
Gap evidence should point to the limitation quote(s) in each paper plus any contradicting or comparable paper. A gap with no evidence span is a hypothesis, and should be labelled `hypothesis` with `confidence`. Follow the SBC system's trade-off: prefer precision and show confidence.

### L5. Novelty checks as a separate, explicit step
Do not generate and claim novelty in one pass. Use a retrieve-then-check step (Scideator, CoI novelty checker). Store the retrieved neighbours and the verdict so the user can audit them. Do not treat a binary novel/not-novel label as final (RINoBench critique).

### L6. Idea chat: keep the idea as a versioned record
Scideator's loop (adopt, regenerate, change facets) argues for storing each idea as a record linked to its facets and its novelty check, with versions. The chat edits the record; the record is the source of truth.

### L7. Evaluation hooks
Use the Si et al. lesson: LLM self-evaluation is unreliable. Keep the human decision as the final field, and log which paper quotes an idea relied on.

### L8. Optional external sources
Semantic Scholar offers TLDR, citation intents, and recommendations (see Part 1.2 for verification status). Any external API call sends paper metadata or text off the machine, so the AGENTS.md rule applies: explicit user request and a clear preview of what will be sent.

---

## Part 4. Proposed JSON schemas

These are proposals justified by the sources above. Field names are suggestions.

### 4.1 Paper profile

```json
{
  "paper_id": "string (local id, stable across re-parses)",
  "source": {
    "file_sha256": "string",
    "file_name": "string",
    "physical_page_count": "integer",
    "external_ids": { "doi": "string|null", "arxiv": "string|null", "semantic_scholar": "string|null" }
  },
  "bibliographic": { "title": "string", "authors": ["string"], "year": "integer|null", "venue": "string|null" },
  "page_labels": [ { "physical_page": "integer", "printed_label": "string|null" } ],
  "facets": {
    "problem":     { "value": "string", "evidence": ["EvidenceSpan"] },
    "method":      { "value": "string", "evidence": ["EvidenceSpan"] },
    "contributions": [ { "value": "string", "evidence": ["EvidenceSpan"] } ],
    "strengths":   [ { "value": "string", "evidence": ["EvidenceSpan"] } ],
    "limitations": [ { "value": "string", "evidence": ["EvidenceSpan"], "origin": "author_stated|inferred" } ],
    "datasets":    [ { "name": "string", "evidence": ["EvidenceSpan"] } ],
    "metrics":     [ { "name": "string", "result": "string|null", "evidence": ["EvidenceSpan"] } ],
    "evaluation":  { "value": "string", "evidence": ["EvidenceSpan"] }
  },
  "section_roles": [ { "physical_page": "integer", "sentence_id": "string", "role": "AIM|BASIS|OWN|OTHER|TEXTUAL|UNKNOWN" } ],
  "extraction": { "model": "string", "prompt_version": "string", "run_at": "ISO-8601", "status": "draft|user_verified" }
}
```

```json
{
  "EvidenceSpan": {
    "physical_page": "integer (1-based PDF page)",
    "printed_label": "string|null",
    "section": "string|null",
    "quote": "string (exact text from the page)",
    "char_start": "integer|null",
    "char_end": "integer|null",
    "verified_by_match": "exact|fuzzy|manual"
  }
}
```

Justification: PaperQA2 keeps per-chunk summaries with scores and page-range citations (VERIFIED). Elicit shows supporting quotes per cell (SEARCH-ONLY). Scideator's facets (SEARCH-ONLY, verified abstract) map to problem/method/evaluation. Limitations as a separate slot follows BAGELS and FutureGen. The `section_roles` field follows Teufel's AZ scheme (SEARCH-ONLY). Physical vs printed pages follow the AGENTS.md rule.

### 4.2 Paper link

```json
{
  "link_id": "string",
  "from_paper_id": "string",
  "to_paper_id": "string",
  "relation": "cites|cited_by|co_cited|bibliographically_coupled|same_problem|same_method|extends|contradicts|supports|uses_dataset|compares_against",
  "direction": "directed|undirected",
  "strength": "number 0..1",
  "basis": {
    "source": "citation_graph|facet_match|llm_judgment|user",
    "citation_intent": "background|method|result_comparison|supporting|mentioning|contrasting|null",
    "influential": "boolean|null"
  },
  "evidence": [ { "from_paper_evidence": "EvidenceSpan", "to_paper_evidence": "EvidenceSpan|null", "citing_sentence": "string|null" } ],
  "status": "suggested|accepted|rejected",
  "created_by": "string"
}
```

Justification: relation types come from scite's supporting/mentioning/contrasting and SciCite's intents (SEARCH-ONLY). `influential` and `citing_sentence` mirror Semantic Scholar's `isinfluential` and `contexts` fields (SEARCH-ONLY, datasets release index). Co-citation and bibliographic coupling come from Connected Papers (SEARCH-ONLY). The `status` field keeps user decisions separate from machine suggestions, consistent with Si et al. on LLM judgment reliability.

### 4.3 Gap record

```json
{
  "gap_id": "string",
  "scope": { "paper_ids": ["string"], "mode": "single_paper|multi_paper_corpus" },
  "statement": "string (the gap, one sentence)",
  "gap_type": "unexplored_combination|unaddressed_limitation|conflicting_findings|missing_dataset_or_metric|untested_setting|method_not_applied_to_problem",
  "supporting_limitations": [ { "paper_id": "string", "limitation_index": "integer", "evidence": ["EvidenceSpan"] } ],
  "supporting_contradictions": [ { "paper_a": "string", "paper_b": "string", "claim_a": "EvidenceSpan", "claim_b": "EvidenceSpan", "detector": "llm|user" } ],
  "absent_in": [ { "paper_id": "string", "facet": "problem|method|dataset|metric|evaluation", "note": "string" } ],
  "retrieved_neighbours_checked": ["string (paper_id or external id)"],
  "novelty_check": { "verdict": "not_found|similar_found|uncertain", "neighbours": ["string"], "checked_at": "ISO-8601" },
  "confidence": "number 0..1",
  "status": "hypothesis|supported|user_accepted|rejected"
}
```

Justification: limitation-based gap extraction (BAGELS, FutureGen, SBC system) and contradiction detection (PaperQA2 ContraCrow, verified) motivate the two evidence arrays. `absent_in` is the comparison-matrix empty-cell idea; this is a proposal, not a verified method (see Part 2). The `novelty_check` field follows the retrieve-then-check step in Scideator and CoI, and avoids a binary-only verdict (RINoBench). `confidence` and `status: hypothesis` follow the SBC precision-over-recall trade-off.

### 4.4 Idea record (for the refinement chat)

```json
{
  "idea_id": "string",
  "version": "integer",
  "parent_version": "integer|null",
  "facets": { "problem": "string", "method": "string", "evaluation": "string" },
  "source_paper_ids": ["string"],
  "source_evidence": ["EvidenceSpan"],
  "analogous_paper_ids": ["string"],
  "novelty_check_ref": "string (gap or novelty check id)",
  "feasibility_notes": "string",
  "user_decision": "open|keep|drop",
  "chat_log_ref": "string"
}
```

Justification: Scideator's loop (adopt, regenerate, edit facets) (SEARCH-ONLY). Versioning follows the AGENTS.md rule that the record is the source of truth. `analogous_paper_ids` follows Scideator's distance-controlled retrieval.

---

## Part 5. Items not verified and conflicts

- NotebookLM limits and retrieval design: UNVERIFIED (no Google primary page).
- Consensus paper count (200M vs 220M) and pricing: UNVERIFIED.
- Undermind recall and precision numbers: vendor-only; the 96% figure is a blogger's inference, UNVERIFIED.
- SciSpace column caps: sources disagree; UNVERIFIED.
- Semantic Scholar API endpoint paths, rate limits, and recommendation limit (500 vs 100): UNVERIFIED (primary docs did not render).
- open_deep_research clarify and brief phases: SEARCH-ONLY (aggregator); repo page showed a different layout.
- GPT Researcher star count: 27.7k to 28.1k depending on snapshot.
- Zotero plugin maintenance status: UNVERIFIED for all.
- Smart Connections MCP cloud-transmission claim: UNVERIFIED; inspect code before use.
- Chain of Ideas: aggregator arXiv IDs 2409.07578 and 2408.17404 are wrong; use 2410.13185.
- IdeaBench author list conflicts across sources; UNVERIFIED.
- SciCite figures and intent label names: UNVERIFIED against the primary paper.
- STORM coverage percentages (25%, 10%): from a news article; UNVERIFIED.
- Nova novelty definition: UNVERIFIED.
- Scideator code release: not linked on the arXiv abstract page; UNVERIFIED.
- Chain of Ideas and Nova code repos: named in SEARCH-ONLY results; not confirmed on arXiv pages.

## Part 6. Source URL index (primary first)

- https://arxiv.org/abs/2409.13740 (PaperQA2, VERIFIED)
- https://arxiv.org/html/2409.13740v2 (PaperQA2 methods and LitQA2 numbers, VERIFIED)
- https://www.futurehouse.org/paperqa (SEARCH-ONLY)
- https://arxiv.org/pdf/2408.15232v1.pdf (Co-STORM, SEARCH-ONLY)
- https://arxiv.org/abs/2411.14199 (OpenScholar, SEARCH-ONLY)
- https://github.com/assafelovic/gpt-researcher (SEARCH-ONLY)
- https://github.com/langchain-ai/open_deep_research (VERIFIED)
- https://support.elicit.com/en/articles/4267649 (SEARCH-ONLY)
- https://support.elicit.com/en/articles/14758162 (SEARCH-ONLY)
- https://undermind.ai/ (SEARCH-ONLY)
- https://casrai.org/guides/consensus-ai-search-engine-guide (SEARCH-ONLY)
- https://stagecf.scispace.com/extract-data (SEARCH-ONLY)
- https://www.connectedpapers.com/about (SEARCH-ONLY)
- https://paperguide.ai/blog/litmaps-vs-researchrabbit/ (SEARCH-ONLY, secondary)
- https://arxiv.org/abs/2004.15011 (TLDR, SEARCH-ONLY)
- https://api.semanticscholar.org/datasets/v1/release/latest (SEARCH-ONLY)
- https://api.semanticscholar.org/api-docs/ (fetch returned navigation only)
- https://doaj.org/article/81fa50fb3c294f6ba01cc597d41a974e (scite, SEARCH-ONLY)
- https://library.hkust.edu.hk/sc/?p=1704 (scite accuracy, SEARCH-ONLY)
- https://github.com/brianpetro/obsidian-smart-connections (SEARCH-ONLY)
- https://github.com/msdanyg/smart-connections-mcp (SEARCH-ONLY)
- https://arxiv.org/abs/2404.07738 (ResearchAgent, SEARCH-ONLY)
- https://arxiv.org/abs/2305.14259 (SciMON, SEARCH-ONLY)
- https://arxiv.org/abs/2410.13185 (Chain of Ideas, VERIFIED abstract)
- https://arxiv.org/abs/2409.04109v1 (Si et al., SEARCH-ONLY)
- https://arxiv.org/abs/2409.14634 (Scideator, VERIFIED abstract)
- https://arxiv.org/abs/2410.14255 (Nova, VERIFIED abstract)
- https://arxiv.org/abs/2411.02429 (IdeaBench, SEARCH-ONLY)
- https://arxiv.org/abs/2412.17596 (LiveIdeaBench, SEARCH-ONLY)
- https://arxiv.org/html/2409.16605v1 (SchNovel, SEARCH-ONLY)
- https://arxiv.org/pdf/2603.10303 (RINoBench, SEARCH-ONLY)
- https://arxiv.org/pdf/2505.18207 (BAGELS, SEARCH-ONLY)
- https://arxiv.org/html/2503.16561v1 (FutureGen, SEARCH-ONLY)
- https://data.mendeley.com/datasets/px9xd7tw8n (SEARCH-ONLY)
- https://sol.sbc.org.br/index.php/wesaac/article/download/45243/45004/ (SEARCH-ONLY)
- https://repository.tudelft.nl/record/uuid:bebea6a3-0921-440a-8a29-7aa7f55cac4e (SEARCH-ONLY)
- https://arxiv.org/pdf/1904.01608 (SciCite, SEARCH-ONLY)
- https://www.cl.cam.ac.uk/~sht25/thesis/abstract.html (Teufel thesis, SEARCH-ONLY)
