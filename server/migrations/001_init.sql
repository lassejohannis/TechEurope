-- WS-0 — Initial schema for Tech Europe Context Engine
-- Safe to run on empty project. Idempotent-ish via IF NOT EXISTS where possible.

-- Extensions (ensure available; harmless if already enabled)
create extension if not exists vector;
create extension if not exists btree_gist;

-- Enums
do $$ begin
    create type extraction_status as enum ('pending','extracted','failed');
exception when duplicate_object then null; end $$;

do $$ begin
    create type entity_status as enum ('live','draft','archived');
exception when duplicate_object then null; end $$;

do $$ begin
    create type fact_status as enum ('live','draft','superseded','disputed','needs_refresh');
exception when duplicate_object then null; end $$;

do $$ begin
    create type object_type as enum ('entity','string','number','date','bool','enum','json');
exception when duplicate_object then null; end $$;

do $$ begin
    create type extraction_method as enum ('rule','gemini','pioneer','human');
exception when duplicate_object then null; end $$;

do $$ begin
    create type resolution_decision as enum ('pick_one','merge','both_with_qualifier','reject_all');
exception when duplicate_object then null; end $$;

-- 1) source_records — raw, normalized input units
create table if not exists source_records (
    id               text primary key,
    source_type      text not null,
    source_uri       text,
    source_native_id text,
    payload          jsonb not null default '{}'::jsonb,
    content_hash     text not null,
    ingested_at      timestamptz not null default now(),
    superseded_by    text references source_records(id) on delete set null,
    extraction_status extraction_status not null default 'pending'
);

create index if not exists source_records_source_type_idx on source_records (source_type);
create index if not exists source_records_payload_gin on source_records using gin (payload);

-- 2) entities — canonical things (people, orgs, products, ...)
create table if not exists entities (
    id                text primary key,
    type              text not null,
    canonical_name    text not null,
    aliases           text[] not null default '{}'::text[],
    attributes        jsonb not null default '{}'::jsonb,
    status            entity_status not null default 'live',
    provenance        text[] not null default '{}'::text[],
    inference_text    text,
    embedding         vector(768),
    inference_updated_at timestamptz,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

create index if not exists entities_type_idx on entities (type);
create index if not exists entities_aliases_gin on entities using gin (aliases);
create index if not exists entities_attributes_gin on entities using gin (attributes);
create index if not exists entities_embedding_hnsw on entities using hnsw (embedding vector_l2_ops) with (m=16, ef_construction=64);

-- 3) facts — bi-temporal, reified relations with provenance
create table if not exists facts (
    id               text primary key,
    subject_id       text not null references entities(id) on delete cascade,
    predicate        text not null,
    object           jsonb not null,
    object_type      object_type not null,
    confidence       numeric(3,2) not null check (confidence >= 0 and confidence <= 1),
    status           fact_status not null default 'live',
    derived_from     text[] not null,
    last_hash_seen   jsonb not null default '{}'::jsonb,
    -- bi-temporal columns
    valid_from       timestamptz,
    valid_to         timestamptz,
    ingested_at      timestamptz not null default now(),
    superseded_at    timestamptz,
    extraction_method extraction_method,
    qualifiers       jsonb not null default '{}'::jsonb,
    embedding        vector(768),
    superseded_by    text references facts(id) on delete set null,
    -- generated tstzrange for clean EXCLUDE constraint
    validity         tstzrange generated always as (tstzrange(valid_from, valid_to, '[)')) stored,
    constraint derived_from_not_empty check (array_length(derived_from, 1) is not null and array_length(derived_from, 1) >= 1)
);

create index if not exists facts_subject_predicate_idx on facts (subject_id, predicate);
create index if not exists facts_current_subject_predicate_idx on facts (subject_id, predicate) where valid_to is null and status = 'live';
create index if not exists facts_object_type_idx on facts (object_type);
create index if not exists facts_object_gin on facts using gin (object);
create index if not exists facts_embedding_hnsw on facts using hnsw (embedding vector_l2_ops) with (m=16, ef_construction=64);

-- Prevent temporal overlap for the same (subject, predicate) among live facts
alter table facts
    add constraint if not exists no_temporal_overlap
    exclude using gist (
        subject_id with =,
        predicate with =,
        validity with &&
    ) where (status = 'live');

-- 4) resolutions — human decisions on conflicts
create table if not exists resolutions (
    id                text primary key,
    conflict_facts    text[] not null,
    decision          resolution_decision not null,
    chosen_fact_id    text references facts(id) on delete set null,
    qualifier_added   jsonb,
    rationale         text,
    resolved_by       text,
    resolved_at       timestamptz not null default now()
);

