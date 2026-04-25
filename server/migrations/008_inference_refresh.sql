-- Migration 008: Tier-B inference embedding lifecycle.
--
-- Adds `inference_needs_refresh` flag and a trigger that marks both subject
-- and object entities for re-embed whenever a fact is inserted/updated.
-- The lazy re-embed loop (`uv run server reembed --tier=B`) reads this flag
-- and rebuilds inference embeddings for hot entities (≥ N facts).

alter table entities
  add column if not exists inference_needs_refresh boolean not null default true;

create or replace function mark_inference_refresh() returns trigger as $$
begin
  if new.subject_id is not null then
    update entities set inference_needs_refresh = true where id = new.subject_id;
  end if;
  if new.object_id is not null then
    update entities set inference_needs_refresh = true where id = new.object_id;
  end if;
  return new;
end; $$ language plpgsql;

drop trigger if exists facts_mark_inference_refresh on facts;
create trigger facts_mark_inference_refresh
  after insert or update of subject_id, object_id, predicate on facts
  for each row execute function mark_inference_refresh();
