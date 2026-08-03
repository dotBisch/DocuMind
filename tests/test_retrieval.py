from app.retrieval.prompt import (
    NOT_FOUND_TEXT,
    SYSTEM_PROMPT,
    build_user_prompt,
    format_context,
)
from app.retrieval.search import RetrievedChunk


def _chunk(content: str, page: int | None = 0, similarity: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        id="c1",
        document_id="d1",
        content=content,
        metadata={"page": page} if page is not None else {},
        similarity=similarity,
    )


def test_context_is_numbered_for_citation():
    ctx = format_context([_chunk("first excerpt"), _chunk("second excerpt")])
    assert "[1]" in ctx and "[2]" in ctx
    assert "first excerpt" in ctx and "second excerpt" in ctx


def test_context_includes_human_page_numbers():
    # loader pages are 0-based; humans read 1-based
    ctx = format_context([_chunk("text", page=4)])
    assert "(page 5)" in ctx


def test_context_handles_missing_page_metadata():
    ctx = format_context([_chunk("text", page=None)])
    assert "page" not in ctx.split("\n")[0]


def test_user_prompt_contains_question_and_context():
    prompt = build_user_prompt("What is the deploy process?", [_chunk("ship it")])
    assert "What is the deploy process?" in prompt
    assert "ship it" in prompt


def test_system_prompt_pins_grounding_rules():
    # the three properties eval depends on: context-only, citations, honest miss
    assert "ONLY" in SYSTEM_PROMPT
    assert "[1]" in SYSTEM_PROMPT
    assert NOT_FOUND_TEXT in SYSTEM_PROMPT
