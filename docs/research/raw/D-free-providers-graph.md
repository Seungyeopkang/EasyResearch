# Research D: Free LLM providers and paper-graph options

Date of research: 2026-11-10. Verification legend: **[V]** verified by fetching the official page in this session; **[S]** from search snippets or third-party sites only; **[U]** UNVERIFIED (could not check, or sources conflict). Every claim carries a source URL.

Note on fetch limits: several official pages redirected or returned 404 (Mistral tier docs, OpenAlex attribute pages, Semantic Scholar graph API docs, Groq and Gemini limit tables). Those items are marked [S] or [U].

---

## Part 1: Free LLM options

### 1.1 Google Gemini API (AI Studio)

- Base URL for OpenAI SDK: `https://generativelanguage.googleapis.com/v1beta/openai/` [V] (https://aistudio.google.com/docs/openai)
- Auth: API key from AI Studio. Streaming supported; structured output supported via `response_format` with a schema (Pydantic/Zod examples), not labeled "json_schema" in the page [V] (https://aistudio.google.com/docs/openai)
- Docs moved: ai.google.dev/gemini-api/docs/* now redirects to aistudio.google.com/docs/* [V] (https://ai.google.dev/gemini-api/docs/pricing redirect)
- Free-tier models per the pricing page [V] (https://aistudio.google.com/docs/pricing): Gemini 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite, 3.1 Flash-Lite, 3 Flash Preview, 2.5 Flash, 2.5 Flash-Lite, Gemma 4, embeddings. Gemini 2.5 Pro is deprecated and routes to Gemini 3.8 Flash on 2026-12-01. Gemini 3.1 Pro Preview and Gemini 4 Argon are NOT on the free tier [V].
- **Privacy: free tier content IS used to improve Google products; paid tier content is not** [V] (https://aistudio.google.com/docs/pricing). This is the decisive point for private research notes.
- Rate limits (RPM/RPD per model): the official page defers to AI Studio's account-specific limits page [V] (https://aistudio.google.com/docs/rate-limits; https://aistudio.google.com/rate-limit). Third-party sources disagree on numbers (e.g. Flash RPD cut sharply in Dec 2025; Flash-Lite around 15 RPM) [S] (https://apidog.com/blog/gemini-api-free-tier/, https://yingtu.ai/blog/google-gemini-api-free-tier). Treat all specific numbers as **[U]**.
- Context length: not verified here **[U]**.
- Quality: strong Flash models; best free quality among the cloud options, but the data policy restricts use.

### 1.2 Groq (GroqCloud)

- Base URL `https://api.groq.com/openai/v1` **[U]** (standard documented value, not fetched this session).
- Free tier: no credit card, org-level rate limits per model [S] (https://community.groq.com/t/is-there-a-free-tier-and-what-are-its-limits/790).
- Limits: third-party tables cite about 30 RPM and 1,000 RPD for 70B-class models, and about 14,400 RPD for 8B-class models [S] (https://localaimaster.com/blog/groq-api-free-guide; https://benchlm.ai/free-tier/groq). The official rate-limits page was readable but did not show figures [V on page-readable; figures U].
- Structured output / JSON mode: **[U]**.
- Data training policy on free tier: **[U]**.
- Quality: fast; 70B-class and gpt-oss-120b models listed in third-party tables [S].

### 1.3 OpenRouter (":free" models)

- Base URL `https://openrouter.ai/api/v1` **[U]** (standard, not fetched).
- Free-model limits [V] (https://openrouter.ai/docs/api-reference/limits):
  - Fewer than 10 credits purchased (lifetime): 20 requests/min, 50 requests/day.
  - At least 10 credits purchased (lifetime): 20 requests/min, 1,000 requests/day.
  - Daily cap is account-wide across all `:free` models; the daily counter is per UTC day (the docs say "current UTC day"; the explicit 00:00 UTC reset is stated only for key management) [V/U on reset time].
- Some third-party sites claim 200/day; treated as outdated [S].
- Failed free requests reportedly count against the quota [S] (https://www.mintlify.com/cheahjs/free-llm-api-resources/providers/free/openrouter).
- Structured output, context length and per-model training policy: **[U]**; they vary by upstream provider, so check each model's page before sending private text.
- Free variants "may have different rate limits or availability" [V] (https://openrouter.ai/docs/guides/routing/model-variants/free).

### 1.4 Cerebras

- **No permanent free tier.** Free Trial credits: $5 after adding a verified payment method, expiring 30 days after grant [V] (https://inference-docs.cerebras.ai/support/rate-limits).
- Free Trial limits: 5 RPM, 30K uncached / 90K total TPM, 1M TPH and 1M TPD per model [V] (same page).
- Developer (pay-as-you-go) tier has no hourly/daily token caps [V] (same page).
- Older pages still advertising 30 RPM / 14,400 RPD are stale [S].
- Base URL `https://api.cerebras.ai/v1` **[U]**.
- Recommendation: not a default provider.

### 1.5 Mistral (La Plateforme, "Experiment"/"Free mode")

- Official tier doc returned HTTP 404 in this session **[U]** (https://docs.mistral.ai/deployment/ai-studio/tier).
- Third-party sources: about 1 req/s, 500K TPM, about 1B tokens/month per model [S] (https://pricepertoken.com/endpoints/mistral/free). A more recent source says Mistral does not publish per-model free-mode limits and points to the Limits page [S] (https://fremodel.pages.dev/providers/mistral-ai).
- **Data use: requests on the free plan may be used to train Mistral's models** [S] (https://help.mistral.ai/en/articles/455206-how-can-i-try-the-api-for-free-with-the-experiment-plan). Treat as a privacy blocker for private text.
- Phone verification required; upgrade path conflicting **[U]**.
- Base URL `https://api.mistral.ai/v1` **[U]**.

### 1.6 GitHub Models

- **Retired.** "As of July 30, 2026, GitHub Models has been fully retired"; playground, catalog, inference API and BYOK are no longer available [V] (https://docs.github.com/en/github-models). Do not use. Older free-tier numbers (15 RPM / 150 RPD) are stale.

### 1.7 Cloudflare Workers AI

- Free allocation: **10,000 Neurons per day** at no charge, resets 00:00 UTC; exceeding it causes failures until reset [V] (https://developers.cloudflare.com/workers-ai/platform/pricing/).
- Shared pool across models; large models burn it fast [S] (https://www.mintlify.com/cheahjs/free-llm-api-resources/providers/free/cloudflare-workers-ai).
- Endpoint: REST `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions` (OpenAI-compatible) **[U]**.
- Good small fallback; not suited for large-context summarization on free tier.

### 1.8 Hugging Face Inference Providers (router)

- OpenAI-compatible base URL `https://router.huggingface.co/v1` with an HF token [V] (https://huggingface.co/docs/inference-providers/index).
- **Chat completions only** for the OpenAI-compatible endpoint [V] (same page).
- Free tier exists; PRO users and Enterprise orgs get monthly included credits [V] (same page). Exact free credit amount and rate limits: **[U]** (third-party sources conflict).
- Model suffixes `:fastest`, `:cheapest`, `:preferred`, or `:provider-name` [V].

### 1.9 NVIDIA NIM (build.nvidia.com)

- Hosted endpoint `https://integrate.api.nvidia.com/v1`, OpenAI Chat Completions format, namespaced model IDs (e.g. `meta/llama-3.3-70b-instruct`) [S] (https://lilting.ch/en/articles/nvidia-nim-free-inference-100-models-openai-compatible).
- Credits conflict: 1,000 at sign-up with up to 5,000; 40 RPM figure [S] (https://forums.developer.nvidia.com/t/api-credits-for-build-nvidia-com/306633). Production use requires an enterprise license per the same sources **[S]**.
- Data policy: **[U]**. Treat as optional.

### 1.10 Local: Ollama

- OpenAI-compatible base URL `http://localhost:11434/v1/`; the API key is required by clients but ignored [V] (https://docs.ollama.com/openai).
- `/v1/chat/completions` supports streaming, JSON mode, tools, vision, `response_format`. Not supported: logprobs, `tool_choice`, `n`, `user`, `logit_bias` [V] (same page). The page does not explicitly name `json_schema`; verify before relying on it **[U]**.
- **Native schema-constrained output** is more reliable: pass a JSON schema in `format` on the native `/api/chat` endpoint (Python `format=Model.model_json_schema()`), then validate with Pydantic/Zod. The page recommends also putting the schema in the prompt and using temperature 0 [V] (https://docs.ollama.com/capabilities/structured-outputs). Cloud Ollama does not support structured outputs [V] (same page).
- Model sizing (secondary sources, approximate) [S]:
  - Qwen3 14B at Q4 about 10.7 GB; recommended for 16 GB GPUs for summarization (https://zendevy-rebuild.pages.dev/en/ai/local-llm-lightweight-comparison-2026/; https://summarize.sh/docs/ollama.html).
  - Qwen3 32B at Q4_K_M about 22 GB; needs 24 GB card with context capped (https://mustafa.net/llm-vram-requirements-2026/).
  - Gemma 3: rough tiers 3B ~2–4 GB, 7B ~4–6 GB, 12B ~8–12 GB [S]. A 2026 comparison says Gemma 4 has replaced Gemma 3 (E4B, 31B Q4 ~20 GB) **[U]** (https://computingforgeeks.com/how-much-vram-to-run-llm/).
  - Ollama may size the context window to detected VRAM; long contexts add substantial memory [S].
- CPU-only: feasible for 3–8B models with slow throughput **[U]**.
- Privacy: fully local; no data leaves the machine. Best default for private notes, consistent with AGENTS.md.

### 1.11 Local: LM Studio

- Local server default `http://localhost:1234/v1` [V] (https://lmstudio.ai/docs/developer/openai-compat).
- Supported endpoints include `/v1/models`, `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, `/v1/completions` [V] (same page).
- Auth and `json_schema` structured output: not stated on the fetched page **[U]**.

### 1.12 Using a Claude or ChatGPT subscription via Claude Code / Codex CLI driving the app over MCP

- **Anthropic.** Consumer Terms prohibit access by automated or non-human means (bots, scripts) except via an Anthropic API key or where Anthropic explicitly permits it; third-party integrations are allowed but the user is responsible for them [V] (https://www.anthropic.com/legal/consumer-terms). Reports from Feb–Apr 2026 say subscription OAuth tokens are "intended exclusively for Claude Code and Claude.ai," and that subscriptions stopped covering third-party harnesses from 2026-04-04 [S] (https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access; https://venturebeat.com/ai/anthropic-reinstates-openclaw-and-third-party-agent-usage-on-claude-subscriptions-with-a-catch/). Sources conflict on Agent SDK exceptions. A single secondary source says a June 15, 2026 change moves Agent SDK / `claude -p` usage off subscription pools to API-rate credit **[U]** (https://www.digitalapplied.com/blog/anthropic-claude-credit-overhaul-june-15-2026).
- **Interpretation:** having the app call `claude -p` or the Agent SDK with subscription auth is the grey/likely-disallowed area. Having the user run Claude Code interactively and connect to the app's own MCP server, with the app serving only its own data and tools, is the safer pattern. Verdict: **viable with caution; not a reliable default.** Not verified against an explicit Anthropic statement on MCP-server use.
- **OpenAI Codex CLI.** Sign in with a ChatGPT account [S] (https://help.openai.com/en/articles/11369540-codex-usage-limits). Free-tier eligibility conflicts between sources [S]. Usage uses a rolling 5-hour window shared with web and IDE [S]. Whether MCP tool calls count against limits: **[U]**. An API key bills at standard API rates [S].
- Conclusion: subscription-backed usage is a convenience for the user's own interactive sessions, not a dependable backend for an app that makes unattended LLM calls.

---

## Part 2: Paper graph

### 2.1 OpenAlex Works

- Works endpoint: `https://api.openalex.org/works`. The docs say works can be filtered, searched, sorted and paged over documented attributes [V] (https://help.openalex.org/api-entities/works; the Attributes page holds the field list).
- Field names `referenced_works` (outgoing citations, OpenAlex IDs), `related_works` (ML-similar works), `cited_by_api_url` (query URL for citing works) [S] (https://docs.anysite.io/api-reference/openalex/openalexworksreferences; https://developers.openalex.org/guides/recipes.md). Exact schema not confirmed on a fetched official page **[S/U]**.
- Filter for citing works: `filter=cites:W...` (e.g. `https://api.openalex.org/works?filter=cites:W2741809807&sort=cited_by_count:desc&per_page=25`) [S] (https://help.openalex.org/how-to/api-recipes/). Note: `cites:X` returns works that cite X.
- Batch lookup by ID list with `filter=openalex:W1|W2|...` [S] (https://help.openalex.org/how-to/api-recipes/).
- Rate limits: commonly cited as 100,000 requests/day [S] (https://cdn.jsdelivr.net/npm/@saibolla/ada@0.1.3/skills/openalex-database/references/api_guide.md). Polite-pool behavior via `mailto` conflicts between sources **[U]**.
- Recommended for this app: fetch `referenced_works` for seed papers, batch-resolve IDs, and use `cites:` for citers with `per_page` up to 200 **[S; per_page max U]**.

### 2.2 Semantic Scholar Graph and Recommendations API

- Official overview [V] (https://www.semanticscholar.org/product/api): "rate-limited to 1000 requests per second shared among all unauthenticated users," with possible extra throttling under heavy load. Recommendations: "recommended papers similar to a given paper."
- Third-party guides claim roughly 100 requests per 5 minutes without a key [S] (https://awesome.ecosyste.ms/projects/github.com%2FSnippetSquid%2FSemanticScholarMCP). The two figures conflict; the 1000 rps figure is the official one **[V for official; conflict U]**.
- Free API key available; introductory limit of about 1 RPS on some endpoints per third-party reports [S].
- Endpoint paths from prior knowledge, **not verified this session** [U]: `GET https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references` and `/citations` (limit up to 1000 per page); recommendations at `https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}`. The API docs page (https://api.semanticscholar.org/api-docs/graph) did not load.

### 2.3 How Obsidian builds its graph

- Nodes are notes; attachments and tags are optional nodes; orphan notes are hidden unless the Orphans filter is off [V] (https://obsidian.md/help/plugins/graph).
- Links are drawn between nodes from internal `[[wikilinks]]`. Markdown links are not documented as graph edges on that page [V].
- Unresolved links (targets not existing as files) appear unless "Existing files only" is enabled [V].
- Node size grows with the number of references [V]. Local graph shows notes within a depth of the active note [V].
- Wikilinks are on by default in Files and Links settings [S] (https://itsfoss.com/obsidian-create-links.md).
- Implication: for this app, write each paper note with `[[citekey-or-title]]` links to referenced and citing papers. The graph then comes from the vault for free, with unresolved links shown as ghost nodes.

### 2.4 Obsidian plugins for papers

- **Zotero Integration** (mgmeyers): inserts citations, bibliographies, notes and PDF annotations from Zotero; requires Better BibTeX; talks to a running Zotero over the Better BibTeX local connection, so no mobile use [S] (https://github.com/mgmeyers/obsidian-zotero-integration; https://community.obsidian.md/plugins/zotero-annotation-to-pandoc).
- **Citations** (author listing conflicts: hanshans vs Jon Gauthier): reads an export file Zotero writes, so it works with Zotero closed but can lag; bibliographic metadata only, no annotations [S] (https://community.obsidian.md/plugins/obsidian-citation-plugin).
- **ZotLit** and **Simple Citations**: literature-note helpers [S] (https://www.obsidianstats.com/plugins/zotlit; https://www.obsidianstats.com/plugins/simple-citations).
- **Juggl**: interactive, expandable, CSS-stylable replacement for the graph view, with edge labels, code blocks and mobile support. Last push noted as Feb 27, 2025, so maintenance may have slowed **[S]** (https://community.obsidian.md/plugins/juggl; https://github.com/HEmile/juggl).
- **ExcaliBrain**: interactive mind-map of the vault [S]. **Smart Connections**: named only as a related link, no details found **[U]**.

### 2.5 Lightweight force-directed graph in vanilla JS

- Barnes-Hut approximation reduces repulsion from O(N²) to roughly O(N log N) using a quadtree and a theta accuracy parameter; the quadtree is rebuilt each iteration [S] (https://twosixtech.com/faster-force-directed-graph-layouts-by-reusing-force-approximations/).
- Rebuilding the quadtree only periodically (force reuse) cut layout time by 10%–90% in one library's benchmarks [S] (https://cdn.jsdelivr.net/npm/d3-force-reuse@1.0.1/README.md).
- Canvas is reported 4–5× faster than SVG for a roughly 10k-node d3-force graph, but it still stutters; SVG is not advisable beyond a few hundred elements [S] (blog snippets from search, source unclear **[U]**).
- ngraph.forcelayout is framework-agnostic and uses a quadtree; its docs say a few thousand nodes layout at 60 FPS on a modern laptop [S] (https://www.npmjs.com/package/ngraph.forcelayout; https://unpkg.com/mgraph.forcelayout@3.4.3/README.md).
- **Estimate for ~500 nodes (not sourced):** naive all-pairs repulsion is about 125K pair computations per tick (500×499/2), which should fit a 16 ms frame in JS on canvas, so Barnes-Hut is optional at this size. Use a fixed iteration budget or alpha decay so the layout stops. Keep the simulation off the main render loop when settled. **[U as measured figures]**
- Suggested design: Fruchterman-Reingold or simple spring + repulsion with cooling; HTML canvas with a `devicePixelRatio` scale; pan/zoom via a view matrix; hit-testing via a spatial grid; drag by pinning nodes; double-buffer nothing else. About 200–300 lines, no dependencies.

---

## Recommended default provider order for this app

Principle: AGENTS.md forbids external transmission of private notes and PDF text without an explicit user request and a preview. So the default chain must be local-first, with cloud providers only for public text (abstracts, metadata) or after explicit opt-in.

1. **Ollama (local)**: default for everything involving private text. Qwen3 14B on 16 GB GPU, or a 7–8B model on CPU. Use native `format` with a JSON schema. Free, unlimited, private.
2. **LM Studio (local)**: alternate local server on `http://localhost:1234/v1`, same OpenAI-style client code.
3. **Gemini API free tier**: best free cloud quality via the OpenAI-compatible base URL. Use only for non-private text or with explicit opt-in, because free-tier content is used to improve Google products. Check AI Studio for current limits.
4. **Groq free tier**: fast fallback for public text; check its data policy first **[U]**.
5. **OpenRouter `:free`**: fallback; 50 RPD until 10 credits are purchased; check each model's training policy **[U]**.
6. **Cloudflare Workers AI**: small-model fallback within 10K neurons/day.
7. **Hugging Face router**: chat-only fallback; free allocation unclear.
8. **NVIDIA NIM**: optional; credits and terms conflict.

Drop from default: **GitHub Models** (retired 2026-07-30), **Cerebras** (no permanent free tier), **Mistral** free mode (training on free-plan requests). **Claude/Codex subscriptions**: optional, interactive-only via MCP. Do not use for unattended app calls.

---

## Unverified items (summary)

- Gemini per-model RPM/RPD and context windows.
- Groq, OpenRouter, Mistral, Cerebras, NVIDIA base URLs and free-tier training policies.
- Ollama `/v1` `response_format: json_schema` support.
- Semantic Scholar references/citations/recommendations endpoint paths and page-size maxima.
- OpenAlex `per_page` maximum and polite-pool effect.
- Anthropic June 15, 2026 Agent SDK change (single secondary source).
- Whether Codex MCP tool calls count against plan limits.
- Gemma 4 and Qwen3 VRAM figures (secondary sources).
- Juggl and ExcaliBrain current status; Smart Connections features.

## Source list (main)

- https://aistudio.google.com/docs/openai
- https://aistudio.google.com/docs/pricing
- https://aistudio.google.com/docs/rate-limits
- https://openrouter.ai/docs/api-reference/limits
- https://openrouter.ai/docs/guides/routing/model-variants/free
- https://inference-docs.cerebras.ai/support/rate-limits
- https://docs.github.com/en/github-models
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://huggingface.co/docs/inference-providers/index
- https://docs.ollama.com/openai
- https://docs.ollama.com/capabilities/structured-outputs
- https://lmstudio.ai/docs/developer/openai-compat
- https://www.anthropic.com/legal/consumer-terms
- https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access
- https://help.openai.com/en/articles/11369540-codex-usage-limits
- https://help.openalex.org/api-entities/works
- https://help.openalex.org/how-to/api-recipes/
- https://www.semanticscholar.org/product/api
- https://api.semanticscholar.org/api-docs/graph (did not load)
- https://obsidian.md/help/plugins/graph
- https://community.obsidian.md/plugins/juggl
- https://github.com/mgmeyers/obsidian-zotero-integration
- https://www.npmjs.com/package/ngraph.forcelayout
- https://twosixtech.com/faster-force-directed-graph-layouts-by-reusing-force-approximations/
- https://help.mistral.ai/en/articles/455206-how-can-i-try-the-api-for-free-with-the-experiment-plan (search snippet; data-training clause)
