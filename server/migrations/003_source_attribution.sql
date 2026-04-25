-- WS-Kathi: Source Attribution enhancements

-- Primary source convenience column (first element of derived_from)
alter table facts
    add column if not exists primary_source_id text
    generated always as (case when array_length(derived_from,1) >= 1 then derived_from[1] else null end) stored;

-- Derivation text column (backfill from extraction_method textual form when available)
alter table facts
    add column if not exists derivation text;

-- Optional quick backfill: copy extraction_method into derivation where empty
update facts set derivation = coalesce(derivation, extraction_method::text) where derivation is null;

-- Multi-Source-Confirmation view: count of sources and list
create or replace view fact_evidence as
select
    id as fact_id,
    cardinality(derived_from) as source_count,
    derived_from as sources,
    primary_source_id
from facts;

