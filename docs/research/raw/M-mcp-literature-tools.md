# M. MCP literature tools: prior art, MCP design rules, and tool catalog for EasyResearch

- Date: 2026-11-10
- Scope: scout research for ExecPlan 006 (Claude Code research system). Target: the new tools of the app's stdio MCP server (`services/mcp/easyresearch_mcp.py`, `mcp` Python package).
- Legend:
  - **[V]** primary page opened and read in this session (the page text was used).
  - **[S]** search-result snippet or third-party listing only. Not opened as a primary source.
  - **[U]** unconfirmed. Page could not be opened, was truncated, or sources conflict. Do not implement from it without checking.
- Status of this file: research input only. No code or config was changed.

---

## Part 1. Source records

### 1.1 MCP specification and official MCP guidance

**1. Tools (MCP spec, 2026-07-28)**
- Org: Model Context Protocol. Date: spec version 2026-07-28.
- URL: https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- Tag: [V]
- Bullets:
  - `tools/list` returns `name`, `title`, `description`, `inputSchema`, optional `outputSchema` and `annotations`. Tool names SHOULD be 1 to 128 characters from `A-Za-z0-9_.-`.
  - `structuredContent` may be any JSON value that conforms to `outputSchema`. Servers MUST return conforming structured results when a schema is declared. For compatibility, a text block with the same JSON SHOULD also be returned.
  - Errors: protocol errors (unknown tool, malformed request) are JSON-RPC errors. Tool execution errors (bad input, API failure) use `isError: true` so the model can self-correct.
  - Annotations: clients MUST consider tool annotations untrusted unless they come from trusted servers.
  - Servers MUST validate inputs, rate-limit tool invocations, and sanitize outputs. Clients SHOULD keep a human in the loop for sensitive operations.
  - Stateful tools: the spec's non-normative guidance is to return an explicit handle from a creation tool and to return a tool execution error when a handle has expired.
- Relevance: directly defines the result envelope and error model for every tool in Part 2. The "annotations are untrusted" rule means our write guards must be enforced server-side and by hooks, not by annotations.

**2. Pagination (MCP spec, 2026-07-28)**
- Org: Model Context Protocol. URL: https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination
- Tag: [V]
- Bullets:
  - Cursors are opaque. Clients MUST NOT parse or modify them, and an empty string is a valid cursor.
  - Page size is chosen by the server. Clients MUST NOT assume a fixed size.
  - `nextCursor` absent means the end of results. An invalid cursor SHOULD return error code -32602.
  - `tools/list` supports pagination too. The server SHOULD return tools in a deterministic order.
- Relevance: the search and related-work tools should return opaque cursors that wrap upstream OpenAlex cursors. Our own event and ledger lists use explicit `after_seq` integers as a domain parameter (see Part 2).

**3. Multi Round-Trip Requests (MRTR, 2026-07-28)**
- Org: Model Context Protocol. URL: https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr
- Tag: [V]
- Bullets:
  - Tools may answer `tools/call` with `resultType: "input_required"` plus `inputRequests` (elicitation or sampling) and an opaque `requestState`. The client retries with a new JSON-RPC `id`.
  - `requestState` is attacker-controlled input. Servers MUST integrity-protect it when it affects authorization or business logic, and MUST bind it to the principal and request.
  - Servers MUST NOT send `inputRequests` the client did not declare support for.
- Relevance: MRTR is a possible approval channel, but Claude Code's client support is not verified here [U]. The design should not depend on it. Approvals stay in the app UI (`approval_request` plus `approval_status`).

**4. Security best practices (MCP)**
- Org: Model Context Protocol. URL: https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices
- Tag: [V]
- Bullets:
  - Covers confused deputy, token passthrough (servers MUST NOT accept tokens not issued for them), SSRF, session hijacking, and local server compromise.
  - Local servers SHOULD use stdio to limit access to the client. Restrict HTTP transports with auth if they are used.
  - Scope minimization: expose only the tools each caller needs.
- Relevance: our server is stdio and local, which fits. The OpenAlex key must never be returned in tool output and never placed in URLs (use the `Authorization` header). Token passthrough is an anti-pattern, so agents never see the key.

**5. Tool design: "Writing effective tools for agents (with agents)"**
- Org: Anthropic Engineering. Date: 2025-09-11.
- URL: https://www.anthropic.com/engineering/writing-tools-for-agents
- Tag: [V]
- Bullets:
  - Namespace tools by service and resource. Use unambiguous parameter names (for example `user_id`).
  - Cap responses with sensible defaults. Offer a concise and a detailed response format. Detailed responses include the IDs needed for follow-up calls.
  - Use pagination, range selection, filters, and truncation. When truncating, steer the agent toward narrower queries.
  - Make errors actionable: say what to fix or show a correct example.
  - Evaluate with realistic multi-step tasks, track accuracy, calls, tokens, and errors, and keep a held-out set.
  - The article notes that Claude Code limits tool responses to 25,000 tokens by default.
- Relevance: drives the `response_format`, `limit`, `cursor`, and error-shape decisions in Part 2. Our held-out evaluation set matches the design doc's hidden evaluation set.

**6. MCP tasks extension and 2026-07-28 release (secondary)**
- Org: various. Dates: 2026.
- URLs: https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/ (release candidate post, [S]); https://tasks.extensions.modelcontextprotocol.io/ ([U], not opened); https://claudeissues.com/issue/102347-feature-support-the-mcp-tasks-extension-io-modelcontextprotocol-tasks-spec-2026 ([S])
- Tag: [S] / [U]
- Bullets:
  - Tasks moved out of core into the extension `io.modelcontextprotocol/tasks`. Clients poll with `tasks/get`.
  - A search snippet reports an open Claude Code issue for Tasks support on 2026-07-28. Treat Claude Code support as unverified.
  - Some secondary sources say the spec is final, and others say it is a release candidate. Treat the exact status as unverified.
- Relevance: do not depend on Tasks. Keep each tool call short (seconds) and make long snowballing a sequence of bounded calls driven by the lead.

**7. Python SDK and FastMCP (version questions)**
- Orgs: Model Context Protocol (python-sdk); gofastmcp (FastMCP).
- URLs: https://github.com/modelcontextprotocol/python-sdk ([V]); https://pypi.org/project/mcp/ ([V]); https://gofastmcp.com/servers/tools ([V])
- Tag: [V] with conflicts flagged
- Bullets:
  - PyPI `mcp` page as fetched: latest version 2.3.0, released Oct 2, 2026, Python 3.10 or later, MIT. This conflicts with the project assumption of `mcp` 1.27.x in the task brief. Verify the installed version before implementing.
  - The python-sdk GitHub page shows `MCPServer` and tools via `@mcp.tool()`. It does not document `FastMCP` features, so its feature list could not be confirmed.
  - The gofastmcp tools page (a separate FastMCP project, not the official SDK) documents output schemas from return annotations, `ToolAnnotations` (`readOnlyHint` default false, `destructiveHint` default true, `idempotentHint` default false, `openWorldHint` default true, advisory only), and a `Context` object for progress and logging. Those features are not confirmed for `mcp.server.fastmcp` in 1.x or 2.x.
  - The gofastmcp page also says output schemas must be object types and that a bare `list` annotation yields no output schema.
- Relevance: the existing server registers tools with `server.tool(annotations=...)` and returns plain dicts. Whether `outputSchema` is generated automatically for return types in the official package is an open question (Part 3).

**8. Claude Code: MCP configuration and output limits**
- Org: Anthropic (Claude Code docs). URL: https://code.claude.com/docs/en/mcp
- Tag: [V] (page truncated; tool search and permission syntax sections not fully read)
- Bullets:
  - Project servers live in `.mcp.json`. Interactive sessions ask for approval first. `claude -p` runs and Agent SDK sessions load project servers without asking. Use `--strict-mcp-config` or `disabledMcpjsonServers` to control this.
  - Output: Claude Code warns at 10,000 tokens and limits MCP tool output to 25,000 tokens by default. `MAX_MCP_OUTPUT_TOKENS` raises the cap. Successful text results longer than 50,000 characters are saved to a file unless the server raises a tool's own limit.
  - Tool search is on by default. Claude Code can list server tool names to Claude mid-turn, and failed servers are reported through `ToolSearch`.
  - Timeouts: `MCP_TIMEOUT` (startup), `MCP_TOOL_TIMEOUT` (per call), and a per-server `timeout` field in milliseconds.
