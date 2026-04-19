import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
from io import StringIO

WIKI_TITLE = "Economy of Pakistan"

# -----------------------------
# 1. Fetch Wikipedia HTML
# -----------------------------
url = "https://en.wikipedia.org/w/api.php"

params = {
    "action": "parse",
    "page": WIKI_TITLE,
    "format": "json",
    "prop": "text",
    "redirects": True
}

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, params=params, headers=headers)

if response.status_code != 200:
    raise Exception(f"HTTP Error {response.status_code}")

data = response.json()
html = data.get("parse", {}).get("text", {}).get("*", "")

if not html:
    raise ValueError("No HTML content found")

# -----------------------------
# 2. Parse HTML
# -----------------------------
soup = BeautifulSoup(html, "html.parser")

# -----------------------------
# 3. Clean unwanted elements
# -----------------------------
for tag in soup.find_all(["script", "style", "sup"]):
    tag.decompose()

def clean_text(text):
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# -----------------------------
# 4. Extract Tables
# -----------------------------
tables = []
table_chunks = []

try:
    raw_tables = pd.read_html(StringIO(html))

    for i, table in enumerate(raw_tables):

        # Flatten columns
        if isinstance(table.columns, pd.MultiIndex):
            table.columns = [
                " ".join([str(c) for c in col]).strip()
                for col in table.columns.values
            ]
        else:
            table.columns = [str(col) for col in table.columns]

        table = table.fillna("").astype(str)

        table_dict = {
            "table_id": i,
            "columns": list(table.columns),
            "data": table.to_dict(orient="records")
        }

        tables.append(table_dict)

        # -------- Row-wise chunks --------
        for row in table_dict["data"]:
            parts = []
            for col in table_dict["columns"]:
                val = row.get(col, "")
                if val:
                    parts.append(f"{col} is {val}")

            if parts:
                text = " | ".join(parts)
                table_chunks.append({
                    "text": text,
                    "type": "table_row",
                    "table_id": i
                })

        # -------- Summary chunk --------
        # summary_text = f"This table contains data with columns: {', '.join(table_dict['columns'])}"
        # table_chunks.append({
        #     "text": summary_text,
        #     "type": "table_summary",
        #     "table_id": i
        # })

        if table_dict["data"]:
            first_row = table_dict["data"][0]
            sample = " | ".join(
                f"{col}: {first_row.get(col, '')}"
                for col in table_dict["columns"]
                if first_row.get(col, "")
            )
            table_chunks.append({
                "text": f"Table {i} covers: {sample}",
                "type": "table_summary",
                "table_id": i
            })

except Exception as e:
    print("Table extraction issue:", e)

# -----------------------------
# 5. Extract Sections
# -----------------------------
content = []

current_section = "Introduction"
section_text = []

for tag in soup.find_all(["h2", "h3", "h4", "h5" , "p"]):

    if tag.name in ["h2", "h3" , "h4" , "h5"]:
        if section_text:
            content.append({
                "heading": current_section,
                "text": clean_text(" ".join(section_text))
            })

        current_section = clean_text(tag.get_text())
        section_text = []

    elif tag.name == "p":
        section_text.append(tag.get_text())

# last section
if section_text:
    content.append({
        "heading": current_section,
        "text": clean_text(" ".join(section_text))
    })

# -----------------------------
# 6. Create Chunks (text + tables)
# -----------------------------
chunks = []

# ---- Text chunks (sentence-aware) ----
for i, section in enumerate(content):
    full_text = section["heading"] + ". " + section["text"]
    sentences = full_text.split(". ")

    chunk = ""
    for sent in sentences:
        if len(chunk) + len(sent) < 500:
            chunk += sent + ". "
        else:
            chunks.append({
                "id": f"text_{i}_{len(chunks)}",
                "text": chunk.strip(),
                "type": "text",
                "section": section["heading"]
            })
            chunk = sent + ". "

    if chunk:
        chunks.append({
            "id": f"text_{i}_{len(chunks)}",
            "text": chunk.strip(),
            "type": "text",
            "section": section["heading"]
        })

# ---- Add table chunks ----
for i, t in enumerate(table_chunks):
    chunks.append({
        "id": f"table_{i}",
        "text": t["text"],
        "type": t["type"],
        "table_id": t["table_id"]
    })

# -----------------------------
# 7. Save outputs
# -----------------------------
dataset = {
    "title": WIKI_TITLE,
    "source": f"https://en.wikipedia.org/wiki/{WIKI_TITLE.replace(' ', '_')}",
    "sections": content,
    "tables": tables
}

with open("rag_dataset.json", "w", encoding="utf-8") as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)

# Save chunks as JSONL (best for embeddings)
with open("chunks.jsonl", "w", encoding="utf-8") as f:
    for c in chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

print(f"✅ Done: {len(chunks)} chunks created")