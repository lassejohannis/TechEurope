-- Demo bootstrap: projectable companies/products/deals from existing source_records.
-- Safe to run multiple times (ON CONFLICT guards + idempotent ids).

-- 1) Customers → entities(type='customer') from CRM customers.json
insert into entities (id, type, canonical_name, aliases, attributes, status, provenance)
select
  'customer:' || regexp_replace(lower(payload->>'customer_id'), '[^a-z0-9]+','-','g') as id,
  'customer' as type,
  initcap(payload->>'customer_name') as canonical_name,
  array[]::text[] as aliases,
  jsonb_build_object('segment', null) as attributes,
  'live'::entity_status,
  array[sr.id] as provenance
from source_records sr
where sr.source_type = 'customer'
on conflict (id) do update
  set canonical_name = excluded.canonical_name,
      provenance    = (select array(select distinct unnest(entities.provenance || excluded.provenance)));

-- 2) Products → entities(type='product') from CRM products.json
insert into entities (id, type, canonical_name, aliases, attributes, status, provenance)
select
  'product:' || payload->>'product_id',
  'product',
  left(payload->>'product_name', 200),
  array[]::text[],
  jsonb_build_object('category', payload->>'category'),
  'live'::entity_status,
  array[sr.id]
from source_records sr
where sr.source_type = 'product'
on conflict (id) do update
  set canonical_name = excluded.canonical_name,
      attributes     = entities.attributes || excluded.attributes,
      provenance     = (select array(select distinct unnest(entities.provenance || excluded.provenance)));

-- 3) Deals → facts(predicate='ordered') from CRM sales.json
with s as (
  select
    'customer:' || regexp_replace(lower(payload->>'customer_id'), '[^a-z0-9]+','-','g') as subject_id,
    'product:' || (payload->>'product_id') as object_entity_id,
    array[sr.id] as derived_from,
    coalesce((payload->>'sales_record_id')::text, (row_number() over())::text) as sale_key
  from source_records sr
  where sr.source_type = 'sale'
)
insert into facts (id, subject_id, predicate, object, object_type, confidence, status, derived_from, valid_from)
select
  'fact:' || md5(subject_id || 'ordered' || object_entity_id || sale_key),
  subject_id,
  'ordered',
  to_jsonb(object_entity_id),
  'entity'::object_type,
  1.0,
  'live'::fact_status,
  derived_from,
  now()
from s
on conflict (id) do nothing;

