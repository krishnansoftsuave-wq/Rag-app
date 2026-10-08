from typing import List, Optional
from app.core.logger import get_logger
from app.schemas.chat import SourceCitation, ChatResponse
from app.services.llm.client import complete

logger = get_logger("llm_service")


class LLMService:
    def generate_answer(
        self,
        question: str,
        sources: List[SourceCitation],
        api_key: Optional[str] = None,
        provider: str = "gemini"
    ) -> ChatResponse:
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

        # An LLM is required: raises LLMUnavailableError when no model can answer
        answer, _ = complete(prompt, api_key=api_key)
        return ChatResponse(
            question=question,
            answer=answer,
            sources=sources,
            used_fallback=False
        )
