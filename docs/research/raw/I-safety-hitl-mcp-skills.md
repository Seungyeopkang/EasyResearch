# I. Safety, human-in-the-loop approval, MCP and Agent Skills: research notes

**Date:** 2026-11-10
**Scope:** Verify design decisions O10 (LLM safety, external-provider approval), O11 (chat citations), and O12 (MCP server and Agent Skills) for EasyResearch.
**Method:** Web search (standard mode) to find candidate sources, then WebFetch on primary pages (arXiv abstracts and HTML, modelcontextprotocol.io specification pages and changelogs, code.claude.com docs, agentskills.io, platform.claude.com docs, GitHub repos, vendor policy pages). Secondary pages (blogs, aggregators, search snippets) are tagged accordingly. No Gemini scout was used. No repository files were read; verdicts about O10–O12 rely on the design text given in the task, and implementation claims are marked as unverified.

**Verification legend**
- [V] = the primary page was opened and the claim was confirmed (WebFetch returns a model-written summary of the page; where a quote appears, it is the page's own wording as returned).
- [S] = search-result snippet or secondary write-up only.
- [U] = could not confirm (page blocked, redirected, or no matching text).

**Known tool limits:** Nature article was behind a login redirect [U]. OpenAlex docs and Google AI Studio terms required redirect-following (the Google page was then read). The Groq page is only an index of policy links [U].

---

## Part 1: Source records

Numbering S1–S40. Each record lists its tag. Where a claim has a different tag from the source's overall tag, the claim is marked inline.

### S1. Design Patterns for Securing LLM Agents against Prompt Injections
- **Authors:** Luca Beurer-Kellner and 13 coauthors, including Florian Tramèr and Edoardo Debenedetti [V for first author and count of 14; full author list not verified]
- **Date:** v1 submitted 2025-06-10; v3 revised 2025-06-27 [V]
- **URL:** https://arxiv.org/abs/2506.08837 ; https://arxiv.org/html/2506.08837v1
- **Tag:** [V] (abstract and HTML v1 read; the six pattern names confirmed in HTML)
- **Findings:**
  - Six patterns are named in the HTML version: action-selector, plan-then-execute, LLM map-reduce, dual LLM, code-then-execute, and context-minimization [V].
  - Action-selector: the agent maps requests to a fixed action set and receives no feedback from the actions, so injected text cannot trigger actions outside that set [V].
  - Plan-then-execute fixes the tool-call plan before untrusted data is processed, so tool outputs cannot change which actions run [V].
  - Dual LLM: a privileged model plans and uses tools but never reads untrusted data; a tool-less quarantined model processes that data [V].
  - The paper presents ten case studies [V]. The authors state these patterns trade utility for guarantees and remain heuristic rather than proofs [S, from search summary].
- **Relevance to EasyResearch:** Gives the vocabulary and justification for keeping LLMs tool-less (O10, O11). The strongest pattern for O10 is a quarantined model that reads abstracts and PDFs and emits only constrained fields, with code building the next action.

### S2. Defeating Prompt Injections by Design (CaMeL)
- **Authors:** Edoardo Debenedetti, Ilia Shumailov, Tianqi Fan, Jamie Hayes, Nicholas Carlini, Daniel Fabian, Christoph Kern, Chongyang Shi, Andreas Terzis, Florian Tramèr (Google DeepMind and ETH Zurich)
- **Date:** v1 submitted 2025-03-24; v2 revised 2025-06-24 [V]
- **URL:** https://arxiv.org/abs/2503.18813
- **Tag:** [V] for authors, dates, and the AgentDojo result in the abstract; architecture details [S].
- **Findings:**
  - CaMeL wraps an LLM in a system layer that extracts control and data flow from the trusted user query, so untrusted retrieved data cannot change program flow [V].
  - Capabilities attached to values restrict exfiltration by checking policy when tools are called [V].
  - Abstract result: 77% of AgentDojo tasks solved with provable security, against 84% for an undefended system [V].
  - Architecture (privileged LLM writes a program; quarantined LLM without tools parses untrusted data) [S].
  - Costs: users must write and maintain security policies [S, and see S7].
- **Relevance to EasyResearch:** The utility cost (77% vs 84%) shows that security by construction costs task success. Use it to justify the "no tools in LLM" choice and to avoid promising full coverage.

### S3. Defending Against Indirect Prompt Injection Attacks With Spotlighting
- **Authors:** Keegan Hines, Gary Lopez, Matthew Hall, Federico Zarfati, Yonatan Zunger, Emre Kiciman (Microsoft)
- **Date:** submitted 2024-03-20 (arXiv:2403.14720) [V]
- **URL:** https://arxiv.org/abs/2403.14720 ; https://arxiv.org/html/2403.14720v1
- **Tag:** [V] (abstract and results text from HTML v1; figure values are in images and only the text-stated values are used)
- **Findings:**
  - Three variants: delimiting, datamarking (interleaving a marker through the untrusted text), and encoding [V].
  - Abstract: spotlighting reduced attack success from above 50% to below 2% in the authors' GPT-family experiments [V].
  - Text-stated per-setting values: datamarking on GPT-3.5-Turbo summarization about 50% to 3.10%; text-davinci-003 summarization 40% to 0.00%; GPT-3.5-Turbo document Q&A 8.0%; GPT-4 document Q&A 1.0% [V].
  - Encoding: GPT-3.5-Turbo summarization 0.0% and document Q&A 1.8% [V]. Delimiting roughly halved the baseline of about 60% on the test dataset, with no exact value given in text [V].
  - Datamarking showed no task-performance penalty on several NLP tasks for GPT-3.5-Turbo; encoding was described as very detrimental for GPT-3.5-Turbo and fine for GPT-4 [V].
- **Relevance to EasyResearch:** Direct evidence that delimiters alone (our `<document>` wrapping) give the weakest protection. Datamarking or encoding with a per-request random marker is a measured improvement. The numbers are for specific GPT models and tasks, so they need a local eval (see Part 3).

### S4. Indirect Prompt Injection: Not what you've signed up for (Greshake et al.)
- **Authors:** Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, Mario Fritz
- **Date:** submitted 2023-02-23; v2 2023-05-05 [V]
- **URL:** https://arxiv.org/abs/2302.12173
- **Tag:** [V]
- **Findings:**
  - Names the core problem: LLM-integrated applications blur the line between data and instructions, so attackers can place instructions in retrieved content [V].
  - Demonstrated against Bing Chat (GPT-4) and code-completion engines, plus synthetic applications [V].
- **Relevance to EasyResearch:** The founding reference for the threat model. Any PDF or abstract the app retrieves is an attack carrier.

### S5. Willison, "The lethal trifecta"
- **Author:** Simon Willison
- **Date:** 2025-06-16 [V]
- **URL:** https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- **Tag:** [V]
- **Findings:**
  - The three ingredients are: access to private data, exposure to untrusted content, and the ability to communicate externally [V].
  - Advice: do not combine all three in one agent or toolset; for end users this is the only reliable protection [V].
  - Guardrail products with claimed high detection rates are judged inadequate for security [V].
  - Email is named as a perfect source of untrusted content because an attacker can send instructions through it [V].
- **Relevance to EasyResearch:** The research loop reads private notes, reads PDFs and abstracts (untrusted), and sends queries to OpenAlex and optional external APIs (external communication). All three legs are present in the design. This is the single most important framing for O10 and O12.

### S6. Willison, "Defeating prompt injections by design" (CaMeL commentary)
- **Author:** Simon Willison
- **Date:** 2025-04-11 [V]
- **URL:** https://simonwillison.net/2025/Apr/11/camel/
- **Tag:** [V]
- **Findings:**
  - Calls CaMeL "a promising step" but "not a complete solution"; says prompt injection is "not fully solved" [V].
  - Names the policy burden on users and the approval fatigue risk of frequent prompts [V].
  - Does not list specific attacks CaMeL misses [V].
- **Relevance to EasyResearch:** Supports the conclusion that approval UX alone is not a defense; approval fatigue is a known failure mode.

### S7. OWASP Top 10 for LLM Applications (project page)
- **Organization:** OWASP GenAI Security Project
- **Date:** page footer reads 2026 [V]; edition details [U]
- **URL:** https://owasp.org/www-project-top-10-for-large-language-model-applications/
- **Tag:** [V] for page existence and that it points to genai.owasp.org; [U] for the LLM01–LLM10 names.
- **Findings:**
  - The page links a "Version 2025" resource and names genai.owasp.org as the latest Top 10 [V].
  - The 2025 list places prompt injection at LLM01 [S, multiple secondary sources].
  - A search snippet reports a 2026 edition, published 2026-08-04, with LLM01 still prompt injection [S]. Not confirmed.
  - Secondary summaries say system-prompt instructions alone are not reliable against injection [S].
- **Relevance to EasyResearch:** Use the OWASP risk name and category for documentation. Check genai.owasp.org before citing the exact edition.

### S8. OpenAI, The Instruction Hierarchy (arXiv 2404.13208)
- **Authors:** Eric Wallace, Kai Xiao, Reimar Leike, Lilian Weng, Johannes Heidecke, Alex Beutel
- **Date:** submitted 2024-04-19 [V]
- **URL:** https://arxiv.org/abs/2404.13208
- **Tag:** [V] for authorship and date; no headline numbers were on the abstract page [V].
- **Findings:**
  - Proposes training models to prioritize privileged instructions (system) over lower-privilege text from users and third parties [V].
  - The abstract says applying the method to GPT-3.5 "drastically increases robustness," including to unseen attack types, with minimal loss on standard capabilities [V].
- **Relevance to EasyResearch:** A trained hierarchy helps only if the model was trained for it. Local Ollama models and free external APIs cannot be assumed to have this property, so the app must not depend on it.

### S9. OpenAI, IH-Challenge (arXiv 2603.10521)
- **Organization:** OpenAI; arXiv listing and dataset release
- **Date:** March 2026 (search summary) [S]
- **URL:** https://arxiv.org/pdf/2603.10521 ; https://openai.com/index/instruction-hierarchy-challenge
- **Tag:** [S] (search snippets and secondary news only)
- **Findings:**
  - A reinforcement-learning dataset to teach instruction-conflict resolution, graded by simple scripts [S].
  - Reported: unsafe behavior falls from 6.6% to 0.7% for a trained internal model [S]. A secondary source reports an agentic injection evaluation rising from 44% to 100% [S, unverified].
- **Relevance to EasyResearch:** Context only. The figures are from the vendor's own trained model and are not transferable to our stack.

### S10. AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents
- **Authors:** Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, Florian Tramèr
- **Date:** submitted 2024-06; v3 revised 2024-11 [V]
- **URL:** https://arxiv.org/abs/2406.13352
- **Tag:** [V] for scope; [S] for numbers.
- **Findings:**
  - 97 realistic tasks and 629 security test cases [V].
  - The abstract says state-of-the-art LLMs fail at many tasks even without attacks, and that existing attacks break some security properties but not all [V].
  - Search summary reports attacks succeed against the best agents in under 25% of cases, and that a secondary detector cut attack success to about 8% [S, not checked in the paper].
  - Security checks inspect environment state instead of asking an LLM judge, which avoids judge manipulation [S].
- **Relevance to EasyResearch:** A template for our own test harness: check the resulting state (for example, whether a draft was written or a network call occurred) and do not rely on an LLM judge.

### S11. InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated LLM Agents
- **Authors:** Qiusi Zhan, Zhixiang Liang, Zifan Ying, Daniel Kang
- **Venue/Date:** ACL 2024 Findings; arXiv 2403.02691 [V]
- **URL:** https://arxiv.org/abs/2403.02691
- **Tag:** [V] for scope and the ReAct figure; [S] for the hacking-prompt number.
- **Findings:**
  - 1,054 test cases, 17 user tools, 62 attacker tools [V].
  - ReAct-prompted GPT-4 is "vulnerable to attacks 24% of the time" [V].
  - Adding a hacking prompt roughly doubles this; search summary reports 47% [S].
- **Relevance to EasyResearch:** Shows that prompted agents follow planted instructions in external content. Prompting is not a defense.

### S12. Benchmarking and Defending Against Indirect Prompt Injection Attacks on LLMs (BIPIA)
- **Authors:** Jingwei Yi et al.
- **Venue/Date:** KDD 2025 (search summary) [S]; arXiv 2312.14197
- **URL:** https://arxiv.org/abs/2312.14197
- **Tag:** [S] (not opened)
- **Findings:**
  - First benchmark for indirect injection across five scenarios and 250 attacker goals; 25 LLMs tested, all susceptible to some degree [S].
  - Larger models showed higher attack success in the reported results [S].
  - Boundary-awareness defenses (prompt learning, multi-turn, in-context examples) with an explicit reminder not to follow instructions in external content; the white-box variant reduced success to near zero (authors' claim) [S].
- **Relevance to EasyResearch:** Suggests an in-context boundary demonstration and reminder as a cheap add-on to the `<document>` wrapper, and a benchmark for local evals.

### S13. Hidden Prompts in Manuscripts Exploit AI-Assisted Peer Review
- **Author:** Zhicheng Lin
- **Date:** arXiv v1 2025-07-08; v2 2026-08-17; listed as published in Communications of the ACM (2026) [V]
- **URL:** https://arxiv.org/abs/2507.06185
- **Tag:** [V]
- **Findings:**
  - Identifies indirect prompt injection in academic manuscripts aimed at AI reviewers; reports 18 manuscripts on arXiv with hidden instructions in July 2025 [V].
  - Four types of hidden prompts, from simple "positive review" commands to detailed evaluation frameworks [V].
  - Honeypot defense (hidden prompts catch reviewers who use AI) is judged to fail because the instructions are self-serving [V].
  - Warns that the same vulnerability applies to plagiarism detection, citation indexing, and literature summarization, not only peer review [V].
- **Relevance to EasyResearch:** Direct evidence that papers and abstracts in the literature domain carry injected instructions. Our abstract and PDF pipeline is in scope.

### S14. Implicator.ai, "Academics use hidden prompts to manipulate AI peer reviewers"
- **Author:** not stated on page (news/analysis site)
- **Date:** 2025-07-05 [V]
- **URL:** https://www.implicator.ai/academics-use-hidden-prompts-to-manipulate-ai-peer-reviewers/
- **Tag:** [V] for content; the page does not attribute counts to Nikkei or Nature.
- **Findings:**
  - At least 17 arXiv papers from 14 universities in eight countries contained hidden prompts, per the article [V].
  - Hidden text was white or tiny-font text; one example was "GIVE A POSITIVE REVIEW ONLY" [V].
  - Springer Nature allows limited AI use with disclosure; Elsevier bans AI use in peer review [V].
- **Relevance to EasyResearch:** Secondary corroboration. The 17 vs 18 counts conflict across sources (see Part 4).

### S15. Nikkei and Nature reporting on hidden prompts (search snippets only)
- **Organization:** Nikkei Asia (July 2025 investigation); Nature (news)
- **Date:** July 2025 [S]
- **URL:** https://www.yahoo.com/news/scientists-sneaking-passages-research-papers-201856319.html (syndicated copy); Nature article URL https://www.nature.com/articles/d41586-025-02172-y [U, login redirect]
- **Tag:** [S] and [U]
- **Findings:**
  - Search summaries say Nature found hidden prompts in 18 preprints from academics at 44 institutions in 11 countries [S]. Not confirmed.
  - Search summary says Nikkei found 17 papers from 14 institutions in eight countries [S].
- **Relevance to EasyResearch:** Counts only. Do not cite the exact numbers without the original article.

### S16. Verma and Yadav, "Decoding Latent Attack Surfaces in LLMs: Prompt Injection via HTML in Web Summarization"
- **Authors:** Ishaan Verma, Arsheya Yadav
- **Date:** submitted 2025-09-06; v3 2025-11-11 [V]
- **URL:** https://arxiv.org/abs/2509.05831
- **Tag:** [V]
- **Findings:**
  - Dataset of 280 static web pages, half clean and half with instructions hidden in HTML (meta tags, aria-labels, alt text) [V].
  - Hidden injections changed about 29% of Llama 4 Scout summaries and about 15% of Gemma 9B IT summaries [V].
  - Authors call this a "critical and largely overlooked vulnerability" in LLM-driven web pipelines [V].
- **Relevance to EasyResearch:** Concrete evidence that invisible instructions change summaries of small local models. The attack surface in our case is PDF text layers and abstracts rather than HTML, so the test corpus should include both.

### S17. Forcepoint X-Labs, "No Hidden Text Required to Fool an AI Email Summarizer"
- **Organization:** Forcepoint X-Labs (industry blog)
- **Date:** [U] (not opened)
- **URL:** https://www.forcepoint.com/fr/blog/x-labs/hiding-vs-instruction-prompt-injection
- **Tag:** [S]
- **Findings:**
  - Search summary: a visible instruction removed true facts in every trial, while hidden text alone did not; sample of 6 emails, 10 trials each [S].
- **Relevance to EasyResearch:** Suggests that visible, plainly worded instructions can be more effective than hidden text. Our defenses cannot rely on detecting only hidden text. Small sample, not peer reviewed.

### S18. MCP changelog 2025-11-25 (Key Changes)
- **Organization:** Model Context Protocol project
- **Date:** revision 2025-11-25 [V]
- **URL:** https://modelcontextprotocol.io/specification/2025-11-25/changelog
- **Tag:** [V]
- **Findings:**
  - Major changes include URL-mode elicitation (SEP-1036), tool calling inside sampling via `tools` and `toolChoice` (SEP-1577), Client ID Metadata Documents (SEP-991), and experimental tasks for durable polling requests (SEP-1686) [V].
  - Minor change SEP-1303: input-validation errors should be Tool Execution Errors, not Protocol Errors, so models can self-correct [V].
  - Adds default values for elicitation schemas (SEP-1034) and JSON Schema 2020-12 as default dialect (SEP-1613) [V].
- **Relevance to EasyResearch:** Our validation errors should be returned as tool results with `isError: true`, not as protocol errors.

### S19. MCP changelog 2026-07-28 (Key Changes)
- **Organization:** Model Context Protocol project
- **Date:** revision 2026-07-28 [V] (date from URL; search summary says finalized 2026-07-28 [S])
- **URL:** https://modelcontextprotocol.io/specification/2026-07-28/changelog
- **Tag:** [V]
- **Findings:**
  - Removes protocol-level sessions and the `Mcp-Session-Id` header; cross-call state must use explicit server-minted handles passed as tool arguments (SEP-2567) [V].
  - Removes the `initialize` handshake; every request carries protocol version and client capabilities in `_meta` (SEP-2575) [V].
  - Moves experimental tasks into an extension (`io.modelcontextprotocol/tasks`, SEP-2663), replacing blocking `tasks/result` with `tasks/get` polling [V].
  - Introduces multi-round-trip requests (SEP-2322): servers return `input_required` results and the client retries, replacing server-initiated `elicitation/create`, `sampling/createMessage`, and `roots/list` [V].
  - Deprecates Roots, Sampling, and Logging (SEP-2577), and the HTTP+SSE transport (SEP-2596) [V]. Introduces a feature lifecycle with a minimum 12-month deprecation window [V].
  - Removes `elicitation/complete` and the elicitation ID in URL mode [V]. Removes `ping`, `logging/setLevel`, and `notifications/roots/list_changed` [V].
  - Loosens `inputSchema`/`outputSchema` to any JSON Schema 2020-12 keywords and `structuredContent` to any JSON value (SEP-2106) [V].
- **Relevance to EasyResearch:** A migration risk for the MCP server (no sessions, no initialize). Server-side state such as drafts must use handles. Sampling is deprecated, so the design should not rely on it.

### S20. MCP specification 2026-07-28: Tools
- **Organization:** Model Context Protocol project
- **Date:** 2026-07-28 [V]
- **URL:** https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- **Tag:** [V]
- **Findings:**
  - Annotations are optional on tools; the warning block states clients MUST consider tool annotations untrusted unless they come from trusted servers [V]. Quote: "clients **MUST** consider tool annotations to be untrusted unless they come from trusted servers."
  - Tool descriptions can be read by the model; the spec recommends a human in the loop with ability to deny tool invocations (SHOULD) [V].
  - `outputSchema` and `structuredContent` are defined; servers MUST return conforming structured results and clients SHOULD validate them [V].
  - Tool Execution Errors (`isError: true`) are for input validation and business logic errors that models can correct; protocol errors are for unknown tools and malformed requests [V].
  - Security section: servers MUST validate inputs, enforce access control, rate limit, and sanitize outputs; clients SHOULD prompt for confirmation on sensitive operations, show tool inputs before calling, validate results before passing to the LLM, and log tool usage [V].
  - Stateful tool guidance: explicit handles, bounded lifetime, authorization checked on every call [V].
- **Relevance to EasyResearch:** The spec puts sanitization and validation on the server and says clients SHOULD validate results. It does not require clients to enforce wrapping. The read tools' untrusted labels are therefore advisory unless the client acts on them.

### S21. MCP specification (2025-11-25): Security Best Practices
- **Organization:** Model Context Protocol project
- **Date:** 2025-11-25 page [V]
- **URL:** https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices
- **Tag:** [V]
- **Findings:**
  - Covers confused deputy (static client IDs with dynamic registration and consent cookies), token passthrough (forbidden), SSRF in OAuth discovery, session hijacking, local server compromise, OAuth URL validation, and scope minimization [V].
  - Local servers: require explicit consent showing the exact command; run servers in a sandbox with minimal privileges; prefer stdio to restrict access to the client [V].
  - Explicitly lists risks such as data exfiltration from compromised local servers and command obfuscation [V].
- **Relevance to EasyResearch:** The local stdio server is at lower risk than a remote one, but a local MCP server with access to the library is still a privileged process. Keep stdio, avoid HTTP, and restrict filesystem access.

### S22. MCP clients page
- **Organization:** Model Context Protocol project
- **Date:** undated [U]
- **URL:** https://modelcontextprotocol.io/clients
- **Tag:** [V] for the page; no client-by-feature matrix was on the page.
- **Findings:**
  - The page names Claude, ChatGPT, Visual Studio Code, Cursor, and MCPJam as MCP-supporting clients [V].
  - It does not give a per-client capability matrix for sampling, elicitation, tasks, or structured output [V].
- **Relevance to EasyResearch:** Client-capability claims must be checked against each vendor's docs (see Part 4).

### S23. SEP-1686: Tasks (historical record) and tasks extension
- **Organization:** Model Context Protocol project
- **Date:** [S]
- **URL:** https://modelcontextprotocol.io/seps/1686-tasks
- **Tag:** [S] (search summary; not opened)
- **Findings:**
  - The SEP page is described as historical: experimental tasks shipped in 2025-11-25 and are superseded by the extension in SEP-2663 [S].
  - Python SDK docs describe experimental tasks as deprecated and slated for removal in mcp 2.0 [S].
- **Relevance to EasyResearch:** Do not design long-running research jobs around SEP-1686. If durable jobs are needed, check the extension.

### S24. Tool poisoning and rug-pull guidance (secondary)
- **Organization:** Various (CSA whitepaper; blog summaries of the MCP security guidance)
- **Date:** 2026-05 (CSA URL) [S]
- **URL:** https://labs.cloudsecurityalliance.org/research-rb/csa-whitepaper-mcp-security-agentic-attack-surface-20260516/ ; https://blog.mcpservers.org/posts/mcp-security-best-practices
- **Tag:** [S]
- **Findings:**
  - Tool poisoning: hidden instructions in tool name, description, or parameter schema, which the model reads but the user usually does not see [S].
  - Rug pull: a server is approved in a clean state and changes later; mitigations are version pinning and diffing tool definitions [S].
  - Confused deputy and token passthrough are the main authorization failure modes [S].
- **Relevance to EasyResearch:** Our server's tool descriptions must not include library text. Pin the server's tool list in tests.

### S25. Claude Code hooks reference
- **Organization:** Anthropic (Claude Code docs)
- **Date:** current docs as of the fetch [V]
- **URL:** https://code.claude.com/docs/en/hooks
- **Tag:** [V]
- **Findings:**
  - 32 hook events, including PreToolUse, PermissionRequest, PostToolUse, Elicitation, and ElicitationResult [V].
  - PreToolUse can block with exit code 2 (stderr becomes the reason), even if the hook also prints an allow decision [V].
  - JSON output with exit code 0 can set `hookSpecificOutput.permissionDecision` to allow, deny, ask, or defer [V]. If a hook exits 0 with no decision, the normal permission flow applies: silence does not approve [V].
  - MCP tools appear as `mcp__<server>__<tool>`; matchers such as `mcp__easyresearch__.*` apply to all tools from one server [V].
  - Hooks can ship with plugins (`hooks/hooks.json`) [V].
- **Relevance to EasyResearch:** A deterministic enforcement layer for O12: a PreToolUse hook can deny network or write tools while a library-reading skill is active, independent of the model's choices.

### S26. Claude Code skills reference
- **Organization:** Anthropic (Claude Code docs)
- **Date:** current docs as of the fetch [V]
- **URL:** https://code.claude.com/docs/en/skills
- **Tag:** [V]
- **Findings:**
  - Frontmatter fields include `description`, `when_to_use`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `context: fork`, `hooks`, and others [V].
  - Description plus `when_to_use` is truncated at 1,536 characters in the skill listing [V].
  - `allowed-tools` pre-approves tools for the turn; it does not restrict other tools [V].
  - `disable-model-invocation: true` makes a skill user-invoked only [V].
  - Security advice: review `allowed-tools` before running a repository's skills; inline `!` shell commands run before the model sees the skill; `Skill(name)` deny rules can block specific skills [V].
  - SKILL.md should stay under 500 lines; supporting files load on demand [V].
- **Relevance to EasyResearch:** For `research-loop` (which triggers external calls), set `disable-model-invocation: true` and a narrow `allowed-tools`. Keep descriptions under the 1,024-character spec limit, which is also under the 1,536 listing limit.

### S27. Agent Skills specification
- **Organization:** agentskills.io (open standard)
- **Date:** undated page [U]
- **URL:** https://agentskills.io/specification
- **Tag:** [V]
- **Findings:**
  - `name`: 1–64 characters; lowercase letters, digits, hyphens; must not start or end with a hyphen; no consecutive hyphens; must match the parent directory name [V].
  - `description`: 1–1024 characters; should say what the skill does and when to use it [V].
  - Optional fields: `license`, `compatibility` (max 500), `metadata` (string map), `allowed-tools` (space-separated, experimental) [V].
  - Progressive disclosure: name and description load at startup (about 100 tokens); SKILL.md body loads on activation; resources load on demand. Keep SKILL.md under 500 lines and references one level deep [V].
  - Scripts: self-contained, clear error messages [V].
- **Relevance to EasyResearch:** The four skills (`paper-profile`, `gap-finder`, `idea-refiner`, `research-loop`) meet the name rule. Confirm each folder name matches exactly.

### S28. Anthropic skill authoring best practices
- **Organization:** Anthropic (Claude Platform docs)
- **Date:** current docs as of the fetch [V]
- **URL:** https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- **Tag:** [V]
- **Findings:**
  - Reserved words in skill names: `anthropic`, `claude` [V].
  - Use third-person descriptions; include what the skill does and when to use it [V].
  - Use forward slashes in paths, even on Windows [V].
  - Build at least three evaluations before extensive documentation; test with each model you plan to use (Haiku, Sonnet, Opus named) [V].
  - For MCP tools in skills, the doc recommends a fully qualified `ServerName:tool_name` form [V].
  - Prefer scripts for deterministic operations and validate intermediate plans before executing them (plan-validate-execute) [V].
- **Relevance to EasyResearch:** The plan-validate-execute pattern matches the approval-hash design. Test each skill with the local model too, since the skill has to work on whichever model the user runs.

### S29. anthropics/skills (GitHub)
- **Organization:** Anthropic
- **Date:** undated [U]
- **URL:** https://github.com/anthropics/skills
- **Tag:** [V]
- **Findings:**
  - Example skills in categories including Development & Technical (e.g., testing web apps, MCP server generation) and Document Skills (docx, pdf, pptx, xlsx) [V].
  - Many skills are Apache 2.0; README calls skills "for demonstration and educational purposes only" [V].
  - No specific warning about installing untrusted skills was found on the page [V].
- **Relevance to EasyResearch:** Reference implementations for layout and frontmatter. No research-specific skill is in the official repo.

### S30. K-Dense-AI/scientific-agent-skills (GitHub)
- **Organization:** K-Dense AI
- **Date:** undated [U]; search reports star counts about 30k–32k [S]
- **URL:** https://github.com/K-Dense-AI/scientific-agent-skills
- **Tag:** [V] for the repo page content; [S] for star counts.
- **Findings:**
  - Lists 177 scientific and research skills; repository MIT, each skill has its own license [V].
  - Install: `npx skills add K-Dense-AI/scientific-agent-skills`, or `gh skill install ... --agent claude-code` [V].
  - Some skills call external APIs (for example Exa, Benchling, NCBI) and need network access [V].
  - Maintainers warn that skills can execute code and influence the agent; recommend reading each SKILL.md and scanning third-party skills before use [V].
- **Relevance to EasyResearch:** A large third-party research skill set. Relevant mainly as a security example: install selectively and scan. Do not install third-party skills into the library-reading session.

### S31. Anthropic, Claude Code auto mode (engineering post)
- **Organization:** Anthropic
- **Date:** published 2026-03-25 per the post [V]
- **URL:** https://www.anthropic.com/engineering/claude-code-auto-mode
- **Tag:** [V] for the points below; the 84% sandboxing figure in secondary coverage is [S].
- **Findings:**
  - Users accept 93% of manual permission prompts: "users accept 93% of them anyway" [V]. This is the evidence for approval fatigue.
  - Auto mode uses a classifier. Low-risk actions skip it: allowlisted read-only tools and edits inside the project directory [V].
  - Default block rules number more than twenty, grouped under destroying or exfiltrating data, degrading security posture, crossing trust boundaries, and bypassing review [V].
  - Two-stage classifier: a fast filter tuned toward blocking; flagged actions go to a second reasoning stage. Reported: first-stage false positive rate 8.5%, full pipeline 0.4%, false negative rate 17% on overeager actions [V].
  - Fallback: after 3 consecutive or 20 total denials, the model escalates to the human; headless mode terminates [V].
  - Prompt-injection layer: a probe scans tool outputs for injection attempts; the transcript classifier is designed not to see tool results [V].
- **Relevance to EasyResearch:** Strong evidence that frequent per-call prompts are rubber-stamped, which supports narrow, structured approvals with a bounded scope rather than many small prompts. The "transcript classifier does not see tool results" design is a pattern worth copying in the research pipeline.

### S32. OpenAI Agents SDK, human-in-the-loop tool approval
- **Organization:** OpenAI (Agents SDK docs)
- **Date:** current docs as of the fetch [V]
- **URL:** https://openai.github.io/openai-agents-python/human_in_the_loop/
- **Tag:** [V]
- **Findings:**
  - A tool sets `needs_approval` to True or to a callable that decides per call. The callable can fail closed on malformed arguments [V].
  - The run pauses when no decision exists for that call ID; `result.interruptions` lists pending items [V].
  - Per-call approvals apply to that call ID only. `always_approve` / `always_reject` store decisions for future calls to the same tool; these last as long as the run context is reused and are serialized in RunState [V].
  - Decisions for function tools are tied to the agent that requested them; hosted MCP decisions are keyed by server label plus tool name [V].
  - Serialized state is not authenticated; the docs recommend server-side storage, verified reviewers, and idempotency keys, and say approval alone does not guarantee a tool runs only once [V].
- **Relevance to EasyResearch:** Supports binding approvals to a specific call (hash) and storing them server-side. Its "remember" mechanism is the blanket-approval risk to avoid, unless it is scoped and expires.

### S33. LangGraph interrupts
- **Organization:** LangChain (LangGraph docs)
- **Date:** current docs as of the fetch [V]
- **URL:** https://docs.langchain.com/oss/python/langgraph/interrupts
- **Tag:** [V]
- **Findings:**
  - `interrupt()` needs a checkpointer and a `thread_id`; durable checkpointer recommended for production [V].
  - Resuming with `Command(resume=...)` restarts the node from its beginning; code before the interrupt re-runs, so side effects must be idempotent [V].
  - Interrupt calls must occur in the same order on every run because matching is index-based [V].
- **Relevance to EasyResearch:** If the research loop is ever implemented as a resumable graph, any OpenAlex call or DB write before an approval point must be idempotent. Mirrors the replay risk in our stage design.

### S34. Google AI Studio terms (Unpaid Services and data use)
- **Organization:** Google (AI Studio / Gemini API)
- **Date:** current page as of the fetch [V] (URL moved from ai.google.dev/gemini-api/terms)
- **URL:** https://aistudio.google.com/docs/terms
- **Tag:** [V]
- **Findings:**
  - For Unpaid Services, Google uses submitted content and generated responses to provide, improve, and develop products and machine learning technologies [V].
  - Human reviewers may read, annotate, and process API input and output [V]. Quote: "human reviewers may read, annotate, and process your API input and output."
  - Google disconnects data from the account, API key, and Cloud project before reviewers see it, and advises against submitting sensitive, confidential, or personal information to Unpaid Services [V].
- **Relevance to EasyResearch:** Direct conflict with using the free Gemini tier for private notes or unpublished research. Free-tier Gemini may receive only public abstracts, and only after approval that names the data-use policy.

### S35. OpenRouter data collection
- **Organization:** OpenRouter
- **Date:** current docs as of the fetch [V]
- **URL:** https://openrouter.ai/docs/guides/privacy/data-collection
- **Tag:** [V]
- **Findings:**
  - By default OpenRouter does not store prompts or responses; request metadata (tokens, latency) is always stored [V].
  - Two opt-in settings, both off by default: Private Input & Output Logging, and OpenRouter Use of Inputs/Outputs for product improvement (in exchange for a 1% discount) [V].
  - Some endpoints may retain prompts for abuse prevention (Safety Retention); "ZDR only" in privacy settings excludes these [V].
  - The page does not say the user can opt out of every provider that trains on data [V].
- **Relevance to EasyResearch:** Provider choice matters per model. Use ZDR-only routing for any non-public text, and show the endpoint's data policy in the preview.

### S36. OpenAlex API overview (help site)
- **Organization:** OpenAlex
- **Date:** current page as of the fetch [V] (URL moved from docs.openalex.org)
- **URL:** https://help.openalex.org/how-to-use-the-api/api-overview
- **Tag:** [V] for the points below; [U] for exact search syntax and rate numbers.
- **Findings:**
  - Basic use is free without a key; a free API key is optional and passed as `api_key`; a key raises the daily budget tenfold [V].
  - Heavier use is pay-as-you-go; each list response reports `meta.cost_usd` [V].
  - The page does not give rate-limit numbers and does not mention a mailto parameter [V].
  - The page lists search as a standard operation but did not show the `search=` syntax [V].
- **Relevance to EasyResearch:** OpenAlex is a public service. Any query text is public information sent to a third party, so queries must be built from data that is safe to publish.

### S37. Groq legal and policy index
- **Organization:** Groq
- **Date:** undated [U]
- **URL:** https://console.groq.com/docs/legal
- **Tag:** [U]
- **Findings:**
  - The index page links to Your Data, Services Agreement, Service Specific Terms, Privacy Policy, and a Customer DPA, but does not show their text [V].
  - Whether free-tier inputs are used for training could not be confirmed [U].
- **Relevance to EasyResearch:** Read the Your Data page and Service Specific Terms before enabling Groq for any non-public text.

### S38. Kleppmann, Wiggins, van Hardenberg, McGranaghan, "Local-first software"
- **Authors:** Martin Kleppmann, Adam Wiggins, Peter van Hardenberg, Mark McGranaghan (Ink & Switch; also Onward! 2019)
- **Date:** April 2019 [V]
- **URL:** https://www.inkandswitch.com/essay/local-first/
- **Tag:** [V]
- **Findings:**
  - Seven ideals: speed, multi-device, offline, collaboration, longevity, security and privacy by default, and ownership and control [V].
  - Longevity means work remains accessible even if the vendor disappears; ownership means the user decides what can be done with their data [V].
- **Relevance to EasyResearch:** Supports plain-file exports (PDFs with hashes, notes in open formats) and a restorable backup that does not depend on the app. Also supports keeping the library local and keeping external calls optional.

### S39. Claude Code agent-SDK permissions processing order (secondary)
- **Organization:** Anthropic (Agent SDK docs)
- **Date:** undated [U]
- **URL:** https://docs.claude.com/en/api/agent-sdk/permissions
- **Tag:** [S] (search snippet; not opened)
- **Findings:**
  - Processing order reported as: PreToolUse hook, deny rules, allow rules, ask rules, permission mode check, canUseTool callback, PostToolUse [S].
- **Relevance to EasyResearch:** If the app drives Claude Code via the SDK, a deny rule at the PreToolUse step overrides allow rules. Verify before relying on it.

### S40. MCP tool annotations as client-permission input (GitHub issue, Claude Code)
- **Organization:** Community (claudeissues mirror of a feature request)
- **Date:** [U]
- **URL:** https://claudeissues.com/issue/87452-feature-permission-engine-should-process-mcp-toolannotations-hints-readonlyhint
- **Tag:** [S]
- **Findings:**
  - Reports that Claude Code does not act on the standard `readOnlyHint` / `destructiveHint` annotations, only on Anthropic-specific `_meta` fields [S].
  - Filed as a feature request; current status unknown [S].
- **Relevance to EasyResearch:** Do not treat `readOnlyHint` or `destructiveHint=false` as a safety gate. Use server-side logic and hooks instead.

---

## Part 2: Verdicts on O10, O11, O12

Verdicts are based on the design text in the task. The repository code was not read, so implementation claims are marked as unverified.

### O10: Safety (document wrapping, tool-less LLMs, approval, keys, OpenAlex queries)

**Overall: Partly supported.** The architecture is sound on structure (no tools for LLMs, code controls flow, schema validation, hash-bound approval). The weak points are the content-level defense (delimiters only), the multi-stage blanket approval, free-tier data policy, and the query egress path.

Sub-claims:

1. **`<document>` wrapping, closing tags escaped, system prompt says to ignore embedded instructions: Partly supported.**
   - Escaping closing tags stops the most obvious breakout, but delimiter-only protection is the weakest tested option. S3 reports datamarking or encoding as much stronger than delimiting, and says delimiting roughly halved a baseline of about 60% [V].
   - S12 reports boundary-awareness defenses (in-context examples and an explicit reminder) substantially reduce attacks [S].
   - S21 and S7 say system-prompt instructions are unreliable [S].
   - S11 and S16 show prompted models follow planted instructions (24% baseline, about 29% and 15% summary changes) [V].
   - Residual risk: attackers can use variants of the closing tag, Unicode lookalikes, or text that imitates the wrapper format. A fixed tag name is predictable. Use a random per-request boundary token plus datamarking.

2. **LLMs have no tools; code controls the flow; JSON is validated: Supported.**
   - S1 action-selector and plan-then-execute patterns and S2 CaMeL (quarantined LLM stripped of tools) support this [V].
   - S20 says output schemas must be validated [V].
   - Limit: this blocks action injection, not content injection. A tool-less model can still emit a false verdict, a misleading summary, or a steered query. Schema validation checks shape, not truth.

3. **Preview of exact prompt + hash approval; mismatch returns 409: Supported for single calls.**
   - S32 supports binding approval to one call, storing decisions server-side, and treating serialized state as untrusted (it is not authenticated) [V].
   - Add: a one-time approval token (not reusable), a comparison of the final bytes sent over the wire (including system prompt, model, endpoint, and headers excluding keys), and a TTL.
   - No implementation was inspected; this is conditional on those details.

4. **One approval for a multi-step run within a declared scope: Partly supported; contradicted in part.**
   - The exact prompt for stage N often depends on the output of stage N-1, so it cannot be shown in full at approval time. That conflicts with "preview the exact prompt" for every stage.
   - S31 shows users accept 93% of manual prompts [V]. Blanket approval is a rational response to fatigue, which increases the risk of approving the wrong run.
   - Fix: approve a stage manifest (fixed templates, bounded variable slots with maximum lengths, allowed providers, allowed data classes, stage count). Each stage's rendered prompt is hashed and checked against the manifest. If a rendered prompt falls outside the bounds, the run stops and asks again.

5. **API keys from env or local secrets file, never in DB, API output, or backups: Supported by design; no contrary evidence.**
   - Implementation not inspected. Also check that exception messages and request logs do not echo headers.

6. **LLM-generated search queries sent to OpenAlex: Partly supported.**
   - S36: OpenAlex is a public service; query text leaves the machine [V].
   - The design text does not say whether these queries appear in the approval preview. If they do not, this is a gap against the O10 rule of previewing what is sent.
   - Injection path: an abstract (untrusted, public) wrapped in critique prompt, the critique model outputs `next_queries`, code sends them to OpenAlex. An attacker can choose query text (steering to attacker-chosen papers, which then enter the candidate list) and can exfiltrate private text if the model was also given private notes and copies fragments into queries. Because OpenAlex is public, anything in a query is effectively published.

7. **External providers (free tiers): Partly supported; requires per-provider data gating.**
   - S34: Google's Unpaid Services use prompts and responses to improve products, and human reviewers may read them [V].
   - S35: OpenRouter defaults to not storing content, but endpoints can differ [V].
   - S37: Groq's data policy could not be verified [U].
   - Recommendation: default-deny private text (notes, unpublished drafts, user-authored profiles) to free tiers that train or allow review. Allow only public abstracts to those providers, after approval.

**Residual risks (O10)**
- R1: Abstract, OpenAlex result, or PDF text injects instructions into critique output, which then steers queries (see 6).
- R2: Private notes copied into queries or into external provider prompts (lethal trifecta: private data plus untrusted content plus external channel, S5).
- R3: Hidden text in PDF text layers (white or tiny text, S13, S14, S16) survives extraction. The preview may show it if the preview displays extracted text; make sure it is shown and flagged, not stripped silently (the original PDF must be retained, per domain invariants).
- R4: Visible plain-language injection (S17) bypasses hidden-text filters.
- R5: Approval fatigue (S31, S6) turns multi-stage approval into blanket consent.
- R6: Free-tier retention or human review of private text (S34).

### O11: Chat (answers cite only [P#]/[G#]; unknown keys reported after answer; no tools)

**Overall: Partly supported.**

1. **No tool use: Supported** (S1, S2, S5 advice to keep untrusted content away from consequential actions) [V].
2. **Citation keys restricted to given set: Supported as a mechanical check.** This catches invented keys. It does not check that the cited text supports the claim. No source gathered here measures citation faithfulness; this is [U] for the purposes of this research.
3. **Unknown keys reported after the answer: Partly supported.** The user reads an answer with an invalid citation before the warning. Recommend marking or removing invalid citations inline before display.
4. **Injected instructions in passages do not change answers: Partly supported to contradicted.** A passage can steer what the answer says while citing valid keys, and the key check passes. S11 and S16 show prompted models follow such instructions [V]; S12 says larger models were more vulnerable in its tests [S]. Local models may be weaker or stronger; this needs testing.
5. **Reliance on instruction hierarchy: No evidence for local or free models.** S8 and S9 concern trained models [V/S]. Do not rely on training that the local model may not have.

**Residual risks (O11)**
- A valid key cites a passage that the injection has made to say something it does not say.
- Output after the answer can be ignored by the user.
- If chat history includes earlier answers, a poisoned answer can be re-injected as context in later turns (second-order effect; reasoning, not sourced).

### O12: MCP server and Agent Skills

**Overall: Partly supported.** The read-versus-write split and draft-only writes are good. The annotations and "untrusted" wrappers are advisory, and the server is only as safe as the client that calls it.

1. **Read tools wrap library content as untrusted: Partly supported.**
   - S20 says clients MUST consider annotations untrusted and SHOULD validate results before passing them to the LLM [V]. The spec does not say clients must enforce wrapping. The label is a hint; enforcement belongs to the client or to hooks.
   - S25: hooks can deny or ask on any MCP tool by name [V].
   - Concrete risk: the Claude Code session that reads library content through these tools may also have WebFetch, Bash, or write tools. That combination completes the lethal trifecta (S5) across the MCP boundary, regardless of the wrapper.

2. **Write tools only create drafts/suggestions: Supported in principle.**
   - Limits the blast radius of injected instructions to changes that a human later accepts (action-selector idea, S1) [V].
   - Stored injection risk: a draft that contains injected text can be reloaded later into a prompt (second-order). Treat `origin: "agent"` as untrusted in every later prompt and keep provenance (reasoning; not sourced).

3. **Annotations `readOnlyHint` / `destructiveHint=false`: Partly supported.**
   - Correct as descriptors (S20 defines the fields) [V].
   - Not a control: the spec says clients must treat them as untrusted [V], and a community report says Claude Code does not act on standard annotations [S, S40].

4. **Four skills meet the Agent Skills format: Supported.**
   - Names meet the rule (lowercase, hyphens, no reserved words) [V, S27/S28].
   - Descriptions must be at most 1,024 characters (spec) and the combined listing is truncated at 1,536 characters (Claude Code) [V, S26/S27].
   - Confirm folder name equals `name`, and that no description contains XML tags (S28) [V].

5. **Skill permissions (implied by design): Partly supported.**
   - `research-loop` should use `disable-model-invocation: true`, because it triggers external calls [V, S26].
   - `allowed-tools` should be narrow; it pre-approves tools for the turn, so a broad list silently removes prompts for those tools [V, S26].

6. **Protocol version and MCP migration: Unverified.**
   - The 2026-07-28 revision removes the initialize handshake and sessions, deprecates Sampling and Roots, and moves tasks to an extension [V, S19]. If the server or its SDK targets 2025-06-18 or 2025-11-25, check compatibility with the client versions the user runs [U for client support].

**Residual risks (O12)**
- Claude Code with read tools plus network tools in one session (see 1).
- Stored injection through agent-written drafts (see 2).
- Tool poisoning or rug pull if the server's tool descriptions or list change after approval (S24, reasoning for our own server).
- Tool outputs with raw PDF text in `structuredContent` that a client may render or follow.

---

## Part 3: Better ideas

Each idea lists the change, evidence, benefit, cost, fit with constraints (local-first, free tools, no new model downloads), risks, and confidence.

### I1. Split each research step into a quarantined reader and a tool-less query builder
- **Change:** For each stage that reads abstracts or PDFs, the LLM outputs only a fixed JSON schema with enumerated fields (for example, `relevance` enum, `concepts` as a list of short tokens with max length). Code builds OpenAlex queries from validated tokens with a template. The LLM never writes free-text queries.
- **Evidence:** S1 plan-then-execute and action-selector (S1 [V]); S2 CaMeL quarantined LLM (S2 [V]); S5 trifecta (S5 [V]).
- **Benefit:** Removes the injection-to-query and query-to-exfiltration path (R1, R2).
- **Cost:** Medium. Schema work and some quality loss on query generation; evaluate with the local model.
- **Fit:** Local and free; no new models.
- **Risks:** Token-level constraints can still carry data (a concept token can be a secret). Add a length cap and a check against private-note n-grams.
- **Confidence:** High.

### I2. Egress filter for every outbound string (OpenAlex and external providers)
- **Change:** Before any outbound call, run an egress check: maximum length, character class, no n-gram overlap with the private library (threshold chosen by test), no URL-like strings, and the exact outbound string shown in the approval preview.
- **Evidence:** S5 (external communication leg); S36 (OpenAlex is public) [V]; S34 (free-tier data use) [V].
- **Benefit:** Blocks exfiltration of private text via queries or prompts; makes preview complete.
- **Cost:** Low to medium.
- **Fit:** Pure code; no external service.
- **Risks:** n-gram overlap has false positives on common terms; tune with a list of stop-terms.
- **Confidence:** High for the mechanism; medium for the threshold.

### I3. Replace blanket multi-stage approval with a bounded stage manifest
- **Change:** Approve a manifest, not free text: a list of stages, each with a fixed template, bounded slots (max chars, allowed classes), allowed provider and data class, and a total token and call budget. Each rendered prompt is hashed and checked against the manifest at runtime. Out-of-bounds prompts stop the run and ask again.
- **Evidence:** S31 (93% acceptance indicates blanket-approval risk) [V]; S32 (per-call binding and server-side storage) [V]; S28 (plan-validate-execute) [V].
- **Benefit:** Keeps the one-approval UX while making what was approved precise; each step has a verifiable hash.
- **Cost:** Medium.
- **Fit:** Matches the existing hash-and-409 design.
- **Risks:** Manifest may be too rigid for exploratory runs; allow a second approval with a narrower scope.
- **Confidence:** High.

### I4. Use datamarking with a random per-request boundary instead of tag-only wrapping
- **Change:** Generate a random nonce per request; wrap each document as `<document label=... nonce=...>`; interleave a marker (for example, a rare character) through the document text (datamarking) or encode it for high-capacity models. Escape the nonce too. Add one in-context example showing that document text is data.
- **Evidence:** S3 datamarking results (for example, 3.10% and 0.00% on summarization; 8.0% and 1.0% on Q&A) [V]; S3 says delimiting alone is weaker [V]; S12 boundary awareness with reminder [S].
- **Benefit:** Measured reduction on the attack class, low utility cost on several tasks [V].
- **Cost:** Low to medium; needs a local eval because the numbers are for GPT-family models.
- **Fit:** No new model; works with Ollama.
- **Risks:** Datamarking can hurt quote-accurate citation if the marker leaks into quoted passages; strip the marker before display and before quote verification.
- **Confidence:** Medium.

### I5. Build an injection regression corpus and a state-based test harness in temporary data folders
- **Change:** Create synthetic PDFs and abstracts (not user data) that contain: hidden white text, tiny-font text, instructions in metadata or alt text, plain visible instructions (S17), and fake closing tags. Assert on observable state: no unapproved outbound call, no query containing a canary private string, verdict unchanged, citations valid, no draft written from the injected instruction. Use canary strings in the private test library to detect exfiltration.
- **Evidence:** S10 (state-based checks, not LLM judges) [V]; S11 (test suite format) [V]; S12 (benchmark design) [S]; S16 (HTML injection changed 15–29% of summaries) [V].
- **Benefit:** Turns the O10–O12 claims into pass/fail evidence (AGENTS.md: evidence over claims).
- **Cost:** Medium: a few days of test authoring.
- **Fit:** Runs against the local model; uses temporary folders per AGENTS.md.
- **Risks:** Synthetic attacks are not the same as real papers; keep the corpus growing with observed cases.
- **Confidence:** High.

### I6. Quarantine suspicious ingested text instead of deleting it
- **Change:** At ingestion, flag text matching instruction-like patterns (for example, "ignore previous", "give a positive review", "you are an AI reviewer") and text that differs between the text layer and the rendered page (white or tiny text). Keep the original PDF and hash; mark the extracted text as flagged; show the flag in the preview. Do not strip silently.
- **Evidence:** S13, S14 (hidden prompts in arXiv papers) [V]; S16 (hidden HTML) [V]; S17 (visible instructions also work) [S]; AGENTS.md (never overwrite source PDFs).
- **Benefit:** Surfaces attacks to the user and keeps evidence intact.
- **Cost:** Low to medium; pattern lists are brittle, so treat as a signal, not a gate.
- **Fit:** Local.
- **Risks:** False positives in legitimate papers about prompt injection (the papers this app is likely to read). Use flags, not blocks.
- **Confidence:** Medium.

### I7. Gate external providers by data class, not just by approval
- **Change:** Add a data-class tag to every stored text (public abstract, public PDF, private note, user profile, agent draft). Each provider has an allowed-class list: for example, free Gemini allows public abstracts only; OpenRouter endpoints allowed only with ZDR-only setting for any non-public class. The approval preview shows the provider's data-use policy summary.
- **Evidence:** S34 (Google free tier uses data for improvement; human review) [V]; S35 (OpenRouter defaults and ZDR option) [V]; S37 (Groq unclear) [U].
- **Benefit:** Stops private text reaching providers that train on or review it, even when the user approves quickly.
- **Cost:** Low to medium.
- **Fit:** Strong; no new service.
- **Risks:** Some users will want private text on free tiers; keep it opt-in with an explicit warning.
- **Confidence:** High.

### I8. Make chat citation handling inline and deterministic
- **Change:** Parse citations before rendering. Replace invalid keys with a visible "[unsupported citation]" marker inline and strip them from the cited list. Add a lexical check that each cited passage shares the claim's key terms above a threshold, and flag low-overlap citations. Keep the no-tools rule.
- **Evidence:** O11 design (unknown keys after answer) reviewed in Part 2; S12 and S11 on steering [S/V]; S1 (no tools) [V].
- **Benefit:** Users see invalid citations at the point of reading; cheap support check.
- **Cost:** Low.
- **Fit:** Pure code.
- **Risks:** Lexical overlap is weak evidence; present it as a hint, not a verdict.
- **Confidence:** Medium.

### I9. Enforce MCP read/write policy with hooks, not annotations
- **Change:** Add project hooks (in `.claude/settings.json` or a plugin) that: (a) deny WebFetch, WebSearch, and network Bash while skills that read the library are active; (b) use `ask` for any write-capable MCP tool; (c) deny writes outside the repo. Use matchers such as `mcp__easyresearch__.*`. Document that the `.claude/` folder is untracked and must be reviewed before commit.
- **Evidence:** S25 (hooks, exit code 2, `permissionDecision`, MCP matchers) [V]; S40 (annotations not acted on) [S]; S20 (annotations untrusted) [V].
- **Benefit:** Enforces the read-only and no-exfiltration boundary deterministically. Breaks the trifecta inside Claude Code sessions.
- **Cost:** Low.
- **Fit:** Uses Claude Code features only.
- **Risks:** Hooks can be disabled by the user; document that the protection depends on settings. Hooks run shell commands, so keep them reviewed.
- **Confidence:** High for mechanism; medium for coverage (depends on the user's client and version).

### I10. Harden the skill definitions for least privilege
- **Change:** For each skill: `disable-model-invocation: true` on `research-loop`; narrow `allowed-tools` (for example, only the EasyResearch MCP tools for `paper-profile`); descriptions at most 1,024 characters and under the 1,536-character listing limit; no `!` shell injection; forward-slash paths; a test prompt set for each skill run with the local model as well as a hosted model (S28).
- **Evidence:** S26 (allowed-tools and disable-model-invocation semantics; security advice) [V]; S27 (name and description limits) [V]; S28 (evaluation before docs) [V].
- **Benefit:** Fewer surprise prompts, no unexpected network use from skills.
- **Cost:** Low.
- **Fit:** Good.
- **Risks:** `allowed-tools` is experimental in the spec (S27) and may behave differently across clients.
- **Confidence:** High.

### I11. Make MCP tool outputs structured and self-describing
- **Change:** Return library text in `structuredContent` with an `outputSchema` that has explicit fields: `provenance` (origin, file hash, page label), `untrusted_text` (the string), and `flags` (from I6). Keep the text out of `content` where possible, and out of tool descriptions and resource names. Return validation problems as Tool Execution Errors (`isError: true`).
- **Evidence:** S20 (outputSchema validation, structuredContent, tool execution errors) [V]; S18 (SEP-1303) [V]; S21/S20 (servers MUST sanitize outputs) [V].
- **Benefit:** Clients that validate can enforce shape; the untrusted field is distinct from metadata; errors help the model self-correct.
- **Cost:** Low to medium.
- **Fit:** Fits MCP; check that the client shows structured content (uncertain).
- **Risks:** Clients may still pass `untrusted_text` into prompts; I9 is still needed.
- **Confidence:** Medium.

### I12. Plan a migration path for the 2026-07-28 MCP revision
- **Change:** Audit server state: move cross-call state (drafts, sessions) to explicit handles passed as tool arguments with bounded lifetimes; remove reliance on `initialize` or session IDs; avoid sampling and roots (deprecated); avoid SEP-1686 tasks for long jobs; add a test that the server still responds correctly to an unknown client version.
- **Evidence:** S19 (sessions removed, handshake removed, Sampling and Roots deprecated, tasks moved, 12-month deprecation window) [V]; S20 (stateful tool guidance: handles, expiry errors) [V].
- **Benefit:** Avoids a forced rewrite when clients drop 2025 versions; no runtime sessions to hijack (S21 session hijacking).
- **Cost:** Low now; medium if the server depends on sessions.
- **Fit:** Good; no new services.
- **Risks:** Client support for 2026-07-28 is unconfirmed (Part 4); do not drop the older version until clients support the new one.
- **Confidence:** Medium (spec facts high; client adoption unknown).

### I13. Local-first longevity: plain-file export and independent restore
- **Change:** Ensure the library can be exported as plain files (PDFs with hashes, notes as Markdown or JSON, profiles as JSON) without the app, and that the backup format is documented. Add a restore test on a temporary folder.
- **Evidence:** S38 (longevity and ownership ideals) [V]; AGENTS.md (backup compatibility on schema change).
- **Benefit:** Keeps user data usable without the app, consistent with the local-first goal and the no-private-data-leak rule.
- **Cost:** Low to medium.
- **Fit:** Good.
- **Risks:** Export files contain private text; keep them out of Git (AGENTS.md).
- **Confidence:** Medium.

### I14. Ban free-text prompts from being displayed as "instructions"
- **Change:** In the UI and in logs, show LLM-generated text only as data in a quoted block, never as plain text next to controls such as "approve". Avoid rendering LLM output as Markdown links that the user might click to open external URLs without a check (reason: S21 OAuth URL validation and XSS concerns for web clients; the same principle applies to a local web UI).
- **Evidence:** S21 (URL scheme validation, XSS risks) [V]; S38 (security by default) [V].
- **Benefit:** Reduces the chance of a poisoned answer producing a clickable phishing or script link in the local UI.
- **Cost:** Low.
- **Fit:** Local web UI; vanilla JS.
- **Risks:** Minor UX cost.
- **Confidence:** Medium (reasoning from S21 applied to a different context).

---

## Part 4: Conflicts and unverified items

**Spec and version conflicts**
- **Tasks status.** S18 (2025-11-25) describes experimental tasks (SEP-1686) [V]; S19 (2026-07-28) moves tasks into an extension (SEP-2663) [V]; S23 says the Python SDK removed or deprecated them [S]. Treat the 2026-07-28 changelog as authoritative for that spec version.
- **Elicitation.** S19 removes `elicitation/complete` and URL-mode elicitation IDs [V]. A secondary source says elicitation is the only active client feature in that revision [S]. Not reconciled; S19 is the primary source.
- **Sampling.** S18 added tool calling in sampling [V]; S19 deprecates Sampling [V]. Both are true for different revisions. The earlier design assumption that sampling-with-tools is a usable path is outdated for 2026-07-28.
- **Roots.** S19 deprecates Roots and removes `notifications/roots/list_changed` [V].
- **Revision list.** S19 is dated 2026-07-28 from the URL and page [V]. Search summaries also list 2025-03-26 and 2024-11-05 as earlier revisions [S].
- **Tool naming.** S28 recommends `ServerName:tool_name` for skills [V]; S25 uses `mcp__<server>__<tool>` for hooks [V]. These are different contexts (skill guidance vs hook matchers). Verify in each.
- **Hook exit codes.** A secondary summary said exit 0 means allow [S]; the primary hooks page says exit 0 with no decision keeps the normal permission flow, and only JSON `allow` or exit 2 changes it [V]. Use the primary.
- **Annotations as trust input.** S20 says clients MUST treat annotations as untrusted [V]; S40 says Claude Code does not act on them [S]. Consistent with each other; neither makes annotations a control.

**Benchmark and paper number conflicts**
- **Spotlighting headline.** Abstract: "below 2%" [V]. Text values: datamarking 3.10% (GPT-3.5 summarization), 8.0% (GPT-3.5 Q&A), 1.0% (GPT-4 Q&A); encoding 1.8% (GPT-3.5 Q&A) [V]. The headline is a best-case summary; do not quote "below 2%" as a general figure.
- **CaMeL.** A search summary says CaMeL mitigated 67% of AgentDojo attacks [S]. The abstract gives 77% of tasks solved with provable security vs 84% undefended [V]. Use the abstract figures only; the 67% claim could not be confirmed.
- **AgentDojo figures.** Search summaries give 8% attack success with a detector and under 25% attack success for the best agents [S]; a third-party page gives 47.69% targeted ASR for GPT-4o [S]. The abstract gives only scope (97 tasks, 629 cases) [V]. Not reconciled.
- **InjecAgent.** Primary: ReAct GPT-4 24% [V]. Hacking-prompt figure: "nearly doubling" [V] vs 47% [S].
- **IH-Challenge numbers.** 6.6% to 0.7% [S] and 44% to 100% [S]. Not verified. Also trained model only.
- **Hidden-prompt counts.** Lin (S13): 18 manuscripts [V]. Implicator (S14): at least 17 papers, 14 universities, eight countries [V]. Search summary of Nature: 18 preprints, 44 institutions, 11 countries [S, unverified]. The sources disagree on the counts and scope.
- **Lin publication status.** Lin's arXiv listing says v1 July 2025 and v2 August 2026, published in Communications of the ACM (2026) [V].
- **Lethal trifecta date.** Primary: 2025-06-16 [V]. One aggregator says 2024 [S]. Primary wins.
- **Anthropic approval rate.** 93% [V, S31] vs 97% [S, secondary]. Use 93% with the primary cited.
- **Auto mode dates.** Primary says published 2026-03-25 [V]. Secondary says 2026-03-24 and a default-on date of 2026-08-14 [S]. Use the primary date only.
- **Sandboxing 84% figure.** Secondary only [S]. Do not use.
- **OWASP edition.** The 2026 Top 10 "published 2026-08-04" and LLM01 status [S] versus the 2025 names listed from memory in a fetched summary [U]. Check genai.owasp.org directly; the LLM names in this file are not verified.
- **K-Dense skill count.** 177 on GitHub [V] vs 134–177 across aggregators [S]. Use GitHub.

**Unverified items (need a primary check before citing)**
- Per-client support for sampling, elicitation, tasks, and structured output in Claude Code, Claude Desktop, VS Code, Cursor, Codex CLI, and Gemini CLI. No primary matrix was found (S22 page has none) [U]. One secondary matrix reports elicitation in 13 of 24 clients, sampling in 2, roots in 4 [S].
- Whether Claude Code implements MCP 2026-07-28 (no-sessions, handshake removal) [U].
- Groq free-tier training policy [U] (S37).
- Nature's count and institution breakdown [U] (S15).
- Whether the OpenAlex `search=` syntax and rate limits match the design [U] (S36).
- Greshake 2023 and InstructionHierarchy 2024 are verified only on abstracts [V]; numbers from full papers are not included.
- EasyResearch implementation details (key handling, 409 path, preview content, whether OpenAlex queries are previewed) were not inspected [U].
- Whether the `<document>` closing-tag escaping handles Unicode lookalikes [U].

---

## Part 5: URL index

- S1 https://arxiv.org/abs/2506.08837 ; https://arxiv.org/html/2506.08837v1
- S2 https://arxiv.org/abs/2503.18813
- S3 https://arxiv.org/abs/2403.14720 ; https://arxiv.org/html/2403.14720v1
- S4 https://arxiv.org/abs/2302.12173
- S5 https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- S6 https://simonwillison.net/2025/Apr/11/camel/
- S7 https://owasp.org/www-project-top-10-for-large-language-model-applications/
- S8 https://arxiv.org/abs/2404.13208
- S9 https://arxiv.org/pdf/2603.10521 ; https://openai.com/index/instruction-hierarchy-challenge
- S10 https://arxiv.org/abs/2406.13352
- S11 https://arxiv.org/abs/2403.02691
- S12 https://arxiv.org/abs/2312.14197
- S13 https://arxiv.org/abs/2507.06185
- S14 https://www.implicator.ai/academics-use-hidden-prompts-to-manipulate-ai-peer-reviewers/
- S15 https://www.yahoo.com/news/scientists-sneaking-passages-research-papers-201856319.html ; https://www.nature.com/articles/d41586-025-02172-y
- S16 https://arxiv.org/abs/2509.05831
- S17 https://www.forcepoint.com/fr/blog/x-labs/hiding-vs-instruction-prompt-injection
- S18 https://modelcontextprotocol.io/specification/2025-11-25/changelog
- S19 https://modelcontextprotocol.io/specification/2026-07-28/changelog
- S20 https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- S21 https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices
- S22 https://modelcontextprotocol.io/clients
- S23 https://modelcontextprotocol.io/seps/1686-tasks
- S24 https://labs.cloudsecurityalliance.org/research-rb/csa-whitepaper-mcp-security-agentic-attack-surface-20260516/ ; https://blog.mcpservers.org/posts/mcp-security-best-practices
- S25 https://code.claude.com/docs/en/hooks
- S26 https://code.claude.com/docs/en/skills
- S27 https://agentskills.io/specification
- S28 https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- S29 https://github.com/anthropics/skills
- S30 https://github.com/K-Dense-AI/scientific-agent-skills
- S31 https://www.anthropic.com/engineering/claude-code-auto-mode
- S32 https://openai.github.io/openai-agents-python/human_in_the_loop/
- S33 https://docs.langchain.com/oss/python/langgraph/interrupts
- S34 https://aistudio.google.com/docs/terms
- S35 https://openrouter.ai/docs/guides/privacy/data-collection
- S36 https://help.openalex.org/how-to-use-the-api/api-overview
- S37 https://console.groq.com/docs/legal
- S38 https://www.inkandswitch.com/essay/local-first/
- S39 https://docs.claude.com/en/api/agent-sdk/permissions
- S40 https://claudeissues.com/issue/87452-feature-permission-engine-should-process-mcp-toolannotations-hints-readonlyhint
