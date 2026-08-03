"""Supabase client wrapper — the only place a connection is created.

Everything else imports get_client() from here; no raw connection
strings or per-module clients scattered across the codebase.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import SUPABASE_KEY, SUPABASE_URL


@lru_cache(maxsize=1)
def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set (see .env.example)"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)
