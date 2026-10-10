# Week 10 race: single agent vs docs squad

Document `w10_novacloud` · contestant model `openai/gpt-oss-120b` · judge `qwen/qwen3.8-27b` · 5 paired runs per system (5 questions × repeats [1]) · errored runs: 0

## The four numbers

| Metric | single | team |
|---|---|---|
| Quality, judge mean (1-5) | 3.13 | 4.73 |
| Pass rate (all three scores >= 4), % | 40.0 | 80.0 |
| Correctness / completeness / groundedness | 3.40 / 3.40 / 2.60 | 4.80 / 5.00 / 4.40 |
| Latency p50, s (no rate-limit waits) | 5.2 | 6.6 |
| Latency p95, s (no rate-limit waits) | 7.4 | 10.3 |
| Tokens per question, input | 4715 | 4561 |
| Tokens per question, output | 1071 | 1784 |
| LLM calls per question | 5.4 | 7.2 |
| Cost per question, USD | 0.001327 | 0.001751 |
| Cost per 1,000 questions, USD | 1.327 | 1.751 |
| Quality by repeat | [3.133] | [4.733] |
| Failed attempts, retried (not rate limits) | 6 | 0 |
| Failed answers (every attempt failed) | 2 | 0 |

### Only the questions every system answered (3 runs per system)

| Metric | single | team |
|---|---|---|
| Quality, judge mean (1-5) | 4.56 | 4.56 |
| Latency p50, s | 5.2 | 6.6 |
| Tokens per question (in + out) | 6274 | 6497 |
| Cost per question, USD | 0.001465 | 0.001911 |

## Team vs single

- Quality: +1.60 judge points; pass rate +40.0 pp
- Tokens: 1.096x (input 0.967x); LLM calls 1.333x
- Cost: 1.319x; latency p50: 1.25x
- Per question (mean quality, ±0.5 = tie): team better 2, tie 3, single better 0
- Categories where the team gains >= 0.3: multi_part, not_in_docs, reasoning

## By question type

| Category | Runs | Quality single | Quality team | Tokens single | Tokens team | Cost single | Cost team |
|---|---|---|---|---|---|---|---|
| explain | 1 | 4.00 | 3.67 | 5334 | 10267 | 0.001397 | 0.002980 |
| multi_part | 1 | 4.67 | 5.00 | 8831 | 6304 | 0.001957 | 0.001998 |
| not_in_docs | 1 | 1.00 | 5.00 | 8880 | 8700 | 0.001814 | 0.001968 |
| reasoning | 1 | 1.00 | 5.00 | 1232 | 3534 | 0.000425 | 0.001053 |
| single_fact | 1 | 5.00 | 5.00 | 4656 | 2919 | 0.001042 | 0.000755 |

## Where the team tokens go (mean per question)

| Role | LLM calls | Input tokens | Output tokens | Share of tokens | Cost, USD |
|---|---|---|---|---|---|
| manager.plan | 1.0 | 375 | 208 | 9% | 0.000181 |
| concepts | 2.0 | 1543 | 562 | 33% | 0.000569 |
| reference | 3.2 | 2323 | 636 | 47% | 0.000726 |
| manager.synthesize | 1.0 | 320 | 377 | 11% | 0.000274 |

Hand-off payload (sub-tasks sent + reports returned, ≈chars/4): 212 tokens per question.

## Per question (mean judge quality over repeats)

| Question | Category | single | team |
|---|---|---|---|
| W04 | reasoning | 1.00 | 5.00 |
| W05 | explain | 4.00 | 3.67 |
| W12 | single_fact | 5.00 | 5.00 |
| W22 | multi_part | 4.67 | 5.00 |
| W23 | not_in_docs | 1.00 | 5.00 |

## Verdict (pre-registered rule)

Keep the team only if its judge quality beats the single agent by at least max(0.3, run-to-run noise = 0.0) AND it costs at most 2.0x AND its p50 latency is at most 2.0x the single agent's.

- quality_gain: 1.6 (needed >= 0.3) → pass
- cost_ratio: 1.319 (needed <= 2.0) → pass
- latency_ratio: 1.25 (needed <= 2.0) → pass

**Keep: team**
