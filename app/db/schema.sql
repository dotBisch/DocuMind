-- DocuMind schema — single source of truth (no schema-in-code drift).
-- Idempotent: safe to re-run on a project where some objects already exist.
-- Run in the Supabase SQL editor (or via psql).

create extension if not exists vector;

create table if not exists sessions (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz default now()
);

create table if not exists documents (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references sessions(id) on delete cascade,
    filename text not null,
    page_count int,
    created_at timestamptz default now()
);

create table if not exists chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid references documents(id) on delete cascade,
    session_id uuid references sessions(id) on delete cascade,
    content text not null,
    -- 1536 dims = OpenAI text-embedding-3-small (set in app/config.py);
    -- changing the embedding model means re-creating this column + index.
    embedding vector(1536),
    metadata jsonb,
    created_at timestamptz default now()
);

-- RLS on, with no policies: the auto-generated Supabase REST API (anon /
-- authenticated keys) can't touch these tables at all. Our FastAPI backend
-- uses the service_role key, which bypasses RLS — server-side only.
alter table sessions enable row level security;
alter table documents enable row level security;
alter table chunks enable row level security;

-- HNSW over IVFFlat: better recall at low latency for our scale (a few
-- thousand chunks/session), and no training step — IVFFlat needs data
-- present before building lists, which complicates a fresh deploy.
-- Cosine distance matches how the embedding model is trained/normalized.
create index if not exists chunks_embedding_hnsw_idx
    on chunks using hnsw (embedding vector_cosine_ops);

-- Every query filters by session_id first (isolation guarantee), so it
-- needs its own btree index.
create index if not exists chunks_session_id_idx
    on chunks (session_id);

-- Session-scoped similarity search, called via Supabase RPC.
-- Filtering happens *inside* the function, so isolation is enforced at
-- the query layer — callers cannot get cross-session rows.
create or replace function match_chunks(
    query_embedding vector(1536),
    match_session_id uuid,
    match_count int
)
returns table (
    id uuid,
    document_id uuid,
    content text,
    metadata jsonb,
    similarity float
)
language sql stable
as $$
    select
        chunks.id,
        chunks.document_id,
        chunks.content,
        chunks.metadata,
        1 - (chunks.embedding <=> query_embedding) as similarity
    from chunks
    where chunks.session_id = match_session_id
    order by chunks.embedding <=> query_embedding
    limit match_count;
$$;
