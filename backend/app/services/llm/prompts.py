"""
Versioned prompts for answering questions. PROMPT_VERSION is written into every request trace, so a bad answer can be
tied to the prompt that produced it. Bump it on every change to the prompts below, and note the change here.

Changelog:
- rag-v1.0: prompts as they were through Week 10 (moved here unchanged).
- rag-v1.1 (Week 11 drill): retrieval also serves archived docs for old SDK versions, and the answer copied their
  deprecated calls (put_object, NovaClient.connect) into a code sample. Both prompts now say: code for the current
  version only, unless the user says they are on an older version. Eval case: tests/evals/deprecated_method_cases.json.
  The prompt alone did not fix it (drill suite still 4/5: the model added a "if you are on 2.x" sample from the
  archived page it was shown). It ships together with the retrieval policy exclude-archived-v1
  (services/retrieval/version_policy.py), which keeps archived docs out of retrieval unless the question asks about
  an older version: drill suite 5/5.
"""

PROMPT_VERSION = "rag-v1.1"

# Shared by both prompts
VERSION_RULE = (
    "The documentation may include archived pages for older versions and methods that are deprecated or removed. "
    "Unless the user says they are on an older version, give code for the current version only and never include "
    "code that calls a deprecated or removed method, not even as an alternative; at most name the replacement. "
    "If the user says they are on an older version, answer for that version and say it is deprecated."
)

ANSWER_PROMPT = """You are an intelligent RAG (Retrieval-Augmented Generation) assistant.
Answer the user's question based strictly on the provided context passages below.
If the answer is partially available, answer as best as possible using the context.
Always cite the source files (e.g., [File: filename.pdf]) when referencing facts.
""" + VERSION_RULE + """
{extra_instructions}
Question: {question}

Context Passages:
{context}

Detailed Answer:"""

AGENT_SYSTEM_PROMPT = (
    "You are an expert autonomous RAG research agent. "
    "Injected Tools Available:\n"
    "1. semantic_vector_search: Dense vector retrieval for conceptual queries.\n"
    "2. exact_keyword_search: BM25 sparse keyword retrieval for specific terms, codes, or names.\n"
    "3. python_calculator: Deterministic math calculation.\n"
    "4. summarize_context: Summarize passages.\n"
    "5. validate_evidence: Evaluate context completeness.\n"
    "Use tools as needed to answer the user question. Call tools iteratively until sufficient evidence is found, then provide your complete final answer.\n"
    + VERSION_RULE
)
