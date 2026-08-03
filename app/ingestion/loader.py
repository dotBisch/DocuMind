"""Document loading: turn an uploaded PDF or text file into LangChain
Documents, one per page, skipping unusable pages instead of crashing."""

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


class UnsupportedFileType(ValueError):
    pass


def load_document(path: Path) -> list[Document]:
    """Load a file into per-page Documents, dropping empty/whitespace-only
    pages (scanned images, blank pages) with a warning rather than an error
    — one bad page shouldn't sink a 100-page upload."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(
            f"unsupported file type {suffix!r} (supported: {sorted(SUPPORTED_EXTENSIONS)})"
        )

    if suffix == ".pdf":
        pages = PyPDFLoader(str(path)).load()
    else:
        pages = TextLoader(str(path), encoding="utf-8").load()

    usable = []
    for i, page in enumerate(pages):
        if page.page_content and page.page_content.strip():
            usable.append(page)
        else:
            logger.warning("skipping empty/non-text page %d of %s", i + 1, path.name)

    if not usable:
        logger.warning("%s contained no extractable text", path.name)
    return usable
