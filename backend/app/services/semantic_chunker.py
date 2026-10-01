"""
Semantic Chunking Service (Embedding-Based Chunking)
Splits document text into semantic sentence units, computes sentence embeddings,
calculates cosine distances between consecutive sentences, and identifies semantic
breakpoints to group text into cohesive chunks.
"""
import re
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import CHUNK_SIZE, CHUNK_OVERLAP
from app.core.logger import get_logger

logger = get_logger("semantic_chunker")


def split_into_sentences_with_spans(text: str) -> List[Dict[str, Any]]:
    """
    Split text into sentence units while tracking character start and end indices.
    """
    if not text:
        return []

    # Match sentence endings followed by whitespace or double newlines
    sentence_end_pattern = re.compile(r'(?<=[.!?])\s+|\n\n+')
    
    sentences = []
    start = 0
    
    raw_splits = sentence_end_pattern.split(text)
    
    for split in raw_splits:
        split_str = split.strip()
        if not split_str:
            continue
        
        pos = text.find(split_str, start)
        if pos != -1:
            s_start = pos
            s_end = pos + len(split_str)
            start = s_end
        else:
            s_start = start
            s_end = start + len(split_str)
            start = s_end
            
        sentences.append({
            "text": split_str,
            "start_char": s_start,
            "end_char": s_end
        })

    if not sentences and text.strip():
        sentences.append({
            "text": text.strip(),
            "start_char": 0,
            "end_char": len(text)
        })

    return sentences


class SemanticChunkerService:
    """Service handling semantic (embedding-based) document chunking."""

    def chunk_text_semantically(
        self,
        full_text: str,
        model: SentenceTransformer,
        max_chunk_size: int = CHUNK_SIZE * 2,  # e.g., 1000 chars limit
        min_chunk_size: int = 150,
        breakpoint_percentile: float = 85.0
    ) -> List[Dict[str, Any]]:
        """
        Groups text into semantically cohesive chunks based on sentence embedding distances.
        """
        if not full_text or not full_text.strip():
            return []

        sentences = split_into_sentences_with_spans(full_text)
        if len(sentences) <= 1:
            return [{
                "content": full_text.strip(),
                "start_char": 0,
                "end_char": len(full_text)
            }]

        sentence_texts = [s["text"] for s in sentences]
        
        try:
            # Encode sentences to vectors
            embeddings = model.encode(sentence_texts, show_progress_bar=False, normalize_embeddings=True)
            
            # Compute cosine distances between adjacent sentence embeddings
            distances = []
            for i in range(len(embeddings) - 1):
                sim = np.dot(embeddings[i], embeddings[i+1])
                dist = 1.0 - float(sim)
                distances.append(dist)
            
            if distances:
                threshold = float(np.percentile(distances, breakpoint_percentile))
            else:
                threshold = 0.3

            logger.info(
                f"Semantic chunking: {len(sentences)} sentences processed. "
                f"Distance threshold ({breakpoint_percentile}th percentile): {threshold:.4f}"
            )

            chunks = []
            current_chunk_sentences = []
            current_len = 0
            chunk_start_char = sentences[0]["start_char"]
            chunk_end_char = sentences[0]["end_char"]

            for i, sentence in enumerate(sentences):
                current_chunk_sentences.append(sentence["text"])
                current_len += len(sentence["text"])
                chunk_end_char = sentence["end_char"]

                is_last = (i == len(sentences) - 1)
                
                dist_to_next = distances[i] if i < len(distances) else 0.0
                exceeds_threshold = (dist_to_next >= threshold)
                exceeds_max_size = (current_len >= max_chunk_size)
                meets_min_size = (current_len >= min_chunk_size)

                if is_last or ((exceeds_threshold or exceeds_max_size) and meets_min_size):
                    chunk_text_content = full_text[chunk_start_char:chunk_end_char].strip()
                    if not chunk_text_content:
                        chunk_text_content = " ".join(current_chunk_sentences)

                    chunks.append({
                        "content": chunk_text_content,
                        "start_char": chunk_start_char,
                        "end_char": chunk_end_char
                    })

                    current_chunk_sentences = []
                    current_len = 0
                    if not is_last:
                        chunk_start_char = sentences[i+1]["start_char"]

            return chunks

        except Exception as e:
            logger.warning(f"Semantic chunking failed: {e}. Falling back to standard chunking.")
            from app.services.document_processor import chunk_text_with_spans
            return chunk_text_with_spans(full_text)


semantic_chunker_service = SemanticChunkerService()
