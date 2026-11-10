# H. Paper understanding with small/free models, linking, gap detection, field taxonomy

**Date:** 2026-11-10
**Scope:** K1 (paper profile), K2 (paper links), K3 (gap candidates), K4 (field auto-organization), O8/O9 (research-loop evidence and per-stage JSON schemas).

**Method:** Web search (about 25 queries) followed by WebFetch of primary pages (arXiv abstracts and HTML, official Ollama, OpenAlex, Semantic Scholar, and Anthropic docs). Where a fetch failed or returned only a summary, the entry is tagged accordingly. Search-result snippets were used only where no primary page was opened. No repository files were modified and no private data was sent anywhere. All queries used generic terms.

**Verification legend**
- [V] = primary page opened and the claim confirmed (abstract-level or full-text as noted)
- [S] = search-result snippet or third-party summary only
- [U] = could not confirm (page not reached, or claim not found)

---

## Part 1 — Source records

Sources are numbered S01 to S40. Cross-references in Parts 2 to 4 use these numbers.

### S01. Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models
- **Authors / org:** Zhi Rui Tam, Cheng-Kuang Wu, Yi-Lin Tsai, Chieh-Yen Lin, Hung-yi Lee, Yun-Nung Chen (National Taiwan University, Appier AI Research)
- **Venue / date:** arXiv 2408.02442 (cs.CL), submitted 5 Aug 2024, v3 14 Oct 2024. Search snippets link it to an EMNLP 2024 Industry paper [S].
- **URL:** https://arxiv.org/abs/2408.02442 ; full HTML https://arxiv.org/html/2408.02442v3
- **Tag:** [V] (HTML body read)
- **Findings:**
  - Formats tested: JSON-mode and format-restricting instructions, XML, YAML, against a natural-language (NL) baseline. Also an "NL-to-Format" two-step method. Markdown was not tested.
  - Models: gpt-3.5-turbo-0125, claude-3-haiku-20240307, gemini-1.5-flash, LLaMA-3-8B-Instruct, Gemma-2-9B-Instruct. Appendices add Mistral-7B-v0.3 and gpt-4o-mini.
  - GSM8K zero-shot, Text vs JSON: Claude 3 Haiku 86.5 vs 23.4; GPT-3.5 76.6 vs 49.3; Gemini 1.5 Flash 89.3 vs 89.2; LLaMA-3-8B 74.7 vs 48.9.
  - Last Letter (GPT-3.5): 56.7 (Text) vs 25.2 (JSON). The paper reports that 100% of GPT-3.5 JSON-mode responses put the "answer" key before the "reason" key, so the model answered directly without chain-of-thought.
  - Classification (DDXPlus), Text vs JSON: Gemini 41.6 vs 60.3; GPT-3.5 44.1 vs 55.5; Haiku 33.8 vs 52.0. Gains were smaller or absent on other classification tasks (MultiFin GPT-3.5 63.0 vs 64.0).
  - Stricter formats generally hurt reasoning more; format restriction can help classification by narrowing the answer space.
- **Relevance to EasyResearch:** This is the main evidence against a single schema-constrained call that asks for an answer before the reasoning or quote. The key-order effect is directly actionable for K1. The LLaMA-3-8B row is the closest proxy for the local model. The DDXPlus gains suggest structure helps when the task is picking from a small label set (for example, facet classification).

### S02. "Say What You Mean" (dottxt rebuttal to Tam et al.)
- **Authors / org:** dottxt (a company that sells structured generation)
- **Venue / date:** Blog post; date not confirmed in the fetch [U].
- **URL:** https://blog.dottxt.ai/say-what-you-mean.html
- **Tag:** [V] (fetched; the summarizer read the post, but the numbers were not checked against the reproduction code)
- **Findings:**
  - Re-ran tasks with Llama-3-8B-Instruct. GSM8K unstructured 0.77 vs structured 0.78; Last Letter 0.73 vs 0.77; Shuffle Object 0.41 vs 0.44.
  - Claims Tam et al.'s JSON prompt never mentions JSON or a schema and refers to tools that are not provided, which the post says explains the low JSON accuracy (<10%).
  - Claims the NL and structured conditions used different prompts, so the comparison is not like-for-like.
  - Notes that Tam et al. used claude-3-haiku as a parser, which the post calls the "AI parser". On recorded Last Letter outputs, a strict regex scored 0.35, the AI parser 0.57, and a flexible regex 0.61.
  - Reports that the reproduction code is public on GitHub.
- **Relevance to EasyResearch:** Shows that the Tam et al. result depends on prompt wording and answer parsing. This matters for K1 because our own parser is also a risk factor. The post is a vendor rebuttal, so its numbers need independent replication before we rely on them. It does not contradict the answer-before-reasoning ordering effect, which is a schema-level issue.

### S03. The Format Tax (arXiv 2604.03616)
- **Authors / org:** Ivan Yee Lee, Loris D'Antoni, Taylor Berg-Kirkpatrick
- **Venue / date:** arXiv, submitted 4 Apr 2026.
- **URL:** https://arxiv.org/abs/2604.03616
- **Tag:** [V] (abstract page read; per-model tables not reached)
- **Findings:**
  - Six open-weight and four API models; formats JSON, XML, LaTeX, Markdown; tasks math, science, logic, writing.
  - Reports that structured-output requirements substantially degrade reasoning and writing in open-weight models, while most recent closed-weight models show little or no penalty.
  - Attributes most of the accuracy loss to the format-requesting instructions themselves, with constrained decoding explaining only a fraction.
  - Proposes separating reasoning from formatting: freeform generation followed by a reformatting pass, or extended thinking in one generation. Reports that this recovers most of the lost accuracy. Per-model numbers were not reached [U].
- **Relevance to EasyResearch:** The most recent evidence that our local open-weight 8B is the case most exposed to the penalty. It supports a two-pass design (free notes or quotes, then schema-constrained output) for K1 and O8/O9.

### S04. Thinking Before Constraining: A Unified Decoding Framework (In-Writing; arXiv 2601.07525)
- **Authors / org:** Ngoc Trinh Hung Nguyen, Alonso Silva, Laith Zumot, Liubov Tupikina, Armen Aghasaryan, Mehwish Alam (Nokia Bell Labs and collaborators)
- **Venue / date:** arXiv, submitted 12 Jan 2026, v2 28 May 2026. v2 comment lists EMNLP.
- **URL:** https://arxiv.org/abs/2601.07525
- **Tag:** [V]
- **Findings:**
  - Model reasons freely, and structured decoding starts only after a trigger token (examples given: `<eos>` or `{`).
  - Defines "premature triggering": constrained decoding interrupts reasoning still in progress. Reports that trigger-token strategies "virtually eradicate" it.
  - Abstract reports accuracy gains of up to 27% over natural generation, with a 10 to 20 token overhead [S for the overhead, from the arXiv listing]. Models named in aggregators: Qwen, Llama, Gemma, DeepSeek, SmolLM (1.5B to 14B). Per-model numbers not reached [U].
  - Code in a Nokia-Bell-Labs InWriting repository (as stated in the paper listing) [S].
- **Relevance to EasyResearch:** Gives a principled version of "reason first, then format" that can run in one call if the runtime supports triggers. Our Ollama path uses a grammar-based `format` parameter, so trigger-based decoding would need a custom runtime. The practical equivalent is two calls, which Part 3 covers.

### S05. JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models (arXiv 2501.10868)
- **Authors / org:** Saibo Geng, Hudson Cooper, Michał Moskal, Samuel Jenkins, Julian Berman, Nathan Ranchin, Robert West, Eric Horvitz, Harsha Nori (EPFL, Microsoft and collaborators)
- **Venue / date:** arXiv, submitted 18 Jan 2025, last revised 27 Feb 2025 (v3). Earlier versions titled "Generating Structured Outputs from Language Models: Benchmark and Studies" [S].
- **URL:** https://arxiv.org/abs/2501.10868 ; code https://github.com/guidance-ai/jsonschemabench
- **Tag:** [V] (abstract page; numbers were not on the page)
- **Findings:**
  - About 10K real-world JSON schemas in 10 groups, plus the official JSON Schema Test Suite.
  - Six frameworks: Guidance, Outlines, Llamacpp, XGrammar, OpenAI, Gemini.
  - Metrics: efficiency, coverage (declared, empirical, compliance rate), and quality.
  - Search snippets report about 50% speed-up for constrained decoding and a large coverage gap between best and worst frameworks [S, not confirmed on the abstract page].
- **Relevance to EasyResearch:** Supports the claim that schema support varies by runtime, so our schemas should stay within the subset Ollama handles, and that we should test compliance and coverage on our own schemas. Use the framework comparison as a check on our schema complexity, not as a choice of runtime.

### S06. Ollama Structured Outputs documentation
- **Authors / org:** Ollama
- **Venue / date:** Official docs (undated on the fetched page)
- **URL:** https://docs.ollama.com/capabilities/structured-outputs
- **Tag:** [V]
- **Findings:**
  - `format` accepts `"json"` or a JSON schema object. Examples validate the output with Pydantic (Python) or Zod (JavaScript) after generation.
  - Recommended practices: define schemas with Pydantic or Zod, include the schema as a string in the prompt, set temperature to 0.
  - Works through the OpenAI-compatible `response_format` as well.
  - Ollama Cloud does not support structured outputs (as of the fetch).
  - The docs do not explain the decoding mechanism in detail. Third-party sources describe a grammar conversion [S].
  - Community reports of preambles ("Sure! Here is the JSON") and invented fields are anecdotal [S].
- **Relevance to EasyResearch:** Official confirmation that schemas can be passed to the local runtime, and that post-validation is expected. Supports O8/O9 and the post-validation step in K1.

