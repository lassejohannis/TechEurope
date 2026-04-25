-- WS-Kathi: Temporal State helpers

-- Facts for an entity as of a timestamp (live or disputed, within validity window)
create or replace function facts_for_entity_as_of(eid text, as_of timestamptz)
returns setof facts
language sql
stable
as $$
    select * from facts f
    where f.subject_id = eid
      and (f.valid_from is null or f.valid_from <= as_of)
      and (f.valid_to   is null or f.valid_to   >  as_of)
      and f.status in ('live','disputed');
$$;

