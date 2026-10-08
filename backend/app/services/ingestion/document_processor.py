import os
from typing import List, Dict, Any
from pypdf import PdfReader
import docx

from app.core.config import CHUNK_SIZE, CHUNK_OVERLAP


def extract_text_from_file(file_path: str, filename: str) -> str:
    """Extract raw text from PDF, DOCX, TXT, or MD files."""
    ext = os.path.splitext(filename)[1].lower()
    text = ""

    if ext == ".pdf":
        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                pages.append(f"[Page {i+1}]\n{page_text}")
        text = "\n\n".join(pages)

    elif ext in [".docx", ".doc"]:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)

    elif ext in [".txt", ".md", ".csv", ".json", ".log"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks using a recursive character splitting logic
    to preserve sentence and paragraph context where possible.
    """
    if not text:
        return []

    separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def _split_text(text_segment: str, current_separators: List[str]) -> List[str]:
        if len(text_segment) <= chunk_size:
            return [text_segment] if text_segment.strip() else []

        if not current_separators:
            chunks = []
            for i in range(0, len(text_segment), chunk_size - overlap):
                chunks.append(text_segment[i:i + chunk_size])
            return chunks

        sep = current_separators[0]
        if sep != "" and sep not in text_segment:
            return _split_text(text_segment, current_separators[1:])

        splits = text_segment.split(sep) if sep != "" else list(text_segment)

        result = []
        current_chunk = ""

        for i, split in enumerate(splits):
            item = split if (i == len(splits) - 1 or sep == "") else split + sep
            if len(current_chunk) + len(item) <= chunk_size:
                current_chunk += item
            else:
                if current_chunk.strip():
                    result.append(current_chunk.strip())

                if len(item) > chunk_size:
                    result.extend(_split_text(item, current_separators[1:]))
                    current_chunk = ""
                else:
                    current_chunk = item

        if current_chunk.strip():
            result.append(current_chunk.strip())

        return result

    raw_chunks = _split_text(text, separators)

    final_chunks = []
    for chunk in raw_chunks:
        if not chunk.strip():
            continue
        final_chunks.append(chunk)

    return final_chunks


def chunk_text_with_spans(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """
    Split text into chunks while tracking start_char and end_char character spans
    for contextual embedding methods like Late Chunking.
    """
    raw_chunk_texts = chunk_text(text, chunk_size, overlap)
    chunks_with_spans = []
    current_search_idx = 0

    for chunk_str in raw_chunk_texts:
        pos = text.find(chunk_str, current_search_idx)
        if pos != -1:
            start_char = pos
            end_char = pos + len(chunk_str)
            current_search_idx = max(0, start_char + max(1, len(chunk_str) - overlap))
        else:
            pos_any = text.find(chunk_str)
            if pos_any != -1:
                start_char = pos_any
                end_char = pos_any + len(chunk_str)
            else:
                start_char = 0
                end_char = len(chunk_str)

        chunks_with_spans.append({
            "content": chunk_str,
            "start_char": start_char,
            "end_char": end_char,
        })

    return chunks_with_spans


def process_document(file_path: str, filename: str, doc_id: str) -> List[Dict[str, Any]]:
    """
    Reads a document file, extracts text, chunks it, and returns structured chunk dictionaries
    including character span boundaries and reference to the document text.
    """
    full_text, chunks = process_document_with_text(file_path, filename, doc_id)
    return chunks


def process_document_with_text(file_path: str, filename: str, doc_id: str):
    """
    Reads document, extracts text, and returns both full text and structured chunks with spans.
    """
    full_text = extract_text_from_file(file_path, filename)
    if not full_text:
        raise ValueError(f"Could not extract readable text from file '{filename}'")

    spans_data = chunk_text_with_spans(full_text)

    processed_chunks = []
    for idx, item in enumerate(spans_data):
        chunk_data = {
            "id": f"{doc_id}_chunk_{idx}",
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": idx,
            "content": item["content"],
            "start_char": item["start_char"],
            "end_char": item["end_char"],
            "full_text": full_text,
        }
        processed_chunks.append(chunk_data)

    return full_text, processed_chunks
