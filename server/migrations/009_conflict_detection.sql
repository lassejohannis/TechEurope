-- Migration 009: Cross-Source Fact Conflict Detection
--
-- Replaces the strict GIST EXCLUDE with a partial-unique-index that allows
-- multiple disputed facts to coexist for the same (subject, predicate),
-- and adds a BEFORE INSERT trigger that detects collisions and routes them
-- to the fact_resolutions inbox.
--
-- Flow:
-- 1. New fact arrives for (subject_id=X, predicate=Y, status='live')
-- 2. Trigger looks up existing live fact with same (X, Y)
-- 3. SAME value → cross-confirmation, drop new insert (silent dedup)
-- 4. DIFFERENT value → mark both 'disputed', write pending fact_resolutions row,
--    allow new insert to land as 'disputed'
-- 5. Auto-resolve cascade (resolver/auto_resolve.py) walks pending rows; the
--    rest bubbles to the human inbox UI.

alter table facts drop constraint if exists no_temporal_overlap;

create unique index if not exists facts_live_one_per_subject_predicate
  on facts (subject_id, predicate)
  where status = 'live' and valid_to is null;

alter table fact_resolutions
  alter column decision drop not null,
  alter column resolved_at drop not null;

alter table fact_resolutions
  add column if not exists status text not null default 'pending'
    check (status in ('pending', 'auto_resolved', 'human_resolved', 'rejected'));

create index if not exists fact_resolutions_status_idx on fact_resolutions (status);

create or replace function detect_fact_conflict() returns trigger
language plpgsql as $$
declare
  existing_id text;
  existing_object_id text;
  existing_object_literal jsonb;
  same_value boolean;
begin
  if new.status is distinct from 'live' then
    return new;
  end if;

  select id, object_id, object_literal
    into existing_id, existing_object_id, existing_object_literal
  from facts
  where subject_id = new.subject_id
    and predicate = new.predicate
    and status = 'live'
    and valid_to is null
    and id <> new.id
  limit 1;

  if existing_id is null then
    return new;
  end if;

  same_value := (
    (existing_object_id is not null and new.object_id = existing_object_id)
    or
    (existing_object_literal is not null and new.object_literal is not null
       and existing_object_literal = new.object_literal)
  );
  if same_value then
    return null;  -- silent cross-confirmation skip
  end if;

  update facts set status = 'disputed' where id = existing_id;
  new.status := 'disputed';

  insert into fact_resolutions (id, conflict_facts, status, rationale)
  values (
    gen_random_uuid()::text,
    array[existing_id, new.id],
    'pending',
    'auto-detected (subject, predicate) collision with different object'
  );

  return new;
end; $$;

drop trigger if exists facts_detect_conflict on facts;
create trigger facts_detect_conflict
  before insert on facts
  for each row execute function detect_fact_conflict();
