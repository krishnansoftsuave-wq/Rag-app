# DocuBrain - Fullstack RAG Application & MCP Server / Client (Next.js + Python FastAPI)

A modern Retrieval-Augmented Generation (RAG) & Model Context Protocol (MCP) web application allowing users to upload documents (PDF, DOCX, TXT, MD), run adaptive agentic chunking, interactively ask questions, and connect external Standalone MCP Servers.

---

## Key Features

- **Document Processing & Agentic Chunking**: Supports PDF, DOCX, TXT, and MD files with Late Chunking, Semantic, and Agentic chunking options.
- **Vector Database**: High-performance semantic indexing powered by **ChromaDB** and **Jina AI / SentenceTransformers**.
- **Adaptive RAG Agent & Fixed Workflow**: Evaluate and compare Adaptive RAG Agent performance vs Fixed Workflow pipelines side-by-side.
- **Model Context Protocol (MCP) Server**: Internal FastMCP server exposing authenticated RAG tools (`upload_document`, `query_document_and_reply`, `summarize_document`, `list_documents`, `delete_document`).
- **Standalone Artifact Studio MCP Server (`backend/mcp_servers/artifact_studio/server.py`)**: Microservice running on port `8005` over SSE that turns each chat answer into a visual artifact:
  - 🧩 `generate_artifact`: Takes the user's request and the retrieved document chunks, and returns a **key points**, **table**, **timeline**, **chart**, or **mind map** artifact. Built by the configured LLM using only facts from the sources; returns an error when the LLM is unavailable.
  - 📋 `list_artifact_types`: Lists the supported artifact formats, the LLM provider, and whether its API key is configured.
- **LLM provider (Groq or Gemini)**: set in `backend/.env`. `LLM_PROVIDER=groq` uses `GROQ_API_KEY` and the models in `GROQ_MODELS` (OpenAI-compatible API); `LLM_PROVIDER=gemini` uses `GEMINI_API_KEY`. Without `LLM_PROVIDER`, Groq is used whenever `GROQ_API_KEY` is set. Restart the backend and the standalone server after changing `.env`.
- **LLM required**: chat answers, query expansion, evidence validation, and artifacts all depend on a working API key; there is no local fallback. When no model can answer (missing key, rate limit, overload), the API returns `503` with the reason, which the chat shows as an error. Failing models are skipped until their rate limit resets (`backend/app/services/llm/client.py`).
- **MCP in chat, decided per question by the backend** (`backend/app/mcp/client/agent_tools.py`), in three stages:
  1. **Select**: the LLM sees only the question and the enabled MCP servers' descriptions (no tools) and decides whether the request needs one, and which. A server's description is the one entered in the MCP manager, or else the `instructions` the server sends when a client connects.
  2. **Connect**: only for the chosen server, the backend connects now and lists its tools over MCP (`list_tools`).
  3. **Act**: once the agent has searched the documents, a dedicated LLM call gets only that server's tools and must pick the one that fulfils the request (tool choice "required") and its arguments; the backend runs it, filling context parameters (`sources`, `answer`) from the retrieved passages. The research conversation is told what was produced, so the final answer refers to it instead of repeating it.

  Plain questions stop at stage 1 and load no MCP tools. The steps appear in the agent trace (`mcp_select_server`, `mcp_list_tools`, `mcp_call:<tool>`), and the chat response returns tool calls in `mcp_results`. The frontend renders artifacts as cards (copy/download as Markdown, expanded view) and other tools' output as a result block.
- **Claude Desktop-Style Frontend MCP Manager**: React modal for managing custom remote MCP URLs (`http://localhost:8005/sse`), configuring authentication (Bearer/API Key), inspecting tool schemas, and running tools in a live sandbox.
- **OAuth 2.1 & JWT Authentication**: User registration, login, and OAuth 2.1 server metadata discovery for Claude Desktop / Open WebUI integrations.

---

## Directory Structure

```
rag-fullstack-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app: middleware, 503 LLM handler, routers, /mcp mount
│   │   ├── api/
│   │   │   ├── router.py        # Mounts all v1 routers under /api
│   │   │   └── v1/endpoints/    # auth, oauth, health, documents, chat,
│   │   │                        # mcp_tools, mcp_servers
│   │   ├── core/                # Configuration, logging, JWT security
│   │   ├── schemas/             # Pydantic request/response models (chat, document, health, mcp)
│   │   ├── services/
│   │   │   ├── llm/             # Provider client (Groq / Gemini) + answer generation
│   │   │   ├── retrieval/       # ChromaDB vector store, hybrid (vector + BM25) retriever, relevant-sentence excerpts
│   │   │   ├── ingestion/       # Text extraction + standard/semantic/late/agentic chunkers
│   │   │   └── users.py         # User accounts (SQLite)
│   │   ├── agents/              # Adaptive RAG agent, tools, budgets, state
│   │   ├── workflows/           # Fixed (non-agentic) RAG pipeline
│   │   ├── evaluation/          # Agent vs. workflow benchmark, evaluator, metrics
│   │   └── mcp/
│   │       ├── server/          # DocuBrain's own FastMCP server (RAG tools) + token auth
│   │       └── client/          # External MCP servers: client, and their tools offered to the agent
│   ├── mcp_servers/
│   │   └── artifact_studio/     # Standalone MCP server (port 8005) that builds chat artifacts
│   ├── tests/
│   │   ├── unit/                # In-process tests (import app directly)
│   │   └── integration/         # Tests against a running backend on localhost:8000
│   ├── benchmarks/              # Benchmark questions and runners
│   ├── scripts/                 # One-off utilities (PDF evaluation report)
│   ├── data/                    # ChromaDB storage, uploads, users DB, external MCP server registry
│   ├── requirements.txt         # Python dependencies
│   └── run.py                   # FastAPI server runner
└── frontend/
    ├── src/
    │   ├── app/                 # Next.js pages & layout
    │   ├── components/          # UI components (Upload, Chat, Citations, McpServerManagerModal)
    │   ├── lib/                 # API client
    │   └── types/               # TypeScript interfaces
    ├── package.json             # NPM dependencies
    └── tailwind.config.js       # Tailwind CSS config
```

---

## How to Run

### 1. Start Standalone MCP Server (Port 8005)

```bash
cd backend
python mcp_servers/artifact_studio/server.py
```
> Standalone server runs on `http://localhost:8005/sse`

### 2. Start FastAPI RAG Backend (Port 8000)

```bash
cd backend
python run.py
```
> API running at `http://localhost:8000` (Docs available at `http://localhost:8000/docs`).

### 3. Start Next.js Frontend (Port 3000)

```bash
cd frontend
npm install
npm run dev
```
> Open `http://localhost:3000` in browser. Click **"MCP Servers"** in the top header to manage external MCP servers!

---

## API Endpoints Summary

- `GET /api/health` - Health check.
- `POST /api/upload` - Upload document file & generate vector chunks.
- `POST /api/chat` - RAG query endpoint (Agent, Workflow, Standard, Compare modes).
- `GET /api/v1/mcp/external-servers` - List configured external MCP servers & active tools.
- `POST /api/v1/mcp/external-servers/test` - Test custom MCP server connection & discover tools over SSE/HTTP.
- `POST /api/v1/mcp/external-servers` - Add new external MCP server.
- `POST /api/v1/mcp/external-servers/call-tool` - Invoke remote MCP tool on connected server.