### S07. Ollama context length documentation
- **Authors / org:** Ollama
- **Venue / date:** Official docs (undated)
- **URL:** https://docs.ollama.com/context-length
- **Tag:** [V]
- **Findings:**
  - Default context by VRAM tier: under 24 GiB: 4k; 24 to 48 GiB: 32k; 48 GiB or more: 256k.
  - Recommends at least 64,000 tokens for agentic, web-search, or coding tools.
  - Set via the app slider, or `OLLAMA_CONTEXT_LENGTH` on the server. The fetched page did not cover Modelfile or per-request options, so the precedence claim from third-party sources is [S] only.
  - A larger context needs more memory. The docs advise avoiding CPU offload and checking `ollama ps` (PROCESSOR column).
- **Relevance to EasyResearch:** The official default for an 8 GB card is 4k. Our `num_ctx = min(32768, max(8192, ...))` formula sets the window above the official default, which increases the risk of offload on an 8 GB card. The docs tell us to check `ollama ps` in practice.

### S08. Lost in the Middle: How Language Models Use Long Contexts (arXiv 2307.03172)
- **Authors / org:** Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang (Stanford and collaborators)
- **Venue / date:** TACL 2023 (accepted). arXiv v1 6 Jul 2023, v3 20 Nov 2023.
- **URL:** https://arxiv.org/abs/2307.03172
- **Tag:** [V] (abstract page)
- **Findings:**
  - Two tasks: multi-document QA and key-value retrieval.
  - Performance is often highest when the relevant information is at the start or end of the context, and drops when it is in the middle. This holds for explicitly long-context models too.
  - Performance decreases as the input grows. Specific numbers were not on the abstract page [U].
- **Relevance to EasyResearch:** Supports sending section-targeted, shorter inputs rather than one long text, and placing the target evidence (conclusion, limitations) near the start of each call.

### S09. Language agents achieve superhuman synthesis of scientific knowledge (PaperQA2; arXiv 2409.13740)
- **Authors / org:** Michael D. Skarlinski, Sam Cox, Jon M. Laurent, James D. Braza, Michaela Hinks, Michael J. Hammerling, Manvitha Ponnapati, Samuel G. Rodriques, Andrew D. White (FutureHouse and collaborators)
- **Venue / date:** arXiv, submitted 10 Sep 2024, v2 26 Sep 2024.
- **URL:** https://arxiv.org/abs/2409.13740
- **Tag:** [V] (abstract)
- **Findings:**
  - Agent covers information retrieval, cited summarization (Wikipedia-style), and contradiction detection.
  - Authors say it "matches or exceeds" subject-matter experts on three literature tasks. Expert comparison details are not on the abstract page.
  - Contradictions: 2.34 ± 1.99 per paper on a random biology subset; human experts validated 70%.
  - Introduces the LitQA2 benchmark, on which the agent exceeds human performance (no numeric score on the abstract page).
  - Authors frame the reliability concern as hallucination risk.
- **Relevance to EasyResearch:** The 70% validation rate is the most useful number for K3. Even a strong agent produces roughly 30% false contradictions, so candidate-plus-human-acceptance is the right design. Also supports retrieval-grounded summaries with citations (quotes plus pages).

### S10. Prompting best practices (Anthropic / Claude Platform docs), long-context section
- **Authors / org:** Anthropic
- **Venue / date:** Official docs (undated on the fetched page; lists current model names including Haiku 5.5)
- **URL:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- **Tag:** [V] (full text read from the fetch; the long-context section was located in the saved output)
- **Findings:**
  - Long-context prompting applies to "20k+ tokens". Put long-form data near the top, above the query and instructions. Says this improves performance across models.
  - For long-document tasks, ask the model to quote relevant parts first, then carry out the task; quotes go in tags (an example uses `<quotes>` and `<info>` tags).
- **Relevance to EasyResearch:** Official source for quote-first grounding, which matches K1's quote-plus-page requirement. Note that this guidance is written for large frontier models; it has not been validated for 8B local models.
- **Conflict note:** A secondary source claimed a 20K threshold. The official page says "20k+ tokens", which agrees. Our papers are shorter than 8000 chars of usable text in the first pass, so the threshold does not apply directly to our current design.

### S11. Ollama streaming, timeouts, and keep_alive (third-party guidance)
- **Authors / org:** Various blogs (markaicode, adhdecode, SSD Nodes, mljourney)
- **Venue / date:** Undated community guides
- **URL (representative):** https://markaicode.com/errors/ollama-timeout-error-fix/
- **Tag:** [S]
- **Findings:**
  - With `stream: false`, the client receives nothing until generation completes, so the whole generation must fit one timeout window. Streaming resets the clock per chunk.
  - Default keep-alive is 5 minutes; per-request `keep_alive` or `OLLAMA_KEEP_ALIVE` can extend it. Unloaded models pay a reload cost on the next request.
  - Partial CPU offload (for example, a 49/51 CPU/GPU split) slows generation and can cause timeouts on long outputs.
  - Sources disagree on timeout variables. `OLLAMA_LOAD_TIMEOUT` is cited as real; `OLLAMA_REQUEST_TIMEOUT` and `OLLAMA_READ_TIMEOUT` could not be confirmed [U].
- **Relevance to EasyResearch:** Explains why 120 to 300 s timeouts occur with a long non-streaming schema call. The fix is streaming plus a per-chunk watchdog, not just a longer timeout. Official docs for the timeout variables were not reached [U].

### S12. SciREX: A Challenge Dataset for Document-Level Information Extraction (arXiv 2005.00512)
- **Authors / org:** Yi Luan et al. (University of Washington and collaborators; author list not confirmed on the fetch)
- **Venue / date:** ACL 2020 (per general knowledge; not confirmed in this session [U]).
- **URL:** https://arxiv.org/pdf/2005.00512
- **Tag:** [S]
- **Findings:**
  - Document-level extraction of 4-ary result tuples (Dataset, Metric, Method, Task) from ML papers, with Score in some formulations.
  - Labels were distantly supervised from Papers with Code leaderboards (weak labels, not textual spans). Snippet-level details conflict across summaries (438 papers vs 1,170 papers) [U on the exact counts].
  - Tuples span multiple sentences and sections.
- **Relevance to EasyResearch:** Shows that result-type facets (datasets, metrics, results) are a known schema and that span-level grounding is hard, which supports our quote-plus-page design and explains why "results" and "metrics" facets are the most error-prone.

### S13. TDMS-IE / TDMR-PR and the Papers with Code leaderboard extraction line of work
- **Authors / org:** Various (per survey snippet)
- **Venue / date:** Various
- **URL:** https://www.paperswithcode.com/dataset/scirex (dataset page reached only via search)
- **Tag:** [U] for the Papers with Code TDMS page itself. [S] for the research lines.
- **Findings:**
  - TDMS-IE aims to extract task, dataset, metric and score from NLP papers toward automatic leaderboards. A survey lists it as closed, extracting (task, dataset, metric) plus best score.
  - A 2024 method, TDMS-PR, extracts a similar tuple [S].
- **Relevance to EasyResearch:** A proven small schema (task, dataset, metric, score) that could be a constrained sub-schema for the "datasets, metrics, results" facets. The Papers with Code TDMS page was not reached, so the exact task definition is [U].

### S14. Exploring LLMs for Scientific Information Extraction Using The SciEx Framework (arXiv 2512.10004)
- **Authors / org:** Sha Li, Ayush Sadekar, Nathan Self, Yiqi Su, Lars Andersland, Mira Chaplin, Annabel Zhang, Hyoju Yang, James B Henderson, Krista Wigginton, Linsey Marr, T.M. Murali, Naren Ramakrishnan (Virginia Tech and collaborators)
- **Venue / date:** arXiv 10 Dec 2025, v2 23 Jan 2026. Non-archival, KGML Bridge at AAAI 2026.
- **URL:** https://arxiv.org/abs/2512.10004
- **Tag:** [V] (abstract)
- **Findings:**
  - Modular framework decoupling PDF parsing, multi-modal retrieval, extraction, and aggregation. Aggregation reconciles information across publications into standard formats.
  - Says current pipelines struggle with long-context documents, multi-modal content, and inconsistent information across papers.
  - The abstract does not say that the design is map-reduce, names no datasets, and gives no numbers [U for all of these].
- **Relevance to EasyResearch:** Validates the decoupling we already plan: parse, retrieve, extract, aggregate as separate stages, each with its own validation. Do not rely on it for numbers.

### S15. LLM MapReduce (ACL 2025) — chunked map, collapse, reduce for long text
- **Authors / org:** Various
- **Venue / date:** ACL 2025 (as named in search results)
- **URL:** not confirmed [U]; a search result mislabelled the ACL 2025 paper, so the link is not reliable.
- **Tag:** [S]
- **Findings:** Training-free long-text method that splits a document into chunks (by token length and semantic boundary), runs map steps, collapses intermediate outputs, then reduces.
- **Relevance to EasyResearch:** The standard reference for chunked map-reduce. Relevant as a fallback for long papers, but a per-page or per-section map can multiply the call count on an 8B model. Use only if section targeting fails.

### S16. CLAIM-BENCH (arXiv 2506.08235)
- **Authors / org:** Various (ACL/IJCNLP 2025)
- **URL:** https://arxiv.org/pdf/2506.08235 (search-result link) [S]
- **Tag:** [S]
- **Findings:** Over 300 expert-annotated claim-evidence pairs from AI papers. Reports that models struggle to link dispersed evidence across long documents and tend to show higher recall at the cost of precision.
- **Relevance to EasyResearch:** Supports precision-first filtering of AI-generated claims and expecting higher recall than precision in our K1 facets. Use as a benchmark template for our own gold set.

