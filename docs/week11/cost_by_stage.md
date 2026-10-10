# Cost per query by stage

**Request:** the bad code-sample answer: a real `/chat` request in agent mode with prompt `rag-v1.0` (it is the template for the planted trace, `backend/results/week11/plant_template.json`).

**Where the numbers come from:** token counts are the ones Groq reported for each call. Prices are in `app/services/llm/pricing.py`, checked 2026-10-09, in USD per 1M tokens:

| Model | Input | Output |
|---|---|---|
| gpt-oss-120b | 0.15 | 0.60 |
| qwen3.8-27b | 0.80 | 4.00 |

## By stage

| Stage | Cost (USD) | Share | Latency (ms) | What is in it |
|---|---|---|---|---|
| Retrieval | 0.000410 | 5.5% | 2,086 | 2 searches. Each one's cost is its query-expansion LLM call; embeddings run locally, so they cost $0. |
| Generation | 0.006102 | 81.7% | 3,971 | 3 agent LLM turns, including the final answer. |
| Tools | 0.000953 | 12.8% | 1,775 | MCP server selection and `validate_evidence`. |
| **Total** | **0.007465** | 100% | 7,836 | 7 LLM calls, 10,470 tokens (8,516 in, 256 of them cached; 1,954 out). |

## By span

`child` means the span ran inside the span above it. Its cost isn't counted again in the parent.

| Span | Stage | Nesting | ms | In tokens | Out tokens | USD | Model |
|---|---|---|---|---|---|---|---|
| mcp_select_server | tool | top | 1,451 | 290 | 112 | 0.000111 | gpt-oss-120b |
| agent_llm_step | generation | top | 903 | 998 | 92 | 0.001166 | qwen3.8-27b |
| tool:semantic_vector_search | retrieval | top | 1,119 | 0 | 0 | 0 | |
| ↳ retrieval | retrieval | child | 1,119 | 159 | 269 | 0.000185 | gpt-oss-120b |
| tool:exact_keyword_search | retrieval | top | 966 | 0 | 0 | 0 | |
| ↳ retrieval | retrieval | child | 966 | 155 | 336 | 0.000225 | gpt-oss-120b |
| agent_llm_step | generation | top | 2,161 | 2,463 | 798 | 0.000829 | gpt-oss-120b |
| tool:validate_evidence | tool | top | 323 | 728 | 65 | 0.000842 | qwen3.8-27b |
| agent_llm_step | generation | top | 907 | 3,723 | 282 | 0.004106 | qwen3.8-27b |

## What this says before optimising anything

- **The fallback model accounts for most of the cost.** Three calls went to `qwen3.8-27b` because `gpt-oss-120b` was rate-limited. Those 3 of the 7 calls cost $0.006114, which is **82%** of the request. The last agent turn alone, which carried the longest history (3,723 input tokens), cost $0.0041.
- **On the primary model the same request would cost about $0.0024, a third of what it cost.** The 3 qwen calls used 5,449 input and 439 output tokens. At gpt-oss-120b rates that is $0.0011 instead of $0.0061; add $0.0014 for the other calls. So the cheapest fix is staying within the rate limit, not trimming prompts.
- **Retrieval is cheap.** It costs $0.0004 (5.5%), and that is all query expansion. Removing expansion would save at most 5.5%.
