# CLAUDE.md

> Founding document for an agent working in this repository.
> **This is a greenfield project.** The repo does not exist yet — this file defines the
> target architecture you are building toward. Treat the structure and conventions below
> as the spec. Scaffold incrementally; do not generate the whole tree at once.

---

## 1. What this project is

A **desktop application for running AI agents**. Each agent is implemented as an explicit
**workflow** (a LangGraph state graph) with full control over every step. Agents have access
to the full Anthropic-recommended tool surface — **MCP, RAG, Skills, code execution, and
browser automation** — and every agent is validated by **evals** and wrapped in
**guardrails**.

The model provider is **OpenRouter** (unified completions + tool calling).

The application is a two-process desktop app:
- a **Tauri** shell (Rust) hosting a **React + RTL** UI, and
- a **Python core** running as a local **FastAPI sidecar** that owns all agent logic.

The UI talks to the core over local HTTP/WebSocket. The UI never calls the model provider
directly — all model traffic flows through the Python core.

---

## 2. Architecture & key decisions

| Concern | Decision | Rationale |
|---|---|---|
| Core language | **Python** | LangGraph, RAG, code-exec, browser tooling are most mature here |
| Orchestration | **LangGraph** (state graph, checkpointer, `interrupt()`/`Command`) | Per-step control, resumability, human-in-the-loop |
| UI shell | **Tauri** (Rust) + React/RTL | Lightweight desktop shell; UI is Hebrew/RTL |
| UI ↔ core transport | Local **HTTP + WebSocket** (WS streams graph events) | Decoupled, streamable step inspector |
| Provider | **OpenRouter** | Single client; provider gives completions + tool calling only |
| Tools | Exposed as **MCP servers** wherever possible | One uniform integration + permission model |
| Browser automation | **DOM / accessibility-tree driven**, via **Playwright MCP** | Cheap, deterministic, no vision model required |
| Code execution | **Docker sandbox** | Isolation is the security boundary |
| Guardrails | **SafeAI** gateway as an I/O proxy + local policies | Reuse the existing SafeAI moderation platform |
| Evals | Per-agent suites, CI-runnable regression | Every agent gated by evals before merge |

**Critical mental model:** OpenRouter only provides completions + tool calling.
RAG, Skills, code execution, and browser control are **implemented client-side as tools/
orchestration in `core/`** — they are NOT provider features. Do not assume the provider
"gives" any of these.

**Browser automation is not a special category** — it is just another MCP server
(Playwright MCP). Route it through the same MCP client and permission broker as every other
tool. Default to DOM/accessibility-tree driven control; only fall back to screenshots if the
DOM is genuinely insufficient.

---

## 3. Repository structure

```
ai-agents-desktop/
├─ apps/
│  └─ desktop/                  # Tauri shell + React/RTL UI
│     ├─ src-tauri/             # window, IPC, Python sidecar lifecycle
│     └─ src/                   # agent runs, step inspector, approval gates
│
├─ core/                        # Python core (FastAPI sidecar) — owns all agent logic
│  ├─ server/                   # HTTP/WS API; streams graph events to the UI
│  ├─ agents/
│  │  ├─ registry.py            # loads agents from config
│  │  └─ <agent_name>/
│  │     ├─ graph.py            # the LangGraph workflow
│  │     ├─ nodes.py            # individual steps
│  │     └─ agent.yaml          # model, tools, guardrails, gates, budget
│  ├─ runtime/
│  │  ├─ orchestrator.py        # run loop, checkpointer, interrupt/resume
│  │  ├─ state.py               # state schema + persistence
│  │  └─ events.py              # per-node tracing + timing
│  ├─ tools/
│  │  ├─ mcp/
│  │  │  ├─ client.py           # MCP client (stdio + streamable-http)
│  │  │  └─ servers.yaml        # registered servers: playwright, safeai, code-exec…
│  │  ├─ code_exec/             # Docker sandbox runner
│  │  ├─ rag/                   # ingestion, chunking, retrieval
│  │  └─ skills/                # Skills loader (SKILL.md discovery)
│  ├─ guardrails/
│  │  ├─ safeai_proxy.py        # all model I/O routed through SafeAI gateway
│  │  └─ policies.py            # local input/output policies
│  ├─ memory/
│  │  ├─ short_term.py          # conversation window
│  │  └─ long_term.py           # semantic memory (vector store)
│  ├─ providers/
│  │  └─ openrouter.py          # client, usage tracking, budget caps
│  ├─ security/
│  │  ├─ permissions.py         # permission broker (incl. domain allowlist)
│  │  └─ secrets.py             # key management
│  └─ observability/
│     └─ tracing.py             # LangSmith / OpenTelemetry exporter
│
├─ evals/
│  ├─ datasets/                 # inputs + expected outputs
│  ├─ suites/                   # per-agent eval suites
│  └─ runner.py                 # CI-friendly regression runner
│
├─ packages/
│  └─ shared-schemas/           # event/state schemas shared by UI ↔ core
│
├─ infra/
│  ├─ sandbox/                  # Dockerfile for code-exec sandbox
│  └─ mcp-servers/
│     ├─ playwright/            # Playwright MCP (browser automation)
│     ├─ safeai/                # MCP wrapper around the SafeAI API
│     └─ …                      # additional local MCP servers
│
├─ config/
│  └─ default.yaml              # keys, budgets, domain allowlist, paths
└─ tests/
```