### S17. Human-LLM Compound System for Scientific Ideation through Facet Recombination and Novelty Evaluation (Scideator; arXiv 2409.14634)
- **Authors / org:** Marissa Radensky, Simra Shahid, Raymond Fok, Pao Siangliulue, Tom Hope, Daniel S. Weld
- **Venue / date:** arXiv 23 Sep 2024; current v7 revised 16 May 2026. Earlier title "Scideator: Human-LLM Scientific Idea Generation Grounded in Research-Paper Facet Recombination."
- **URL:** https://arxiv.org/abs/2409.14634
- **Tag:** [V] (abstract)
- **Findings:**
  - Facets: purpose (problem), mechanism (solution), evaluation (how success is judged). Facets are extracted from starting and related papers.
  - Idea Novelty Checker: facet-based retrieve-then-rerank. Ablations report it surfaces more relevant papers than standard retrieval and reranking; a facet-grounded novelty classifier beats classifiers that reason over unstructured text.
  - User study with computer scientists: significantly more creativity support than a same-backbone baseline without facet modules, mainly for exploration and expressiveness. Participant count not in the abstract.
  - "SOLVENT" (the name in our brief) did not appear in any result [U]; Scideator is the matching system.
- **Relevance to EasyResearch:** Gives a facet schema that matches K1's problem/method/evaluation framing. The facet-based retrieval result supports using facets as retrieval keys for K2 linking, instead of keywords alone.

### S18. BAGELS: Benchmarking the Automated Generation and Extraction of Limitations from Scholarly Text (arXiv 2505.18207)
- **Authors / org:** Ibrahim Al Azher, Miftahul Jannat Mokarrama, Zhishuai Guo, Sagnik Ray Choudhury, Hamed Alhoori
- **Venue / date:** Findings of EMNLP 2025; arXiv v2 Sep 2025.
- **URL:** https://arxiv.org/abs/2505.18207 ; code https://github.com/IbrahimAlAzhar/BAGELS_Limitation_Gen
- **Tag:** [V] (abstract and metadata)
- **Findings:**
  - Data from ACL, NeurIPS, and PeerJ papers, with limitations from the paper text supplemented with external reviews.
  - Two tasks: extract limitations; generate them with RAG. Also a fine-grained evaluation framework and a meta-evaluation.
  - Paper count and numeric results not on the abstract page [U].
  - "LimTopic" (from our brief) did not appear anywhere in results [U].
- **Relevance to EasyResearch:** The extraction task is the direct analogue of our K3 cue-sentence step. The fine-grained evaluation and meta-evaluation design is worth copying for our gold-set check.

### S19. Can LLMs Identify Critical Limitations within Scientific Research? (LimitGen; arXiv 2507.02694)
- **Authors / org:** Zhijian Xu, Yilun Zhao, Manasi Patwardhan, Lovekesh Vig, Arman Cohan
- **Venue / date:** arXiv 3 Jul 2025, v1.
- **URL:** https://arxiv.org/abs/2507.02694
- **Tag:** [V] (abstract)
- **Findings:**
  - LimitGen-Syn: synthetic limitations created by controlled perturbations of high-quality papers. LimitGen-Human: real human-written limitations.
  - Scope is AI and NLP research.
  - The abstract says literature retrieval augmentation "enhances" limitation generation, with no numbers on the page [U].
- **Relevance to EasyResearch:** The synthetic subset is a useful way to test whether our K3 extractor catches a planted limitation sentence. Supports building a synthetic-perturbation check for our gap detector.

### S20. FutureGen: A RAG-based Approach to Generate the Future Work of Scientific Article (arXiv 2503.16561)
- **Authors / org:** Ibrahim Al Azher and colleagues (Northern Illinois University)
- **Venue / date:** arXiv, cs.CL, v3 4 Sep 2025.
- **URL:** https://arxiv.org/abs/2503.16561
- **Tag:** [S] (not opened directly; search summaries disagree on dataset size)
- **Findings:**
  - Future-work generation with RAG over related papers, iterative LLM feedback, and LLM-as-judge evaluation.
  - Papers often lack a separate future-work section, so an LLM extracts future-work sentences, which were validated with human annotators.
  - Dataset size conflicts: v2 says about 8,000 ACL papers (2012 to 2024) plus 1,000 NeurIPS; an alphaXiv summary says about 4,000 ACL (2023 to 2024) plus 1,000 NeurIPS (2021 to 2022) [U on the exact count].
  - Code: IbrahimAlAzhar/FutureWorkGeneration; dataset iaadlab/FutureGen on Hugging Face (from search metadata).
- **Relevance to EasyResearch:** Directly relevant to K3's future-work mining. Shows that LLM-based sentence extraction for future work needed annotator validation, supporting a manual check of our cue-sentence precision.

### S21. Fact or Fiction: Verifying Scientific Claims (SciFact; arXiv 2004.14974)
- **Authors / org:** David Wadden and colleagues
- **Venue / date:** EMNLP 2020 (pp. 7534 to 7550 per ACL Anthology snippet); arXiv April 2020, last version 3 Oct 2020.
- **URL:** https://arxiv.org/abs/2004.14974
- **Tag:** [S] (search snippet; abstract summary consistent with the arXiv listing)
- **Findings:**
  - Task: given a claim, find abstracts that support or refute it and identify rationale sentences.
  - About 1.4K expert-written claims. Domain adaptation helps substantially over Wikipedia- or news-trained models.
- **Relevance to EasyResearch:** Establishes the "claim plus rationale sentence" pattern that our quote-plus-page verification mirrors. Useful for designing AI gap-candidate verification.

### S22. Citation intent: Cohan et al. 2019 (multitask structural scaffolds) and SciCite
- **Authors / org:** Arman Cohan, Waleed Ammar, Madeleine van Zuylen, Field Cady (Allen Institute for AI and collaborators)
- **Venue / date:** NAACL 2019, pp. 3586 to 3596, DOI 10.18653/v1/N19-1361.
- **URL:** https://aclanthology.org/N19-1361/ ; SciCite https://allenai.org/data/scicite
- **Tag:** [S]
- **Findings:**
  - SciCite: about 11K annotated citation intents from CS and biomedical papers. TensorFlow catalog labels: Method, Background, Result; splits 8,194 / 916 / 1,859.
  - Reported macro F1 of about 84.0% on the larger set, per a third-party summary [U on the number].
  - Semantic Scholar later added citation-intent tags (method, background, result extension) to its graph, per an AI2 blog snippet [S].
- **Relevance to EasyResearch:** Shows that three coarse citation intents are a practical default; our nine relation types are finer and would need a separate, human-labeled check.

### S23. CiTO: A Citation Typing Ontology (Shotton 2010) and FaBiO/CiTO (Peroni and Shotton 2012)
- **Authors / org:** David Shotton, Silvio Peroni (with Ciccarese and Clark)
- **Venue / date:** Journal of Biomedical Semantics (2010, PMC2903725); Journal of Web Semantics (2012)
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC2903725/ ; https://msi.dublincore.org/standards/cito
- **Tag:** [S]
- **Findings:**
  - OWL 2 DL ontology for typing citations factually and rhetorically. Example properties: cites as authority, confirms, disagrees with, uses method in, uses data from.
  - FOCO companion classifies CiTO properties by factual and positive/neutral/negative rhetorical function [S].
  - Adoption in publishing is limited, per a 2020 editorial snippet [S]. Inter-rater agreement on citation function is reported as low in one condition [S].
- **Relevance to EasyResearch:** Gives a standard vocabulary for our nine relation types, which helps export to Obsidian or RDF-like forms later. Full property list not verified [U].

### S24. SPECTER2 (Ai2) — scientific document embeddings and adapters
- **Authors / org:** Ai2 (Allen Institute for AI)
- **Venue / date:** Ai2 blog, 27 Nov 2023; models on Hugging Face (allenai/specter2_base; proximity adapter; ad hoc query; classification and regression adapters).
- **URL:** https://allenai.org/blog/specter2-adapting-scientific-document-embeddings-to-multiple-fields-and-task-formats-c95686c06567 ; https://huggingface.co/allenai/specter2
- **Tag:** [S] (blog and Hugging Face metadata seen in search; model card not opened)
- **Findings:**
  - BERT-base with adapters, initialized from SciBERT, Apache 2.0; trained on citation triplets (over 6M, per model card snippet).
  - Input is typically title plus abstract. Proximity adapter is for link prediction and nearest-neighbour search.
  - Base model renamed on Hugging Face (old `allenai/specter2` is now `allenai/specter2_base`).
- **Relevance to EasyResearch:** The right embedding for K2 "similar paper" links, but it needs a model download or the API. The brief forbids new local model downloads, so use it only through the Semantic Scholar API (S25) if the user approves external transmission.

### S25. Semantic Scholar API product page
- **Authors / org:** Semantic Scholar / Ai2
- **Venue / date:** Official product page (undated)
- **URL:** https://www.semanticscholar.org/product/api
- **Tag:** [V]
- **Findings:**
  - Unauthenticated access: a shared pool of 1000 requests per second across all unauthenticated users.
  - With an API key, the introductory limit is 1 request per second on all endpoints. Higher rates possible after review.
  - Academic Graph includes author, paper, citation, venue and SPECTER2 embedding data. Recommendations suggest similar papers. The page does not say whether either is free.
  - Links to an API License Agreement; attribution and terms not summarized [U].
- **Relevance to EasyResearch:** Official confirmation that SPECTER2 vectors are reachable via API. The 1 RPS key limit is enough for tens of papers per hour, not hundreds of pairs at once. Sending titles or abstracts to an external service requires explicit user request and preview (repo invariant).