- Relevance: target responses well under 10,000 tokens (about 40,000 characters as a hard cap) so the warning never fires. Project MCP servers in headless runs load without a prompt, so the design should not rely on the approval dialog as a control.

**9. Claude Code: subagents**
- Org: Anthropic (Claude Code docs). URL: https://code.claude.com/docs/en/sub-agents
- Tag: [V] (large page; first 100,000 characters read)
- Bullets:
  - Frontmatter fields include `name`, `description`, `tools`, `disallowedTools`, `model` (`opus`, `sonnet`, `haiku`, `fable`, or a full ID), `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `effort`, `color`.
  - Subagents can spawn subagents by default, up to three layers. `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` turns nesting off. The design doc requires depth 1, so this env var (or omitting `Agent` from non-lead tool lists) must be set explicitly.
  - Subagents inherit parent MCP tools by default. If `tools` is set, MCP tools are included only when named (for example `mcp__easyresearch__*`). `disallowedTools` accepts `mcp__<server>` or `mcp__*`.
  - Inline `mcpServers` definitions connect when the subagent starts and disconnect when it finishes. This allows a per-role environment token (Part 3).
- Relevance: the design's allowlists are enforceable with `tools` and `disallowedTools`. Without an allowlist, every subagent inherits all MCP tools.

**10. Claude Code: hooks**
- Org: Anthropic (Claude Code docs). URL: https://code.claude.com/docs/en/hooks
- Tag: [V] (large page; first 100,000 characters read)
- Bullets:
  - `PreToolUse` runs before a call. Exit code 2 blocks the call and sends stderr to Claude. Alternatively, print JSON with `permissionDecision: "deny"`.
  - MCP tools are named `mcp__<server>__<tool>`. A matcher with characters beyond letters, digits, `_`, `-`, space, `,`, `|` is a regex, unanchored. `mcp__memory` (without `.*`) matches nothing.
  - A failed or timed-out `PreToolUse` hook does not block by default. Set `"onFailure": "block"` (requires Claude Code v2.1.295 or later).
  - Hooks run inside subagents too. Input includes `agent_id` and `agent_type`.
- Relevance: the protected-area guard (`data/`, `.claude/`, `AGENTS.md`, evaluation set, backup code) and the "no external access" check can be enforced here. The hook input can identify which subagent is calling, which the MCP server cannot see.

**11. Claude Code: permissions (partial)**
- Org: Anthropic (Claude Code docs). URL: https://code.claude.com/docs/en/permissions
- Tag: [V] for the permission table; [U] for MCP rule syntax (the MCP section was not in the returned text).
- Bullets:
  - Read-only tools (Read, Grep) need no approval inside the working directory. Edits need approval until session end. WebFetch and WebSearch need approval except preapproved domains.
  - The MCP rule syntax (`mcp__server__tool`) was not confirmed from this page. Plugin tools are referenced by full name, per the MCP docs page.
- Relevance: keep access control in the subagent `tools` allowlists and in hooks, which are confirmed.

### 1.2 OpenAlex (primary data source for search and citation graph)

**12. OpenAlex: authentication and rate limits**
- Org: OpenAlex (help center). Date: page "last updated November 3, 2026".
- URL: https://help.openalex.org/api-reference/authentication
- Tag: [V]
- Bullets:
  - Keyless requests work. A free key raises the daily budget to 10 times the keyless budget. A key works only after its email is verified.
  - Cursor paging past the first page requires a key.
  - Keys go in the `api_key` query parameter or the `Authorization: Bearer` header. Both work. Use the header in our client so the key never appears in URLs or logs.
  - Agent-requested keys (`POST https://api.openalex.org/api-keys`) stay inactive until the owner clicks an emailed link. They spend the owner's budget. The app should let the user paste a key instead.
  - Per-second limits: no key 10 requests per second; free key or prepaid 30; annual plan 50. Semantic search 1 request per second. Searches with more than 5 `OR`/`AND`/`NOT` operators: 1, 5, or 25 per second by tier.
  - 429 causes: daily budget exceeded, per-second limit exceeded, or new-account first-dollar pacing. Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Credits-Used`, `X-RateLimit-Reset`. `GET /rate-limit` reports usage.
  - Hard limits: 100 OR values per filter, `per_page` max 100, `page x per_page` max 10,000 (use cursors beyond that).
  - The page does not mention the polite pool or an email parameter.
- Relevance: the budget envelope for our `search_literature` and `get_related` tools. The app should read `X-RateLimit-*` headers and return budget state in every response.

**13. OpenAlex: pricing and plan tiers**
- Org: OpenAlex. Date: page "last updated November 3, 2026".
- URL: https://help.openalex.org/access/pricing/
- Tag: [V]
- Bullets:
  - Free key: $0 per year, $1 of API usage per day, reset at midnight UTC. A new account spends its first $1 at up to $0.10 every 5 minutes.
  - Plans as stated: Member $5,000 per year with $20 per day; Member+ $10,000 per year with $100 per day; Partner from $20,000 per year. Pay-as-you-go is prepaid in $1 increments and is used after the free $1 runs out. Prepaid usage expires 3 months after the latest purchase.
  - The page measures everything in dollars, not credits.
- Relevance: a free key gives $1 per day. The app should show remaining dollars and refuse calls when the budget is near zero.

**14. OpenAlex: example per-call costs**
- Org: OpenAlex. URL: https://help.openalex.org/access/example-costs/
- Tag: [V]
- Bullets:
  - Single entity lookup by ID or DOI: free.
  - List and filter: $0.10 per 1,000 calls ($0.0001 per call).
  - Full-text keyword search: $1 per 1,000 calls ($0.001 per call).
  - Autocomplete and per-result cost are not stated on the page.
- Relevance (derived arithmetic from the published prices, not stated by OpenAlex): $1 per day buys about 1,000 search calls or about 10,000 list calls. Fetching `referenced_works` through single-entity lookups is free. This makes reference expansion much cheaper than citing-paper expansion.

**15. OpenAlex: list works, paging, and filters**
- Org: OpenAlex. URL: https://help.openalex.org/api-entities/works/get-lists-of-works
- Tag: [V]
- Bullets:
  - `per_page` range 1 to 100, default 25. `page` has no fixed cap, but `page x per_page` must not exceed 10,000.
  - Cursor paging: start with `cursor=*` and follow `meta.next_cursor` until it is null and results are empty. Cursors past the first page need an API key.
  - The page advises the snapshot for full downloads.
- Relevance: keeps `search_literature` within the basic-paging ceiling and makes cursor paging the normal path.

**16. OpenAlex: filter reference (partial)**
- Org: OpenAlex. URL: https://help.openalex.org/api-entities/works/filter-works
- Tag: [V] for `title.search`, `publication_year`, `open_access.is_oa`, OR limit; [U] for `cites`, `referenced_works`, `openalex_id`.
- Bullets:
  - Up to 100 values can be combined with `|` in one filter, and OR works only within one filter.
  - The page's examples use `title.search`, `cited_by_count:>1`, and `is_oa:true`.
  - The page does not document `cites:`, `referenced_works`, or `related_to`. These are needed for `get_related` and must be checked against the Works API reference before implementation.
- Relevance: a blocking open item for `get_related`. A third-party server (cyanheads, [V] repo page) exposes a citation-graph tool with `cites`, `cited_by`, and `related_to` directions, which suggests these exist, but this is not confirmed from an OpenAlex primary page.

**17. cyanheads/openalex-mcp-server**
- Org: cyanheads (individual). URL: https://github.com/cyanheads/openalex-mcp-server
- Tag: [V] (repo page)
- Bullets:
  - Apache-2.0. 17 stars, 6 forks, 10 open issues, 185 commits on `main`, version 0.11.0 by badge. Last commit date not shown.
  - Five tools: `openalex_search_entities`, `openalex_analyze_trends`, `openalex_resolve_name`, `openalex_get_citation_graph` (`direction`: `cites`, `cited_by`, `related_to`), `openalex_describe_fields`.
  - Transports: stdio and Streamable HTTP. Auth modes `none`, `jwt`, `oauth`.
  - Reports daily-budget cost, remaining balance, and reset time in each API-calling tool. Caps `per_page` at 100 (200 for analysis, 50 for semantic). Responses over 8,000,000 bytes fail with `response_too_large`. Reads `OPENALEX_API_KEY` and `OPENALEX_MAILTO`.
- Relevance: the closest prior art for budget reporting and tool shapes. It does not fit our rule that all external access passes through the app's own budget, cache, and log. Reuse as a reference only (Part 2).

**18. OpenAlex MCP listings (community)**
- Orgs: various (abhijain864, oksure, reetp14, hbiaou, dominikusbrian). URLs: https://glama.ai/mcp/servers/e5dpkjuo7r ; https://glama.ai/mcp/servers/oksure/openalex-research-mcp ; https://github.com/dominikusbrian/openalex-mcp-server
- Tag: [S]
- Bullets:
  - Several community servers search works and authors through the OpenAlex REST API. One (oksure) is listed with 18 tools including `get_citation_network`. Another (abhijain864) is a small Python server with an optional email for the polite pool.
  - No official OpenAlex MCP server was found in these results.
  - Listings disagree on counts and maintenance. Verify each repo before any use.
- Relevance: confirms the pattern is common. None is a good dependency for us.

### 1.3 Semantic Scholar

**19. Semantic Scholar API product page**
- Org: Allen Institute for AI / Semantic Scholar. URL: https://www.semanticscholar.org/product/api
- Tag: [V]
- Bullets:
  - Unauthenticated: "most endpoints are rate-limited to 1000 requests per second shared among all unauthenticated users," with possible throttling under heavy use.
  - With an API key: a new key starts at 1 request per second on all endpoints. Higher limits are not stated on the page.
  - Three services: Academic Graph (papers, authors, citations, venues, embeddings), Recommendations, Datasets. An API License Agreement is linked. Its text was not read, so caching and redistribution rules are unknown [U].
- Relevance: the official page conflicts with community READMEs on unauthenticated limits (see below). Plan for a 1 request per second cap with a key.

**20. Semantic Scholar API docs (index)**
- URL: https://api.semanticscholar.org/api-docs/ . Tag: [V] (navigation only; endpoint details not on this page; `/api-docs/graph` was not opened).
- Bullets: lists the Academic Graph, Recommendations, and Datasets sections. Endpoint paths, batch sizes, and `fields` syntax are [U] until the Graph page is read.

**21. akapet00/semantic-scholar-mcp**
- Org: akapet00 (individual). URL: https://github.com/akapet00/semantic-scholar-mcp
- Tag: [V] (repo page; PyPI 0.3.1 seen in search results [S])
- Bullets:
  - MIT. 38 stars, 9 forks, 86 commits. Last commit date not shown.
  - 16 tools listed, including `search_papers` (with filters), `get_paper_details`, `get_paper_citations`, `get_paper_references`, `get_recommendations`, `get_related_papers`, and `export_bibtex`. No parameter schemas on the page. A search snippet reported 13 tools, so counts disagree.
  - Rate limits as stated: without key, 5,000 requests per 5 minutes in a shared pool; with key, 1 request per second. `SEMANTIC_SCHOLAR_API_KEY` env var. It also documents `DISABLE_SSL_VERIFY`, which should not be used.
- Relevance: a useful catalog of Semantic Scholar endpoint names. Its unauthenticated figure conflicts with the official page and with the next entry.

**22. FujishigeTemma/semantic-scholar-mcp**
- Org: FujishigeTemma (individual). URL: https://github.com/FujishigeTemma/semantic-scholar-mcp
- Tag: [V]
- Bullets:
  - MIT. 10 stars. Last commit date not shown.
  - Four tools with parameters: `search_paper` (`query` required; `fields`, `limit`, `offset`, `year`, `fieldsOfStudy`, `openAccessPdf`), `get_paper` (`paper_id` accepts DOI, arXiv ID, S2 ID), `get_authors`, `get_citation` (`format`: bibtex, apa, mla, chicago).
  - Rate limits as stated: without key 100 requests per 5 minutes; with key 1 request per second.
  - Does not mention caching.
- Relevance: a compact reference for parameter names. Its unauthenticated figure (100 per 5 minutes) conflicts with entry 21 (5,000 per 5 minutes) and must be verified against the official API documentation. The safe design uses a single global limiter at 1 request per second when a key exists and a conservative 1 request per 5 seconds otherwise [design choice, not a sourced number].

**23. SnippetSquid/SemanticScholarMCP and other S2 listings**
- URL: https://awesome.ecosyste.ms/projects/github.com%2FSnippetSquid%2FSemanticScholarMCP (and several others)
- Tag: [S]
- Bullets:
  - Listings show `search_papers` with `query` and optional year filters, plus batch retrieval and author search.
  - A truaxki listing describes a remote Streamable HTTP server. Not reviewed.
- Relevance: confirms `search_papers` is the common name. No further reliance.

### 1.4 arXiv, Crossref, Unpaywall, NCBI, Europe PMC

**24. arXiv API terms of use**
- Org: arXiv (Cornell). URL: https://info.arxiv.org/help/api/tou.html
- Tag: [V]
- Bullets:
  - For the legacy API (including the arXiv API), make no more than one request every three seconds, with a single connection at a time. Limits apply across all machines.
  - You may use e-print content for personal use or research. You must not store and serve arXiv e-prints from your own servers without permission or a permissive license.
  - Limits "may change in the future."
- Relevance: the arXiv connector (if added) must serialize requests with a 3-second gap. The app must not cache and republish e-print content; caching metadata is a separate question.

**25. arXiv API user manual**
- URL: https://info.arxiv.org/help/api/user-manual.html . Tag: [V]
- Bullets:
  - `search_query` prefixes: `ti`, `au`, `abs`, `co`, `jr`, `cat`, `rn`, `id`, `all`. Operators `AND`, `OR`, `ANDNOT`. Phrases in double quotes.
  - `start` default 0. `max_results` default 10, total capped at 30,000, slices of at most 2,000 per request. Above 30,000 returns HTTP 400.
  - `sortBy` (`relevance`, `lastUpdatedDate`, `submittedDate`); `sortOrder` (`ascending`, `descending`); `id_list` for specific IDs.
  - Recommends a 3-second delay between repeated calls.
- Relevance: the arXiv search tool can mirror this shape (`limit` up to 2,000 per slice, paging by `start`).

**26. Crossref: rate-limit changes (effective 1 December 2025)**
- Org: Crossref. URL: https://crossref.org/blog/announcing-changes-to-rest-api-rate-limits/
- Tag: [V]
- Bullets (table as published):
  - Public pool, single record: 5 requests per second, concurrency 1.
  - Public pool, list or query: 1 request per second, concurrency 1.
  - Polite pool, single DOI: 10 requests per second, concurrency 3.
  - Polite pool, list or query: 3 requests per second, concurrency 3.
  - Effective date: 1 December 2025.
- Relevance: use the polite pool with a contact identifier that the user provides (a `mailto` parameter or a User-Agent with contact). This is a real identifier the user sets, so it counts as external sharing; get the user's consent for the value.

**27. Crossref REST API tips (partial)**
- URL: https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/ . Tag: [V]
- Bullets:
  - `rows` default 20, maximum 1,000.
  - Cursor paging: add `cursor=*`; the response includes `next-cursor`. Stop when fewer items than `rows` are returned.
  - A 429 means back off. The page gives no numeric limits, so the blog (entry 26) is the source for numbers.
- Relevance: cursor semantics for a future Crossref connector.

**28. Crossref polite-pool forum post (conflict)**
- URL: https://community.crossref.org/t/rest-api-pools-which-to-use-and-when/15317 . Tag: [S]
- Bullets: a community post lists the polite pool at 10 requests per second with a concurrency limit of 5. This conflicts with the blog table (concurrency 3). Check the `x-concurrency-limit` response header at runtime.

**29. Unpaywall**
- Org: OurResearch. URLs: https://unpaywall.org/api/v2 (listed in search results, [S]; fetch returned only the page title, [U]).
- Tag: [S] for the figures; [U] for the endpoint format and field names.
- Bullets:
  - A search summary quotes Unpaywall's documentation as requiring the email as a URL parameter, with usage kept to 100,000 calls per day.
  - Higher limits need contact with OurResearch for a key (third-party skill pages, [S]).
  - Field names such as `best_oa_location` and `url_for_pdf` are common knowledge but were not verified here [U].
- Relevance: a DOI-to-open-access lookup for the "can I read the PDF legally" check. Sending DOIs and the user email is an external transmission and needs consent.

**30. NCBI E-utilities (PubMed)**
- Org: NCBI. URLs: https://support.nlm.nih.gov/knowledgebase/article/KA-05318/en-us ([S]); https://www.ncbi.nlm.nih.gov/books/NBK25497/ ([U]: fetch returned a browser-check page, no content).
- Tag: [S] / [U]
- Bullets:
  - Search snippets report 3 requests per second per IP without a key and 10 per second with a key. Exceeding the limit returns a JSON error.
  - Keys are one per account. Higher limits are granted on request.
- Relevance: PubMed is out of the current scope. Record the figure for later, pending verification on the official page.

**31. Europe PMC REST API**
- URL: https://europepmc.org/RestfulWebService . Tag: [U] (HTTP 403, no content read).
- Relevance: not verified. Do not rely on any Europe PMC figures in this file.

### 1.5 Existing MCP servers for scholarly sources (other)

**32. openags/paper-search-mcp**
- Org: openags (community). URL: https://github.com/openags/paper-search-mcp
- Tag: [V]
- Bullets:
  - MIT. About 3.0k stars, 155 commits. Last commit date not shown.
  - Tools include `search_papers(query, sources)` across arXiv, PubMed, Crossref, OpenAlex, Semantic Scholar, CORE, Europe PMC, and others, plus `download_with_fallback` (`source`, `paper_id`, `doi`, `use_scihub`) and per-source readers.
  - Includes an optional Sci-Hub fallback (off by default) and ACM, Scopus, and Web of Science connectors with access caveats.
  - Several sources are marked planned or TODO. The README is inconsistent on which connectors are complete.
- Relevance: broad, but it gives an agent direct downloads and paywall-adjacent paths. That conflicts with our rule that all access goes through the app. Reuse ideas only. Exclude the Sci-Hub path entirely.

**33. kujenga/zotero-mcp**
- Org: kujenga (individual). URL: https://github.com/kujenga/zotero-mcp
- Tag: [V]
- Bullets:
  - MIT. 162 stars, 83 commits. Last commit date not shown.
  - Three tools: `zotero_search_items`, `zotero_item_metadata`, `zotero_item_fulltext` (PDF contents). Parameter names not documented on the page.
  - Read-only is implied by the descriptions but not stated.
- Relevance: an optional future import path for users who already have a Zotero library. Not needed for the current design.

**34. 54yyyu/zotero-mcp**
- Org: 54yyyu (individual). URL: https://github.com/54yyyu/zotero-mcp
- Tag: [V]
- Bullets:
  - MIT for the server and `zotero-cli`. The Zotero Agent plugin under `plugin/` is AGPL-3.0-or-later.
  - About 5.8k stars, 458 forks. Default profile of 38 tools (50 total), grouped by `ZOTERO_MCP_TOOLSETS`.
  - Write operations: add items, manage collections and tags, merge duplicates, create notes and highlights. Semantic search via optional embeddings, and full-text reads with page images.
- Relevance: too broad and write-capable for this design. The AGPL plugin is a licensing concern if any code is copied. Do not reuse.

**35. Citation-graph MCP tools (listings)**
- URLs: https://glama.ai/mcp/servers/Liyux3/scholar-mcp/tools/build_paper_graph ; https://glama.ai/mcp/servers/zoharbabin/web-researcher-mcp/tools/citation_graph ; https://glama.ai/mcp/servers/DaniManas/ResearchMCP/tools/get_citations ; https://scite.ai/blog/citation-surfing-scite-mcp
- Tag: [S]
- Bullets:
  - Liyux3 `build_paper_graph`: multi-hop expansion with `max_hops` 1 to 3 and `max_papers` up to 200.
  - Web Researcher `citation_graph`: single-hop, `direction` `cited_by` or `references`, up to 25 per direction.
  - ResearchMCP `get_citations`: OpenAlex IDs, `direction` `cited_by`, `references`, or `both`, default `max_results` 10.
  - Scite `citation_graph`: edges labeled supporting, contrasting, or mentioning. Scite is a paid service.
- Relevance: confirms single-hop plus caller-driven loops is the common shape. Our `get_related` is one hop; the lead controls depth. Scite's stance labels are a useful idea for the verifier but cost money.

**36. Obsidian MCP servers (listings)**
- URLs: https://glama.ai/mcp/servers/faisalhossainnyc/obsidian-mcp-server ; https://mcpservers.org/tr/servers/cyanheads/obsidian-mcp-server
- Tag: [S]
- Bullets: several servers read and write vault notes via direct file access, the Obsidian Local REST API plugin, or the Obsidian CLI. Some warn that write access should be backed up.
- Relevance: out of scope for the current milestone. Our own notes are the in-app data. If exports to Obsidian are added later, file-based writes must respect the protected-area rules.

**37. Google Scholar (terms and automation)**
- URLs: https://www.casrai.org/dictionary/term/google-scholar-api ([S]); https://conductatlas.com/platform/google/google-terms-of-service/prohibited-conduct-automated-access-and-ai-training-restrictions/ ([S]); Google Scholar inclusion pages ([S]).
- Tag: [S]
- Bullets:
  - Secondary sources say Google's Terms of Service require express permission for automated queries, which Google Scholar has not granted for bulk querying. A tracker says the terms were updated in April 2026 and apply to signed-out users too.
  - No sanctioned Scholar API was found. Scholar's robots rules disallow crawler access to search pages, per one secondary source.
  - Primary Google terms and robots.txt were not opened [U].
- Relevance: do not build a Google Scholar connector or scraper. Use OpenAlex and other open APIs instead.

**38. MCP output shape commentary (secondary)**
- URLs: https://eseospace.com/blog/mcp-structured-tool-output/ ; https://dev.to/gustavo_gated/the-2026-07-28-mcp-spec-a-server-readiness-checklist-14nf ; https://khavel.substack.com/p/mcp-outputschema-y-structuredcontent
- Tag: [S]
- Bullets:
  - Commentary describes `outputSchema` as validation for `structuredContent`, with JSON Schema 2020-12 by default. Remote `$ref` must not be dereferenced automatically.
  - Commentary describes the 2026-07-28 change that allows any JSON root for `structuredContent` (an array root is allowed). This matches the spec page's wording [V].
- Relevance: supports an object root for all new tools, which is simpler for clients and for our own validation.

**39. Other Semantic Scholar and scholarly MCP listings (not reviewed)**
- Examples: `cktbarking/semanticMCP` (search_papers with limit default 5, max 100, uvx install), `JackKuo666/semanticscholar-MCP-Server` (`search_semantic_scholar`). Tag: [S]. Not opened.

**40. Anthropic MCP tool-search and deferred loading (partial)**
- URL: https://code.claude.com/docs/en/mcp (same page as entry 8). Tag: [V] for "on by default"; [U] for the schema loading mechanism, which was in the truncated part.
- Relevance: the number of tools matters less when schemas are deferred, but each subagent should still get a narrow `tools` allowlist.

**41. OpenAlex filter-level evidence from community servers (not a primary source)**
- Tag: [S]. Covered in entries 16 and 17. No separate action.

---

## Part 2. Tool catalog proposal (EasyResearch MCP server)

### 2.0 Global conventions

- **Namespace.** Claude Code exposes server tools as `mcp__easyresearch__<name>`. Keep short, resource-first names. Existing tools (`list_projects`, `search_library`, and others in `services/mcp/easyresearch_mcp.py`) keep their names for compatibility. New tools use the names below. Anthropic's guidance on namespacing argues for a prefix on new tools if collisions appear. Decision needed (Part 3).
- **Transport and runtime.** Local stdio server only. No HTTP transport. External calls happen inside the FastAPI app, not in the MCP process, so the budget, cache, and audit log stay in one place.
- **Result envelope.** Declare `outputSchema` with an object root. Return the JSON both as `structuredContent` and as a JSON text block (spec "SHOULD"). Errors are returned as `isError: true` with `structuredContent` `{ "ok": false, "error": { "code", "message", "retryable", "fix" } }`. Whether `outputSchema` requires conforming error shapes is an open question (Part 3).
- **Untrusted text.** Titles, abstracts, quotes, and lesson text are data. Keep the existing `untrusted_content` wrapper style with a top-level `"untrusted": true` marker on every result that carries external or PDF text. Clip each text field (see limits).
- **response_format.** `"concise"` (default) or `"detailed"`, following Anthropic's guidance. Concise returns IDs and short text. Detailed adds abstracts and extra fields.
- **Size budget.** Target 4,000 tokens for a typical call and 10,000 at most. Hard cap of 40,000 characters per result (below Claude Code's 50,000-character file-spill threshold and 25,000-token default cap).
- **Annotations.** Read tools: `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`. External read tools: also `openWorldHint: true`. Write tools: `readOnlyHint: false`, `destructiveHint: false`, plus `idempotentHint` where a key is used. Annotations are untrusted (spec) and advisory, so every write rule below is enforced in code.
- **Rate limiting.** Server-side token bucket per upstream and per tool (spec requires servers to rate-limit tool invocations).
- **Secrets.** The OpenAlex key is read from the app's settings store. It is sent in the `Authorization` header and never returned in any result, log, or error.
- **Actor identity.** Writes take an `actor` field. Because the MCP server cannot see which subagent called it, the actor value is advisory until a per-role identity is bound (Part 3, item 3).

### 2.1 Literature tools (external, read-only)

**Tool: `search_literature`**
- Purpose: keyword and filter search over OpenAlex works. Used to find candidate papers. Results are candidates, not evidence.
- Agent: `literature-scout` (also `verifier` for counter-search, budgeted).
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["query"],
  "properties": {
    "query": {"type": "string", "minLength": 3, "maxLength": 300, "description": "Keyword query. Do not paste private note text; keep queries short."},
    "year_from": {"type": "integer", "minimum": 1900, "maximum": 2100},
    "year_to": {"type": "integer", "minimum": 1900, "maximum": 2100},
    "open_access_only": {"type": "boolean", "default": false},
    "min_cited_by": {"type": "integer", "minimum": 0, "default": 0},
    "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
    "cursor": {"type": "string", "description": "Opaque cursor from a previous call."},
    "response_format": {"type": "string", "enum": ["concise", "detailed"], "default": "concise"}
  }
}
```
- Output shape (structuredContent):
  - `results[]`: `work_id` (OpenAlex `W...`), `doi`, `title` (≤300 chars), `year`, `first_author`, `venue`, `cited_by_count`, `is_oa`, `url`.
  - Concise: no abstract. Detailed adds `abstract` (≤2,000 chars), `authors` (≤5), `referenced_count`, `ids` (`openalex`, `doi`, `arxiv` if present).
  - Envelope: `next_cursor` (or null), `truncated` (bool), `budget` (`daily_limit_usd`, `remaining_usd`, `reset_utc`), `cache` (`hit`, `fetched_at`), `untrusted: true`.
