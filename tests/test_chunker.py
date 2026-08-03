import tiktoken
from langchain_core.documents import Document

from app.config import CHUNK_SIZE_TOKENS
from app.ingestion.chunker import chunk_documents

_enc = tiktoken.get_encoding("cl100k_base")


def _tokens(text: str) -> int:
    return len(_enc.encode(text))


def _fake_page(page: int, paragraphs: int = 20) -> Document:
    text = "\n\n".join(
        f"Section {page}.{i}: Operational guidance for scenario {i}. "
        "When the alert fires, check the dashboard, confirm the deploy "
        "window, and follow the escalation matrix before paging anyone."
        for i in range(paragraphs)
    )
    return Document(page_content=text, metadata={"page": page})


def test_short_doc_single_chunk():
    doc = Document(page_content="A single short note.", metadata={"page": 0})
    chunks = chunk_documents([doc])
    assert len(chunks) == 1
    assert chunks[0].page_content == "A single short note."


def test_hundred_page_doc_respects_token_limit():
    pages = [_fake_page(p) for p in range(100)]
    chunks = chunk_documents(pages)
    # a 100-page doc must actually split...
    assert len(chunks) > 100
    # ...and every chunk must respect the configured token budget
    assert all(_tokens(c.page_content) <= CHUNK_SIZE_TOKENS for c in chunks)


def test_chunks_keep_page_metadata_for_citation():
    pages = [_fake_page(p) for p in range(3)]
    chunks = chunk_documents(pages)
    assert {c.metadata.get("page") for c in chunks} == {0, 1, 2}


def test_consecutive_chunks_overlap():
    chunks = chunk_documents([_fake_page(0, paragraphs=60)])
    assert len(chunks) >= 2
    # overlap means the start of chunk 2 also appears at the end of chunk 1
    head = chunks[1].page_content[:40]
    assert head in chunks[0].page_content


def test_empty_input_returns_no_chunks():
    assert chunk_documents([]) == []


def test_whitespace_only_page_produces_no_chunks():
    doc = Document(page_content="   \n\n  ", metadata={"page": 0})
    assert chunk_documents([doc]) == []