### S26. OpenAlex authentication and rate limits (help center)
- **Authors / org:** OpenAlex
- **Venue / date:** Official help page (the page says "Last updated November 3, 2026")
- **URL:** https://help.openalex.org/api-reference/authentication (redirected from developers.openalex.org)
- **Tag:** [V]
- **Findings:**
  - Basic queries work without a key. A free key is required for heavier use and for cursor paging past the first page.
  - Free key budget: $1 per day. No-key budget is not stated; the page says a free key gives 10x the no-key budget, which implies about $0.10 per day (inference).
  - New free accounts: first $1 paced at up to $0.10 every 5 minutes, ending after about 50 minutes of steady use. Does not apply to accounts created before 3 Nov 2026.
  - Per-second limits: 10 requests (no key); 30 (free key or prepaid).
  - Per-request costs are on the pricing and example-cost pages (not reached). The `X-RateLimit-Credits-Used` header reports the cost.
  - The date the key became required is not on this page [U].
- **Relevance to EasyResearch:** OpenAlex is usable for K2 referenced_works lookups with a free key within budget. Batch the calls and cache results. Conflicts with older figures (see Part 4).

### S27. OpenAlex works attributes, topics, and subfields (help center and developer docs)
- **Authors / org:** OpenAlex
- **Venue / date:** Official docs (undated)
- **URL:** https://help.openalex.org/data/works/attributes ; https://help.openalex.org/data/topics ; https://developers.openalex.org/guides/key-concepts
- **Tag:** [S]
- **Findings:**
  - `related_works`: OpenAlex IDs of algorithmically similar works, mainly recent papers sharing the most topics with this one.
  - `referenced_works`: outgoing references; `referenced_works_count` gives the length. `cited_by_api_url` links to citing works (recipes guide).
  - Topic hierarchy: domain > field > subfield > topic. Key concepts page lists 4 domains and 26 fields. Subfield counts conflict (252 vs 254) [U on the exact count].
  - Filters such as `primary_topic.field.id` and `topics.subfield.id` are supported.
- **Relevance to EasyResearch:** `referenced_works` is the high-precision citation link source for K2. `related_works` gives a free similarity signal. The hierarchy supports K4 at field and subfield level.

### S28. Evidence on OpenAlex topic and metadata accuracy (2024 to 2025)
- **Authors / org:** Various (arXiv 2408.04163, 2312.00043, 2409.10633, 2502.18427; Georgia Tech thesis; UAlberta case study)
- **Venue / date:** 2023 to 2025 preprints and theses
- **URL:** https://arxiv.org/pdf/2408.04163 ; https://arxiv.org/pdf/2312.00043 ; https://arxiv.org/abs/2409.10633 ; https://arxiv.org/pdf/2502.18427
- **Tag:** [S]
- **Findings:**
  - Vendor-reported topic accuracy quoted in arXiv 2408.04163: top-1 0.72 with complete metadata, 0.53 on average; top-3 0.73 on average.
  - A 2023 AI-research check found a 2.3% false-negative rate on 128 works for AI concept labels; the authors think the true rate is higher.
  - Thelwall 2025 preprint: the broadest classification scheme gives the best indicators for research evaluation.
  - A 2025 case study of the "Art" Level 0 concept reports hierarchical and semantic shortcomings.
  - Metadata review (arXiv 2409.10633, manual check of 6,836 articles): language labels not always accurate and overstate English.
- **Relevance to EasyResearch:** Topic-level labels are not precise enough for automatic categories. Use the field or subfield level, and keep user confirmation for every category (K4).

### S29. TnT-LLM: Text Mining at Scale with Large Language Models (arXiv 2403.12173)
- **Authors / org:** Mengting Wan, Tara Safavi, Sujay Kumar Jauhar, Yujin Kim, Scott Counts, Jennifer Neville, Siddharth Suri, Chirag Shah, Ryen W. White, Longqi Yang, Reid Andersen, Georg Buscher, Dhruv Joshi, Nagu Rangan (Microsoft and collaborators)
- **Venue / date:** arXiv 18 Mar 2024; KDD 2024 per review listing [S].
- **URL:** https://arxiv.org/abs/2403.12173
- **Tag:** [V] (abstract)
- **Findings:**
  - Phase 1: zero-shot, multi-stage LLM generation and refinement of a label taxonomy.
  - Phase 2: LLM labels a sample to build pseudo-labels; a lightweight classifier labels the full corpus.
  - Evaluated on Bing Copilot user intent and conversation domain. Abstract claims more accurate and relevant taxonomies than baselines, with a good accuracy-efficiency balance. No numbers in the abstract.
- **Relevance to EasyResearch:** Supports the K4 pattern: LLM proposes a taxonomy once from a sample, the user edits it, and a cheap classifier (keyword or BM25) labels the rest. Avoids an LLM call per paper.

### S30. The CSO Classifier (Computer Science Ontology topic tagging)
- **Authors / org:** Salatino, Osborne, Thanapalasingam, Motta (Open University)
- **Venue / date:** TPDL 2019; CSO Classifier 3.0 in IJDL 2021.
- **URL:** https://skm.kmi.open.ac.uk/the-cso-classifier-ontology-driven-detection-of-research-topics-in-scholarly-articles
- **Tag:** [S]
- **Findings:**
  - Unsupervised. Syntactic module matches explicit topic names; semantic module uses POS tagging and word embeddings; combines results, adds super-areas, and discards outliers (v3).
  - Ontology about 14K topics (earlier figures) or about 26K topics (later paper); numbers conflict across sources [U].
  - Apache 2.0, pip-installable, needs a spaCy English model. Note the embedding module may require a model download, which conflicts with our constraint.
- **Relevance to EasyResearch:** A CS-domain ontology tagger that could help K4, but it is English-only and CS-biased, and the semantic module may need an embedding model, so a download would be needed. Likely not allowed under our constraint.

### S31. Swanson ABC and literature-based discovery (LBD) surveys
- **Authors / org:** Don Swanson (origin); survey by Smalheiser and others; LLM4SR survey (arXiv 2501.04306)
- **Venue / date:** 1980s origin; PeerJ CS-235 systematic review; 2025 survey overview
- **URL:** https://peerj.com/articles/cs-235 ; https://arxiv.org/pdf/2501.04306
- **Tag:** [S]
- **Findings:**
  - ABC model: if A relates to B in one literature and B to C in another, and A and C never co-occur, the A-C link may be a hidden hypothesis. Known cases: fish oil and Raynaud's; migraine and magnesium.
  - Undiscovered public knowledge: fragments that are public but never connected.
  - An arXiv biomedical paper (late 2025) reports that LLM-only hypothesis generation often hallucinates connections without mechanistic validity, and proposes checking against an existing system [S].
- **Relevance to EasyResearch:** ABC gives a candidate-gap generator from concept co-occurrence across our library. It is noisy and needs a hard filter (concept must appear in two sources with no shared direct link), as in K3.

### S32. Retrieval: BM25 vs dense for scientific text (SciRet, LitSearch, RARE, NanoMTEB SciDocs)
- **Authors / org:** Various
- **Venue / date:** 2024 to 2026
- **URL:** https://arxiv.org/pdf/2608.03860 (SciRet; ID looks unusual, verify) ; https://preview.aclanthology.org/setup/2024.emnlp-main.840 (LitSearch) ; https://arxiv.org/pdf/2604.19047 (RARE)
- **Tag:** [S]
- **Findings:**
  - NanoMTEB SciDocs: dense retrieval beats BM25 on scientific paper recommendation (BM25 nDCG@10 0.2067 on that page). Attributed to scientific relatedness being more semantic than lexical.
  - RARE (2026): dense beats BM25 across domains, but the gap shrinks in high-overlap corpora. Relevant for small, homogeneous libraries.
  - SciRet compares BGE-M3, BM25, and reciprocal-rank-fusion hybrids; numbers not reached [U].
  - No 2024 study found that directly compares BM25 and dense on a small scientific library [U].
- **Relevance to EasyResearch:** For a small library of similar-topic papers, BM25 with a hybrid fallback is the defensible default for K2. Dense embeddings help for paraphrase and relatedness, which lexical Jaccard misses.

### S33. Connected Papers, Inciteful, Litmaps, ResearchRabbit: link discovery methods (secondary descriptions)
- **Authors / org:** Vendors and secondary reviewers (ponder.ing, CASRAI, HKUST and Graduate Institute guides)
- **Venue / date:** 2025 to 2026 guides
- **URL:** https://ponder.ing/blog/connected-papers-alternatives ; https://www.casrai.org/guides/inciteful-citation-network-paper-discovery
- **Tag:** [S]
- **Findings:**
  - Connected Papers and Inciteful rank by co-citation and bibliographic coupling. Inciteful adds Adamic/Adar similar-paper lists, PageRank importance, and shortest citation chains between two papers.
  - Litmaps: time-axis graph; monitoring alerts.
  - Free-tier limits conflict across guides (Connected Papers: 5 graphs/month in one source; Litmaps: 2 maps of 100 papers in another) [U].
- **Relevance to EasyResearch:** Confirms that co-citation and coupling are standard, low-cost link signals. Use the same signals from OpenAlex `referenced_works` instead of a third-party service.

### S34. Research-gap and limitation datasets and LLM gap evaluation (2025)
- **Authors / org:** Mendeley dataset (3,326 arXiv CS papers); arXiv 2510.25055 (biomedical, implicit gaps); SchNovel (arXiv 2506.22026); Idea Novelty Checker (2025 SDP workshop)
- **URL:** https://data.mendeley.com/datasets/px9xd7tw8n ; https://arxiv.org/html/2510.25055v1 ; https://www.arxiv.org/pdf/2506.22026
- **Tag:** [S]
- **Findings:**
  - Mendeley dataset: LLM-written limitation and gap sentences from abstracts; not validated by human experts (per its description).
  - arXiv 2510.25055: first systematic evaluation of LLMs inferring unstated knowledge gaps from section-level context (biomedical).
  - SchNovel: uses publication date as a novelty proxy (newer = more novel), which the authors call simplistic.
  - Idea Novelty Checker: about 13% higher agreement with experts than prior approaches (per summary).