- Size limits: `limit` ≤ 25 concise, ≤ 10 detailed; text fields clipped; total ≤ 40,000 characters.
- Pagination: opaque cursor that wraps OpenAlex `next_cursor` (cursors past page one need a key; without a key, return a clear error with a fix message).
- Annotations: `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: true`.
- Error cases:
  - `query_too_short` / `query_too_long`: fix message with the allowed length.
  - `budget_exhausted`: remaining daily balance under the per-call cost; include `reset_utc`; `retryable: false` for today.
  - `rate_limited` (429): include the reset or retry-after; `retryable: true`.
  - `key_missing` or `key_not_activated` (403): tell the user to activate or paste a key in app settings. Never tell the agent to request a key.
  - `too_many_boolean_operators`: fix message suggesting fewer operators (OpenAlex limit is 1 request per second above 5 operators).
  - `upstream_timeout` / `upstream_unavailable`: retryable.
- Rate-limit and budget handling:
  - App-side pacing: semantic search at 1 request per second; keyword search capped at the tier limit (30 per second with a free key, 10 without). Use a single global limiter with a margin.
  - Pre-check the remaining daily budget from the last `X-RateLimit-*` headers and `GET /rate-limit`. Refuse if remaining is below one search cost ($0.001 published).
  - Per-cycle budget set by the policy profile (for example max searches per cycle). Enforced in the app, not by the agent.
  - Cache normalized (query, filters) for 24 hours; cached results still report budget state.
  - Every external call is written to the audit log with query text, count, and cost. Queries sent to OpenAlex are external transmission; the cycle-start consent must cover them (Part 3).
