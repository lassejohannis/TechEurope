-- Soft-delete support for entities.
--
-- deleted_at is set by the VFS DELETE endpoint instead of removing the row,
-- so facts keep their provenance chain.  The Supabase Realtime UPDATE event
-- triggers the Neo4j projection to DETACH DELETE the node there.

alter table entities
  add column if not exists deleted_at timestamptz;

-- Fast filter for "all active entities" queries.
create index if not exists entities_active_idx
  on entities (entity_type)
  where deleted_at is null;

-- Rebuild entity_trust view to exclude soft-deleted entities.
create or replace view entity_trust as
select
  e.id,
  e.canonical_name,
  e.entity_type,
  coalesce(
    avg(f.confidence)
    * least(count(distinct f.source_id)::float / 3.0, 1.0)
    * exp(
        -extract(epoch from (now() - max(f.recorded_at))) / (30.0 * 86400.0)
      ),
    0.0
  ) as trust_score,
  e.fact_count as fact_count,
  count(distinct f.source_id) as source_diversity
from entities e
left join facts f on f.subject_id = e.id and f.valid_to is null
where e.deleted_at is null
group by e.id, e.canonical_name, e.entity_type, e.fact_count;