- **Relevance to EasyResearch:** Gap labels generated by LLMs without expert validation are weak. Our K3 should keep every gap as a candidate and measure precision on a hand-labeled set. Novelty by date is not a usable proxy.

### S35. Anthropic / Ollama / model-selection evidence (Tam et al. Gemini row and Ollama default)
- This item is covered by S01 and S07. Listed for completeness so that the 40-source count is clear.

### S36. Semantic Scholar rate-limit and key conflicts (third-party wrappers)
- **URL:** https://glama.ai/mcp/servers/@zongmin-yu/semantic-scholar-fastmcp-mcp-server ; https://tooluniverse (zitniklab.hms.harvard.edu) [S]
- **Tag:** [S]
- **Findings:** Wrappers claim 100 requests per second with a key, 10 RPS for some endpoints, or 100 requests per 5 minutes unauthenticated. None matches the official 1 RPS introductory key limit.
- **Relevance to EasyResearch:** Use the official 1 RPS as the planning figure (S25). Ignore wrapper numbers.

### S37. Ollama num_ctx default conflicts (third-party)
- **URL:** https://www.ssdnodes.com/learn/lang/fr/ollama-context-length-num-ctx [S]
- **Tag:** [S]
- **Findings:** A French-language guide reports that Ollama's FAQ gives 4096 as the default while the Modelfile reference gives 2048. The official page (S07) lists tiers instead.
- **Relevance to EasyResearch:** Do not hardcode the default. Always set `num_ctx` explicitly and read it back with `ollama ps`.

### S38. Document-level claim extraction and LLM-as-judge alignment (Makaiová et al., Nov 2025)
- **URL:** not confirmed [U]
- **Tag:** [S]
- **Findings:** Secondary summary says LLM-as-judge metrics agree best with humans, and that giving the model a claim-count target improves alignment.
- **Relevance to EasyResearch:** A claim-count hint could reduce over-generation in K1 facets. Source not opened; treat as hypothesis.

### S39. LitSearch: retrieval benchmark for scientific literature search (EMNLP 2024)
- **URL:** https://preview.aclanthology.org/setup/2024.emnlp-main.840
- **Tag:** [S]
- **Findings:** Benchmark for scientific literature retrieval; BM25 versus dense numbers not reached.
- **Relevance to EasyResearch:** A benchmark to consult when the K2 retrieval choice is revisited. Not used for a verdict.

### S40. Ollama keep-alive and offload guidance (official snippets via docs)
- **URL:** https://docs.ollama.com/context-length (S07) ; third-party keep-alive guides [S]
- **Tag:** [V] for the offload and `ollama ps` advice (S07); [S] for keep_alive durations.
- **Relevance to EasyResearch:** Check `ollama ps` PROCESSOR column after each run to confirm 100% GPU. Set `keep_alive` for batch runs.

---

## Part 2 — Verdicts on K1, K2, K3, K4, O8/O9

### K1. Paper profile: one LLM call per paper, up to 8,000 characters, JSON-schema output, nine facets, quote plus page for every item, quotes verified against stored text
**Verdict: Partly supported.**

**Supporting evidence**
- Quote-first grounding is endorsed by official Anthropic guidance for long-document tasks (S10 [V]). Quote plus page verification is consistent with that and with the claim-plus-rationale pattern in SciFact (S21 [S]) and PaperQA2's cited summaries (S09 [V]).
- Ollama officially accepts a JSON schema via `format` and recommends post-validation with Pydantic or Zod (S06 [V]). So the schema route itself is supported.
- Short, section-focused inputs are supported by Lost in the Middle (S08 [V]).

**Contrary evidence**
- Tam et al. (S01 [V]) show that JSON-mode and format constraints can cut reasoning accuracy sharply on smaller models. LLaMA-3-8B fell from 74.7 to 48.9 on GSM8K. The largest GPT-3.5 losses came from answer-before-reason key order (100% of JSON-mode responses).
- The Format Tax (S03 [V] abstract) reports that open-weight models degrade under structured-output requirements, and that most of the loss comes from the format instruction itself. This applies directly to our local 8B.
- dottxt (S02 [V]) disputes the Tam result for Llama-3-8B and reports no penalty (0.77 vs 0.78 on GSM8K). The two sources disagree on the same model family, which means prompt and parser design decide the outcome. We cannot assume the penalty is absent.

**Diagnosis: why an 8B model with one long schema-constrained call probably failed**
Each item below is labeled as evidence-backed or an inference.

1. **Answer-before-evidence commit (evidence-backed by S01).** If the schema lists facet answers before quote and page fields, the model commits to a claim, then fills in a quote that matches it or leaves the field empty. Reversing the order (quote, page, then claim) is the first fix to test.
2. **Empty facets as the cheapest valid output (inference).** A schema that allows empty arrays lets a constrained decoder produce valid JSON with empty facets for a model that is uncertain or slow. "Empty facets" is consistent with this. Fix: set `minItems: 1` for facets that have a cue-sentence candidate, and treat an empty facet as a retry trigger, not a success.
3. **Timeouts from a non-streaming, long output (evidence-backed by S11 [S]).** Nine facets, each with items carrying quote text and page, makes a long structured output. With `stream: false`, the client receives nothing until the whole output is complete, so a 120 to 300 s window can expire even while generation is progressing (inference from S11).
4. **Context spill to CPU on 8 GB VRAM (partly evidence-backed by S07 [V]; memory estimate is inference).** Setting `num_ctx` to at least 8,192, which the formula forces, is above the official 4k default for cards under 24 GiB (S07 [V]). A Q5 8B model plus a KV cache at that size is likely close to the 8 GB limit. A rough estimate, not verified in this session: Llama-3-8B-class models with grouped-query attention store about 128 KiB of KV cache per token in fp16, so the cache alone is about 1 GiB at 8k and about 4 GiB at 32k. Check with `ollama ps` (PROCESSOR column). If it shows a CPU split, every token gets slower.
5. **Coverage gap from truncation (inference).** 8,000 characters covers only part of a typical paper. Limitations and future-work sentences are often in the conclusion, which may fall outside the first 8,000 characters, so those facets are empty. Lost in the Middle (S08 [V]) predicts that evidence in the middle of a long input is used less reliably.
6. **Quote verification failures from PDF text (inference).** Extracted PDF text has hyphenation at line breaks, ligatures, and column interleaving. An LLM that paraphrases or normalizes whitespace will fail exact matching, producing "not_found" even when the content is right. The fix is normalization before matching, and storing the matched span.

**What changes the evidence suggests**
- Put quote and page before the claim field in every item.
- Replace free quote generation with candidate selection: code finds candidate sentences (cue or term match, with page IDs); the model returns sentence IDs and a short label; code copies exact text. This removes most quote hallucination by construction.
- Split into two or three calls (for example, background: problem, method, datasets; results and limits: contributions, strengths, limitations, future work, results, metrics), each with under 4,000 characters of targeted sections.
- Use `stream: true` for schema calls and a per-chunk watchdog.
- Set `num_ctx` explicitly (for example 4,096 to 6,144) and confirm 100% GPU with `ollama ps` before running a batch.
- Set temperature 0 (S06 [V] recommends it).

### K2. Paper links: nine relation types; OpenAlex referenced_works and Jaccard similarity; user acceptance; rejections never re-suggested; Obsidian wikilink export
**Verdict: Partly supported.**

- **Supported:** OpenAlex exposes `referenced_works`, `related_works`, and `cited_by` (S27 [S]). Co-citation and bibliographic coupling are the standard link signals used by established tools (S33 [S]). A free OpenAlex key is enough for modest use (S26 [V]). SPECTER2 vectors are available through the Semantic Scholar API (S25 [V]), which is an alternative to lexical similarity without downloading models.
- **Supported with caveats:** Typed relations have an established vocabulary in CiTO (S23 [S]), which makes nine types defensible, but the exact nine are our design, not sourced.
- **Partly supported:** Jaccard over keyword, method, and problem tokens is a lexical method. Scientific relatedness is more semantic than lexical (S32 [S], SciDocs). BM25 or a hybrid is more defensible than Jaccard for a small library (S32 [S]).
- **No evidence:** The specific Jaccard threshold, the rejection memory, and the wikilink export. These are design choices. Note that Obsidian wikilink export needs no external evidence.
- **Privacy note:** Sending titles or abstracts to OpenAlex or Semantic Scholar for link discovery is external transmission. The repository invariant requires an explicit user request and a preview of what will be sent. Reference lookups by DOI or OpenAlex ID are lower risk, but still need the same rule if they include private notes.

### K3. Gaps: rule-based cue-sentence candidates (noisy) plus AI candidates with verified quotes; all stay `candidate` until accepted
**Verdict: Partly supported.**

- **Supported:** Keeping every gap as a candidate until a human accepts it is well supported. PaperQA2's contradictions are validated by experts at only 70% (S09 [V]). Even a strong agent produces about 30% false positives on a contradiction-style task, so unreviewed output is unsafe.
- **Supported:** Limitation and future-work extraction is an active task with benchmarks (S18 BAGELS [V], S19 LimitGen [V], S20 FutureGen [S]). FutureGen found that LLM extraction of future-work sentences needed human validation (S20 [S]).
- **Partly supported:** Quote verification as a filter. The evidence supports quote-plus-rationale checks (S21 [S]). It does not measure how many verified-quote candidates are useful gaps.
- **Partly supported:** Cue-phrase mining. No precision measurement was found. The 25-candidate observation from a few papers is consistent with noise, but cannot be checked here.
- **No evidence:** The specific claim that quote verification removes "not_found" candidates means the gap is valid. A verified quote shows the sentence exists, not that it is an open problem.
- **Diagnosis of the 25-candidate noise (inference):** Cue words such as "limitation", "future", "however", and "remains" appear in boilerplate sentences (for example, "future work will address..." in a related-work section). Filter by section (only limitation, conclusion, future-work headings) and by sentence form (must name a specific gap, not a general hedge).

