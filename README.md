# PakEconBot

**PakEconBot** is a production-deployed, end-to-end **Agentic RAG** (Retrieval-Augmented Generation) system that answers questions about Pakistan's economy. It combines a custom **ReAct agent**, a **Pinecone vector database**, and **Groq-hosted LLaMA 3.3 70B** — served through a FastAPI backend on AWS EC2 and a React frontend hosted on AWS S3.

---

## ✨ Features

- **Wikipedia ingestion pipeline** — scrapes, parses, and chunks the Pakistan Economy article into a structured JSONL dataset
- **Dual embedding support** — ingestion uses `sentence-transformers/all-MiniLM-L6-v2`; inference uses `fastembed` (ONNX Runtime, no PyTorch) to keep the production image lightweight
- **Pinecone vector store** — 384-dimension cosine-similarity index with metadata filtering by section and chunk type (text vs. table)
- **Custom ReAct agent** — hand-rolled Reason+Act loop over Groq's LLaMA 3.3 70B; no dependency on LangChain's frequently-changing agent internals
- **Sliding-window conversation memory** — retains the last 5 turns per session; per-conversation agent isolation on the server
- **Four agent tools** — semantic search, section-level lookup, table/numeric search, safe arithmetic evaluator
- **React + Vite chat UI** — markdown rendering with GFM tables, syntax highlighting, and copy buttons
- **FastAPI REST API** — chat, clear memory, delete conversation thread endpoints
- **Dockerised backend** — single-container FastAPI/uvicorn image on EC2 with health checks
- **CI/CD via GitHub Actions** — push to `main` deploys backend to EC2 over SSH and frontend to S3 simultaneously

---
<!-- 
## 🏛️ Architecture

```
                          push to main
                               │
               ┌───────────────┴───────────────┐
               │      GitHub Actions CI/CD      │
               └───────────────┬───────────────┘
                 ┌─────────────┴─────────────┐
                 │                           │
         SSH → EC2                     aws s3 sync
                 │                           │
    ┌────────────▼──────────┐    ┌───────────▼────────────┐
    │   Docker (EC2)        │    │   S3 Static Website    │
    │   FastAPI + uvicorn   │◄───│   React + Vite SPA     │
    │   port 8000           │    │   (browser fetch)      │
    └────────────┬──────────┘    └────────────────────────┘
                 │
      ┌──────────┼──────────┐
      │          │          │
   Groq      Pinecone    fastembed
  LLaMA 3   Vector DB    (ONNX)
  (LLM)     (retrieval)  (embeddings)
```

**Data flow per request:**
1. User types a question in the React UI (S3)
2. Browser POSTs to `http://<EC2-IP>:8000/api/chat`
3. FastAPI passes the question to the ReAct agent
4. Agent embeds the query via `fastembed` (ONNX, in-process) and queries Pinecone
5. Retrieved chunks are passed as context to Groq (LLaMA 3.3 70B)
6. Agent iterates (Thought → Action → Observation) up to 8 steps
7. Final answer streamed back to the browser as JSON

--- -->

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Data ingestion** | Requests, Unstructured (HTML parsing), Pandas |
| **Embedding (ingestion)** | `sentence-transformers/all-MiniLM-L6-v2` (PyTorch) |
| **Embedding (inference)** | `fastembed` — same model via ONNX Runtime, ~700 MB lighter |
| **Vector database** | Pinecone (Serverless, cosine, 384-dim) |
| **LLM** | Groq — `llama-3.3-70b-versatile` |
| **Agent framework** | Custom ReAct loop + LangChain Core (tools, messages) |
| **Backend** | Python 3.12, FastAPI, uvicorn |
| **Frontend** | React 18, Vite, react-markdown (GFM + highlight.js) |
| **Infrastructure** | AWS EC2 (t2.micro), AWS S3 static hosting |
| **CI/CD** | GitHub Actions — SSH deploy + `aws s3 sync` |
| **Containerisation** | Docker, Docker Compose |

---

## 📁 Project Structure

