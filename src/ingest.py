"""
ingest.py — Embed chunks.jsonl and upsert into Pinecone.

Usage:
    python src/ingest.py

Run this ONCE (or whenever you update chunks.jsonl).
It is idempotent: re-running will overwrite existing vectors with the same IDs.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

PINECONE_API_KEY   = os.environ["PINECONE_API_KEY"]
INDEX_NAME         = os.getenv("PINECONE_INDEX_NAME", "pak-econ-rag")
CHUNKS_FILE        = Path(__file__).parent.parent / "chunks.jsonl"
EMBED_MODEL        = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM      = 384
BATCH_SIZE         = 100          # Pinecone upsert batch limit
CLOUD              = "aws"
REGION             = "us-east-1"  # Free tier region

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_chunks(path: Path) -> list[dict]:
    """Read all chunks from chunks.jsonl."""
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def build_pinecone_index(pc: Pinecone) -> object:
    """Create the Pinecone index if it doesn't exist, then return it."""
    existing = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"[ingest] Creating Pinecone index '{INDEX_NAME}'…")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=CLOUD, region=REGION),
        )
        print(f"[ingest] Index created.")
    else:
        print(f"[ingest] Index '{INDEX_NAME}' already exists — skipping creation.")
    return pc.Index(INDEX_NAME)


def chunk_to_vector(chunk: dict, embedding: list[float]) -> dict:
    """Convert a chunk dict + embedding into a Pinecone vector record."""
    metadata = {
        "text":     chunk["text"],
        "type":     chunk.get("type", "text"),
        "section":  chunk.get("section", ""),
        "table_id": str(chunk.get("table_id", "")),
    }
    return {"id": chunk["id"], "values": embedding, "metadata": metadata}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1. Load chunks
    if not CHUNKS_FILE.exists():
        sys.exit(f"[ingest] ERROR: '{CHUNKS_FILE}' not found. Run wiki_to_rag.py first.")

    chunks = load_chunks(CHUNKS_FILE)
    print(f"[ingest] Loaded {len(chunks)} chunks from {CHUNKS_FILE.name}")

    # 2. Load embedding model
    print(f"[ingest] Loading embedding model '{EMBED_MODEL}'…")
    model = SentenceTransformer(EMBED_MODEL)

    # 3. Connect to Pinecone & ensure index exists
    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = build_pinecone_index(pc)

    # 4. Embed + upsert in batches
    print(f"[ingest] Embedding and upserting {len(chunks)} chunks (batch={BATCH_SIZE})…")
    texts = [c["text"] for c in chunks]

    # Encode all at once (fast with MiniLM)
    print("[ingest] Encoding all chunks…")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    # Upsert in batches
    vectors = [chunk_to_vector(c, emb.tolist()) for c, emb in zip(chunks, embeddings)]

    for i in tqdm(range(0, len(vectors), BATCH_SIZE), desc="[ingest] Upserting"):
        batch = vectors[i : i + BATCH_SIZE]
        index.upsert(vectors=batch)

    # 5. Verify
    stats = index.describe_index_stats()
    total = stats.get("total_vector_count", stats)
    print(f"\n[ingest] ✅ Done! Pinecone index '{INDEX_NAME}' now has {total} vectors.")


if __name__ == "__main__":
    main()