### K4. Field auto-organization: keyword rules, OpenAlex topics, optional AI classification; user-confirmed or rejected categories are never changed by automation
**Verdict: Partly supported.**

- **Supported:** The two-stage approach of LLM-proposed taxonomy plus a cheap classifier, with human edits, is the TnT-LLM pattern (S29 [V]). Keeping user decisions fixed matches the human-in-the-loop framing of that line of work (S29 [V], S30 [S]).
- **Supported with limit:** OpenAlex fields and subfields are usable for coarse categories (S27 [S]). Topic-level labels are not reliable enough for automatic assignment: top-1 accuracy 0.53 on average, vendor-reported (S28 [S]).
- **Partly supported:** The CSO Classifier demonstrates ontology-driven tagging for CS (S30 [S]), but it is CS-only and may need an embedding model download, so it does not fit our constraints.
- **No evidence:** The specific combination of keyword rules and AI classification improving accuracy over either alone. Our Korean UI adds a labeling risk: category names need a bilingual mapping. No source covered this.

### O8/O9. Research-loop evidence: abstract sentences chosen by term overlap; per-stage JSON schemas with post-validation and tolerant parsing
**Verdict: Partly supported.**

- **Supported:** Per-stage schemas with separated reasoning are supported (S03 [V] two-pass recovery; S04 [V] free reasoning then structured decoding). Post-validation is the official recommendation (S06 [V]).
- **Supported:** Tolerant parsing is needed. Community reports of preambles and invented fields (S06 [S]) and the parser sensitivity in S02 [V] both point to parse-and-repair as a required step.
- **Partly supported:** Term-overlap evidence selection. No source tested it directly. Term overlap is lexical, which S32 [S] says is weaker than semantic matching for relatedness, but it is a reasonable baseline for picking abstract sentences that mention the same concepts.
- **No evidence:** Whether one schema per stage beats one combined schema on our data. The Format Tax supports separating reasoning from formatting, which implies separate stages, but no direct comparison was found.

---

## Part 3 — Better ideas (at least 10)

Each idea gives: change, evidence (source numbers), expected benefit, cost, fit with constraints (free, no new local model downloads, privacy, single user, Korean UI), risks, confidence.

**Idea 1. Reverse item field order: quote, page, then claim (and "reason" before "answer").**
- *Change:* In the K1 schema, put `quote`, `page`, `quote_id` before `claim` or `answer` in every item. Keep reasoning fields before any conclusion field.
- *Evidence:* S01 [V] (100% of GPT-3.5 JSON-mode responses put answer before reason, which led to direct answering). S10 [V] (quote first).
- *Benefit:* Likely the largest single fix for empty or unsupported facets, at no extra call cost.
- *Cost:* Schema edit and one re-run on a 5-paper test set.
- *Fit:* Local, free, no download, no external data.
- *Risks:* Key order is not guaranteed to control generation order in every runtime. Verify with a test.
- *Confidence:* High.

**Idea 2. Candidate-ID selection instead of free-text quotes.**
- *Change:* Code finds candidate sentences per facet by cue and term match, labels each with an ID and page, and asks the model to pick IDs and write a short label. Code copies the exact text.
- *Evidence:* S10 [V] (quote grounding), S08 [V] (smaller, focused inputs), S03 [V] (separate reasoning from formatting; this is a form of that split).
- *Benefit:* Removes most quote hallucination by construction and makes "not_found" nearly impossible for valid picks. Cuts output length.
- *Cost:* Moderate code change (candidate extraction module, ID mapping). Some precision loss if candidate retrieval misses the sentence.
- *Fit:* Fully local; no new model.
- *Risks:* Candidate recall is the new bottleneck. Measure recall on a hand-labeled set.
- *Confidence:* High.

**Idea 3. Two-call design: free notes first, then schema-constrained output.**
- *Change:* Call A: a plain-text (no schema) pass over the targeted sections that writes short evidence notes with page numbers. Call B: schema-constrained output, using only Call A's notes as input.
- *Evidence:* S03 [V] (two-pass recovers most accuracy for open-weight models), S04 [V] (free reasoning then structured decoding), S01 [V] (structure hurts reasoning on small models).
- *Benefit:* Addresses the main format-penalty risk for the 8B model. Two shorter calls are less likely to hit the timeout.
- *Cost:* About 2x calls per paper. On a single 8 GB card, calls run sequentially, so latency roughly doubles for short calls.
- *Fit:* Fully local.
- *Risks:* Notes may drift from the source text. Verify quotes in Call B against stored pages (keep the verification step).
- *Confidence:* Medium-high.

**Idea 4. Split the nine facets into three or four group calls with section targeting.**
- *Change:* Group facets: (a) problem, datasets, metrics (introduction and setup); (b) method, contributions (abstract and method section); (c) results, strengths, limitations, future work (results, discussion, conclusion). Each call gets under about 4,000 characters of targeted text.
- *Evidence:* S08 [V] (middle-context degradation; shorter inputs help), S14 [V] (decoupled stages), S12 [S] (facets span sections).
- *Benefit:* Smaller prompts, shorter outputs, lower timeout risk, and fewer empty facets because each call has evidence in view.
- *Cost:* Requires heading detection on PDFs (fallback to physical page ranges). Some setup work.
- *Fit:* Local.
- *Risks:* Heading detection fails on some PDFs. Keep the page-range fallback.
- *Confidence:* Medium-high.

**Idea 5. Use `stream: true` with a per-chunk watchdog for every schema call.**
- *Change:* Replace `stream: false` with streaming. Reset the timeout on each chunk. Abort if no chunk arrives for N seconds. Log the chunk count.
- *Evidence:* S11 [S] (non-streaming waits for full output), S06 [V] (schema call examples).
- *Benefit:* Removes most "timeout at 120 to 300 s" failures without a longer global timeout, and shows progress.
- *Cost:* Small code change; must parse streamed JSON only after completion.
- *Fit:* Local.
- *Risks:* Streaming partial JSON is not valid until complete. Parse only the final concatenated text.
- *Confidence:* Medium (mechanism is clear; the failure-rate improvement is inference).

**Idea 6. Pin `num_ctx` to a value that stays on GPU; verify with `ollama ps`.**
- *Change:* Replace the formula with a fixed `num_ctx` of about 4,096 to 6,144, sized to the actual call input. Add a startup check that runs `ollama ps` and warns if the PROCESSOR column shows a CPU share.
- *Evidence:* S07 [V] (official default 4k below 24 GiB; avoid offload; check PROCESSOR), S11 [S] (CPU split causes slowdowns).
- *Benefit:* Keeps the model on the GPU, so generation is faster and timeouts become less likely.
- *Cost:* Near zero. May require smaller inputs (Idea 4 helps).
- *Fit:* Local, no download.
- *Risks:* Too small a window truncates input. Compute the window from the actual token count, not chars/2 alone.
- *Confidence:* Medium-high.

**Idea 7. Try a smaller or faster local model variant already on disk only if it is in the user's current set; otherwise test the same 8B at lower quantization. Keep the local-only constraint.**
- *Change:* Compare the current model against any already-installed small model on the same 5-paper set, measuring facet recall and quote validity. Do not download new models (repository constraint).
- *Evidence:* S01 [V] (smaller models were more format-sensitive in some rows), S03 [V] (open-weight models most affected; closed models little affected).
- *Benefit:* Empirical answer to "which model fits the task" without new downloads.
- *Cost:* Test time only.
- *Fit:* Local, no new download, complies with constraint.
- *Risks:* Only models already installed are usable. Results may not transfer.
- *Confidence:* Medium.

**Idea 8. Optional free-tier external model for batch profiling, only with explicit user approval and a preview.**
- *Change:* Offer, as an opt-in, a free-tier hosted model (for example Gemini 1.5 Flash, or another free tier the user chooses) for batch profiling of papers the user selects. Show the exact text that would be sent before each run.
- *Evidence:* S01 [V] (Gemini 1.5 Flash GSM8K 89.3 vs 89.2 JSON vs text; DDXPlus gains), S03 [V] (recent closed models show little penalty).
- *Benefit:* Likely higher facet quality with less format penalty, at no cost on a free tier.
- *Cost:* Sends private text externally. Requires explicit user request, preview, and possibly account setup (which this agent cannot do).
- *Fit:* Conflicts with privacy invariants unless approved per run. Must not be the default.
- *Risks:* Free-tier rate limits, data-use terms, and model version drift. Gemini 1.5 Flash is an older model; check current free-tier models before use [U].
- *Confidence:* Medium (quality evidence is from Tam et al. only).

**Idea 9. Use OpenAlex `referenced_works` as the primary, high-precision link signal, and `related_works` as a secondary signal.**
- *Change:* K2 discovery: (a) use `referenced_works` intersections among library papers to propose `cites` links; (b) use `related_works` for `same problem` or `same method` suggestions only where at least two library papers agree; (c) only then apply Jaccard or BM25 on local abstracts.
- *Evidence:* S27 [S] (fields), S26 [V] (free key budget), S33 [S] (co-citation and coupling are standard).
- *Benefit:* Citation links are high precision without any LLM. Cheap in calls.
- *Cost:* OpenAlex calls within the $1/day free key budget (S26 [V]). Batch by ID filters to reduce calls.
- *Fit:* Sends only OpenAlex IDs, which are not private text, so the privacy invariant is easier to meet. Still preview as a precaution.
- *Risks:* OpenAlex reference lists are incomplete for some venues (S28 [S] metadata accuracy concerns).
- *Confidence:* High for cites links; medium for the other types.