-- 5) ontology config tables (data-driven types/edges)
create table if not exists entity_type_config (
    id          text primary key,
    config      jsonb not null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create table if not exists edge_type_config (
    id          text primary key,
    config      jsonb not null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

-- 6) fact_changes — change stream log for facts
create table if not exists fact_changes (
    id           bigserial primary key,
    kind         text not null, -- 'insert' | 'update' | 'delete'
    fact_id      text,
    old_value    jsonb,
    new_value    jsonb,
    triggered_by text,
    at           timestamptz not null default now()
);

-- Trigger: set superseded_at when superseded_by becomes non-null
create or replace function set_superseded_at() returns trigger language plpgsql as $$
begin
    if new.superseded_by is not null and (old.superseded_by is distinct from new.superseded_by) then
        new.superseded_at := now();
    end if;
    return new;
end; $$;

drop trigger if exists facts_set_superseded_at on facts;
create trigger facts_set_superseded_at
before update of superseded_by on facts
for each row execute function set_superseded_at();

-- Trigger: log inserts/updates to fact_changes
create or replace function log_fact_changes() returns trigger language plpgsql as $$
declare
    who text := coalesce(current_setting('request.jwt.claim.sub', true), auth.uid()::text);
begin
    if tg_op = 'INSERT' then
        insert into fact_changes(kind, fact_id, old_value, new_value, triggered_by)
        values ('insert', new.id, null, to_jsonb(new), who);
        return null;
    elsif tg_op = 'UPDATE' then
        insert into fact_changes(kind, fact_id, old_value, new_value, triggered_by)
        values ('update', new.id, to_jsonb(old), to_jsonb(new), who);
        return null;
    end if;
    return null;
end; $$;

drop trigger if exists facts_log_changes on facts;
create trigger facts_log_changes
after insert or update on facts
for each row execute function log_fact_changes();

-- RLS: enable and add minimal policies
alter table if exists source_records enable row level security;
alter table if exists entities enable row level security;
alter table if exists facts enable row level security;
alter table if exists resolutions enable row level security;
alter table if exists entity_type_config enable row level security;
alter table if exists edge_type_config enable row level security;

-- Service role: full access (Supabase evaluates auth.role())
do $$ begin execute $$
create policy service_all_source_records on source_records for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$$; exception when duplicate_object then null; end $$;
do $$ begin execute $$
create policy service_all_entities on entities for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$$; exception when duplicate_object then null; end $$;
do $$ begin execute $$
create policy service_all_facts on facts for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$$; exception when duplicate_object then null; end $$;
do $$ begin execute $$
create policy service_all_resolutions on resolutions for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$$; exception when duplicate_object then null; end $$;
do $$ begin execute $$
create policy service_all_entity_type_config on entity_type_config for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$$; exception when duplicate_object then null; end $$;
do $$ begin execute $$
create policy service_all_edge_type_config on edge_type_config for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$$; exception when duplicate_object then null; end $$;

-- Authenticated read-only for demo (adjust later per product needs)
do $$ begin execute $$
create policy authenticated_read_entities on entities for select using (auth.role() in ('authenticated','service_role'));$$; exception when duplicate_object then null; end $$;
do $$ begin execute $$
create policy authenticated_read_facts on facts for select using (auth.role() in ('authenticated','service_role'));$$; exception when duplicate_object then null; end $$;

-- Timestamps maintenance (simple updated_at touch)
create or replace function touch_updated_at() returns trigger language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end; $$;

drop trigger if exists entities_touch_updated_at on entities;
create trigger entities_touch_updated_at before update on entities for each row execute function touch_updated_at();

drop trigger if exists entity_type_config_touch on entity_type_config;
create trigger entity_type_config_touch before update on entity_type_config for each row execute function touch_updated_at();

drop trigger if exists edge_type_config_touch on edge_type_config;
create trigger edge_type_config_touch before update on edge_type_config for each row execute function touch_updated_at();

-- End of 001_init.sql

-- WS-1.6: helper to mark dependent facts for refresh when sources change
create or replace function mark_facts_needs_refresh(updated_source_ids text[])
returns integer
language sql
as $$
    with upd as (
        update facts
        set status = 'needs_refresh'
        where derived_from && updated_source_ids
          and status <> 'needs_refresh'
        returning 1
    )
    select coalesce(count(*), 0)::int from upd;
$$;
