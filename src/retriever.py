"""
retriever.py — Query Pinecone and return the top-k most relevant chunks.

This module is the shared retrieval backbone used by all agent tools.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
INDEX_NAME       = os.getenv("PINECONE_INDEX_NAME", "pak-econ-rag")
EMBED_MODEL      = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_TOP_K    = 5


# ---------------------------------------------------------------------------
# Lazy singletons (loaded once, reused across all calls)
# ---------------------------------------------------------------------------

_model: SentenceTransformer | None = None
_index = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_index():
    global _index
    if _index is None:
        pc     = Pinecone(api_key=PINECONE_API_KEY)
        _index = pc.Index(INDEX_NAME)
    return _index


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    chunk_type: str | None = None,
    section: str | None = None,
) -> list[dict]:
    """
    Embed *query* and return the top-k matching chunks from Pinecone.

    Args:
        query:       Natural-language query string.
        top_k:       Number of results to return.
        chunk_type:  Optional filter — "text", "table_row", or "table_summary".
        section:     Optional filter — exact section heading to restrict results to.

    Returns:
        List of dicts with keys: score, id, text, type, section, table_id.
    """
    model = _get_model()
    index = _get_index()

    # Build optional metadata filter
    filter_dict: dict = {}
    if chunk_type:
        filter_dict["type"] = {"$eq": chunk_type}
    if section:
        filter_dict["section"] = {"$eq": section}

    query_vec = model.encode(query).tolist()

    response = index.query(
        vector=query_vec,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict if filter_dict else None,
    )

    SCORE_THRESHOLD = 0.65

    results = []
    for match in response.get("matches", []):
        if match["score"] < SCORE_THRESHOLD:
            continue
        meta = match.get("metadata", {})
        results.append(
            {
                "score":    round(match["score"], 4),
                "id":       match["id"],
                "text":     meta.get("text", ""),
                "type":     meta.get("type", ""),
                "section":  meta.get("section", ""),
                "table_id": meta.get("table_id", ""),
            }
        )
    return results


def format_results(results: list[dict]) -> str:
    """
    Format retrieved results as a readable string for the LLM context.
    Each result is labeled with its source section.
    """
    if not results:
        return "No relevant information found."

    parts = []
    for i, r in enumerate(results, 1):
        source = r["section"] if r["section"] else r["type"]
        parts.append(f"[{i}] (source: {source}, score: {r['score']})\n{r['text']}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Pakistan GDP 2005"
    print(f"\nQuery: {query}\n{'─'*50}")
    results = retrieve(query, top_k=3)
    print(format_results(results))
