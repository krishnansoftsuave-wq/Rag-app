"""
Agentic / LLM-Based Chunking Service
Uses Large Language Models (Gemini / GenAI) to analyze document structure,
detect topic transitions, and determine optimal semantic chunk boundaries.
Falls back gracefully to Semantic (Embedding-Based) chunking when API keys or network are unavailable.
"""
import os
import json
import re
from typing import List, Dict, Any, Optional
from app.core.config import GEMINI_API_KEY, CHUNK_SIZE
from app.core.logger import get_logger
from app.services.semantic_chunker import split_into_sentences_with_spans, semantic_chunker_service

logger = get_logger("agentic_chunker")


class AgenticChunkerService:
    """Service handling Agentic (LLM-guided) document chunking."""

    def chunk_text_agentically(
        self,
        full_text: str,
        embedding_model: Any,
        api_key: Optional[str] = None,
        max_chunk_size: int = CHUNK_SIZE * 2
    ) -> List[Dict[str, Any]]:
        """
        Chunks document text using LLM reasoning to identify conceptual topic shifts.
        """
        if not full_text or not full_text.strip():
            return []

        sentences = split_into_sentences_with_spans(full_text)
        if len(sentences) <= 2:
            return [{
                "content": full_text.strip(),
                "start_char": 0,
                "end_char": len(full_text)
            }]

        key_to_use = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

        # Try LLM Agentic boundary extraction if key is available
        if key_to_use:
            try:
                chunks = self._llm_agentic_split(full_text, sentences, key_to_use, max_chunk_size)
                if chunks:
                    logger.info(f"Agentic chunking: LLM generated {len(chunks)} topic-bounded chunks.")
                    return chunks
            except Exception as e:
                logger.warning(f"Agentic LLM chunking encountered issue: {e}. Falling back to Semantic Chunking.")

        # Fallback to Semantic (Embedding-Based) Chunking
        logger.info("Using Semantic Embedding Chunker fallback for Agentic mode.")
        return semantic_chunker_service.chunk_text_semantically(full_text=full_text, model=embedding_model)

    def _llm_agentic_split(
        self,
        full_text: str,
        sentences: List[Dict[str, Any]],
        api_key: str,
        max_chunk_size: int
    ) -> Optional[List[Dict[str, Any]]]:
        """Queries Google Gemini to identify logical topic boundaries across sentences."""
        from google import genai

        client = genai.Client(api_key=api_key)
        
        # Format sentence units for prompt (cap total items to avoid context overflow)
        formatted_units = []
        for i, s in enumerate(sentences[:100]): # Limit to 100 sentences per prompt
            snippet = s["text"].replace("\n", " ")
            formatted_units.append(f"[{i}] {snippet}")

        units_str = "\n".join(formatted_units)

        prompt = f"""You are an expert Document Chunking Agent.
Analyze the following numbered text sentences from a document and group them into logical, semantically coherent chunks based on topic shifts and conceptual boundaries.

Document Sentences:
{units_str}

Respond STRICTLY with a valid JSON array of objects representing chunk ranges of sentence indices.
Do NOT include any extra explanations, markdown formatting, or text outside the JSON array.
Example format:
[
  {{"start_index": 0, "end_index": 3}},
  {{"start_index": 4, "end_index": 8}}
]
"""
        candidate_models = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
        response_text = None

        for model_name in candidate_models:
            try:
                res = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if res and res.text:
                    response_text = res.text
                    break
            except Exception as err:
                logger.warning(f"Agentic chunking model {model_name} error: {err}")

        if not response_text:
            return None

        # Clean potential markdown wrapping (e.g. ```json ... ```)
        cleaned_json = re.sub(r'```(?:json)?\s*', '', response_text).strip('` \n\r')
        boundaries = json.loads(cleaned_json)

        if not isinstance(boundaries, list) or len(boundaries) == 0:
            return None

        chunks = []
        for b in boundaries:
            start_i = max(0, min(b.get("start_index", 0), len(sentences) - 1))
            end_i = max(start_i, min(b.get("end_index", start_i), len(sentences) - 1))

            chunk_start_char = sentences[start_i]["start_char"]
            chunk_end_char = sentences[end_i]["end_char"]
            chunk_content = full_text[chunk_start_char:chunk_end_char].strip()

            if chunk_content:
                chunks.append({
                    "content": chunk_content,
                    "start_char": chunk_start_char,
                    "end_char": chunk_end_char
                })

        # Process any remaining sentences beyond sentence unit cap
        if len(sentences) > 100:
            last_end = chunks[-1]["end_char"] if chunks else 0
            remaining_content = full_text[last_end:].strip()
            if remaining_content:
                chunks.append({
                    "content": remaining_content,
                    "start_char": last_end,
                    "end_char": len(full_text)
                })

        return chunks if chunks else None


agentic_chunker_service = AgenticChunkerService()
