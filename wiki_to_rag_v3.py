import requests
import json
from unstructured.partition.html import partition_html

# -----------------------------
# 1. Config
# -----------------------------
WIKI_TITLE = "Economy of Pakistan"
url = f"https://en.wikipedia.org/wiki/{WIKI_TITLE.replace(' ', '_')}"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# -----------------------------
# 2. Fetch HTML
# -----------------------------
response = requests.get(url, headers=headers)

if response.status_code != 200:
    raise Exception(f"Failed to fetch page: {response.status_code}")

html = response.text

# -----------------------------
# 3. Parse using Unstructured
# -----------------------------
elements = partition_html(text=html)

print(f"Total elements extracted: {len(elements)}")

# -----------------------------
# 4. Convert to RAG chunks
# Track the current section heading so every chunk knows where it came from.
# This is critical for tables — without a section label the GDP table has no
# context and cannot be filtered or semantically retrieved reliably.
# -----------------------------
chunks = []
current_section = "Introduction"   # default before any heading is seen
table_counter = 0

for i, element in enumerate(elements):

    text = str(element).strip()

    # skip empty junk
    if not text or len(text) < 5:
        continue

    element_type = type(element).__name__

    # -------------------------
    # Title / Headings — update current section
    # -------------------------
    if "Title" in element_type:
        current_section = text
        chunks.append({
            "id": f"title_{i}",
            "text": text,
            "type": "title",
            "section": current_section,
            "table_id": "",
        })
        continue

    # -------------------------
    # Table handling
    # Prefix the table text with its section heading so the embedding
    # captures context (e.g. "GDP Table: Year GDP...").
    # Also store section and table_id in metadata for filtering.
    # -------------------------
    if "Table" in element_type:
        table_id = f"table_{table_counter}"
        table_counter += 1
        prefixed_text = f"[{current_section}]\n{text}"
        chunks.append({
            "id": f"table_{i}",
            "text": prefixed_text,
            "type": "table",
            "section": current_section,
            "table_id": table_id,
        })
        continue

    # -------------------------
    # Normal text (Narrative)
    # -------------------------
    chunks.append({
        "id": f"text_{i}",
        "text": text,
        "type": "text",
        "section": current_section,
        "table_id": "",
    })

# -----------------------------
# 5. Light post-processing chunk merge
# Merge very small text fragments (but never across section boundaries
# or table chunks — those are preserved as-is).
# -----------------------------
final_chunks = []
buffer = ""
buffer_section = ""

for c in chunks:

    if len(c["text"]) < 200 and c["type"] == "text":
        # Start a new buffer when the section changes
        if buffer and c["section"] != buffer_section:
            final_chunks.append({
                "id": f"merged_{len(final_chunks)}",
                "text": buffer.strip(),
                "type": "text",
                "section": buffer_section,
                "table_id": "",
            })
            buffer = ""
        buffer += " " + c["text"]
        buffer_section = c["section"]
    else:
        if buffer:
            final_chunks.append({
                "id": f"merged_{len(final_chunks)}",
                "text": buffer.strip(),
                "type": "text",
                "section": buffer_section,
                "table_id": "",
            })
            buffer = ""
        final_chunks.append(c)

if buffer:
    final_chunks.append({
        "id": f"merged_{len(final_chunks)}",
        "text": buffer.strip(),
        "type": "text",
        "section": buffer_section,
        "table_id": "",
    })

# -----------------------------
# 6. Save JSON dataset
# -----------------------------
dataset = {
    "title": WIKI_TITLE,
    "source": url,
    "num_chunks": len(final_chunks),
}

with open("rag_dataset.json", "w", encoding="utf-8") as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)

# Save chunks for embeddings
with open("chunks.jsonl", "w", encoding="utf-8") as f:
    for c in final_chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

# Quick sanity check — show section distribution
from collections import Counter
type_counts = Counter(c["type"] for c in final_chunks)
table_sections = [(c["id"], c["section"]) for c in final_chunks if c["type"] == "table"]
print(f"\n✅ Done: {len(final_chunks)} clean chunks created")
print(f"   Types: {dict(type_counts)}")
print(f"   Table chunks ({len(table_sections)}) with sections:")
for tid, sec in table_sections:
    print(f"     {tid} → {sec[:60]}")