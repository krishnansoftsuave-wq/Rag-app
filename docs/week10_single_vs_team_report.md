# DocuBrain — Week 10 Module 5: Single Agent vs Multi-Agent Team

Track E (developer documentation). The question: does a team of a manager plus two specialists answer developer-documentation questions better than our single agent, and is it worth what it costs?

**Short answer:** by the rule fixed before the race, **keep the team**: it scored +1.60 judge points at 1.32× the cost and 1.25× the latency. The win comes from **reliability, not better answers**. The single agent failed to answer 2 of the 5 questions on every attempt; on the 3 questions both systems answered, quality was tied (4.56 vs 4.56) and the team cost 30% more. The evidence is 5 questions × 1 run, so it is directional (see section 10).

---

## 1. The two contestants

### Single agent (the baseline, unchanged) — `backend/app/agents/rag_agent.py`
One tool-calling loop with 8 tools (hybrid search, refine search, semantic search, keyword search, `python_calculator`, `summarize_context`, `agentic_document_chunker`, `validate_evidence`). Every step re-sends the whole conversation so far to the model.

### Docs squad: a manager plus two specialists — `backend/app/agents/team/`

```
                question
                   │
          ┌────────▼────────┐  call 1: read the specialists' AgentCards, plan
          │     Manager     │  at most one sub-task per specialist
          └───┬─────────┬───┘  (only the specialists the question needs)
     A2A task │         │ A2A task         (run in parallel)
   ┌──────────▼───┐ ┌───▼──────────┐
   │   Concepts   │ │  Reference   │   each: one search tool, ≤ 3 searches,
   │ how and why  │ │ exact values │   hands back compact findings
   │ semantic     │ │ keyword BM25 │   (one sentence + source each)
   └──────────┬───┘ └───┬──────────┘
              └────┬────┘
          ┌────────▼────────┐  call 2: write the cited answer from the findings
          │     Manager     │
          └─────────────────┘
```

| Agent | Its only job | Tool | Instructions in one line |
|---|---|---|---|
| Manager (`manager.py`) | Split the question, then write the answer | none | Group the question's parts by the kind of answer they need; send each specialist at most one sub-task |
| Concepts (`specialists.py`) | Explain how and why things work | `semantic_vector_search` | Use only what the passages say; no numbers unless a passage states them |
| Reference (`specialists.py`) | Find exact facts: values, defaults, limits, prices, lists | `exact_keyword_search` | Copy values exactly; never guess; list what was not found |

Example plan (W22, *"Explain the difference between NovaObject's three storage classes and give the monthly price per GB of each"*):
Concepts gets "Explain the difference between NovaObject's three storage classes", and Reference gets "Provide the monthly price per GB for each of NovaObject's three storage classes". For an exact-fact question (W12, the default queue timeout), the manager sent work to Reference only.

---

## 2. A2A in this build — `backend/app/agents/team/a2a.py`

The hand-offs follow the Agent2Agent (A2A) data model, run in process so network hops do not distort the latency being measured:

