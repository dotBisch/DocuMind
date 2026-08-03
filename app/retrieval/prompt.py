"""Prompt assembly for grounded Q&A.

The instructions pin the model to the provided context: it must answer
only from the numbered excerpts, cite them, and say so when the answer
isn't there — hallucinated answers are worse than honest misses.
"""

from app.retrieval.search import RetrievedChunk

NOT_FOUND_TEXT = "I couldn't find an answer to that in the uploaded documents."

SYSTEM_PROMPT = f"""You are DocuMind, an assistant that answers questions about an \
internal knowledge base.

Rules:
- Answer ONLY using the numbered context excerpts provided. Do not use outside knowledge.
- Cite the excerpts you used inline, like [1] or [2][3].
- If the excerpts do not contain the answer, reply exactly: "{NOT_FOUND_TEXT}"
- Be concise and factual."""


def format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        page = chunk.metadata.get("page")
        page_note = f" (page {page + 1})" if isinstance(page, int) else ""
        blocks.append(f"[{i}]{page_note}\n{chunk.content}")
    return "\n\n---\n\n".join(blocks)


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    return f"""Context excerpts:

{format_context(chunks)}

Question: {question}"""