- Reuse decision: reimplement the OpenAlex client in the app (about 200 lines of HTTP and mapping). Use cyanheads' budget-header handling and `per_page` caps as reference (Apache-2.0; attribution if code is copied). Do not install a third-party OpenAlex MCP server, because it would bypass the app's budget, cache, and log.

**Tool: `get_related`**
- Purpose: one-hop citation expansion for a seed work. The lead calls it repeatedly with a cap. The tool never crawls recursively.
- Agent: `literature-scout` (snowballing), `research-lead` (rare).
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["work_id", "direction"],
  "properties": {
    "work_id": {"type": "string", "pattern": "^(W[0-9]+|10\\.[0-9]{4,9}/\\S+)$", "description": "OpenAlex work ID or DOI."},
    "direction": {"type": "string", "enum": ["references", "cited_by"]},
    "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
    "sort": {"type": "string", "enum": ["cited_by_count", "publication_year"], "default": "cited_by_count"},
    "cursor": {"type": "string"},
    "response_format": {"type": "string", "enum": ["concise", "detailed"], "default": "concise"}
  }
}
```
- Output shape: `seed` (work summary), `direction`, `items[]` (same fields as `search_literature`), `next_cursor`, `truncated`, `budget`, `untrusted: true`.
- Implementation notes:
  - `references`: read `referenced_works` from the seed record (a single-entity lookup, which is free per published prices), then fetch the referenced works in batches with an OR filter of up to 100 IDs per call (the list cost is $0.0001 per call). Verify the ID filter name first [U].
  - `cited_by`: a works list filtered by a cites-style filter. Syntax [U] until checked against the Works API reference.
  - Works with no `referenced_works` return an empty list with a note, not an error.
- Size limits: `limit` ≤ 25; batches of at most 100 IDs; total ≤ 40,000 characters.
- Pagination: opaque cursor. Basic paging stops at 10,000 results per query; cursors are required beyond page one (key needed).
- Annotations: as `search_literature`.
- Error cases:
  - `work_not_found` (404): suggest checking the ID or DOI.
  - `invalid_identifier`: show accepted formats.
  - `no_references`: empty result with note (not an error).
  - `budget_exhausted`, `rate_limited`, `key_missing`, `upstream_timeout`: as above.
- Rate-limit and budget handling: the same app limiter. The lead must set a per-cycle cap on expansion depth and on total seed count (for example, one hop from at most N seeds per cycle). The app enforces the cap in the cycle state, not in the prompt.
- Reuse decision: reimplement. Reference: the citation-graph tools in entry 35 (single-hop plus caller loop is the common design). The multi-hop `build_paper_graph` pattern is not needed because the lead controls depth.

**Tool: `verify_quote`**
- Purpose: deterministic check that a quoted string appears in the stored text of a library paper. Used by `citation-checker` and `verifier`. Returns where the match is, so the agent can cite a page.
- Agent: `citation-checker` (primary), `verifier`.
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["paper_id", "quote"],
  "properties": {
    "paper_id": {"type": "string", "minLength": 1},
    "quote": {"type": "string", "minLength": 10, "maxLength": 400},
    "page_index": {"type": "integer", "minimum": 0, "description": "Physical PDF page index (0-based). Optional; when omitted, all pages are searched."},
    "match_mode": {"type": "string", "enum": ["normalized", "fuzzy"], "default": "normalized"},
    "fuzzy_min_ratio": {"type": "number", "minimum": 0.85, "maximum": 1.0, "default": 0.92}
  }
}
```
- Output shape: `match` (`exact`, `fuzzy`, `none`, `no_text_layer`), `page_index` (physical), `printed_page_label` (if known), `char_start`, `char_end`, `context` (≤200 characters around the match), `fuzzy_score` (fuzzy only), `page_text_sha256`, `pdf_sha256`, `untrusted: true`.
- Normalization rules (proposal): Unicode NFKC, collapse whitespace, unify quote and dash variants, join hyphenated line breaks, drop soft hyphens. Document these in the tool description so the agent knows what counts as a match.
- Size limits: `context` ≤ 200 characters; never return whole pages.
- Annotations: `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false` (local data only).
- Error cases:
  - `paper_not_found`.
  - `no_text_layer`: scanned or image-only page. The design treats this as unverifiable and triggers the automatic failure rule (the app records it, not the agent).
  - `quote_too_short` / `quote_too_long`.
  - `page_out_of_range`.
