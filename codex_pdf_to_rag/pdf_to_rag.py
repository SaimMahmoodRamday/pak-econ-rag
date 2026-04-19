from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
import pdfplumber


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "document"


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\x00", "")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def rows_to_rectangular(rows: list[list[str | None]]) -> list[list[str]]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    output: list[list[str]] = []
    for row in rows:
        padded = list(row) + [""] * (width - len(row))
        output.append([clean_text("" if cell is None else str(cell)) for cell in padded])
    return output


def table_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    divider = ["---"] * len(header)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(divider) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def table_to_text(rows: list[list[str]]) -> str:
    return "\n".join("\t".join(cell for cell in row) for row in rows)


def write_csv(rows: list[list[str]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    if overlap >= chunk_size:
        raise ValueError("chunk overlap must be smaller than chunk size")

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(length, start + chunk_size)
        if end < length:
            boundary = text.rfind("\n", start, end)
            if boundary <= start:
                boundary = text.rfind(" ", start, end)
            if boundary > start + max(200, chunk_size // 3):
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def nearest_caption_text(page_dict: dict, image_bbox: tuple[float, float, float, float]) -> str:
    x0, y0, x1, y1 = image_bbox
    candidates: list[tuple[float, str]] = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        bx0, by0, bx1, by1 = block["bbox"]
        vertically_close = abs(by1 - y0) < 60 or abs(by0 - y1) < 60
        horizontal_overlap = not (bx1 < x0 or bx0 > x1)
        if not (vertically_close and horizontal_overlap):
            continue

        snippets: list[str] = []
        for line in block.get("lines", []):
            spans = [span.get("text", "").strip() for span in line.get("spans", [])]
            joined = clean_text(" ".join(spans))
            if joined:
                snippets.append(joined)
        text = clean_text(" ".join(snippets))
        if text:
            distance = min(abs(by1 - y0), abs(by0 - y1))
            candidates.append((distance, text))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


@dataclass
class Record:
    id: str
    doc_id: str
    source_pdf: str
    kind: str
    page: int
    text: str
    metadata: dict


def process_pdf(pdf_path: Path, output_root: Path) -> tuple[list[Record], list[dict]]:
    doc_id = slugify(pdf_path.stem)
    doc_root = ensure_dir(output_root / doc_id)
    pages_root = ensure_dir(doc_root / "pages")
    tables_root = ensure_dir(doc_root / "tables")
    images_root = ensure_dir(doc_root / "images")

    records: list[Record] = []
    manifest_pages: list[dict] = []

    with fitz.open(pdf_path) as fitz_doc, pdfplumber.open(pdf_path) as plumber_doc:
        for page_idx, (fitz_page, plumber_page) in enumerate(zip(fitz_doc, plumber_doc.pages), start=1):
            raw_text = fitz_page.get_text("text")
            page_text = clean_text(raw_text)
            page_filename = f"page_{page_idx:04d}.md"
            page_path = pages_root / page_filename

            page_md = [
                f"# {pdf_path.stem} - Page {page_idx}",
                "",
                page_text or "_No text extracted from this page._",
            ]
            page_path.write_text("\n".join(page_md), encoding="utf-8")

            page_record = Record(
                id=f"{doc_id}:page:{page_idx}",
                doc_id=doc_id,
                source_pdf=str(pdf_path),
                kind="page",
                page=page_idx,
                text=page_text,
                metadata={
                    "page_markdown_path": str(page_path),
                },
            )
            records.append(page_record)

            page_manifest = {
                "page": page_idx,
                "markdown_path": str(page_path),
                "text_char_count": len(page_text),
                "tables": [],
                "images": [],
            }

            extracted_tables = plumber_page.extract_tables()
            for table_idx, table in enumerate(extracted_tables, start=1):
                rows = rows_to_rectangular(table or [])
                if not rows or not any(any(cell for cell in row) for row in rows):
                    continue

                table_base = f"page_{page_idx:04d}_table_{table_idx:02d}"
                csv_path = tables_root / f"{table_base}.csv"
                json_path = tables_root / f"{table_base}.json"
                md_path = tables_root / f"{table_base}.md"

                write_csv(rows, csv_path)
                json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
                md_path.write_text(table_to_markdown(rows), encoding="utf-8")

                table_text = table_to_text(rows)
                records.append(
                    Record(
                        id=f"{doc_id}:table:{page_idx}:{table_idx}",
                        doc_id=doc_id,
                        source_pdf=str(pdf_path),
                        kind="table",
                        page=page_idx,
                        text=table_text,
                        metadata={
                            "table_index": table_idx,
                            "csv_path": str(csv_path),
                            "json_path": str(json_path),
                            "markdown_path": str(md_path),
                            "rows": len(rows),
                            "columns": len(rows[0]) if rows else 0,
                        },
                    )
                )

                page_manifest["tables"].append(
                    {
                        "table_index": table_idx,
                        "csv_path": str(csv_path),
                        "json_path": str(json_path),
                        "markdown_path": str(md_path),
                    }
                )

            page_dict = fitz_page.get_text("dict")
            image_entries_seen: set[int] = set()
            for image_idx, image in enumerate(fitz_page.get_images(full=True), start=1):
                xref = image[0]
                if xref in image_entries_seen:
                    continue
                image_entries_seen.add(xref)

                image_data = fitz_doc.extract_image(xref)
                extension = image_data.get("ext", "png")
                image_filename = f"page_{page_idx:04d}_image_{image_idx:02d}.{extension}"
                image_path = images_root / image_filename
                image_path.write_bytes(image_data["image"])

                image_rects = fitz_page.get_image_rects(xref)
                caption = ""
                if image_rects:
                    rect = image_rects[0]
                    caption = nearest_caption_text(
                        page_dict,
                        (rect.x0, rect.y0, rect.x1, rect.y1),
                    )

                records.append(
                    Record(
                        id=f"{doc_id}:image:{page_idx}:{image_idx}",
                        doc_id=doc_id,
                        source_pdf=str(pdf_path),
                        kind="image",
                        page=page_idx,
                        text=caption,
                        metadata={
                            "image_index": image_idx,
                            "image_path": str(image_path),
                            "xref": xref,
                            "width": image_data.get("width"),
                            "height": image_data.get("height"),
                            "caption_guess": caption,
                        },
                    )
                )

                page_manifest["images"].append(
                    {
                        "image_index": image_idx,
                        "image_path": str(image_path),
                        "caption_guess": caption,
                    }
                )

            manifest_pages.append(page_manifest)

    manifest = {
        "doc_id": doc_id,
        "source_pdf": str(pdf_path),
        "output_root": str(doc_root),
        "pages": manifest_pages,
    }
    (doc_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return records, manifest_pages


def write_jsonl(records: Iterable[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_chunks(records: list[Record], chunk_size: int, overlap: int) -> list[dict]:
    chunks: list[dict] = []
    for record in records:
        if record.kind == "image" and not record.text:
            continue
        text_chunks = split_text(record.text, chunk_size, overlap)
        if not text_chunks and record.text:
            text_chunks = [record.text]
        for chunk_idx, chunk in enumerate(text_chunks, start=1):
            chunks.append(
                {
                    "chunk_id": f"{record.id}:chunk:{chunk_idx}",
                    "record_id": record.id,
                    "doc_id": record.doc_id,
                    "source_pdf": record.source_pdf,
                    "kind": record.kind,
                    "page": record.page,
                    "chunk_index": chunk_idx,
                    "text": chunk,
                    "metadata": record.metadata,
                }
            )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract PDF text, tables, images, and RAG-ready chunks."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="One or more PDF file paths.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Folder where extracted assets and JSONL outputs will be written.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1200,
        help="Chunk size in characters for chunked JSONL output.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Character overlap between chunks.",
    )
    args = parser.parse_args()

    output_root = ensure_dir(Path(args.output_dir))
    all_records: list[Record] = []
    summary: list[dict] = []

    for raw_input in args.inputs:
        pdf_path = Path(raw_input)
        if pdf_path.suffix.lower() != ".pdf":
            pdf_path = pdf_path.with_suffix(".pdf")
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        records, manifest_pages = process_pdf(pdf_path, output_root)
        all_records.extend(records)
        summary.append(
            {
                "source_pdf": str(pdf_path),
                "doc_id": slugify(pdf_path.stem),
                "page_count": len(manifest_pages),
                "record_count": len(records),
            }
        )

    raw_records = []
    for record in all_records:
        item = asdict(record)
        raw_records.append(item)

    records_path = output_root / "records.jsonl"
    write_jsonl(raw_records, records_path)

    chunks = build_chunks(all_records, chunk_size=args.chunk_size, overlap=args.chunk_overlap)
    chunks_path = output_root / "chunks.jsonl"
    write_jsonl(chunks, chunks_path)

    summary_path = output_root / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "documents": summary,
                "records_jsonl": str(records_path),
                "chunks_jsonl": str(chunks_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({"summary_path": str(summary_path), "records": len(raw_records), "chunks": len(chunks)}, indent=2))


if __name__ == "__main__":
    main()
