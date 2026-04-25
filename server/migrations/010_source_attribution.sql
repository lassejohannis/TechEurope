-- WS-Kathi: Source Attribution enhancements
-- Adapted for schema with scalar source_id (not derived_from[])

-- Derivation text column (how was this fact extracted)
alter table facts
    add column if not exists derivation text;

-- Backfill: copy extraction_method into derivation where empty
update facts
set derivation = extraction_method::text
where derivation is null and extraction_method is not null;

-- Multi-Source-Confirmation view
-- confirmation_count = how many active facts share the same (subject, predicate, object_literal)
create or replace view fact_evidence as
select
    f.id                                                                          as fact_id,
    f.subject_id,
    f.predicate,
    f.object_literal,
    f.object_id,
    f.confidence,
    f.source_id,
    f.derivation,
    sr.source_type,
    sr.ingested_at,
    count(*) over (
        partition by f.subject_id, f.predicate,
                     coalesce(f.object_id::text, f.object_literal::text)
    )                                                                             as confirmation_count,
    avg(f.confidence) over (
        partition by f.subject_id, f.predicate,
                     coalesce(f.object_id::text, f.object_literal::text)
    )                                                                             as avg_confidence
from facts f
left join source_records sr on sr.id = f.source_id
where f.status in ('live', 'active');
