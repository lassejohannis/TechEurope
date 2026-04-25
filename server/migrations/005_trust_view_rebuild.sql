-- Re-create trust view + match_entities RPC after migration 003 renamed the
-- entities columns and migration 004 renamed facts.ingested_at → recorded_at.
-- This replaces the original 002_trust_view.sql which referenced columns
-- (UUID id, name_embedding, recorded_at) that didn't match the actual schema.

drop view if exists entity_trust;

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
  count(f.id) as fact_count,
  count(distinct f.source_id) as source_diversity
from entities e
left join facts f on f.subject_id = e.id and f.valid_to is null
group by e.id, e.canonical_name, e.entity_type;

create or replace function match_entities(
  query_embedding vector(768),
  match_threshold float default 0.7,
  match_count int default 20,
  use_inference_embedding bool default true
)
returns table(
  id text,
  canonical_name text,
  entity_type text,
  similarity float
)
language sql stable
as $$
  select
    e.id,
    e.canonical_name,
    e.entity_type,
    case
      when use_inference_embedding and e.inference_embedding is not null
        then 1.0 - (e.inference_embedding <=> query_embedding)
      else
        1.0 - (e.embedding <=> query_embedding)
    end as similarity
  from entities e
  where
    case
      when use_inference_embedding and e.inference_embedding is not null
        then (1.0 - (e.inference_embedding <=> query_embedding)) > match_threshold
      else
        e.embedding is not null
        and (1.0 - (e.embedding <=> query_embedding)) > match_threshold
    end
  order by similarity desc
  limit match_count;
$$;

create or replace function get_fact_provenance_json(p_fact_id text)
returns json
language sql stable
as $$
  select json_build_object(
    'fact', row_to_json(f),
    'source_record', row_to_json(sr),
    'superseded_by', (
      select row_to_json(fnew) from facts fnew where fnew.id = f.superseded_by
    )
  )
  from facts f
  join source_records sr on sr.id = f.source_id
  where f.id = p_fact_id;
$$;

create index if not exists entities_vfs_path
  on entities ((attrs->>'vfs_path'));
