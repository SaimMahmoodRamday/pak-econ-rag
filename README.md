# PakEconBot 

**PakEconBot** is an end-to-end Agentic RAG application for answering questions about Pakistan's economy.  
It includes a data pipeline (`wiki_to_rag_v3.py` -> `ingest.py`), a ReAct-style reasoning agent, Pinecone-backed retrieval, and a clean web chat interface served by FastAPI.

---

## ✨ Features

- Builds a fresh knowledge dataset from Wikipedia (`wiki_to_rag_v3.py`)
- Embeds and indexes chunks into Pinecone (`src/ingest.py`)
- Uses a custom ReAct agent with tool routing and controlled prompting (`src/prompts.py`)
- Handles table and year-comparison questions with dedicated retrieval logic
- Supports both CLI chat and browser UI
- Fully containerized workflow for bootstrap + serving

---

## 🏗 Tech Stack

- **Scrapping/Parsing:** Unstructured , Requests
- **Backend:** Python, FastAPI, LangChain, Groq 
- **Retrieval:** Pinecone, SentenceTransformers (`all-MiniLM-L6-v2`)
- **Frontend:** Vanilla HTML/CSS/JS (served as static assets)
- **DevOps:** Docker, Docker Compose

---

## 📁 Project Structure

```text
.
├── api_server.py            # FastAPI app + chat API + static frontend serving
├── app.py                   # CLI chatbot entrypoint
├── wiki_to_rag_v3.py        # Scrape + parse + build rag_dataset.json and chunks.jsonl
├── src/
│   ├── agent.py             # Custom ReAct loop
│   ├── prompts.py           # System prompt and behavior rules
│   ├── tools.py             # Agent tools (semantic search, section lookup, table search, calculator)
│   ├── retriever.py         # Pinecone retrieval layer
│   └── ingest.py            # Embed chunks and upsert vectors
├── frontend/
│   ├── index.html
│   └── assets/
│       ├── app.js
│       └── style.css
├── chunks.jsonl             # Generated RAG chunks
├── rag_dataset.json         # Generated dataset metadata
├── Dockerfile
└── docker-compose.yml
```

---

## 🔑 Environment Variables

Create `.env` in the repository root:

```bash
GROQ_API_KEY=your_groq_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here

# Optional
PINECONE_INDEX_NAME=pak-econ-rag
# CORS_ORIGINS=http://localhost:5173
```

---

## 🚀 Quickstart (Local)

### 1) Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2) Build data and index (first run or when refreshing data)

```bash
python wiki_to_rag_v3.py
python src/ingest.py
```

### 3) Run the application

```bash
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

- Web UI: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Optional CLI mode:

```bash
python app.py
```

---

## 🐳 Docker Workflow

### First-time setup (or whenever data needs rebuilding)

```bash
docker compose build --no-cache
docker compose --profile bootstrap run --rm pakecon-bootstrap
```

This executes:

1. `python wiki_to_rag_v3.py`
2. `python src/ingest.py`

The bootstrap service mounts the project directory, so generated files like `chunks.jsonl` and `rag_dataset.json` are preserved on your host.

### Start the app

```bash
docker compose up
```

- App: [http://localhost:8000](http://localhost:8000)
- Health: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🔌 API Endpoints

- `POST /api/chat` - ask a question and get an answer
- `POST /api/clear` - clear memory for one `conversation_id`
- `DELETE /api/conversation/{conversation_id}` - remove cached conversation agent
- `GET /health` - service health check

Example request:

```json
{
  "message": "What is Pakistan's GDP as of 2026?",
  "conversation_id": "optional-thread-id"
}
```

---

## 🛠 Troubleshooting

- **Missing env keys:** ensure `.env` contains `GROQ_API_KEY` and `PINECONE_API_KEY`
- **No Docker engine:** start Docker Desktop before running `docker compose`
- **Empty or weak answers:** rerun the bootstrap flow to refresh `chunks.jsonl` and Pinecone vectors
- **Slow first response:** model/index clients initialize lazily on first query

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

