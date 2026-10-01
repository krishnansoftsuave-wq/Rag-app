# DocuBrain — Week 7 Module 4 Evaluation Report: Adaptive RAG Agent vs. Fixed RAG Workflow

---

## 1. Problem Statement

Retrieval-Augmented Generation (RAG) systems typically follow a static pipeline: user query → document search → LLM answer generation. While efficient for straightforward factual queries, static workflows can fail when initial retrieval yields incomplete context or ambiguous evidence. 

An **Adaptive RAG Agent** introduces a runtime decision loop (`PLAN` → `ACT` → `OBSERVE` → `DECIDE`), allowing the system to dynamically refine queries, gather follow-up evidence, and validate context sufficiency before generating an answer. However, agentic loops introduce token overhead, increased latency, and financial cost.

This report evaluates whether an Adaptive RAG Agent is justified over a Fixed RAG Workflow based on empirical measurements across 10 diverse benchmark questions.

---

## 2. System Architectures

### A. Adaptive RAG Agent (`backend/app/agents/rag_agent.py`)
- **Control Loop**: Explicit hand-built `PLAN / ACT / OBSERVE` loop (zero framework abstractions like LangChain/LangGraph).
- **Dynamic Routing**:
  1. Executes `search_document` for initial retrieval.
  2. Evaluates evidence completeness using `validate_evidence`.
  3. If evidence is sufficient → calls `generate_answer` and terminates cleanly.
  4. If evidence is insufficient → extracts missing information topics, formulates a targeted query, executes `refine_document_search`, and validates again.
- **Safety Enforcement**: Enforces 4 strict safety budgets on every loop iteration.

### B. Fixed RAG Workflow (`backend/app/workflows/fixed_rag_workflow.py`)
- **Control Flow**: Hard-coded, deterministic sequence without LLM routing.
- **Pipeline Steps**: `search_document` → `refine_document_search` → `validate_evidence` → `generate_answer`.
- **Fair Comparison**: Uses the exact same underlying retriever, top_k configuration, LLM service, and benchmark questions as the Agent.

---

## 3. RAG Tools

DocuBrain implements 3 single-responsibility tools wrapping existing services (`backend/app/agents/tools.py`):

1. **`search_document(document_id, query, top_k)`**:
   - Initial evidence retrieval using hybrid vector search (ChromaDB + SentenceTransformers `jina-embeddings-v2-base-en`) and sparse keyword matching (Rank-BM25) fused via Reciprocal Rank Fusion (RRF).
2. **`refine_document_search(document_id, query, top_k)`**:
   - Targeted follow-up retrieval addressing specific missing information gaps identified during evidence validation.
3. **`validate_evidence(question, retrieved_context)`**:
   - Evaluates context completeness and returns structured output (`sufficient`, `reason`, `missing_information`).

---

## 4. Safety Budgets

To prevent infinite loops, run-away costs, and latency spikes, the Agent enforces 4 strict safety limits (`backend/app/agents/budgets.py`):

1. **`MAX_ITERATIONS`**: Limit = `8` steps
2. **`MAX_TOKENS`**: Limit = `8,000` tokens (cumulative across all LLM calls)
3. **`MAX_COST`**: Limit = `$0.05` per question
4. **`MAX_WALL_CLOCK_SECONDS`**: Limit = `15.0` seconds

If any budget threshold is exceeded, the agent immediately terminates execution with a clean status code (`termination_reason`) and synthesizes a best-effort response from accumulated context.

---

## 5. Budget Termination Example

An intentional budget termination test was performed with `MAX_ITERATIONS=2` on a multi-step query requiring iterative refinement.

### Log Output (`logs/budget_termination.log`)
```
[Agent] question_id=test_budget_max_iter step=1 action=search_document input_summary="query='What happens if authentication fails during deployment...'" result_summary="results=4" latency_ms=2619.5 tokens=0 cost=$0.00000
[Agent] question_id=test_budget_max_iter step=2 action=validate_evidence input_summary="context_length=1499" result_summary="sufficient=False" latency_ms=13633.8 tokens=603 cost=$0.00007
[Agent] question_id=test_budget_max_iter termination=max_iterations total_steps=2 total_tokens=603 total_cost=$0.00007
[Agent] question_id=final step=3 action=generate_answer input_summary="citations=4" result_summary="answer_length=438" latency_ms=16077.2 tokens=504 cost=$0.00006
```
> **Result**: The agent detected `iteration_count >= MAX_ITERATIONS`, logged `termination=max_iterations`, avoided an infinite loop, and cleanly generated a best-effort answer.

---

## 6. 10-Question Benchmark Suite

The evaluation suite (`backend/benchmarks/questions.json`) consists of 10 questions covering 6 distinct categories:

| ID | Category | Question Summary |
| :--- | :--- | :--- |
| **Q1** | Simple Factual | Core technologies powering DocuBrain vector search & LLM synthesis |
| **Q2** | Simple Factual | Default chunk size and overlap configuration |
| **Q3** | Simple Factual | Sparse lexical retrieval algorithm used alongside dense vectors |
| **Q4** | Multi-Section | Document upload and chunking workflow summary |
| **Q5** | Comparison | Standard Chunking vs Late Chunking context preservation |
| **Q6** | Multi-Section | Reciprocal Rank Fusion (RRF) rank calculation formula |
| **Q7** | Comparison | Gemini API online execution vs Local Fallback Mode |
| **Q8** | Ambiguous | System behavior when authentication credentials fail during deployment |
| **Q9** | Query Refinement | Evidence validation & query refinement sequence for missing context |
| **Q10** | Multi-Hop | Trace end-to-end multi-hop retrieval and answer synthesis |

---

## 7. Comparative Metrics Summary

Empirical measurements collected from live 10-question benchmark execution (`results/summary.json` & `results/race.csv`):

| Metric | Adaptive RAG Agent | Fixed RAG Workflow | Winner |
| :--- | :--- | :--- | :--- |
| **Pass Rate** | **100.0%** | **100.0%** | Tie |
| **P50 Latency** | **13.58s** (13,580.2 ms) | **10.53s** (10,527.8 ms) | **Fixed Workflow** |
| **Total Tokens** | **12,888** | **12,323** | **Fixed Workflow** |
| **Cost / Question** | **$0.00020** | **$0.00010** | **Fixed Workflow** |

---

## 8. Final Verdict

> **Fixed RAG Workflow is recommended for standard QA workloads.** Across the 10-question benchmark, the Fixed Workflow achieved an identical 100% pass rate while delivering **22% lower P50 latency** (10.53s vs 13.58s), **565 fewer total tokens** (12,323 vs 12,888 tokens), and **50% lower cost per question** ($0.00010 vs $0.00020). For straightforward document QA, the fixed workflow avoids unnecessary loop iterations and token overhead.
