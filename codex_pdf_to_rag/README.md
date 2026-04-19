# PDF to RAG

This script turns PDFs into assets that are much easier to use in a later RAG pipeline:

- page-level markdown text
- extracted tables as CSV, JSON, and Markdown
- extracted embedded images
- `records.jsonl` with one record per page, table, or image
- `chunks.jsonl` with chunked text ready for embedding

## Input PDFs

The script is already set up for these files:

- `D:\Projects\pak-econ-rag\data\pakecon1.pdf`
- `D:\Projects\pak-econ-rag\data\pakecon2.pdf`

## Install

Use your preferred Python environment:

```powershell
pip install -r requirements.txt
```

Or with the bundled Codex Python:

```powershell
"C:\Users\Laptop inn\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pip install -r requirements.txt
```

## Run

```powershell
"C:\Users\Laptop inn\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\pdf_to_rag.py `
  --inputs "D:\Projects\pak-econ-rag\data\pakecon1.pdf" "D:\Projects\pak-econ-rag\data\pakecon2.pdf" `
  --output-dir "D:\Projects\pak-econ-rag\processed"
```

## Output layout

```text
processed/
  chunks.jsonl
  records.jsonl
  summary.json
  pakecon1/
    manifest.json
    pages/
    tables/
    images/
  pakecon2/
    manifest.json
    pages/
    tables/
    images/
```

## Notes

- `records.jsonl` is usually the best place to start if you want custom indexing logic.
- `chunks.jsonl` is the easiest file to embed directly into a vector store.
- Table content is kept separate from page text so numerical data remains queryable.
- Image files are extracted, but only nearby text is used as a caption guess. If you later want vision captions or OCR over charts, add a multimodal enrichment step on top of this output.
