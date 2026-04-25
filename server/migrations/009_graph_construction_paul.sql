-- Graph Construction (Paul)
-- Adds graph-oriented integrity + caches:
-- - facts.derivation text
-- - entities.fact_count cache + trigger maintenance
-- - self-loop guard for entity-to-entity facts
-- - temporal overlap scoped per (subject,predicate,object)
-- - entity_trust.fact_count reads from cached column

alter table facts
  add column if not exists derivation text not null default 'unknown';

alter table entities
  add column if not exists fact_count integer not null default 0;

create or replace function refresh_entity_fact_count(p_entity_id text)
returns void
language plpgsql
as $$
begin
  if p_entity_id is null then
    return;
  end if;

  update entities e
  set fact_count = (
    select count(*)::int
    from facts f
    where f.subject_id = p_entity_id
      and f.valid_to is null
      and f.status = 'live'
  )
  where e.id = p_entity_id;
end;
$$;

create or replace function facts_refresh_entity_fact_count_trg()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'INSERT' then
    perform refresh_entity_fact_count(new.subject_id);
  elsif tg_op = 'DELETE' then
    perform refresh_entity_fact_count(old.subject_id);
  else
    perform refresh_entity_fact_count(old.subject_id);
    perform refresh_entity_fact_count(new.subject_id);
  end if;

  return null;
end;
$$;

drop trigger if exists facts_refresh_entity_fact_count on facts;
create trigger facts_refresh_entity_fact_count
after insert or update or delete on facts
for each row execute function facts_refresh_entity_fact_count_trg();

-- Backfill cache for existing rows.
update entities e
set fact_count = coalesce(fc.cnt, 0)
from (
  select subject_id, count(*)::int as cnt
  from facts
  where valid_to is null and status = 'live'
  group by subject_id
) fc
where e.id = fc.subject_id;

update entities e
set fact_count = 0
where not exists (
  select 1 from facts f
  where f.subject_id = e.id
    and f.valid_to is null
    and f.status = 'live'
);

-- Disallow self loops in facts for entity-to-entity relations.
do $$
begin
  alter table facts
    add constraint facts_no_self_loop
    check (object_id is null or subject_id <> object_id);
exception
  when duplicate_object then null;
end $$;

-- Scope temporal overlap by object, so participant_in/manages can have many targets.
alter table facts drop constraint if exists no_temporal_overlap;
do $$
begin
  alter table facts
    add constraint no_temporal_overlap
    exclude using gist (
      subject_id with =,
      predicate with =,
      coalesce(object_id, '') with =,
      coalesce(object_literal::text, '') with =,
      validity with &&
    ) where (status = 'live');
exception
  when duplicate_object then null;
end $$;

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
group by e.id, e.canonical_name, e.entity_type, e.fact_count;
