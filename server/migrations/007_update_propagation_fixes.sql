-- Migration 007: fix update propagation (Req 10).
--
-- (a) `mark_facts_needs_refresh` originally walked `facts.derived_from` (a
-- text[] array). Migration 003 dropped that column and replaced it with the
-- scalar `source_id`. The function silently broke at that point — re-ingest
-- of an updated source record no longer flagged its dependent facts as
-- stale, so the lazy re-derivation loop had nothing to pick up.
--
-- (b) Supabase Realtime requires tables to be members of the
-- `supabase_realtime` publication for INSERT/UPDATE/DELETE events to flow.
-- Without this, the WS-5 Neo4j projection's listen() subscribed cleanly
-- but never received any events. Likewise for any frontend live-tail.
--
-- (c) Surfacing `fact_changes` lets the frontend "Streaming Ingestion Log"
-- subscribe to the audit trail without hitting the trigger table via REST.

-- (a) ──────────────────────────────────────────────────────────────────
create or replace function mark_facts_needs_refresh(updated_source_ids text[])
returns integer
language sql
as $$
  with upd as (
    update facts
    set status = 'needs_refresh'
    where source_id = any(updated_source_ids)
      and status <> 'needs_refresh'
    returning 1
  )
  select coalesce(count(*), 0)::int from upd;
$$;

-- (b) + (c) ───────────────────────────────────────────────────────────
do $$
declare
  has_entities boolean;
  has_facts boolean;
  has_changes boolean;
begin
  select exists(
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and tablename = 'entities'
  ) into has_entities;
  select exists(
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and tablename = 'facts'
  ) into has_facts;
  select exists(
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and tablename = 'fact_changes'
  ) into has_changes;

  if not has_entities then
    execute 'alter publication supabase_realtime add table entities';
  end if;
  if not has_facts then
    execute 'alter publication supabase_realtime add table facts';
  end if;
  if not has_changes then
    execute 'alter publication supabase_realtime add table fact_changes';
  end if;
end $$;