- Rate limits: none (local). Still rate-limit at the server to avoid loops.
- Reuse decision: in-house. It depends on the app's stored page text. No external server provides this.

### 2.2 Research-cycle state (local, read and write)

**Tool: `research_cycle_create`**
- Purpose: create a research cycle with a snapshot of the approval policy and hard limits. Idempotent with a client key.
- Agent: `research-lead`.
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["topic", "client_request_id"],
  "properties": {
    "topic": {"type": "string", "minLength": 5, "maxLength": 500},
    "project_id": {"type": "string"},
    "policy_profile": {"type": "string", "enum": ["careful", "balanced", "auto"], "default": "balanced"},
    "client_request_id": {"type": "string", "format": "uuid"},
    "limits": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "max_searches": {"type": "integer", "minimum": 1, "maximum": 200},
        "max_reback_per_hypothesis": {"type": "integer", "minimum": 0, "maximum": 2},
        "max_reback_total": {"type": "integer", "minimum": 0, "maximum": 10},
        "max_minutes": {"type": "integer", "minimum": 5, "maximum": 480}
      }
    }
  }
}
```
- Output shape: `cycle_id`, `stage` (`plan`), `policy_snapshot` (profile, gate table, hash), `limits` (after clamping to server maxima), `created_at`, `reused` (bool, true when the key matched an earlier call with the same payload).
- Annotations: `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: true` (because of `client_request_id`), `openWorldHint: false`.
- Error cases:
  - `idempotency_conflict`: same key, different payload. Return the existing `cycle_id` and a fix message.
  - `policy_invalid`.
  - `consent_required`: the cycle cannot start until the user has recorded consent for sending library content and queries to external services (policy row in Part 2.5).
- Limits: the server clamps each limit to its maximum and reports the clamped value. Agents cannot raise limits.

**Tool: `research_cycle_get`**
- Purpose: read cycle state, gate status, counters, and events after a sequence number.
- Agent: `research-lead` (all), `verifier` (read only, the cycle's evidence list), `lesson-curator`.
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["cycle_id"],
  "properties": {
    "cycle_id": {"type": "string"},
    "after_seq": {"type": "integer", "minimum": 0, "default": 0},
    "events_limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
    "include": {"type": "array", "items": {"type": "string", "enum": ["hypotheses", "rejections", "open_approvals"]}}
  }
}
```
- Output shape: `cycle_id`, `stage`, `counters` (`searches_used`, `reback_total`, `reback_by_hypothesis`), `limits`, `open_approvals[]`, `events[]` (`seq`, `ts`, `actor`, `type`, `ref_ids`, `summary` ≤300 characters), `next_after_seq`, `untrusted: true` when summaries contain agent or user text.
- Annotations: read-only, idempotent, local.
- Error cases: `cycle_not_found`; `after_seq_ahead` (greater than the latest sequence).

