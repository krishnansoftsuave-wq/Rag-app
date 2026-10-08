"""
Late Chunking Service
Implements embedding-first contextual span pooling for RAG pipelines.
Unlike traditional chunking which embeds text fragments in isolation,
Late Chunking passes the full document (or long context window) through
the transformer encoder first, then mean-pools token representations across
each chunk's span to preserve global context and cross-sentence dependencies.
"""
from typing import List, Dict, Any, Tuple, Optional
import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer

from app.core.config import (
    USE_LATE_CHUNKING,
    LATE_CHUNKING_MAX_TOKENS,
    LATE_CHUNKING_STRIDE,
)
from app.core.logger import get_logger

logger = get_logger("late_chunker")


def get_token_span(
    offsets: List[List[int]],
    start_char: int,
    end_char: int
) -> Tuple[int, int]:
    """
    Map character offsets [start_char, end_char] to token indices [tok_start, tok_end]
    using tokenizer offset mapping.
    """
    tok_start = None
    tok_end = None

    for idx, (s, e) in enumerate(offsets):
        # Ignore special tokens with (0, 0)
        if s == 0 and e == 0:
            continue
        if tok_start is None and e > start_char:
            tok_start = idx
        if s < end_char:
            tok_end = idx + 1

    if tok_start is None:
        tok_start = 0
    if tok_end is None or tok_end <= tok_start:
        tok_end = tok_start + 1

    return tok_start, tok_end


class LateChunkerService:
    """Service handling late chunking vector generation."""

    def __init__(self):
        pass

    def encode_chunks(
        self,
        full_text: str,
        chunks: List[Dict[str, Any]],
        model: SentenceTransformer,
        use_late_chunking: Optional[bool] = None,
        max_tokens: int = LATE_CHUNKING_MAX_TOKENS,
        stride: int = LATE_CHUNKING_STRIDE,
    ) -> List[List[float]]:
        """
        Encodes document chunks. If late chunking is enabled and valid spans exist,
        computes contextualized token-span embeddings. Otherwise falls back to standard
        isolated chunk encoding.
        """
        if not chunks:
            return []

        should_use_late = USE_LATE_CHUNKING if use_late_chunking is None else use_late_chunking

        if not should_use_late or not full_text or not full_text.strip():
            logger.info("Using standard (isolated) chunk embedding.")
            texts = [c["content"] for c in chunks]
            return model.encode(texts, show_progress_bar=False).tolist()

        try:
            return self._encode_late_chunks(
                full_text=full_text,
                chunks=chunks,
                model=model,
                max_tokens=max_tokens,
                stride=stride,
            )
        except Exception as e:
            logger.warning(
                f"Late chunking encoding encountered an issue: {e}. Falling back to standard encoding."
            )
            texts = [c["content"] for c in chunks]
            return model.encode(texts, show_progress_bar=False).tolist()

    def _encode_late_chunks(
        self,
        full_text: str,
        chunks: List[Dict[str, Any]],
        model: SentenceTransformer,
        max_tokens: int,
        stride: int,
    ) -> List[List[float]]:
        """Core late chunking implementation."""
        tokenizer = model.tokenizer
        encoding = tokenizer(
            full_text,
            return_offsets_mapping=True,
            return_tensors="pt",
            truncation=False
        )
        total_tokens = encoding["input_ids"].shape[1]
        offsets = encoding["offset_mapping"][0].tolist()

        logger.info(
            f"Applying Late Chunking: document length {len(full_text)} chars, {total_tokens} tokens across {len(chunks)} chunks."
        )

        # Case 1: Entire document fits in max_tokens
        if total_tokens <= max_tokens:
            with torch.no_grad():
                features = {
                    "input_ids": encoding["input_ids"],
                    "attention_mask": encoding["attention_mask"],
                }
                out = model(features)
                token_embeddings = out["token_embeddings"]  # [1, seq_len, hidden_dim]

                embeddings = []
                for chunk in chunks:
                    start_c = chunk.get("start_char", 0)
                    end_c = chunk.get("end_char", len(chunk.get("content", "")))
                    tok_start, tok_end = get_token_span(offsets, start_c, end_c)
                    span_tokens = token_embeddings[0, tok_start:tok_end]
                    pooled = span_tokens.mean(dim=0)
                    norm_vec = F.normalize(pooled, p=2, dim=0)
                    embeddings.append(norm_vec.tolist())

                return embeddings

        # Case 2: Document exceeds max_tokens -> Sliding context window
        logger.info(
            f"Document tokens ({total_tokens}) exceed max_tokens ({max_tokens}). Using sliding window of size {max_tokens} with stride {stride}."
        )
        all_embeddings: List[Optional[List[float]]] = [None] * len(chunks)

        window_start = 0
        while window_start < total_tokens:
            window_end = min(window_start + max_tokens, total_tokens)
            sub_ids = encoding["input_ids"][:, window_start:window_end]
            sub_mask = encoding["attention_mask"][:, window_start:window_end]
            sub_offsets = offsets[window_start:window_end]

            # Char span covered by this window
            non_special_offsets = [o for o in sub_offsets if o[0] != 0 or o[1] != 0]
            if not non_special_offsets:
                break
            win_start_char = non_special_offsets[0][0]
            win_end_char = non_special_offsets[-1][1]

            with torch.no_grad():
                out = model({"input_ids": sub_ids, "attention_mask": sub_mask})
                sub_token_embeddings = out["token_embeddings"]

                for idx, chunk in enumerate(chunks):
                    if all_embeddings[idx] is not None:
                        continue
                    start_c = chunk.get("start_char", 0)
                    end_c = chunk.get("end_char", len(chunk.get("content", "")))

                    # If chunk starts inside this window or window covers most of it
                    if start_c >= win_start_char and (start_c < win_end_char or window_end == total_tokens):
                        tok_start, tok_end = get_token_span(sub_offsets, start_c, end_c)
                        span_tokens = sub_token_embeddings[0, tok_start:tok_end]
                        pooled = span_tokens.mean(dim=0)
                        norm_vec = F.normalize(pooled, p=2, dim=0)
                        all_embeddings[idx] = norm_vec.tolist()

            if window_end == total_tokens:
                break
            window_start += (max_tokens - stride)

        # Fallback for any chunks that weren't captured in sliding window
        for idx, emb in enumerate(all_embeddings):
            if emb is None:
                content = chunks[idx]["content"]
                fallback_vec = model.encode([content], show_progress_bar=False)[0]
                all_embeddings[idx] = fallback_vec.tolist()

        return all_embeddings  # type: ignore[return-value]


late_chunker_service = LateChunkerService()
