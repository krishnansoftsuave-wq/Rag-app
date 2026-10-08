# DocuBrain - Fullstack RAG Application & MCP Server / Client (Next.js + Python FastAPI)

A modern Retrieval-Augmented Generation (RAG) & Model Context Protocol (MCP) web application allowing users to upload documents (PDF, DOCX, TXT, MD), run adaptive agentic chunking, interactively ask questions, and connect external Standalone MCP Servers.

---

## Key Features

- **Document Processing & Agentic Chunking**: Supports PDF, DOCX, TXT, and MD files with Late Chunking, Semantic, and Agentic chunking options.
- **Vector Database**: High-performance semantic indexing powered by **ChromaDB** and **Jina AI / SentenceTransformers**.
- **Adaptive RAG Agent & Fixed Workflow**: Evaluate and compare Adaptive RAG Agent performance vs Fixed Workflow pipelines side-by-side.
- **Model Context Protocol (MCP) Server**: Internal FastMCP server exposing authenticated RAG tools (`upload_document`, `query_document_and_reply`, `summarize_document`, `list_documents`, `delete_document`).
- **Standalone Artifact Studio MCP Server (`backend/mcp_servers/artifact_studio/server.py`)**: Microservice running on port `8005` over SSE that turns each chat answer into a visual artifact:
  - 🧩 `generate_artifact`: Takes the question, the answer, and the retrieved document chunks, and returns a **key points**, **table**, **timeline**, **chart**, or **mind map** artifact (auto-picked, or a requested type). Built by the configured LLM using only facts from the sources; returns an error when the LLM is unavailable.
  - 📋 `list_artifact_types`: Lists the supported artifact formats, the LLM provider, and whether its API key is configured.
- **LLM provider (Groq or Gemini)**: set in `backend/.env`. `LLM_PROVIDER=groq` uses `GROQ_API_KEY` and the models in `GROQ_MODELS` (OpenAI-compatible API); `LLM_PROVIDER=gemini` uses `GEMINI_API_KEY` or the key saved in the UI. Without `LLM_PROVIDER`, Groq is used whenever `GROQ_API_KEY` is set. Restart the backend and the standalone server after changing `.env`.
- **LLM required**: chat answers, query expansion, evidence validation, and artifacts all depend on a working API key; there is no local fallback. When no model can answer (missing key, rate limit, overload), the API returns `503` with the reason, which the chat shows as an error. Failing models are skipped until their rate limit resets (`backend/app/services/llm/client.py`).
  - After every chat answer, the frontend calls `POST /api/v1/mcp/artifacts`, which routes to the first active MCP server exposing `generate_artifact`. The artifact renders under the answer with a format switcher, copy/download as Markdown, and an expanded view.
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
│   │   │   └── v1/endpoints/    # auth, oauth, health, documents, chat, evaluation,
│   │   │                        # mcp_tools, mcp_servers, artifacts
│   │   ├── core/                # Configuration, logging, JWT security
│   │   ├── schemas/             # Pydantic request/response models (chat, document, health, mcp)
│   │   ├── services/
│   │   │   ├── llm/             # Provider client (Groq / Gemini) + answer generation
│   │   │   ├── retrieval/       # ChromaDB vector store + hybrid (vector + BM25) retriever
│   │   │   ├── ingestion/       # Text extraction + standard/semantic/late/agentic chunkers
│   │   │   ├── artifacts.py     # Chat artifacts via an external MCP server
│   │   │   └── users.py         # User accounts (SQLite)
│   │   ├── agents/              # Adaptive RAG agent, tools, budgets, state
│   │   ├── workflows/           # Fixed (non-agentic) RAG pipeline
│   │   ├── evaluation/          # Agent vs. workflow benchmark, evaluator, metrics
│   │   └── mcp/
│   │       ├── server/          # DocuBrain's own FastMCP server (RAG tools) + token auth
│   │       └── client/          # Client for external MCP servers
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

- `GET /api/health` - Health check & vector DB statistics.
- `POST /api/upload` - Upload document file & generate vector chunks.
- `POST /api/chat` - RAG query endpoint (Agent, Workflow, Standard, Compare modes).
- `GET /api/v1/mcp/external-servers` - List configured external MCP servers & active tools.
- `POST /api/v1/mcp/external-servers/test` - Test custom MCP server connection & discover tools over SSE/HTTP.
- `POST /api/v1/mcp/external-servers` - Add new external MCP server.
- `POST /api/v1/mcp/external-servers/call-tool` - Invoke remote MCP tool on connected server.
