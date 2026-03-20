---
name: rag-llm-patterns
description: Expert in RAG, LLM synthesis, and ContextBuilder architecture.
---
# RAG & LLM Patterns

**Trigger:** "RAG", "LLM", "Claude API", "context", "rapor üret", "insight"

**Description:**
Knows the AI synthesis layer architecture.
- **Embeddings:** sentence-transformers all-MiniLM-L6-v2 (local, free).
- **Vector Store:** ChromaDB with collection "investment_news".
- **ContextBuilder:** Assembles ContextPackage before any LLM call.
- **LLMClient:** Uses anthropic SDK async, model claude-sonnet-4-20250514.

All prompts are in prompts.py as string constants.
LLM responses are parsed as JSON and validated with Pydantic.
Blind spots: always include "what_i_might_be_missing" in every analysis.
Never call LLM for data that can be computed — LLM is synthesis and reasoning only.