**Tool: `research_cycle_append_event`**
- Purpose: append a state transition or record (verdict, search run, reback, human note). The server validates allowed transitions and caps.
- Agent: all research agents, each with its own allowed event types (see Part 3, item 3).
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["cycle_id", "expected_seq", "type", "actor"],
  "properties": {
    "cycle_id": {"type": "string"},
    "expected_seq": {"type": "integer", "minimum": 0, "description": "Optimistic concurrency: the latest seq the caller has seen."},
    "type": {"type": "string", "enum": ["stage_advanced", "search_run", "candidate_added", "hypothesis_added", "verdict", "reback", "gate_requested", "gate_resolved", "note"]},
    "actor": {"type": "string", "enum": ["research-lead", "literature-scout", "paper-analyst", "hypothesis-builder", "verifier", "citation-checker", "lesson-curator", "user"]},
    "payload": {"type": "object", "description": "Type-specific fields. Max 8 KB serialized."},
    "ref_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 50}
  }
}
```
- Output shape: `seq`, `accepted` (true), `stage`, `counters`.
- Annotations: `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: false`, `openWorldHint: false`.
- Error cases:
  - `seq_conflict` (expected_seq is stale): return the latest `seq`; retryable after re-reading.
  - `transition_not_allowed`: list allowed next types.
  - `reback_cap_reached`: fix message says to ask the user (escalation, not a silent failure).
  - `verdict_without_evidence`: a verdict needs `ref_ids` pointing to evidence or a quote check.
  - `payload_too_large`.
- Rules enforced in code: `verdict` only from `verifier` or the server's automatic checks; `reback` requires a `rejection` reference; cap checks against `limits`.

### 2.3 Failure ledger (local)

**Tool: `failure_ledger_read`**
- Purpose: read rejected directions and reasons before generating hypotheses. The design requires `hypothesis-builder` to read it before generating.
- Agent: `hypothesis-builder` (mandatory), `verifier`, `lesson-curator`.
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "reason_code": {"type": "string", "enum": ["no_evidence", "quote_mismatch", "not_novel", "prior_work_overlap", "infeasible", "ill_posed", "duplicate_direction", "other"]},
    "topic_tags": {"type": "array", "items": {"type": "string", "maxLength": 40}, "maxItems": 10},
    "status": {"type": "string", "enum": ["active", "expired", "released"], "default": "active"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
    "cursor": {"type": "string"},
    "response_format": {"type": "string", "enum": ["concise", "detailed"], "default": "concise"}
  }
}
```
- Output shape: `items[]` (`id`, `reason_code`, `summary` ≤300 characters, `hypothesis_ref`, `evidence_refs[]`, `created_at`, `expires_at`, `user_released`), `next_cursor`, `total_active`, `untrusted: true`.
- Annotations: read-only, idempotent, local.
- Error cases: `invalid_reason_code`; `cursor_invalid` (-32602 per spec).
- Note: the output may be large over time. The design needs a cap on active entries (or summaries with tags). Concise by default.

