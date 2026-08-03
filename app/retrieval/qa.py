"""Q&A orchestration: retrieve -> prompt -> LLM -> answer + sources.

Lives in retrieval/ (not the API layer) so it can be exercised by the
eval harness in Phase 5 without HTTP.
"""

from dataclasses import dataclass
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import GEMINI_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from app.retrieval.prompt import NOT_FOUND_TEXT, SYSTEM_PROMPT, build_user_prompt
from app.retrieval.search import RetrievedChunk, search_chunks


@dataclass
class Answer:
    answer: str
    sources: list[RetrievedChunk]


@lru_cache(maxsize=1)
def _llm() -> ChatGoogleGenerativeAI:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY must be set (see .env.example)")
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL, temperature=LLM_TEMPERATURE, google_api_key=GEMINI_API_KEY
    )


def answer_question(session_id: str, question: str) -> Answer:
    chunks = search_chunks(session_id, question)
    if not chunks:
        # nothing ingested in this session — don't waste an LLM call
        return Answer(answer=NOT_FOUND_TEXT, sources=[])

    response = _llm().invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=build_user_prompt(question, chunks)),
        ]
    )
    return Answer(answer=str(response.content), sources=chunks)
