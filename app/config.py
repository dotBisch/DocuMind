"""Environment/settings loading and tunable constants.

Chunking, retrieval-k, and model choices live here — never hardcoded
inline — because Phase 5 tunes them against the eval set.
"""

import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini free tier makes the demo reproducible at zero cost. The model
# defaults to 3072 dims but supports Matryoshka truncation; we request
# 1536 to match the chunks.embedding column (schema.sql) — changing
# model or dimension = migration.
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 1536

# 600 tokens ≈ 2-3 paragraphs: small enough that a retrieved chunk is
# mostly signal, large enough to keep an explanation intact. Mid-range of
# the plan's 500-800 band; Phase 5 revisits against eval results.
CHUNK_SIZE_TOKENS = 600
# 75 tokens = 12.5% overlap so sentences straddling a boundary appear
# whole in at least one chunk.
CHUNK_OVERLAP_TOKENS = 75

# How many chunks the similarity search returns per query (Phase 4/5).
RETRIEVAL_K = 4

# Grounded answering is a retrieval problem more than a model problem
# at this scale, so: the fastest model with actual free-tier quota.
# Pinned (not gemini-flash-latest) because Phase 5's measured accuracy
# is only meaningful against a fixed model; the -latest alias can change
# models silently. Preview caveat accepted — new accounts get zero
# free-tier quota on the older GA models (2.0/2.5-flash), so preview is
# the only pinned free option. Temperature 0: deterministic Q&A.
LLM_MODEL = "gemini-3-flash-preview"
LLM_TEMPERATURE = 0.0
