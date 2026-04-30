# PakEconBot

**PakEconBot** is an end-to-end Agentic RAG system that answers questions about Pakistan’s economy using a custom ReAct agent over a Pinecone-backed knowledge base built from Wikipedia.

---

## ✨ Features

- Builds a fresh knowledge dataset from Wikipedia (`wiki_to_rag_v3.py`)
- Embeds and indexes chunks into Pinecone (`src/ingest.py`)
- Custom ReAct agent with tool routing and controlled prompting (`src/agent.py`, `src/prompts.py`)
- Dedicated retrieval logic for table and year-comparison questions
- React + Vite chat UI with markdown rendering (tables, lists, code blocks, copy buttons)
- CLI chat, browser UI, and JSON API
- Two-container Docker setup: nginx serves the frontend, FastAPI serves the API

---

## 🛠️ Tech Stack

| Layer               | Technology                                              |
|---------------------|---------------------------------------------------------|
| Scraping & Parsing  | Unstructured, Requests                                  |
| Backend             | Python, FastAPI, LangChain, Groq                        |
| Embeddings          | SentenceTransformers (`all-MiniLM-L6-v2`)               |
| Vector DB           | Pinecone                                                |
| Frontend            | React + Vite, react-markdown (GFM + syntax highlight)   |
| Frontend serving    | nginx (proxies `/api` → backend container)              |
| DevOps              | Docker, Docker Compose                                  |

---

## 🏛️ Architecture

```text
                ┌─────────────────────┐         ┌─────────────────────┐
   browser ───► │ frontend (nginx)    │ ──────► │ backend (uvicorn)   │
   :8080        │ serves dist/, proxy │  /api   │ FastAPI agent       │
                │ /api → backend:8000 │         │ Pinecone + Groq     │
                └─────────────────────┘         └─────────────────────┘
                                                          ▲
                                                          │ direct
                                                       :8000
```

- **Frontend container** (`frontend/Dockerfile`): Node builds `dist/`, nginx serves it and proxies `/api/*` to the backend service over the internal Docker network.
- **Backend container** (`Dockerfile`): API-only FastAPI/uvicorn. Does **not** serve any HTML.
- **Bootstrap service** (one-shot): runs `wiki_to_rag_v3.py` and `src/ingest.py` to populate Pinecone.

---

## 📁 Project Structure

```text
.
├── api_server.py            # FastAPI app: chat API only (no static serving)
├── app.py                   # CLI chatbot entrypoint
├── wiki_to_rag_v3.py        # Build rag_dataset.json and chunks.jsonl from Wikipedia
├── src/
│   ├── agent.py             # Custom ReAct loop
│   ├── prompts.py           # System prompt and behavior rules
│   ├── tools.py             # Agent tools (semantic search, section lookup, tables, calculator)
│   ├── retriever.py         # Pinecone retrieval layer
│   └── ingest.py            # Embed chunks and upsert vectors
├── frontend/                # Vite + React app
│   ├── Dockerfile           # Node build → nginx
│   ├── nginx.conf           # SPA + /api proxy to backend
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx          # empty state, suggestions, composer
│       ├── Message.jsx      # avatar + markdown + copy buttons
│       ├── api.js
│       └── styles.css
├── chunks.jsonl             # Generated RAG chunks
├── rag_dataset.json         # Generated dataset metadata
├── Dockerfile               # Backend image
└── docker-compose.yml       # bootstrap, backend, frontend services
```

---

## 🔑 Environment Variables

Create `.env` in the repository root:

```bash
GROQ_API_KEY=your_groq_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here

# Optional
PINECONE_INDEX_NAME=pak-econ-rag
# CORS_ORIGINS=http://localhost:5173,http://localhost:4173   # only for local Vite without proxy
```

---

## 🐳 Run with Docker (recommended)

> ### ⚡ TL;DR
>
> ```bash
> docker compose --profile bootstrap run --rm bootstrap   # first time only
> docker compose up --build
> ```
>
> Open the UI at **http://localhost:8080**.
> Backend API is on `:8000` — there is no UI on `:8000`, hitting `http://localhost:8000/` returns a JSON pointer to the right places.

### 1) First-time setup — populate Pinecone

Only required on first run, or when refreshing the knowledge base.

```bash
docker compose --profile bootstrap run --rm bootstrap
```

