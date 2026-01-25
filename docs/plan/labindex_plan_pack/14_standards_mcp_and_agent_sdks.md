# 14 — Standards: MCP, Tool Calling, and Agent SDK Options

This document summarizes **established standards and ecosystems** you can reuse for the “LLM agent + tools” portion of LabIndex, instead of building proprietary plumbing.

The guiding principle is:

- Keep LabIndex’s capabilities as a set of **read-only tools** implemented in `labindex_core`.
- Optionally expose those tools through **standard protocols** (MCP) so multiple agent clients (desktop apps, IDEs, CLIs) can consume them.
- Choose an “agent orchestration” layer (SDK/framework) based on how much structure, tracing, and retrieval composition you want.

---

## 1) Tool calling / function calling (baseline mechanism)

Most modern LLM agent systems are built around **tool calling**:
1. You define a tool’s name + JSON schema (inputs/outputs).
2. The model requests a tool call.
3. Your app executes it and returns results.
4. The model uses results to produce an answer (ideally with citations/evidence).

**Why this fits LabIndex perfectly**
- Your agent never gets direct filesystem access.
- Tools operate on **`file_id` handles**, not raw paths.
- You can enforce **budgets** (bytes/time), plus strict read-only behavior, in the tool layer.

---

## 2) MCP (Model Context Protocol) for standardized tool/context integration

**MCP** is an open protocol for exposing tools/resources to LLM applications via a standardized interface.

### What MCP gives you
- A stable, vendor-neutral “connector” layer for tools and resources.
- Interoperability: the same LabIndex tool server can be used by different clients (e.g., desktop apps, IDEs, CLIs) without custom integration per client.
- A clean separation between:
  - **MCP server**: “I provide tools/resources”
  - **MCP client**: “I can call tools/resources”

### Why MCP is attractive for LabIndex
- You can implement a **LabIndex MCP Server** that exposes:
  - `search_fts`, `resolve_name_fuzzy`, `get_related`, `read_snippet`, `parse_abf_header`, etc.
- Then your PyQt app’s agent, and external tools (e.g., IDE assistants) can reuse the same capabilities.

### Security note (important)
Tool protocols increase integration ease but also increase the importance of security controls:
- keep **read-only** guarantees at OS + code layers
- do not accept arbitrary paths from the model (use `file_id` indirection)
- strict byte/time budgets for reads
- treat “tool chaining” as a potential escalation vector (defense-in-depth)

---

## 3) Agent orchestration options (what to use to “run” the agent)

Your core design should remain:
- `labindex_core`: authoritative tool implementations (read-only)
- an “agent runner”: decides which tools to call and how to structure multi-step workflows

Below are common choices that already support tool calling patterns and (in many cases) MCP connectivity.

### Option A — OpenAI Agents SDK (Python / JS)
If you want a straightforward, relatively batteries-included agent loop with good defaults for tool usage, the OpenAI Agents SDK is a practical option.

Advantages:
- Natural fit for tool calling patterns
- Built-in patterns for multi-step agents
- Documentation and examples for MCP integration exist

Tradeoffs:
- You are adopting a specific ecosystem for orchestration (though your core tools remain independent)

### Option B — LlamaIndex (retrieval-first orchestration)
LlamaIndex is often a good fit when your application is fundamentally a retrieval system (which LabIndex is). It provides strong patterns for hybrid retrieval and tool usage, and it has explicit support for consuming MCP servers via the `llama-index-tools-mcp` package.

Advantages:
- Excellent retrieval composition (hybrid search, reranking, chunking strategies)
- Convenient for “RAG-style” workflows built around your SQLite/FTS + optional vectors
- MCP tooling support is documented

Tradeoffs:
- More abstraction; you must be deliberate to avoid accidental complexity

### Option C — LangChain / LangGraph (agent orchestration as a graph)
LangGraph is a low-level orchestration framework for stateful, long-running agents. It can be very strong when you want explicit control over state transitions (“if ambiguous → ask follow-up; else → fetch snippets; else → propose edges”).

Advantages:
- Explicit control over agent state machine
- Strong ecosystem for tracing/evaluation (often via LangSmith)

Tradeoffs:
- Larger surface area; requires careful design to keep the system maintainable

---

## 4) Recommended approach for LabIndex (pragmatic)

### 4.1 Keep LabIndex tools “source of truth”
Implement a stable internal interface (ports) for tools in `labindex_core`, for example:

- Search: `search_fts`, `search_files`, `resolve_name_fuzzy`
- Graph: `get_related`, `find_notes_for_file`, `trace_to_histology`
- Reads: `read_snippet`, `extract_pptx_text`, `extract_pdf_snippet`, `parse_abf_header`
- Learning: `propose_candidate_edge`, `accept_candidate_edge`, `record_assertion`

### 4.2 Add MCP later as an adapter layer
Once the tool surface is stable, add an MCP server wrapper that exposes the same tools externally.

This sequence tends to work well:
1. Build tools + UI/agent integration locally (fast iteration)
2. Harden security + budgets + provenance
3. Wrap tools as MCP server endpoints (interoperability)

### 4.3 Pick an orchestration layer based on your needs
- If you want minimal orchestration glue: start with an Agents SDK-style runner.
- If you want retrieval-focused workflows and hybrid pipelines: consider LlamaIndex.
- If you want explicit state machines and complex multi-step control: consider LangGraph.

In all cases, keep your “core” independent so switching orchestration later is feasible.

---

## 5) How this affects the existing plan pack

Add this document to the plan pack alongside:
- `08_llm_agent_and_tools.md` (agent behavior + tool shapes)
- `09_learning_writeback.md` (write-back guardrails)
- `11_plugins_and_iteration.md` (swappable strategies)

If you implement MCP:
- treat it as an **adapter** around `labindex_core` tools
- keep security controls inside `labindex_core` (not in the protocol wrapper)

---

## 6) Suggested “decision checklist”

Choose MCP and an agent runner if you can answer “yes” to most of these:
- Do you want to reuse the lab index tools outside the PyQt app?
- Do you want a standardized connector format for future portability?
- Do you want to avoid building and maintaining your own tool protocol?

If not, keep the agent local and add MCP when/if you need interoperability.
