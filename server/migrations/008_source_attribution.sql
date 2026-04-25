-- Migration 008: Source Attribution (WS-9) + entity_changes audit (WS-11)
--
-- (a) source_id NOT NULL — backfill any nulls, then add constraint
-- (b) fact_evidence view  — multi-source confirmation window function
-- (c) entity_changes audit table + trigger + Realtime publication

-- (a) ─────────────────���────────────────────────��───────────────────────
-- Backfill any legacy nulls so the NOT NULL constraint can be added safely.
-- 'unknown' is a sentinel; real ingestion always sets source_id.
update facts set source_id = 'unknown' where source_id is null;

do $$
begin
  alter table facts alter column source_id set not null;
exception when others then
  -- Already NOT NULL or constraint issue — skip silently
  null;
end $$;

-- (b) ────────────────────────────────────────────────────────────���─────
create or replace view fact_evidence as
select
  f.id                                                         as fact_id,
  f.subject_id,
  f.predicate,
  f.object_literal,
  f.object_id,
  f.confidence,
  f.source_id,
  f.derivation,
  sr.source_type,
  sr.ingested_at,
  count(*)  over (partition by f.subject_id, f.predicate,
                               coalesce(f.object_id::text, f.object_literal::text))
                                                               as confirmation_count,
  avg(f.confidence) over (partition by f.subject_id, f.predicate,
                               coalesce(f.object_id::text, f.object_literal::text))
                                                               as avg_confidence
from facts f
left join source_records sr on sr.id = f.source_id
where f.status = 'active';

-- (c) ─────────────────────────────────────────────────────────────────���
create table if not exists entity_changes (
  id          bigserial primary key,
  kind        text        not null check (kind in ('insert', 'update', 'delete')),
  entity_id   text        not null,
  old_value   jsonb,
  new_value   jsonb,
  at          timestamptz not null default now()
);

create index if not exists entity_changes_entity_idx on entity_changes (entity_id);
create index if not exists entity_changes_at_idx     on entity_changes (at desc);

create or replace function log_entity_changes() returns trigger language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    insert into entity_changes(kind, entity_id, new_value)
    values ('insert', new.id, to_jsonb(new));
  elsif tg_op = 'UPDATE' then
    insert into entity_changes(kind, entity_id, old_value, new_value)
    values ('update', new.id, to_jsonb(old), to_jsonb(new));
  elsif tg_op = 'DELETE' then
    insert into entity_changes(kind, entity_id, old_value)
    values ('delete', old.id, to_jsonb(old));
  end if;
  return null;
end;
$$;

drop trigger if exists entity_changes_trigger on entities;
create trigger entity_changes_trigger
  after insert or update or delete on entities
  for each row execute function log_entity_changes();

-- Add entity_changes to Realtime publication
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and tablename = 'entity_changes'
  ) then
    execute 'alter publication supabase_realtime add table entity_changes';
  end if;
end $$;