- **AgentCard:** each specialist publishes its name, description and skills (`protocolVersion`, `skills`, `defaultInputModes`, ...). The manager reads the cards to decide who gets which part of the question. This is A2A discovery.
- **Task lifecycle:** the manager sends a message (`message/send`); the specialist's task moves `submitted → working → completed | failed` with timestamps.
- **Parts and artifacts:** messages carry `text` and `data` parts. A finished task returns three artifacts: `findings` (all the manager reads), `evidence` (retrieved chunks, kept for citations only) and `transcript` (the specialist's whole conversation, used only by the "full hand-off" experiment).

| | MCP | A2A |
|---|---|---|
| Connects | an agent to **tools and data** | an agent to **other agents** |
| In this app | Artifact Studio server; the public RAG tools endpoint | Manager ↔ Concepts / Reference |
| Discovery | the server lists its tools | the agent publishes an AgentCard |
| Unit of work | one tool call, one result | a task with a lifecycle, messages and artifacts |
| Who decides how | the calling agent | the receiving agent (it plans its own searches) |

---

## 3. Making the race fair

| Control | How |
|---|---|
| Same tests | Same questions, same document, both systems back to back per question, first-runner shuffled |
| Same document | `w10_novacloud`: NovaCloud developer docs (`backend/benchmarks/novacloud_docs.txt`) |
| Same model | `openai/gpt-oss-120b` pinned for every contestant call; model recorded per call; 0 fallbacks |
| Same retrieval | Same hybrid retriever, `top_k`, chunking and query expansion |
| Same budgets | 12 iterations, 40K tokens, 600 s for both (generous, so a budget cut-off does not decide the race; 0 budget stops) |
| No extra steps | The Artifact Studio MCP server was switched off for the race process only; the saved config is unchanged |
| Outages are not answers | A rate limit or LLM outage retries the run for either system; it is never scored |
| Blind judge | `qwen/qwen3.8-27b`, a different model family, outside both systems' token counts; it sees the question, the reference answer, the parts asked for and the documentation pages, never the system name |

### Measurement problems found and fixed before racing
1. **Tokens were estimated** (characters ÷ 4). The client now records the provider-reported usage of every call, including the hidden LLM query-expansion call that every search makes (`track_usage` in `services/llm/client.py`).
2. **Cost used Gemini prices while the app runs on Groq.** It now uses Groq's published prices for gpt-oss-120b: $0.15 / $0.075 cached / $0.60 per 1M input / cached input / output tokens (`services/llm/pricing.py`).
3. **Silent model fallback:** a rate-limited call could switch to a different model mid-race. The model is now pinned and recorded.
4. **Answer-key leak:** pages 12–14 of the NovaCloud PDF list the evaluation questions with their expected answers. The race indexes a copy without them.
5. **Retry-hint bug** (it affected the app too): Groq's "try again in 105ms" was read as 105 *minutes*, putting the model out of action for hours. Fixed, with a test.
6. **The judge could not see invented details.** With only the reference answer, it scored an answer full of unsupported specifics 5/5 for groundedness. It now gets the source pages.
7. **A rate limit inside a specialist became a wrong answer** ("the documentation does not cover this", scored 1/5). A specialist's LLM outage now fails the run, which is retried, exactly as for the single agent. The invalid run was removed and re-run.

---

## 4. Test set

A 24-question set was built (`backend/benchmarks/questions_week10.json`: 17 existing NovaCloud questions, 5 new multi-part, 2 not answerable from the docs). Each question lists the parts it asks for and its source pages. The race ran on **5 of them, one per question type**:

| ID | Type | Question |
|---|---|---|
| W12 | single_fact | What is the default NovaQueue visibility timeout? |
| W22 | multi_part | Explain the difference between NovaObject's three storage classes and give the monthly price per GB of each. |
| W05 | explain | How does NovaSQL differ from NovaDocument? |
| W04 | reasoning | What would be the monthly storage cost for 500 GB of NovaObject Standard storage? |
| W23 | not_in_docs | What is the maximum amount of memory that can be allocated to a NovaFunction? |

---

## 5. Results: the four numbers

Model `openai/gpt-oss-120b` · 5 questions × 1 run per system · source: `backend/results/week10/summary.json`, `race.csv`

| Metric | Single agent | Team | Team vs single |
|---|---|---|---|
| **Quality**: judge mean, 1–5 | 3.13 | **4.73** | +1.60 |
| Pass rate (correctness, completeness and groundedness all ≥ 4) | 40% | **80%** | +40 pp |
| Correctness / completeness / groundedness | 3.4 / 3.4 / 2.6 | 4.8 / 5.0 / 4.4 | |
| **Speed**: latency p50 (rate-limit waits excluded) | **5.2 s** | 6.6 s | 1.25× |
| Latency p95 | **7.4 s** | 10.3 s | |
| **Tokens** per question: input / output | 4,715 / 1,071 | 4,561 / 1,784 | 1.10× in total |
| LLM calls per question | **5.4** | 7.2 | 1.33× |
| **Cost** per question | **$0.00133** | $0.00175 | 1.32× |
| Cost per 1,000 questions | **$1.33** | $1.75 | |
| Failed attempts (retried) / failed answers | 6 / 2 | **0 / 0** | |

### Only the 3 questions both systems answered (W12, W22, W05)

| Metric | Single agent | Team |
|---|---|---|
| Quality, judge mean | 4.56 | 4.56 |
| Latency p50 | **5.2 s** | 6.6 s |
| Tokens per question | **6,274** | 6,497 |
| Cost per question | **$0.00147** | $0.00191 (1.30×) |

### Per question

| Question | Type | Single | Team | What happened |
|---|---|---|---|---|
| W12 | single_fact | 5.00 | 5.00 | Manager sent it to Reference only: 2.9K tokens vs 4.7K for the single agent |
| W22 | multi_part | 4.67 | **5.00** | Both correct; the single agent added unsupported details (example uses, "higher latency") |
| W05 | explain | **4.00** | 3.67 | Both embellished (groundedness 2). The manager copied the Concepts card's skill description into the sub-task, and the over-broad ask produced invented "typical workflow" steps; 10.3K tokens |
| W04 | reasoning | 1.00 | **5.00** | Single agent: gpt-oss called its built-in `python` tool (not enabled) instead of `python_calculator`; HTTP 400 on 3 of 3 attempts. Team: Reference found $0.023 and showed 500 × $0.023 = $11.50 |
| W23 | not_in_docs | 1.00 | **5.00** | Single agent: 2 tool-call parse errors, plus one attempt that kept searching for a value that does not exist, using 18 calls and 39K tokens until one request (8,506 tokens) exceeded the 8K per-minute cap. Team: Reference stopped at its 3-search cap and said the docs do not state it |

### Where the team's tokens go (mean per question)

| Role | LLM calls | Tokens (in + out) | Share | Cost |
|---|---|---|---|---|
| Manager: plan | 1.0 | 583 | 9% | $0.00018 |
| Concepts | 2.0 | 2,105 | 33% | $0.00057 |
| Reference | 3.2 | 2,959 | 47% | $0.00073 |
| Manager: synthesize | 1.0 | 697 | 11% | $0.00027 |

Coordination (plan + synthesis) is 20% of the team's tokens. The hand-off payload itself (sub-tasks sent plus findings returned) averaged about 212 tokens per question, because specialists return findings, not transcripts.

---

## 6. What the numbers say

1. **The team's quality lead is reliability.** All of the +1.60 comes from W04 and W23, where the single agent produced no answer on any attempt. Where both answered, quality tied. Narrow specialists (one tool, ≤ 3 searches, a short context) avoided every failure the generalist hit: a stray built-in tool call, malformed tool calls and a runaway search loop.
2. **The team is slower.** Plan and synthesis are two extra sequential LLM calls. Running the specialists in parallel does not win that time back on questions this short (+1.4 s at p50).
3. **Re-sent context is the real token cost, and it hit the single agent harder here.** The single agent's loop re-sends its growing history on every step; one W23 attempt grew to 39K tokens. The team pays for more calls (7.2 vs 5.4), but each carries a small context, and the hand-offs are compact.
4. **Counted cost favours the single agent; total cost does not.** Per answered question the team costs 1.32× as much. But the single agent's 6 failed attempts consumed another ~47K tokens (≈ $0.0092) that the per-question figure leaves out. Including them, the single agent spent ≈ $0.0032 per question, about 1.8× the team's $0.00175.
5. **Hand-offs can distort the question.** On W05 the manager pasted the skill description into the sub-task; the answer drifted into unsupported detail and cost twice the tokens. Every hand-off is a place to lose or change meaning.

---

## 7. Verdict

**Pre-registered rule** (fixed in `app/evaluation/team_race.py` before the race): keep the team only if its quality beats the single agent's by at least max(0.3, run-to-run noise), it costs at most 2× as much, and its p50 latency is at most 2× as long.

| Check | Value | Needed | Result |
|---|---|---|---|
| Quality gain | +1.60 | ≥ 0.3 | pass |
| Cost ratio | 1.32× | ≤ 2.0× | pass |
| Latency ratio | 1.25× | ≤ 2.0× | pass |

**Keep: the team**, for this setup (gpt-oss-120b on Groq). It answered every question; the single agent failed 2 of 5.

What would change the verdict: the team won on reliability, which is fixable in the single agent. Trimming its toolset (drop `python_calculator` and `agentic_document_chunker`, which invite the stray tool call) and capping how much history it re-sends would likely remove both failures. On the evidence of the 3 questions both answered, that fixed single agent would match the team's quality at roughly 20–25% lower cost and latency. That is the next experiment to run before treating the team as the permanent choice.

---

## 8. When multi-agent is worth it, and when it is not

**Worth it when:**
- A question splits into parts that need different tools or instructions (W22: one part explanatory, one exact values).
- Narrow roles prevent failures a generalist hits: fewer tools means fewer wrong tool calls, and a step cap with a short context means no runaway loops (W04, W23).
- A single conversation would otherwise grow past context or per-request limits; specialists keep each context small.
- The parts are independent and slow enough that running them in parallel beats the plan and synthesis overhead (not the case for 5–10 second questions).
- Different roles could use different models, such as a cheaper model for the specialists. That was not tested here.

**Not worth it when:**
- The question is a single lookup. Planning and synthesis add two calls; here the manager limited the damage by routing to one specialist.
- One source answers the question. The manager's paraphrase can distort it (W05).
- The single agent is already reliable. Then the team buys nothing: equal quality, about 30% more cost and about 25% more latency.

---

## 9. Reproduce

```bash
cd backend
python benchmarks/seed_week10_docs.py                         # index the race document (w10_novacloud)
python benchmarks/run_team_race.py --ids W12,W22,W05,W04,W23 --repeats 1
python benchmarks/run_team_race.py --repeats 3                # the full 24-question race
python benchmarks/run_team_race.py --systems single,team,team_full --ids W22   # full-transcript hand-off experiment
python benchmarks/run_team_race.py --summarize-only           # rebuild race.csv, summary.json, summary.md
python tests/unit/test_team_race.py                           # 17 offline tests
```

The race resumes from `results/week10/runs.jsonl`, so a run stopped by Groq's free-tier limits (200K tokens/day, 8K tokens/minute) continues where it stopped.

---

## 10. Limitations

- **Small sample:** 5 questions, one per type, one run each. Run-to-run noise was not measured (the rule's noise term is 0), so a single different answer could move the per-type results. Treat the verdict as directional; the 24-question, 3-run race is ready to run.
- **LLM judge:** blind, on a different model family, with the source pages, and its rationales were spot-checked. It is still a model.
- **Free tier:** latency excludes rate-limit waits. 12 rate-limited attempts (11 single, 1 team) were discarded and re-run; most came before the client was changed to wait out per-minute limits.
- **Model-specific failures:** the single agent's failures are gpt-oss-120b-on-Groq behaviours. In the live app, the fallback chain (qwen, gpt-oss-20b) would mask some of them by switching model.
- **Not run:** the full-transcript hand-off experiment (`team_full`) is built but was not run in this race.