```
.
├── api_server.py            # FastAPI app — /api/chat, /api/clear, /health
├── app.py                   # CLI chatbot (local testing)
├── wiki_to_rag_v3.py        # Wikipedia scraper → chunks.jsonl (run locally)
├── chunks.jsonl             # Pre-built RAG chunks (committed, ready to ingest)
├── rag_dataset.json         # Dataset metadata
│
├── src/
│   ├── agent.py             # Custom ReAct loop (LLaMA 3.3 70B via Groq)
│   ├── prompts.py           # System prompt and behavior rules
│   ├── tools.py             # Agent tools: semantic search, section lookup, table search, calculator
│   ├── retriever.py         # Pinecone query layer — uses fastembed at runtime
│   └── ingest.py            # One-time: embed chunks.jsonl → upsert to Pinecone
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Chat UI — empty state, suggestions, composer
│   │   ├── Message.jsx      # Avatar + markdown renderer + copy buttons
│   │   ├── api.js           # fetch wrapper — uses VITE_API_URL in production
│   │   └── styles.css
│   ├── index.html
│   ├── vite.config.js       # Dev proxy: /api → localhost:8000
│   ├── package.json
│   ├── Dockerfile           # Node build → nginx (local / dev only)
│   └── nginx.conf           # SPA routing + /api proxy (local / dev only)
│
├── Dockerfile               # Backend image (python:3.12-slim)
├── docker-compose.yml       # Local development
├── docker-compose.prod.yml  # EC2 production (backend only)
└── .github/workflows/deploy.yml  # CI/CD — backend SSH + frontend S3
```

---

## 🔑 Environment Variables

### Backend `.env` (EC2 server and local)

```bash
GROQ_API_KEY=your_groq_api_key
PINECONE_API_KEY=your_pinecone_api_key

# Optional
PINECONE_INDEX_NAME=pak-econ-rag
CORS_ORIGINS=http://your-s3-bucket.s3-website.eu-north-1.amazonaws.com
```

### GitHub Actions Secrets

| Secret | Purpose |
|---|---|
| `EC2_HOST` | EC2 public IP |
| `EC2_USER` | SSH user (`ubuntu`) |
| `EC2_SSH_KEY` | Private key for SSH |
| `GH_USERNAME` | GitHub username (repo clone auth) |
| `GH_TOKEN` | GitHub PAT (repo clone auth) |
| `AWS_ACCESS_KEY_ID` | IAM user key — S3 write access |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |
| `AWS_REGION` | e.g. `eu-north-1` |
| `AWS_S3_BUCKET` | S3 bucket name |
| `VITE_API_URL` | `http://<EC2-IP>:8000` — baked into the frontend bundle at build time |

---

## 🚀 Deployment

### Production (AWS)

The project deploys automatically on every push to `main` via two parallel GitHub Actions jobs:

| Job | What it does |
|---|---|
| `deploy-backend` | SSHes into EC2, pulls latest code, rebuilds and restarts the Docker container |
| `deploy-frontend` | Builds the Vite SPA with `VITE_API_URL` injected, syncs `dist/` to S3 with production-grade cache headers |

**Cache strategy for S3:**
- Hashed JS/CSS assets → `Cache-Control: public, max-age=31536000, immutable` (1-year browser cache)
- `index.html` → `Cache-Control: no-cache` (always fresh, points to latest hashed chunks)

### One-time backend setup on EC2

The Pinecone index is populated **once locally** (not on the server), since the data ingestion pipeline requires `sentence-transformers` (PyTorch) which is too heavy for a free-tier instance:

```bash
# 1. Uncomment bootstrap deps in requirements.txt (requests, pandas, etc.)
# 2. Install and run locally:
pip install -r requirements.txt
python wiki_to_rag_v3.py      # scrape Wikipedia → chunks.jsonl
python src/ingest.py           # embed + upsert to Pinecone
# 3. Re-comment bootstrap deps before pushing
```

The EC2 backend only needs `fastembed` at runtime — no PyTorch, no scraping libraries.

---

## 💻 Local Development

### Backend

```bash
python -m venv venv && venv\Scripts\activate   # Windows
# source venv/bin/activate                     # macOS/Linux

pip install -r requirements.txt
uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

API docs at: `http://127.0.0.1:8000/docs`

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev        # hot-reload on :5173, proxies /api → :8000
```

To point the dev frontend at the production backend:

```bash
VITE_API_TARGET=http://16.170.216.148:8000 npm run dev
```

### Docker (local, both containers)

```bash
docker compose up --build
```

Frontend at `:8080`, backend at `:8000`.

---

## 🔌 API Reference

| Method | Endpoint | Body | Response |
|---|---|---|---|
| `POST` | `/api/chat` | `{ message, conversation_id? }` | `{ answer, conversation_id }` |
| `POST` | `/api/clear` | `{ conversation_id }` | `{ status, conversation_id }` |
| `DELETE` | `/api/conversation/{id}` | — | `{ status, conversation_id }` |
| `GET` | `/health` | — | `{ status: "ok" }` |

---

## 🤖 Agent Tools

| Tool | Purpose |
|---|---|
| `pak_econ_search` | Broad semantic search across all chunks — facts, history, sectors |
| `section_lookup` | Retrieve chunks from a specific Wikipedia section (e.g. "Agriculture", "Debt") |
| `table_search` | Search table/numeric data — GDP figures, year comparisons, rates |
| `calculate` | Safe arithmetic evaluator — percentage changes, differences, conversions |

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
