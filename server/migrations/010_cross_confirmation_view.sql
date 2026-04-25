-- Migration 010: cross_confirmation_count view.
-- Aggregates how many distinct sources assert the same (subject, predicate, object).
-- Read by auto_resolve.py Tier-4 (Cross-Confirmation cascade tier).

drop view if exists cross_confirmation_count;

create or replace view cross_confirmation_count as
select
  subject_id,
  predicate,
  coalesce(object_id, '') as object_id,
  coalesce(object_literal::text, '') as object_literal_str,
  count(distinct source_id) as source_count,
  array_agg(distinct source_id) as source_ids,
  array_agg(id) as fact_ids,
  max(confidence) as best_confidence,
  max(recorded_at) as latest_recorded_at
from facts
where status in ('live', 'disputed') and source_id is not null
group by subject_id, predicate, coalesce(object_id, ''), coalesce(object_literal::text, '');