**Tool: `failure_ledger_append`**
- Purpose: append-only record of a rejection with reason and evidence. Automatic rejections (quote mismatch, missing evidence) are written by the server itself, not by the agent.
- Agent: `verifier`. Automatic writes from `citation-checker` results.
- Input schema (sketch):
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["cycle_id", "hypothesis_ref", "reason_code", "summary"],
  "properties": {
    "cycle_id": {"type": "string"},
    "hypothesis_ref": {"type": "string"},
    "reason_code": {"type": "string", "enum": ["no_evidence", "quote_mismatch", "not_novel", "prior_work_overlap", "infeasible", "ill_posed", "duplicate_direction", "other"]},
    "summary": {"type": "string", "minLength": 10, "maxLength": 300},
    "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
    "expires_in_days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 180}
  }
}
```
- Output shape: `id`, `created_at`, `expires_at`, `duplicate_of` (set when the same hypothesis and reason already exist).
- Annotations: `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: true` (duplicate detection), `openWorldHint: false`.
- Error cases: `evidence_required` for every reason except `other` with no evidence; `hypothesis_not_found`; `summary_too_short`.
- Rules: no update or delete tool. Release (`user_released`) is available only in the app UI.

### 2.4 Lessons (local)

**Tool: `lessons_read`**
- Purpose: read the active lesson list that the next cycle's `hypothesis-builder` and `verifier` consume.
- Agent: `hypothesis-builder`, `verifier`, `lesson-curator`.
- Input schema (sketch): `applies_to` (enum `hypothesis`, `verification`, `search`), `status` (default `active`), `limit` (≤30), `cursor`, `response_format`.
- Output shape: `items[]` (`id`, `pattern` ≤300 characters, `applies_to`, `evidence_refs[]`, `created_at`, `usage_count`), `active_count`, `active_cap`, `next_cursor`, `untrusted: true`.
- Annotations: read-only, idempotent, local.
- Error cases: `invalid_applies_to`.

**Tool: `lessons_append`**
- Purpose: add one lesson per call. Only `lesson-curator` may call it. Append-only.
- Input schema (sketch): `cycle_id`, `pattern` (10 to 300 characters), `applies_to` (enum), `evidence_refs` (1 to 20), `source_seqs` (integer array, up to 50).
- Output shape: `id`, `active_count`, `active_cap`.
- Annotations: `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: false`, `openWorldHint: false`.
- Error cases: `cap_reached` (ask the user to prune; never auto-delete); `evidence_required`; `pattern_too_long`.
- Rule: lessons cannot change skills, prompts, evaluation sets, or policy. Those changes are proposals written elsewhere under the protected-area rules.

### 2.5 Policy and approval (local)

**Tool: `gate_policy_get`**
- Purpose: read the approval policy for a cycle (profile, per-gate setting, whether each gate can be turned off).
- Agent: `research-lead` only.
- Input schema: `profile` (optional enum) or `cycle_id`.
- Output shape: `profile`, `gates` (`stage` to `ask` / `auto` / `auto_report`), `locked_gates` (for example, the consent gate and the skill-change gate that cannot be turned off), `policy_hash`, `untrusted: false`.
- Annotations: read-only, idempotent, local. No write tool exists for policy. Only the user changes policy in the app.
- Error cases: `profile_not_found`.

**Tool: `approval_request`**
- Purpose: record a pending approval at a stage boundary. The lead must stop and ask the user in the app. It does not block the agent.
- Agent: `research-lead`.
- Input schema (sketch): `cycle_id`, `gate` (enum from the policy table), `summary` (≤1,500 characters), `options` (array, ≤4, each with `id` and `label`), `default_option`.
- Output shape: `request_id`, `status` (`pending`), `created_at`.
- Annotations: `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: false`, `openWorldHint: false`.
- Error cases: `gate_not_in_policy`; `gate_locked_to_ask` (never bypassed, even by the `auto` profile for locked gates); `duplicate_pending` (returns the existing request).

**Tool: `approval_status`**
- Purpose: check whether a pending approval was answered in the app.
- Agent: `research-lead`.
- Input: `request_id`. Output: `status` (`pending`, `approved`, `rejected`, `expired`), `option_id`, `resolved_at`.
- Annotations: read-only, idempotent, local.

### 2.6 Tools deliberately not proposed

- No tool to write policy, delete ledger rows, edit evaluation sets, change `.claude/` or `AGENTS.md`, or read credentials or the API key.
- No tool to download PDFs from open web sources or Sci-Hub. PDF import remains the user's job in the app.
- No Google Scholar tool.
- No MCP Tasks use (Part 3).

### 2.7 Reuse versus reimplementation summary

| Capability | Existing options | Recommendation |
|---|---|---|
| OpenAlex search and citation graph | cyanheads (Apache-2.0, 17 stars), oksure (community), ResearchMCP, Web Researcher | Reimplement inside the app. Borrow budget-header and cap logic from cyanheads with attribution if code is copied. Do not install third-party OpenAlex servers, because agents would bypass the app's budget, cache, and audit log. |
| Semantic Scholar | akapet00 (MIT), FujishigeTemma (MIT), openags | Reimplement later as a second source with one global limiter. Use the two READMEs only as endpoint-name references. |
| arXiv | openags (MIT, bundles many sources) | Reimplement a small Atom client with the 3-second rule and single connection. |
| Crossref | openags; Crossref REST directly | Reimplement with the user's polite-pool contact value. |
| Unpaywall | openags | Reimplement a DOI lookup (needs the user's email; consent required). |
| PubMed, Europe PMC | openags | Out of the current scope. Verify limits first. |
| Zotero import | kujenga (MIT, read-only tools), 54yyyu (MIT with AGPL plugin, write-capable) | Optional future import. If used, prefer kujenga's read-only pattern. Do not reuse 54yyyu. |
| Obsidian | several (S) | Out of scope now. |
| Citation snowballing loop | Liyux3 `build_paper_graph`, Web Researcher, ResearchMCP | Implement the one-hop tool plus lead-driven loop with caps (not a recursive server tool). |
| Quote verification | none found | In-house. |

---

## Part 3. Risks and open questions

**Blocking before implementation**

1. **MCP SDK version and API.** The task brief says `mcp` 1.27.x. The PyPI page fetched in this session shows 2.3.0 released Oct 2, 2026 [V]. Check the installed version in the project environment. Confirm whether `mcp.server.fastmcp.FastMCP` generates `outputSchema` from return annotations, and whether `ToolAnnotations` keyword names match this version. The gofastmcp docs (a different project) describe features that may not exist in the official SDK.
2. **Output-schema conformance on errors.** The spec says servers MUST return conforming structured results when `outputSchema` is declared. It is not explicit about `isError: true` results. Decide between (a) an error variant inside one schema with `ok: false`, or (b) no `outputSchema` on tools that can fail. Test the chosen approach against Claude Code.
3. **Actor identity for writes.** The MCP server cannot see which subagent called a tool. An `actor` field is self-reported and could be spoofed by any agent that has the tool. Options: (a) per-role inline `mcpServers` definitions in subagent frontmatter, each with its own environment token (inline definitions connect at subagent start, per the subagent docs [V]); (b) hook-based gating using `agent_type` from `PreToolUse` input [V] to block disallowed event types; or both. Recommend (a) plus (b).
4. **Subagent nesting depth.** Claude Code's default is 3 nested layers [V]. The design requires depth 1. Set `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in project settings, and check that only `research-lead` has `Agent` in its tools.
5. **OpenAlex cites and referenced_works filters.** Not confirmed from a primary OpenAlex page [U]. Check the Works API reference, and test the OR filter on `openalex_id` with a small query, before implementing `get_related`.
6. **OpenAlex polite pool and email.** The authentication page does not mention email or the polite pool [V]. A search snippet says email is no longer used [S]. The cyanheads server reads `OPENALEX_MAILTO` [V]. Verify before designing a contact field.
7. **Semantic Scholar unauthenticated limits conflict.** Official product page: 1000 requests per second shared among unauthenticated users [V]. akapet00 README: 5,000 per 5 minutes [V]. FujishigeTemma README: 100 per 5 minutes [V]. Resolve against the official API documentation. The design assumes a key and 1 request per second, which is safe under all sources.
8. **Crossref polite-pool concurrency conflict.** Blog table: 3 [V]. Community forum: 5 [S]. Use the runtime `x-concurrency-limit` header.
9. **Unpaywall figures unverified.** The 100,000 per day figure is from a search summary of Unpaywall's documentation [S]. Confirm on the primary page (fetch returned only the title).
10. **NCBI and Europe PMC.** NCBI figures are from snippets [S]. The official page returned a browser check [U]. Europe PMC returned HTTP 403 [U]. Not in the current scope.
11. **Claude Code MCP permission syntax.** The `mcp__server__tool` rule syntax was not in the returned text [U]. Use hooks (confirmed) and subagent `tools` allowlists (confirmed) rather than permission rules until checked.
12. **MRTR in Claude Code.** The spec defines MRTR [V]. Claude Code client support was not verified [U]. Do not use it for approvals.
13. **MCP Tasks.** An open Claude Code issue for Tasks support was seen in search results [S]. Keep tool calls short (seconds) and split long snowballs across calls.

**Design risks**

