# LocalRAG v2.0 - Private Knowledge Intelligence

A production-ready local Retrieval-Augmented Generation (RAG) application with **hybrid search**, **cross-encoder re-ranking**, and **semantic caching**. 

Version 2.0 introduces a brand new **RAGFlow-inspired dark aesthetic UI**, a **Category Management System**, and a robust **Dual-Storage architecture** that guarantees zero data loss across container restarts.

## 🎯 Key Features

### 🎨 RAGFlow-Inspired Interface
- **Dark Glassmorphism & Minimalist UI**: Pure black canvas (`#050508`) with sharp teal (`#10e8b8`) accents and a subtle grid overlay.
- **Live Stats Dashboard**: Track indexed documents, categories, and API health in real-time.
- **Interactive Chat**: View retrieved chunks, exact relevance scores, and source document metadata instantly alongside your answers.

### 🧠 Advanced RAG Pipeline
- **Hybrid Retrieval**: Combines BM25 (sparse keyword search) and Vector (dense semantic search) using Reciprocal Rank Fusion (RRF) for unmatched accuracy.
- **Cross-Encoder Re-ranking**: Passes the top-K hybrid results through `ms-marco-MiniLM` to re-score and re-order them based on deep contextual relevance.
- **Semantic Caching**: Redis-backed caching instantly returns answers for repeated or semantically identical queries, skipping the LLM generation step.

### 📂 Knowledge Management & Dual-Storage
- **Category System**: Organize documents into custom categories (e.g., `Finance`, `Legal`, `Research`).
- **Robust Persistence**: 
  - **Redis Stack** acts as the high-speed volatile layer for vector search.
  - **JSON Backups** act as the durable storage layer. Every document processed is saved as a structured JSON file to your mapped host volume (`KNOWLEDGE_DATA_PATH` in `.env`, `./data` by default).
- **Auto Re-indexing**: If the Docker containers are destroyed or volumes are pruned, the system automatically reads the JSON backups on the next startup and fully restores the Redis index. Zero data loss.
- **Secure Processing**: The original uploaded files are automatically deleted after successful parsing and ingestion.

## 🏗️ Architecture

```
Frontend (Streamlit :8501)
        |  HTTP
        v
Backend (FastAPI :8000)
  |-- Ingestion Pipeline (PDF, DOCX, TXT, CSV, MD, HTML, JSON, XML)
  |-- Retrieval Engine (BM25 + Vector + Cross-Encoder Reranker)
  |-- Semantic Cache
        v
Redis Stack (:6379)  <-- Sub-millisecond Vector & Cache Store
        v
Mounted Host Volume (KNOWLEDGE_DATA_PATH, ./data by default) <-- Durable JSON Backups
```

## 🛠️ Installation & Setup

### Prerequisites
- Docker and Docker Compose
- At least 8GB RAM (16GB+ recommended for loading multiple ML models)

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd LocalRAG
```

2. **Configure your environment**
```bash
cp .env.example .env
# Edit .env: set JWT_SECRET (required -- e.g. `openssl rand -hex 32`),
# KNOWLEDGE_DATA_PATH for where document backups are stored (defaults to
# ./data), and optionally CORS_ALLOWED_ORIGINS.
```

3. **Start the application**
```bash
docker-compose up --build -d
```

4. **Access the Application**
- **UI Dashboard**: `http://localhost:8501`
- **Interactive API Docs (Swagger)**: `http://localhost:8000/docs`
- **RedisInsight**: `http://localhost:8001`

## 🚀 Usage Guide

1. **Create Categories**: Go to the **Knowledge Base** tab and create folders for your data.
2. **Upload Documents**: Select a category, tweak chunk sizes if necessary, and drop your files. Ingestion happens asynchronously in the background.
3. **Query**: Go to the **Chat** tab, adjust your Retrieve (Top-K) and Re-rank sliders, and ask questions.
4. **Manage Data**: Delete documents directly from the UI library to completely wipe them from both Redis and the disk backup.

## 🔧 Under the Hood: The ML Stack

- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (Fast, 384-dimensional dense vectors)
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (Deep contextual similarity scoring)
- **Vector DB**: `Redis Stack` (RediSearch + RedisJSON)

## 🛡️ Security & Privacy

- **100% Local**: No cloud dependencies, no telemetry, no external API calls (e.g., OpenAI). Your documents never leave your machine.
- **Auto-Cleanup**: Your original raw documents are deleted from the server the second they finish chunking and vectorizing.
- **Account-based auth**: every route except `GET /`, `GET /health`, and `POST /auth/*` requires a signed-in session (`POST /auth/signup` or `POST /auth/login`), via an httpOnly cookie (web) or an `Authorization: Bearer` token (mobile/API clients). `JWT_SECRET` is required in `.env`. Multi-tenant document isolation (each account seeing only its own documents) is in progress — accounts gate access today, per-account data scoping is landing incrementally.

## 🧪 Development

Run the backend test suite (requires a reachable Redis; a `redis-stack` instance gives full coverage, including vector-index tests — a plain Redis skips those):
```bash
cd backend
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/ -v
```

Run the frontend test suite:
```bash
cd frontend
npm ci
npm test
```

Both suites run in CI on every push/PR (`.github/workflows/ci.yml`).

## 📝 Detailed Documentation

For a comprehensive breakdown of the API endpoints, storage survival matrix, data flow, and troubleshooting, please refer to the detailed [DOCUMENTATION.md](./DOCUMENTATION.md) included in this repository.