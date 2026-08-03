"""Chunking: split loaded Documents into overlapping, token-measured
chunks ready for embedding. Sizes come from app.config — Phase 5 tunes
them against the eval set, so nothing is hardcoded here."""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS

# Token-based measurement (tiktoken cl100k_base, what text-embedding-3-*
# uses) rather than characters: "500-800 tokens" is only enforceable if
# the splitter counts tokens the same way the embedding model does.
_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE_TOKENS,
    chunk_overlap=CHUNK_OVERLAP_TOKENS,
)


def chunk_documents(pages: list[Document]) -> list[Document]:
    """Split per-page Documents into chunks, preserving page metadata so
    answers can cite where they came from."""
    return _splitter.split_documents(pages)
