from typing import List
from app.core.logger import get_logger
from app.schemas.chat import SourceCitation, ChatResponse
from app.core.tracing import record_contexts, span
from app.services.llm.client import complete
from app.services.llm.prompts import ANSWER_PROMPT, PROMPT_VERSION
from app.services.retrieval.excerpts import focus_terms, focused_excerpt

logger = get_logger("llm_service")

MAX_SOURCES_IN_PROMPT = 6
MAX_SOURCE_CHARS = 1500


class LLMService:
    def generate_answer(
        self,
        question: str,
        sources: List[SourceCitation],
        provider: str = "gemini",
        extra_instructions: str = ""
    ) -> ChatResponse:
        if not sources:
            return ChatResponse(
                question=question,
                answer="No documents have been uploaded yet or no relevant content was found matching your question. Please upload a document to get started.",
                sources=[],
                used_fallback=False
            )

        # The top sources only, with long chunks reduced to their sentences relevant to the question, to stay within
        # per-request token limits (Groq free tier rejects requests above its tokens-per-minute cap)
        terms = focus_terms(question)
        context_str = "\n\n".join(
            [f"--- Source [{i+1}] (File: {s.filename}, Chunk: {s.chunk_index}) ---\n{focused_excerpt(s.content, terms, MAX_SOURCE_CHARS)}"
             for i, s in enumerate(sources[:MAX_SOURCES_IN_PROMPT])]
        )

        prompt = ANSWER_PROMPT.format(extra_instructions=extra_instructions, question=question, context=context_str)

        # An LLM is required: raises LLMUnavailableError when no model can answer
        with span("generate_answer", stage="generation", prompt_version=PROMPT_VERSION):
            record_contexts(sources[:MAX_SOURCES_IN_PROMPT])  # exactly the chunks the model was shown
            answer, _ = complete(prompt)
        return ChatResponse(
            question=question,
            answer=answer,
            sources=sources,
            used_fallback=False
        )
