-- Migration 011: Autonomous Ontology Evolution foundation
-- Extend entity_type_config + edge_type_config with provenance/approval fields.
-- Add source_type_mapping table holding AI-inferred JSONata configs.

alter table entity_type_config
  add column if not exists auto_proposed boolean not null default false,
  add column if not exists approval_status text not null default 'approved'
    check (approval_status in ('pending', 'approved', 'rejected')),
  add column if not exists proposed_by_source_id text,
  add column if not exists similarity_to_nearest float,
  add column if not exists proposal_rationale text,
  add column if not exists approved_at timestamptz,
  add column if not exists approved_by text,
  add column if not exists embedding vector(768);

create index if not exists entity_type_config_status_idx on entity_type_config (approval_status);
create index if not exists entity_type_config_emb_hnsw on entity_type_config
  using hnsw (embedding vector_cosine_ops);

alter table edge_type_config
  add column if not exists auto_proposed boolean not null default false,
  add column if not exists approval_status text not null default 'approved'
    check (approval_status in ('pending', 'approved', 'rejected')),
  add column if not exists proposed_by_source_id text,
  add column if not exists similarity_to_nearest float,
  add column if not exists proposal_rationale text,
  add column if not exists approved_at timestamptz,
  add column if not exists approved_by text,
  add column if not exists from_type text references entity_type_config(id),
  add column if not exists to_type text references entity_type_config(id),
  add column if not exists embedding vector(768);

create index if not exists edge_type_config_status_idx on edge_type_config (approval_status);
create index if not exists edge_type_config_emb_hnsw on edge_type_config
  using hnsw (embedding vector_cosine_ops);

create table if not exists source_type_mapping (
  id text primary key,
  source_type text not null unique,
  mapping_version int not null default 1,
  config jsonb not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  proposed_at timestamptz not null default now(),
  approved_at timestamptz,
  approved_by text,
  validation_stats jsonb,
  created_from_sample_ids text[] not null default '{}'::text[],
  rationale text
);

create index if not exists source_type_mapping_status_idx on source_type_mapping (status);

alter table source_type_mapping enable row level security;
do $$ begin
  create policy service_all_source_type_mapping on source_type_mapping for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
exception when duplicate_object then null; end $$;
do $$ begin
  create policy authenticated_read_source_type_mapping on source_type_mapping for select
    using (auth.role() in ('authenticated', 'anon'));
exception when duplicate_object then null; end $$;