**Idea 10. Use SPECTER2 via the Semantic Scholar API for "similar paper" links only, with a 1 RPS queue and user approval.**
- *Change:* Add an opt-in "similar papers" step that sends paper IDs or titles to the Semantic Scholar recommendations or embedding endpoint, respects the 1 RPS limit, caches vectors locally, and shows what will be sent.
- *Evidence:* S25 [V] (SPECTER2 in Academic Graph; 1 RPS introductory key), S24 [S] (SPECTER2 is a proximity model for similar-paper search), S32 [S] (dense beats BM25 on scientific relatedness).
- *Benefit:* Higher-quality relatedness than Jaccard without downloading a model.
- *Cost:* Requires an API key from the user; 1 RPS means about 3,600 calls per hour at most, which is fine for a library of a few hundred papers.
- *Fit:* Respects the no-download rule, but external transmission needs explicit approval. Only IDs or titles, not full text.
- *Risks:* Terms of the API license (not summarized in S25 [U]); dependence on an external service.
- *Confidence:* Medium.

**Idea 11. Use BM25 (or BM25 plus simple reciprocal-rank fusion with OpenAlex `related_works`) for local similarity instead of Jaccard.**
- *Change:* Replace or supplement Jaccard with BM25 over title, abstract, and extracted facet text. Hybrid with rank fusion.
- *Evidence:* S32 [S] (BM25 strong on exact terminology and high-overlap corpora; hybrid recommended in several sources), S24 [S].
- *Benefit:* Better ranking than raw Jaccard with no model, no network.
- *Cost:* Small code change; a BM25 library or a hand-written implementation.
- *Fit:* Local, no download, private.
- *Risks:* Small-corpus IDF is unstable. Use a fixed parameter set and measure on the user's library.
- *Confidence:* Medium.

**Idea 12. Map relation types onto CiTO-style labels and a confidence tier.**
- *Change:* Name relation types with a CiTO-compatible vocabulary (for example `cites`, `extends`, `compares`, `usesMethodIn`, `disagreesWith`), and store a source tag (OpenAlex, rule, AI) and confidence tier.
- *Evidence:* S23 [S] (CiTO vocabulary and FOCO factual/rhetorical classes), S22 [S] (coarse intent classes work, fine ones need validation).
- *Benefit:* Easier export and future interoperability; forces the team to define what each type means.
- *Cost:* Schema and documentation work; no runtime cost.
- *Fit:* Local, no external calls.
- *Risks:* Inter-rater agreement on citation function is low (S23 [S]). Keep types few and require a rationale quote.
- *Confidence:* Medium.

**Idea 13. Filter gap candidates by section and sentence form before any LLM call.**
- *Change:* K3 rule candidates only from limitation, conclusion, and future-work sections, and only from sentences that name a specific object or dataset (regex for "we did not", "future work should", "remains open", "our approach cannot"). Drop generic hedges ("may", "could") without a specific referent.
- *Evidence:* S18 [V] and S19 [V] (limitation extraction is a distinct task that benefits from targeted extraction), S20 [S] (LLM-based future-work sentence extraction needed annotator validation), S09 [V] (70% validation even for strong agents).
- *Benefit:* Cuts the 25-candidate noise without an LLM; expect fewer but better candidates.
- *Cost:* Regex tuning and a 20-sentence hand check.
- *Fit:* Local, rule-based, no network.
- *Risks:* Missing gaps phrased in non-cue ways. Measure recall on the synthetic perturbation idea (Idea 14).
- *Confidence:* Medium.

**Idea 14. Build a planted-limitation check set to measure gap-extractor recall and precision.**
- *Change:* Take five papers the user has already read. Insert or perturb sentences in a copy (not in the library) to create known limitations, following the LimitGen-Syn idea. Measure how many the extractor finds, plus false positives on unmodified text.
- *Evidence:* S19 [V] (controlled perturbation design), S18 [V] (fine-grained evaluation framework), S34 [S] (LLM-generated gap labels without validation are weak).
- *Benefit:* Gives an observable acceptance metric for K3 and K1, as the repository's evidence rules require.
- *Cost:* One test fixture (temporary folder), a few hours of hand labeling.
- *Fit:* Strong: runs in temp data folders, no private data leaves the machine.
- *Risks:* Synthetic perturbations may be easier than real limitations. Pair with 20 hand-labeled real sentences.
- *Confidence:* High (for the evaluation idea); medium for the transfer to real gaps.

**Idea 15. Taxonomy by LLM proposal from a sample, then cheap classification, with user editing.**
- *Change:* K4: ask the local model once to propose a taxonomy (5 to 12 categories) from titles and keywords of up to 50 papers, with a fixed category list. The user edits, merges, and confirms. Then classify all papers with BM25 or keyword rules; LLM only for ambiguous cases.
- *Evidence:* S29 [V] (taxonomy generation then lightweight classifier), S28 [S] (topic labels unreliable at topic level), S30 [S] (human-curated or ontology-based tagging).
- *Benefit:* One LLM call for the whole library; all labels are user-controlled.
- *Cost:* Small; one prompt and a review UI step.
- *Fit:* Local, Korean UI handled by bilingual category names stored by the user.
- *Risks:* Taxonomy may reflect the sample's bias; allow the user to add categories later.
- *Confidence:* Medium-high.

**Idea 16. Use OpenAlex field or subfield as a suggestion, never an assignment, for K4.**
- *Change:* Show OpenAlex field or subfield as a suggested category with a confidence note. Only the user writes the confirmed category.
- *Evidence:* S27 [S] (hierarchy exists), S28 [S] (topic top-1 0.53 average; metadata gaps), S26 [V] (free key budget).
- *Benefit:* Adds coverage without trusting the labels.
- *Cost:* Requires a stored OpenAlex ID per paper (DOI lookup), a few calls.
- *Fit:* OpenAlex calls send DOIs only, which are low-privacy identifiers; still preview.
- *Risks:* Papers without DOI or in non-English venues will have weak metadata (S28 [S]).
- *Confidence:* Medium.

**Idea 17. Add a deterministic quote-normalization layer before verification.**
- *Change:* Normalize Unicode (NFKC), collapse whitespace, rejoin line-end hyphenation, and strip ligature variants before exact and fuzzy matching. Store the matched span offsets. Report "normalized" versus "exact" in the UI.
- *Evidence:* No external source tested this; the need follows from S10 [V] (quote requirement) and from the nature of PDF text (inference).
- *Benefit:* Fewer false "not_found" results, which the user would otherwise discard manually.
- *Cost:* Small code change, plus tests with real PDF text from the user's library (in temp folders).
- *Fit:* Strong: local, deterministic, no model.
- *Risks:* Over-normalization can accept wrong quotes. Require a match ratio threshold and show the match.
- *Confidence:* High (engineering value); the number of affected quotes is unknown.

**Idea 18. Temperature 0 and a bounded output (`num_predict`) for every schema call.**
- *Change:* Set temperature 0 and a `num_predict` cap sized to the expected output (for example 1,200 tokens per call), with a retry that increases the cap only once.
- *Evidence:* S06 [V] (temperature 0 recommended), S11 [S] (cap output for non-streaming calls).
- *Benefit:* Reproducible runs and bounded latency; easier to debug the empty-facet problem.
- *Cost:* None.
- *Fit:* Local.
- *Risks:* A cap that is too low truncates JSON, which fails validation. Log truncation and retry.
- *Confidence:* High for reproducibility; medium for latency.

**Idea 19. ABC-style gap candidates from concept co-occurrence across the library, with a hard filter.**
- *Change:* K3 extra candidates: concepts that appear in two or more library papers but never in the same paper together, linked through a third paper. Show as candidates only.
- *Evidence:* S31 [S] (ABC model and its noise), S31 notes LLM-only connections hallucinate, so the filter must be structural.
- *Benefit:* A second, independent gap signal without an LLM.
- *Cost:* Concept extraction (keywords) plus a co-occurrence matrix; small.
- *Fit:* Local.
- *Risks:* Noisy for small libraries (few papers, few concepts). Probably useful only for libraries with 50 or more papers.
- *Confidence:* Low.

**Idea 20. Keep a precision-first threshold and show confidence instead of a single score.**
- *Change:* Show each candidate or link with three tags: source (rule, OpenAlex, AI), quote status (exact, normalized, not_found), and user state. Do not auto-accept anything.
- *Evidence:* S09 [V] (70% validation), S16 [S] (recall-precision tradeoff in claim extraction), S34 [S].
- *Benefit:* The user can filter by tag and decide faster; matches the "candidate until accepted" rule.
- *Cost:* UI change in the existing app.
- *Fit:* Local, single user.
- *Risks:* More UI complexity. Keep it to tags, not scores.
- *Confidence:* High.

---

## Part 4 — Conflicts between sources and unverified items

### Conflicts
1. **Does structured output hurt reasoning in an 8B model?**
   - S01 [V]: LLaMA-3-8B GSM8K 74.7 (text) vs 48.9 (JSON).
   - S02 [V]: Llama-3-8B-Instruct GSM8K 0.77 (unstructured) vs 0.78 (structured).
   - Explanation given by S02: different prompts, JSON prompt not mentioning JSON, parser differences (Tam used an AI parser, which S02 says was not perfect). S02 is a vendor rebuttal, so its numbers need replication. Our decision: treat the penalty as possible and design for it (Ideas 1 to 3).
2. **Does the penalty apply to recent models?**
   - S03 [V]: most recent closed-weight models show little or no penalty. Open-weight models are affected.
   - S01 [V]: Gemini 1.5 Flash shows almost no GSM8K change (89.3 vs 89.2). Consistent.
   - No conflict in direction; the difference is open versus closed.
3. **Quote-first threshold.**
   - S10 [V] (official): "20k+ tokens" applies to long-context prompting.
   - Secondary summaries (search only): "20K" as the threshold for extract-quotes-first. Consistent, but the official guidance is for large contexts; our per-call inputs are much smaller. Do not apply the threshold blindly.
