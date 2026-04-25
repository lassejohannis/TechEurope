-- Migration 003: align Postgres schema with code conventions across WS-2/4/5.
--
-- WS-0's original schema (001_init.sql) used `entities.type/attributes`,
-- a polymorphic `facts.object/object_type` pair, and `derived_from text[]`.
-- Code in WS-2 (resolver), WS-4 (API/MCP), and WS-5 (Neo4j projection) was
-- written against `entity_type/attrs/object_id/object_literal/source_id`.
-- 15+ Python files across 3 workstreams use the code convention.
-- This migration aligns Postgres to the code (one file vs. dozens of edits).
--
-- Safe because entities/facts/resolutions all have 0 rows when applied.

-- ─────────────────────────────────────────────────────────────────────────
-- entities: rename type → entity_type, attributes → attrs;
--           add inference_embedding for Tier-B context-rich embeddings.
-- ─────────────────────────────────────────────────────────────────────────
alter table entities rename column type to entity_type;
alter table entities rename column attributes to attrs;
alter index entities_type_idx rename to entities_entity_type_idx;
alter index entities_attributes_gin rename to entities_attrs_gin;

alter table entities add column if not exists inference_embedding vector(768);
create index if not exists entities_inference_emb_hnsw
  on entities using hnsw (inference_embedding vector_cosine_ops);

-- ─────────────────────────────────────────────────────────────────────────
-- facts: drop polymorph + array, add object_id / object_literal / source_id.
-- 0 rows → safe. Drops cascading indexes/constraints automatically.
-- ─────────────────────────────────────────────────────────────────────────
alter table facts drop constraint if exists derived_from_not_empty;
alter table facts drop column if exists object;
alter table facts drop column if exists object_type;
alter table facts drop column if exists derived_from;

alter table facts add column object_id text references entities(id) on delete cascade;
alter table facts add column object_literal jsonb;
alter table facts add column source_id text references source_records(id) on delete cascade;

create index if not exists facts_subject_predicate_idx on facts (subject_id, predicate);
create index if not exists facts_object_idx on facts (object_id) where object_id is not null;
create index if not exists facts_source_idx on facts (source_id);

-- Exactly one of object_id / object_literal must be set.
alter table facts add constraint facts_object_xor
  check ((object_id is null) <> (object_literal is null));

-- ─────────────────────────────────────────────────────────────────────────
-- resolutions: rename schema's fact-level table → fact_resolutions,
-- create a new resolutions table for entity-pair ambiguity inbox
-- (consumed by WS-2 resolver, WS-4 API ResolutionResponse, WS-6 frontend
-- Conflict-Inbox UI).
-- ─────────────────────────────────────────────────────────────────────────
alter table resolutions rename to fact_resolutions;
alter policy service_all_resolutions on fact_resolutions rename to service_all_fact_resolutions;

create table resolutions (
  id text primary key,
  entity_id_1 text not null references entities(id) on delete cascade,
  entity_id_2 text not null references entities(id) on delete cascade,
  status text not null default 'pending',  -- 'pending' | 'merged' | 'rejected'
  resolution_signals jsonb not null default '{}'::jsonb,
  decided_at timestamptz,
  decided_by text,
  created_at timestamptz not null default now(),
  constraint resolutions_status_valid check (status in ('pending','merged','rejected'))
);

create index resolutions_status_idx on resolutions (status);
create index resolutions_entities_idx on resolutions (entity_id_1, entity_id_2);

alter table resolutions enable row level security;

do $$ begin
  create policy service_all_resolutions on resolutions for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
exception when duplicate_object then null; end $$;

do $$ begin
  create policy authenticated_read_resolutions on resolutions for select
    using (auth.role() in ('authenticated','anon'));
exception when duplicate_object then null; end $$;