---

## 4. Core concepts

**An agent = `graph.py` + `agent.yaml`.** Nothing more.
- `graph.py` defines the LangGraph workflow (nodes, edges, conditional routing).
- `agent.yaml` is declarative config: which model, which tools, which guardrails, which
  human gates, and the budget cap. Adding an agent must NOT require touching the runtime.

**`core/runtime` is a generic engine.** It runs any graph, applies the checkpointer, emits
per-node tracing/timing events, and handles `interrupt()`/resume. Keep it agent-agnostic.

**All tools go through MCP + the permission broker.** A node never calls a browser/file/
network capability directly — it requests it through the MCP client, and the permission
broker (`security/permissions.py`) authorizes it against policy (e.g. domain allowlist).

**All model I/O goes through SafeAI.** `providers/openrouter.py` is wrapped by
`guardrails/safeai_proxy.py`. No node calls OpenRouter without passing input/output through
the guardrails layer.

**Memory ≠ RAG.** RAG (`tools/rag/`) is retrieval over external knowledge. Memory
(`memory/`) is the agent's own short-term (conversation) and long-term (semantic) state.

---

## 5. Conventions

- **Python:** async-first (`async def` nodes, `asyncio`), type hints everywhere, Pydantic for
  schemas. Keep nodes small and pure where possible; side effects go through tools.
- **State:** a single typed state schema per agent in `state.py`; never mutate state outside
  declared reducers.
- **Events:** every node emits a start/end event with timing; traces are JSON-serializable
  (this feeds the UI step inspector and observability).
- **UI:** React, **RTL by default** (Hebrew), `dir="rtl"`. The step inspector must show each
  node, its timing, inputs/outputs, and any pending human gate.
- **Config over code:** budgets, allowlists, model names, and tool sets live in YAML, not in
  source.
- **Secrets:** never hardcode keys. Read from `security/secrets.py` / environment. The
  OpenRouter key, SafeAI credentials, and any MCP server tokens are secrets.

---

## 6. Security rules (non-negotiable)

1. **Browser is sandboxed:** isolated persistent context, **domain allowlist enforced by the
   permission broker**, no access to the local filesystem, hard step/timeout limits per run.
2. **Code execution is sandboxed:** runs only inside the Docker sandbox (`infra/sandbox/`),
   never on the host. No host network unless explicitly allowlisted.
3. **Every sensitive action is brokered:** file, network, and browser actions are authorized
   through `security/permissions.py` against `agent.yaml` policy before execution.
4. **Guardrails are mandatory:** no path bypasses the SafeAI I/O proxy.
5. **Budgets are enforced:** `providers/openrouter.py` tracks usage and stops an agent that
   exceeds its `agent.yaml` budget cap.

---

## 7. How to add a new agent

1. Create `core/agents/<name>/` with `graph.py`, `nodes.py`, `agent.yaml`.
2. Define state in/alongside `graph.py` (or reuse a shared schema).
3. List required tools in `agent.yaml`; ensure each is a registered MCP server in
   `tools/mcp/servers.yaml`.
4. Declare guardrails, human gates, model, and budget in `agent.yaml`.
5. Add an eval suite under `evals/suites/<name>/` with a dataset under `evals/datasets/`.
6. The agent must pass its eval suite (`evals/runner.py`) before it is considered done.

---

## 8. Human-in-the-loop

Use LangGraph `interrupt()` + checkpointer for approval gates. The reference pattern is a
**two-gate model**: (1) spec/plan approval before execution, (2) a smoke-test/verification
gate before finalizing. Pending gates surface in the UI; resume via `Command`.

---

## 9. Provider notes (OpenRouter)

- Single client in `providers/openrouter.py`. Always pass through `safeai_proxy`.
- Track `usage` from responses; enforce per-agent budget caps; fail closed on overage.
- For browser/tool agents, prefer **DOM-driven** control so any tool-calling model works —
  do **not** require a vision model (free-tier models will struggle with vision loops).
- Pin model names in `agent.yaml`/config, not in code.

---

## 10. Commands (proposed — define as the project is scaffolded)

```bash
# Python core (sidecar)
uv venv && uv pip install -e ./core      # or poetry, decide once
uvicorn core.server.app:app --reload     # run the core API

# Desktop app
cd apps/desktop && npm install
npm run tauri dev                         # run UI + spawn sidecar

# Evals
python -m evals.runner --suite <agent>    # run one agent's evals
python -m evals.runner --all              # CI regression

# Quality
ruff check . && ruff format .             # lint/format Python
pytest                                    # tests
```

> Update this section with the real commands as soon as the tooling is chosen
> (uv vs poetry, test layout, etc.). Keep it accurate — agents rely on it.

---

## 11. Do NOT

- Do **not** call OpenRouter outside the SafeAI guardrails proxy.
- Do **not** give tools direct OS/file/network access — everything goes through the broker.
- Do **not** run generated code outside the Docker sandbox.
- Do **not** add agent logic to `core/runtime` — the runtime stays generic.
- Do **not** introduce a vision-based browser loop unless DOM control is proven insufficient.
- Do **not** hardcode secrets, model names, budgets, or allowlists in source.