14. **Privacy and external transmission.** Every `search_literature` and `get_related` call sends query text to OpenAlex, and Crossref or Unpaywall would send DOIs and the user's contact value. The repository invariants require explicit user request and a preview of what will be sent. Propose: the cycle-start consent screen lists the query-generation rule (no verbatim library text, maximum query length, no quotes longer than N words) and the list of external services. The app logs every external call. Add a server-side check that rejects queries containing long verbatim spans from stored PDF text (Part 3 item 17 is the detection approach).
15. **Prompt injection through papers.** Titles, abstracts, and quotes are attacker-controllable content. Mitigations: `untrusted` markers, length caps, no free-text fields in tool names or enum values, and verifier reasoning that never follows instructions in returned text. Evaluate with a test set of papers whose abstracts contain instructions.
16. **Budget mismatch.** Derived capacity: about 1,000 keyword searches per day on a free key at $0.001 each (published prices) [derived]. First-dollar pacing for new accounts (up to $0.10 every 5 minutes) [V] slows the first day. The app must show this in the cycle start screen.
17. **Verbatim-leak detection.** Verifying that a query does not contain long quotes from library text needs an n-gram check against stored page text. Not designed here. Proposal for a later milestone.
18. **Output size.** Claude Code's default cap is 25,000 tokens [V]. Set the app's own hard cap at 40,000 characters and test typical results with real papers.
19. **Tool count and naming.** About 17 new tools across six groups. Anthropic recommends narrow, namespaced tools [V]. Scoped `tools` allowlists keep each subagent small. Decide whether to keep the design names (`search_literature`, `get_related`, `verify_quote`) with the `easyresearch` prefix Claude Code adds, or add resource prefixes (`lit_`, `cycle_`, `ledger_`, `lessons_`, `policy_`, `approval_`). Existing tool names should not change.
20. **Hook fail-open.** A failed `PreToolUse` hook does not block by default [V]. Set `"onFailure": "block"` (Claude Code v2.1.295 or later [V]). Check the installed Claude Code version before relying on it.
21. **Headless approvals.** Project-scoped `.mcp.json` servers load in `claude -p` without prompting [V]. The design's approval gates live in the app, but a headless run could still call write tools. Mitigate with `--strict-mcp-config` and allowlists, and by refusing writes outside an active cycle in the server.
22. **Google Scholar.** Terms (secondary [S]) bar automated access without permission. Do not build a scraper or a connector to it.
23. **License and attribution.** Apache-2.0 (cyanheads), MIT (most others), AGPL (54yyyu plugin). Borrowing code requires attribution (Apache-2.0, MIT) and avoiding the AGPL plugin entirely.
24. **OpenAlex data terms.** Not verified in this session. Check OpenAlex's license for stored metadata and abstracts before caching them long term [U].
25. **Stars and maintenance.** Star counts are small for most candidates (10 to 38), and last-commit dates were not shown. Maintenance was not verified. Another reason to reimplement small clients.

**Open questions for the user or lead**

- Which OpenAlex key policy: key stored in the app (recommended), or none (keyless only, 10 requests per second, smaller budget)?
- Should the polite-pool contact (for Crossref and Unpaywall) be the user's email, a generic app identifier, or omitted?
- Are `reason_code` values and the eight-value list in the ledger the final set?
- Does the consent screen at cycle start also cover OpenAlex queries, or only library content?
- Should `search_literature` cover Semantic Scholar in v1, or wait for v2?

---

## Part 4. URL index

Tags as in the legend. Entries marked [U] could not be read as primary pages.

| # | URL | Tag |
|---|---|---|
| 1 | https://www.anthropic.com/engineering/writing-tools-for-agents | V |
| 2 | https://modelcontextprotocol.io/specification/2026-07-28/server/tools | V |
| 3 | https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination | V |
| 4 | https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr | V |
| 5 | https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices | V |
| 6 | https://code.claude.com/docs/en/mcp | V (partial) |
| 7 | https://code.claude.com/docs/en/permissions | V (partial) |
| 8 | https://code.claude.com/docs/en/sub-agents | V |
| 9 | https://code.claude.com/docs/en/hooks | V |
| 10 | https://github.com/modelcontextprotocol/python-sdk | V (conflicting) |
| 11 | https://pypi.org/project/mcp/ | V |
| 12 | https://gofastmcp.com/servers/tools | V (different project) |
| 13 | https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/ | S |
| 14 | https://tasks.extensions.modelcontextprotocol.io/ | U |
| 15 | https://claudeissues.com/issue/102347-feature-support-the-mcp-tasks-extension-io-modelcontextprotocol-tasks-spec-2026 | S |
| 16 | https://help.openalex.org/api-reference/authentication | V |
| 17 | https://help.openalex.org/access/pricing/ | V |
| 18 | https://help.openalex.org/access/example-costs/ | V |
| 19 | https://help.openalex.org/api-entities/works/get-lists-of-works | V |
| 20 | https://help.openalex.org/api-entities/works/filter-works | V (partial) |
| 21 | https://github.com/cyanheads/openalex-mcp-server | V |
| 22 | https://glama.ai/mcp/servers/e5dpkjuo7r | S |
| 23 | https://glama.ai/mcp/servers/oksure/openalex-research-mcp | S |
| 24 | https://github.com/dominikusbrian/openalex-mcp-server | S |
| 25 | https://www.semanticscholar.org/product/api | V |
| 26 | https://api.semanticscholar.org/api-docs/ | V (navigation only) |
| 27 | https://api.semanticscholar.org/api-docs/graph | U (not opened) |
| 28 | https://github.com/akapet00/semantic-scholar-mcp | V |
| 29 | https://github.com/FujishigeTemma/semantic-scholar-mcp | V |
| 30 | https://awesome.ecosyste.ms/projects/github.com%2FSnippetSquid%2FSemanticScholarMCP | S |
| 31 | https://info.arxiv.org/help/api/tou.html | V |
| 32 | https://info.arxiv.org/help/api/user-manual.html | V |
| 33 | https://crossref.org/blog/announcing-changes-to-rest-api-rate-limits/ | V |
| 34 | https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/ | V (partial) |
| 35 | https://community.crossref.org/t/rest-api-pools-which-to-use-and-when/15317 | S |
| 36 | https://unpaywall.org/api/v2 | S (fetch failed) |
| 37 | https://support.nlm.nih.gov/knowledgebase/article/KA-05318/en-us | S |
| 38 | https://www.ncbi.nlm.nih.gov/books/NBK25497/ | U |
| 39 | https://europepmc.org/RestfulWebService | U (HTTP 403) |
| 40 | https://github.com/openags/paper-search-mcp | V |
| 41 | https://github.com/kujenga/zotero-mcp | V |
| 42 | https://github.com/54yyyu/zotero-mcp | V |
| 43 | https://glama.ai/mcp/servers/Liyux3/scholar-mcp/tools/build_paper_graph | S |
| 44 | https://glama.ai/mcp/servers/zoharbabin/web-researcher-mcp/tools/citation_graph | S |
| 45 | https://glama.ai/mcp/servers/DaniManas/ResearchMCP/tools/get_citations | S |
| 46 | https://scite.ai/blog/citation-surfing-scite-mcp | S |
| 47 | https://glama.ai/mcp/servers/faisalhossainnyc/obsidian-mcp-server | S |
| 48 | https://mcpservers.org/tr/servers/cyanheads/obsidian-mcp-server | S |
| 49 | https://www.casrai.org/dictionary/term/google-scholar-api | S |
| 50 | https://conductatlas.com/platform/google/google-terms-of-service/prohibited-conduct-automated-access-and-ai-training-restrictions/ | S |
| 51 | https://eseospace.com/blog/mcp-structured-tool-output/ | S |
| 52 | https://dev.to/gustavo_gated/the-2026-07-28-mcp-spec-a-server-readiness-checklist-14nf | S |
| 53 | https://khavel.substack.com/p/mcp-outputschema-y-structuredcontent | S |
| 54 | https://github.com/cktbarking (listing only; URL not captured) | S |
| 55 | https://glama.ai/mcp/servers/kujenga/zotero-mcp (listing) | S |

Count: 55 indexed sources (about 33 [V], the rest [S] or [U]).

---

## Notes on method

- Search queries used: OpenAlex MCP servers; Semantic Scholar MCP `search_papers`; paper-search-mcp; Zotero MCP; MCP 2026-07-28 tool schema; Anthropic tool-writing article; Google Scholar terms; Unpaywall limits; NCBI E-utilities limits; Obsidian MCP; Crossref polite pool; citation-graph MCP tools; MCP tasks extension.
- Pages that failed or were truncated are listed as [U] and are not used as the basis for any number in Part 2 without a flag.
- No file other than this one was written. No git commands were run. No private library content or API keys were sent in any request. Search queries contained only generic public terms.