4. **Ollama default num_ctx.**
   - S07 [V]: under 24 GiB VRAM defaults to 4k.
   - S37 [S]: FAQ says 4096, Modelfile reference says 2048. Conflict between Ollama's own pages as reported by a third party. Set `num_ctx` explicitly.
5. **OpenAlex keyless and free-key budgets.**
   - S26 [V]: free key $1/day; keyless budget not stated; implied about $0.10/day.
   - Search snippets [S]: keyless $0.01/day in one listing; 100,000 credits per day in another; per-call costs of 1 credit (singleton) and 10 credits (list page) in a third. These figures do not reconcile with the official page. Treat S26 as authoritative and recheck before any batch job.
6. **OpenAlex key requirement date.**
   - Search snippets [S]: key required from 13 Feb 2026 (Google group post, Jan 2026). S26 [V] confirms a key is needed for heavier use, but the start date is not on the page [U]. Treat the 13 Feb date as probable but unverified.
7. **Semantic Scholar rate limits.**
   - S25 [V]: 1 RPS introductory key limit; 1000 RPS shared unauthenticated pool.
   - S36 [S]: wrappers claim 100 RPS with key, 10 RPS for some endpoints, or 100 requests per 5 minutes unauthenticated. Official page wins.
8. **Subfield counts in OpenAlex.** 252 (one page) vs 254 (API reference) [S]. Not verified.
9. **OpenAlex topic accuracy.** Vendor-reported top-1 average 0.53 (S28, via a 2024 arXiv paper quoting OpenAlex) vs much higher accuracy when metadata is complete (0.72). Independent audits are limited.
10. **PaperQA2 framing.** The FutureHouse announcements say "superhuman" [S]; the arXiv abstract [V] says "matches or exceeds." Use the cautious wording.
11. **PaperQA2 date.** One FutureHouse page is dated December 2023 [S]; arXiv submission is 10 Sep 2024 [V]. Use the arXiv date.
12. **Dataset sizes for FutureGen and SciREX.** Search summaries disagree [S]. Not used for numbers.
13. **SemanticScholar SPECTER2 naming.** Hugging Face renamed `allenai/specter2` to `allenai/specter2_base` [S]. Use the new name.
14. **CSO ontology size.** 14,164 topics (one source) vs about 26K topics (another) [S]. Not used.

### Unverified items (could not confirm)
- Papers with Code TDMS task page definition [U].
- ORKG ASK behavior and the exact ORKG template mechanism [U]. Only general template descriptions were found.
- "SOLVENT" as a named system; no result connected it to Scideator [U].
- "LimTopic" [U].
- The numeric results of BAGELS, LimitGen, FutureGen, SciEx, TnT-LLM, In-Writing per-model tables [U].
- Lost in the Middle exact numbers (abstract page had none) [U].
- Ollama keep_alive and offload official text beyond the context-length page [U].
- Ollama timeout environment variables (`OLLAMA_REQUEST_TIMEOUT`, `OLLAMA_READ_TIMEOUT`) [U]. `OLLAMA_LOAD_TIMEOUT` reported by one source only [S].
- Semantic Scholar API license terms and whether Recommendations and Academic Graph are free [U].
- Connected Papers and Litmaps free-tier limits [U].
- SciCite macro F1 of 84.0% [U].
- Makaiová et al. Nov 2025 claim-count finding [U].
- Memory estimate for Llama-3-8B KV cache (about 128 KiB per token in fp16) is from architecture knowledge, not checked this session [U]. Verify with the model's config before relying on it.
- SciRet arXiv ID 2608.03860 looks unusual; verify before citing [U].
- The arXiv ID for LLM MapReduce and its URL [U].
- The Format Tax per-model and per-format numbers [U].
- The CiTO full property list [U].

---

## Part 5 — URL index

| # | Source | URL | Tag |
|---|---|---|---|
| S01 | Let Me Speak Freely? (Tam et al.) | https://arxiv.org/abs/2408.02442 ; https://arxiv.org/html/2408.02442v3 | V |
| S02 | dottxt "Say What You Mean" | https://blog.dottxt.ai/say-what-you-mean.html | V |
| S03 | The Format Tax (arXiv 2604.03616) | https://arxiv.org/abs/2604.03616 | V |
| S04 | Thinking Before Constraining (arXiv 2601.07525) | https://arxiv.org/abs/2601.07525 | V |
| S05 | JSONSchemaBench (arXiv 2501.10868) | https://arxiv.org/abs/2501.10868 ; https://github.com/guidance-ai/jsonschemabench | V |
| S06 | Ollama structured outputs docs | https://docs.ollama.com/capabilities/structured-outputs | V |
| S07 | Ollama context length docs | https://docs.ollama.com/context-length | V |
| S08 | Lost in the Middle (arXiv 2307.03172) | https://arxiv.org/abs/2307.03172 | V |
| S09 | PaperQA2 / Language agents (arXiv 2409.13740) | https://arxiv.org/abs/2409.13740 | V |
| S10 | Anthropic prompting best practices (long context) | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices | V |
| S11 | Ollama timeouts and keep_alive (third-party) | https://markaicode.com/errors/ollama-timeout-error-fix/ | S |
| S12 | SciREX (arXiv 2005.00512) | https://arxiv.org/pdf/2005.00512 | S |
| S13 | TDMS / Papers with Code | https://www.paperswithcode.com/dataset/scirex | U (TDMS page), S (lines) |
| S14 | SciEx (arXiv 2512.10004) | https://arxiv.org/abs/2512.10004 | V |
| S15 | LLM MapReduce (ACL 2025) | not confirmed | U |
| S16 | CLAIM-BENCH (arXiv 2506.08235) | https://arxiv.org/pdf/2506.08235 | S |
| S17 | Scideator (arXiv 2409.14634) | https://arxiv.org/abs/2409.14634 | V |
| S18 | BAGELS (arXiv 2505.18207) | https://arxiv.org/abs/2505.18207 ; https://github.com/IbrahimAlAzhar/BAGELS_Limitation_Gen | V |
| S19 | LimitGen (arXiv 2507.02694) | https://arxiv.org/abs/2507.02694 | V |
| S20 | FutureGen (arXiv 2503.16561) | https://arxiv.org/abs/2503.16561 | S |
| S21 | SciFact (arXiv 2004.14974) | https://arxiv.org/abs/2004.14974 | S |
| S22 | Cohan et al. 2019 / SciCite | https://aclanthology.org/N19-1361/ ; https://allenai.org/data/scicite | S |
| S23 | CiTO (Shotton 2010; Peroni and Shotton 2012) | https://pmc.ncbi.nlm.nih.gov/articles/PMC2903725/ ; https://msi.dublincore.org/standards/cito | S |
| S24 | SPECTER2 (Ai2) | https://allenai.org/blog/specter2-adapting-scientific-document-embeddings-to-multiple-fields-and-task-formats-c95686c06567 ; https://huggingface.co/allenai/specter2 | S |
| S25 | Semantic Scholar API product page | https://www.semanticscholar.org/product/api | V |
| S26 | OpenAlex authentication and rate limits | https://help.openalex.org/api-reference/authentication | V |
| S27 | OpenAlex works, topics, subfields | https://help.openalex.org/data/works/attributes ; https://help.openalex.org/data/topics ; https://developers.openalex.org/guides/key-concepts | S |
| S28 | OpenAlex accuracy evidence | https://arxiv.org/pdf/2408.04163 ; https://arxiv.org/pdf/2312.00043 ; https://arxiv.org/abs/2409.10633 ; https://arxiv.org/pdf/2502.18427 | S |
| S29 | TnT-LLM (arXiv 2403.12173) | https://arxiv.org/abs/2403.12173 | V |
| S30 | CSO Classifier | https://skm.kmi.open.ac.uk/the-cso-classifier-ontology-driven-detection-of-research-topics-in-scholarly-articles | S |
| S31 | Swanson ABC and LBD surveys | https://peerj.com/articles/cs-235 ; https://arxiv.org/pdf/2501.04306 | S |
| S32 | Retrieval: BM25 vs dense | https://arxiv.org/pdf/2608.03860 (verify) ; https://arxiv.org/pdf/2604.19047 | S |
| S33 | Connected Papers / Inciteful / Litmaps guides | https://ponder.ing/blog/connected-papers-alternatives ; https://www.casrai.org/guides/inciteful-citation-network-paper-discovery | S |
| S34 | Gap datasets and LLM gap work | https://data.mendeley.com/datasets/px9xd7tw8n ; https://arxiv.org/html/2510.25055v1 ; https://www.arxiv.org/pdf/2506.22026 | S |
| S36 | Semantic Scholar wrapper rate claims | https://glama.ai/mcp/servers/@zongmin-yu/semantic-scholar-fastmcp-mcp-server | S |
| S37 | Ollama num_ctx default conflicts | https://www.ssdnodes.com/learn/lang/fr/ollama-context-length-num-ctx | S |
| S38 | Makaiová et al. claim extraction (Nov 2025) | not confirmed | U |
| S39 | LitSearch (EMNLP 2024) | https://preview.aclanthology.org/setup/2024.emnlp-main.840 | S |
| S40 | Ollama keep-alive and offload | https://docs.ollama.com/context-length ; third-party guides | V (offload), S (keep_alive) |
| — | OpenAlex key-date and rate-limit snippets | https://groups.google.com/g/openalex-users/c/rI1GIAySpVQ | S |
| — | Thelwall 2025 (OpenAlex suitability) | https://arxiv.org/pdf/2502.18427 | S |
| — | Anthropic prompting best practices (duplicate reference) | see S10 | V |

Note: Entries S35 and S40 are partly cross-references. Source numbers S01 to S34 and S36 to S40 cover the set; S35 is intentionally a pointer and not a separate source.
