# What breaks first at 10x

**The rate limit breaks first.** At 10,470 tokens per agent query, Groq's on-demand limits (about 23,000 tokens per minute across all 3 models) cap us at **~2.2 queries per minute**. 10x of a modest 2 queries/min needs **~210,000 tokens per minute: 9x over the cap**. Cost at that rate is only **$0.15 per minute**.

Today's real volume isn't measured yet: the request log holds only the drill traffic. "2 queries per minute today" is therefore an assumption, and it is about what the current limits can carry anyway. The conclusion holds at any volume above ~0.2 queries per minute. Latency degrades only *because of* the limit: calls wait out cooldowns or fall back to the 5x-pricier model.

## Evidence

- **Tokens per query:** 10,470 for the traced bad answer (`docs/week11/cost_by_stage.md`), and 14,777 for an agent query in the end-to-end test.
- **Groq limits,** taken from the 429 errors in this week's runs:
  - `openai/gpt-oss-120b`: TPM limit 8,000
  - `qwen/qwen3.8-27b`: ITPM limit 7,000
  - `openai/gpt-oss-20b`: TPM limit 8,000
- **Already happening at 1x:**
  - The team-mode query in the end-to-end test failed with a 503 after all three models returned 429 (trace status `error`).
  - The traced bad answer itself fell back to qwen for 3 of its 7 calls, and those calls were 82% of its cost.
- **Cost:** $0.0075 per agent query, measured. 20 queries/min × 60 × 24 × $0.0075 is about **$216/day at a sustained 10x peak**. That's a budget line item, not an outage.

## Plan

1. Move to Groq's Dev tier for higher TPM, or add a second provider through a router such as LiteLLM, so fallbacks go to a model with spare quota.
2. Cut tokens per query, which raises the queries a limit allows:
   - Cap the history the agent re-sends each turn; the last turn alone was 3,723 input tokens.
   - Skip query expansion for exact-identifier searches.
3. Add a semantic cache for repeated questions. In the seeded log, code-sample questions are 30% of traffic and most of them are repeats.
