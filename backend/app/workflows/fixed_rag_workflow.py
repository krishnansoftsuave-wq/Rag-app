import time
from typing import Optional, Dict, Any
from app.agents.state import AgentState
from app.agents.tools import (
    search_document,
    refine_document_search,
    validate_evidence,
    estimate_tokens,
)
from app.agents.rag_agent import calculate_llm_cost
from app.services import llm_service
from app.schemas.chat import SourceCitation


class FixedRAGWorkflow:
    """
    Fixed RAG Workflow: Predetermined execution sequence with NO dynamic LLM routing.
    Pipeline: search_document -> refine_document_search -> validate_evidence -> generate_answer
    """
    def run(
        self,
        question: str,
        document_id: Optional[str] = None,
        question_id: str = "q_fixed",
        top_k: int = 4
    ) -> AgentState:
        state = AgentState(question=question, document_id=document_id)
        accumulated_chunks: Dict[str, Dict[str, Any]] = {}

        # ---------------------------------------------------------------------
        # STEP 1: search_document (Initial Retrieval)
        # ---------------------------------------------------------------------
        start_t1 = time.time()
        res1 = search_document(document_id=document_id, query=question, top_k=top_k)
        lat1 = (time.time() - start_t1) * 1000

        for chunk in res1["results"]:
            chunk_key = f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"
            accumulated_chunks[chunk_key] = chunk

        state.record_step(
            action="search_document",
            input_summary=f"query='{question}'",
            result_summary=f"results={res1['result_count']} top_score={res1['top_score']}",
            latency_ms=lat1,
            input_tokens=0,
            output_tokens=0,
            step_cost=0.0,
            raw_args={"document_id": document_id, "query": question, "top_k": top_k}
        )

        # ---------------------------------------------------------------------
        # STEP 2: refine_document_search (Fixed Follow-up Retrieval)
        # ---------------------------------------------------------------------
        refined_query = f"{question} details context"
        start_t2 = time.time()
        res2 = refine_document_search(document_id=document_id, query=refined_query, top_k=top_k)
        lat2 = (time.time() - start_t2) * 1000

        for chunk in res2["results"]:
            chunk_key = f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"
            accumulated_chunks[chunk_key] = chunk

        state.retrieved_evidence = list(accumulated_chunks.values())
        state.record_step(
            action="refine_document_search",
            input_summary=f"refined_query='{refined_query}'",
            result_summary=f"results={res2['result_count']} top_score={res2['top_score']}",
            latency_ms=lat2,
            input_tokens=0,
            output_tokens=0,
            step_cost=0.0,
            raw_args={"document_id": document_id, "query": refined_query, "top_k": top_k}
        )

        # ---------------------------------------------------------------------
        # STEP 3: validate_evidence (Fixed Validation)
        # ---------------------------------------------------------------------
        start_t3 = time.time()
        combined_context = "\n\n".join([c["full_content"] for c in accumulated_chunks.values()])
        val_res = validate_evidence(question=question, retrieved_context=combined_context)
        lat3 = (time.time() - start_t3) * 1000

        in_tok3 = val_res.get("input_tokens", 0)
        out_tok3 = val_res.get("output_tokens", 0)
        cost3 = calculate_llm_cost(in_tok3, out_tok3)

        state.record_step(
            action="validate_evidence",
            input_summary=f"context_length={len(combined_context)}",
            result_summary=f"sufficient={val_res.get('sufficient', False)}",
            latency_ms=lat3,
            input_tokens=in_tok3,
            output_tokens=out_tok3,
            step_cost=cost3,
            raw_args={"question": question, "retrieved_context_len": len(combined_context)}
        )

        # ---------------------------------------------------------------------
        # STEP 4: generate_answer (Final Answer Generation)
        # ---------------------------------------------------------------------
        start_t4 = time.time()
        citations = []
        for c in accumulated_chunks.values():
            citations.append(
                SourceCitation(
                    content=c.get("full_content", c.get("snippet", "")),
                    doc_id=c.get("doc_id", ""),
                    filename=c.get("filename", "Unknown"),
                    chunk_index=c.get("chunk_index", 0),
                    score=c.get("score", 1.0)
                )
            )

        chat_res = llm_service.generate_answer(
            question=question,
            sources=citations
        )
        lat4 = (time.time() - start_t4) * 1000

        state.final_answer = chat_res.answer
        state.used_fallback = chat_res.used_fallback

        in_tok4 = estimate_tokens(question + "".join([c.content for c in citations]))
        out_tok4 = estimate_tokens(chat_res.answer)
        cost4 = calculate_llm_cost(in_tok4, out_tok4)

        state.record_step(
            action="generate_answer",
            input_summary=f"citations_count={len(citations)}",
            result_summary=f"answer_length={len(chat_res.answer)} fallback={chat_res.used_fallback}",
            latency_ms=lat4,
            input_tokens=in_tok4,
            output_tokens=out_tok4,
            step_cost=cost4,
            raw_args={"question": question, "sources_count": len(citations)}
        )

        state.completed = True
        state.termination_reason = "completed"
        return state
