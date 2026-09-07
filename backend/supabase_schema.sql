-- =========================================================================
-- Predictive Insight Dashboard - Phase 1 (Data Ingestion) - Supabase schema
-- =========================================================================
-- Run this script in the Supabase SQL editor. It is idempotent: re-running
-- it will not drop existing data.
--
-- The storage bucket referenced in .env (`SUPABASE_STORAGE_BUCKET`, default
-- "datasets") must be created separately via the Supabase dashboard OR by
-- running the storage bucket block at the bottom of this file.
-- =========================================================================

-- ---- Extensions ----------------------------------------------------------
create extension if not exists "pgcrypto";        -- gen_random_uuid()

-- ---- Status enum ---------------------------------------------------------
do $$
begin
    if not exists (select 1 from pg_type where typname = 'dataset_status') then
        create type dataset_status as enum (
            'uploaded',
            'detecting',
            'processing',
            'validated',
            'failed'
        );
    end if;
end$$;

-- ---- datasets table ------------------------------------------------------
create table if not exists public.datasets (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid,                              -- FK to auth.users (future)
    filename            text not null,
    original_filename   text not null,
    source_type         text not null,                     -- 'file' | 'sql_database' | 'zip_archive'
    file_format         text not null,                     -- 'csv' | 'xlsx' | ...
    mime_type           text,
    file_size           bigint not null default 0,
    storage_path        text,                              -- object path in Supabase Storage
    row_count           integer,
    column_count        integer,
    status              dataset_status not null default 'uploaded',
    schema              jsonb,
    metadata            jsonb,
    warnings            jsonb not null default '[]'::jsonb,
    errors              jsonb not null default '[]'::jsonb,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

comment on table public.datasets is
    'One row per ingested dataset. Populated by Phase 1 ingestion API.';

-- Bring an existing table up to date (safe if it already matches).
alter table public.datasets
    add column if not exists warnings    jsonb not null default '[]'::jsonb,
    add column if not exists errors      jsonb not null default '[]'::jsonb,
    add column if not exists metadata    jsonb,
    add column if not exists schema      jsonb,
    add column if not exists profile     jsonb,                    -- Phase 2 result
    add column if not exists profiled_at timestamptz;              -- Phase 2 completion time

-- ---- Indexes -------------------------------------------------------------
create index if not exists idx_datasets_status       on public.datasets (status);
create index if not exists idx_datasets_user_id      on public.datasets (user_id);
create index if not exists idx_datasets_created_at   on public.datasets (created_at desc);
create index if not exists idx_datasets_source_type  on public.datasets (source_type);
create index if not exists idx_datasets_file_format  on public.datasets (file_format);
-- JSONB GIN indexes for future filtering by metadata/schema/profile keys
create index if not exists idx_datasets_metadata_gin on public.datasets using gin (metadata);
create index if not exists idx_datasets_schema_gin   on public.datasets using gin (schema);
create index if not exists idx_datasets_profile_gin  on public.datasets using gin (profile);
create index if not exists idx_datasets_profiled_at  on public.datasets (profiled_at desc);

-- ---- updated_at trigger --------------------------------------------------
create or replace function public.set_updated_at() returns trigger
    language plpgsql
as $$
begin
    new.updated_at := now();
    return new;
end$$;

drop trigger if exists trg_datasets_updated_at on public.datasets;
create trigger trg_datasets_updated_at
    before update on public.datasets
    for each row
    execute function public.set_updated_at();

-- =========================================================================
-- Row Level Security (auth-ready)
-- -------------------------------------------------------------------------
-- Phase 1 uses the service_role key from the backend, which BYPASSES RLS.
-- We still enable RLS and add placeholder policies so switching to
-- end-user JWTs in Phase 3+ requires no schema changes.
-- =========================================================================
alter table public.datasets enable row level security;

-- Owners can read/write their own datasets
drop policy if exists "datasets_owner_select" on public.datasets;
create policy "datasets_owner_select"
    on public.datasets
    for select
    using (auth.uid() = user_id);

drop policy if exists "datasets_owner_insert" on public.datasets;
create policy "datasets_owner_insert"
    on public.datasets
    for insert
    with check (auth.uid() = user_id);

drop policy if exists "datasets_owner_update" on public.datasets;
create policy "datasets_owner_update"
    on public.datasets
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "datasets_owner_delete" on public.datasets;
create policy "datasets_owner_delete"
    on public.datasets
    for delete
    using (auth.uid() = user_id);


-- =========================================================================
-- Storage bucket (optional convenience)
-- -------------------------------------------------------------------------
-- Uncomment to auto-provision the bucket. Prefer the dashboard for prod so
-- CORS + file-size limits can be tuned interactively.
-- =========================================================================
-- insert into storage.buckets (id, name, public)
-- values ('datasets', 'datasets', false)
-- on conflict (id) do nothing;

-- Storage policies: allow authenticated users to CRUD objects inside
-- `datasets/{user_id}/...`. Adjust when Phase 3 auth is wired.
-- create policy "storage_owner_read"
--     on storage.objects for select
--     using (
--         bucket_id = 'datasets'
--         and (storage.foldername(name))[2] = auth.uid()::text
--     );
-- create policy "storage_owner_write"
--     on storage.objects for insert
--     with check (
--         bucket_id = 'datasets'
--         and (storage.foldername(name))[2] = auth.uid()::text
--     );