This runs inside the backend image:

1. `python wiki_to_rag_v3.py` → produces `rag_dataset.json`, `chunks.jsonl`
2. `python src/ingest.py`     → embeds chunks and upserts to Pinecone

The bootstrap service mounts the project directory, so generated files persist on your host.

### 2) Start the app

```bash
docker compose up
```

Add `--build` whenever you change source so images are rebuilt:

```bash
docker compose up --build
```

To run in the background:

```bash
docker compose up -d
docker compose logs -f frontend backend
```

To stop:

```bash
docker compose down
```

### 3) Where to access

| What                | URL                                  | Served by         |
|---------------------|--------------------------------------|-------------------|
| Chat UI             | http://localhost:8080                | frontend (nginx)  |
| Chat UI → API       | http://localhost:8080/api/chat       | nginx → backend   |
| Backend direct      | http://localhost:8000/api/chat       | backend (uvicorn) |
| OpenAPI docs        | http://localhost:8000/docs           | backend           |
| Health (frontend)   | http://localhost:8080/health         | nginx → backend   |
| Health (backend)    | http://localhost:8000/health         | backend           |

> The browser **only** needs `http://localhost:8080`. Port `:8000` is exposed for API testing (curl, Postman, `/docs`); the UI never calls it directly.

---

## 💻 Run locally (without Docker)

Use this for fast iteration on frontend code with hot reload.

### 1) Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 2) Build dataset and index (first run / refresh)

```bash
python wiki_to_rag_v3.py
python src/ingest.py
```

### 3) Start the backend (API only)

```bash
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

Backend at: `http://127.0.0.1:8000` (API + `/docs`). It does **not** serve any UI.

### 4) Start the frontend

In a **second terminal**:

```bash
cd frontend
npm install
npm run dev          # hot-reload dev server on :5173
# or
npm run build && npm run preview   # production build on :4173
```

Both modes proxy `/api/*` to `http://127.0.0.1:8000`.

| What                         | URL                          |
|------------------------------|------------------------------|
| UI (dev, hot reload)         | http://localhost:5173        |
| UI (production preview)      | http://localhost:4173        |
| Backend API + docs           | http://127.0.0.1:8000/docs   |

To point Vite at a different backend (e.g. a remote one):

```bash
VITE_API_TARGET=https://api.example.com npm run dev
```

### 5) Optional: CLI chat

```bash
python app.py
```

---

## 🔌 API Endpoints

- `POST /api/chat` — ask a question; returns `{ answer, conversation_id }`
- `POST /api/clear` — clear server-side memory for one `conversation_id`
- `DELETE /api/conversation/{conversation_id}` — drop the cached agent for a thread
- `GET /health` — liveness probe

---

## 🛠 Troubleshooting

- **`GET / 404 Not Found` in backend logs** — expected. The backend is API-only. Open the UI at **http://localhost:8080** instead. Hitting `http://localhost:8000/` directly now returns a JSON pointing at the UI and `/docs`.
- **`localhost:8080` doesn’t load** — the frontend container probably isn’t running. Check it:
  ```bash
  docker compose ps
  docker compose logs frontend --tail 50
  ```
  If you only see `backend-1` in your logs, the frontend image failed to build — re-run `docker compose up --build` and read the build output. Most common causes: stale image (run `--build`), or `npm install` failed because of a network issue inside the build.
- **UI shows but `Send` does nothing / 502** — backend isn’t running or isn’t reachable from the frontend container. Check `docker compose logs backend`. In Docker, nginx proxies to host `backend` (the service name) on port `8000`.
- **Frontend changes don’t appear in Docker** — you skipped `--build`; the container is still running the previously baked `dist/`.
- **Missing env keys** — ensure `.env` contains `GROQ_API_KEY` and `PINECONE_API_KEY`. Backend will return `503` with the missing key name on first call.
- **No Docker engine** — start Docker Desktop before running `docker compose`.
- **Empty or weak answers** — rerun the bootstrap profile to refresh `chunks.jsonl` and Pinecone vectors.
- **Slow first response** — model and Pinecone clients initialize lazily on first query (first call after a fresh start can take 10–20s).
- **CORS errors in local dev** — only happens if you bypass the Vite proxy. Set `CORS_ORIGINS=http://localhost:5173,http://localhost:4173` in `.env` and restart the backend.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
