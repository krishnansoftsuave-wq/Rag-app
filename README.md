# DocuBrain - Fullstack RAG Application (Next.js + Python FastAPI)

A modern Retrieval-Augmented Generation (RAG) web application allowing users to upload documents (PDF, DOCX, TXT, MD) and interactively ask questions about their content.

---

## Features

- **Document Processing**: Supports PDF, DOCX, TXT, and MD files.
- **Smart Chunking**: Recursive character text splitting preserving paragraph context.
- **Vector Database**: High-performance semantic indexing powered by **ChromaDB** and **SentenceTransformers** (`all-MiniLM-L6-v2`).
- **LLM Question Answering**: Integrated with **Google Gemini API** (`gemini-2.5-flash`).
- **Local Fallback Mode**: Intelligent context synthesis mode that runs completely offline/without an API key.
- **Source Attribution**: Transparent citation cards showing exact document snippets, chunk indices, and relevance similarity scores.
- **Interactive UI**: Responsive dashboard built with **Next.js**, **TypeScript**, and **Tailwind CSS**.

---

## Directory Structure

```
rag-fullstack-app/
├── backend/
│   ├── app/
│   │   ├── config.py            # Environment & vector settings
│   │   ├── document_processor.py# Text extraction & chunking
│   │   ├── main.py              # FastAPI routes & CORS
│   │   ├── models.py            # Pydantic schemas
│   │   └── rag_engine.py        # ChromaDB & LLM RAG engine
│   ├── data/                    # Document uploads & ChromaDB storage
│   ├── requirements.txt         # Python dependencies
│   └── run.py                   # Server starter script
└── frontend/
    ├── src/
    │   ├── app/                 # Next.js pages & layout
    │   ├── components/          # React UI components (Upload, Chat, Citations)
    │   ├── lib/                 # API client
    │   └── types/               # TypeScript interfaces
    ├── package.json             # NPM dependencies
    └── tailwind.config.js       # Tailwind CSS config
```

---

## How to Run

### 1. Start FastAPI Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```
> Server will start at: `http://localhost:8000` (API documentation available at `http://localhost:8000/docs`).

### 2. Start Next.js Frontend

```bash
cd frontend
npm install
npm run dev
```
> Frontend will open at: `http://localhost:3000`

---

## API Endpoints

- `GET /api/health` - Health check & vector DB statistics.
- `POST /api/upload` - Upload document file & generate vector chunks.
- `GET /api/documents` - List all uploaded documents.
- `DELETE /api/documents/{doc_id}` - Delete document & clear vector embeddings.
- `POST /api/chat` - RAG query endpoint returning generated answer + source citations.
