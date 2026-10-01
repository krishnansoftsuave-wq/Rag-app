import os
from typing import List, Optional
from app.core.config import GEMINI_API_KEY
from app.core.logger import get_logger
from app.schemas.chat import SourceCitation, ChatResponse

logger = get_logger("llm_service")


class LLMService:
    def generate_answer(
        self,
        question: str,
        sources: List[SourceCitation],
        api_key: Optional[str] = None,
        provider: str = "gemini"
    ) -> ChatResponse:
        key_to_use = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

        if not sources:
            return ChatResponse(
                question=question,
                answer="No documents have been uploaded yet or no relevant content was found matching your question. Please upload a document to get started.",
                sources=[],
                used_fallback=False
            )

        context_str = "\n\n".join(
            [f"--- Source [{i+1}] (File: {s.filename}, Chunk: {s.chunk_index}) ---\n{s.content}" for i, s in enumerate(sources)]
        )

        prompt = f"""You are an intelligent RAG (Retrieval-Augmented Generation) assistant.
Answer the user's question based strictly on the provided context passages below.
If the answer is partially available, answer as best as possible using the context.
Always cite the source files (e.g., [File: filename.pdf]) when referencing facts.

Question: {question}

Context Passages:
{context_str}

Detailed Answer:"""

        # Try Google Gemini API if key is available
        if key_to_use:
            try:
                from google import genai
                client = genai.Client(api_key=key_to_use)
                candidate_models = [
                    "gemini-3.8-flash",
                    "gemini-3.5-flash",
                    "gemini-3.6-flash",
                    "gemini-flash-latest",
                ]
                
                for model_name in candidate_models:
                    for attempt in range(2):
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=prompt
                            )
                            if response and response.text:
                                return ChatResponse(
                                    question=question,
                                    answer=response.text,
                                    sources=sources,
                                    used_fallback=False
                                )
                        except Exception as err:
                            err_str = str(err)
                            if "503" in err_str and attempt == 0:
                                import time
                                time.sleep(1)
                                continue
                            logger.warning(f"Gemini API model '{model_name}' failed: {err}. Trying next candidate model...")
                            break
            except Exception as outer_err:
                logger.warning(f"Google GenAI SDK client error: {outer_err}")

        # Smart Local RAG Synthesis Fallback when no API Key is set or network is unavailable
        fallback_answer = self._synthesize_local_fallback_answer(question, sources)
        return ChatResponse(
            question=question,
            answer=fallback_answer,
            sources=sources,
            used_fallback=True
        )

    def _synthesize_local_fallback_answer(self, question: str, sources: List[SourceCitation]) -> str:
        """
        Synthesizes a structured answer directly from top retrieved context chunks when an external LLM API key is not configured.
        """
        filenames = list(set([s.filename for s in sources]))
        intro = f"*(Note: Generated via Local Context Extractor - Provide a Gemini API key in settings for full LLM generative capabilities)*\n\n"
        intro += f"Based on content retrieved from **{', '.join(filenames)}**:\n\n"

        points = []
        for i, src in enumerate(sources, 1):
            snippet = src.content.strip().replace("\n", " ")
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            points.append(f"**From `{src.filename}` (Chunk #{src.chunk_index}, Relevance: {int(src.score*100)}%)**:\n> \"{snippet}\"\n")

        return intro + "\n".join(points)
