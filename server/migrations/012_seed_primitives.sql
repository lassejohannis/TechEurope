-- Migration 012: Seed-Reset on the ontology.
-- Strategy: keep existing entities/facts but normalize their type strings
-- against the new minimal seed (person, communication, document, organization).
-- Mark all non-seed legacy types as 'rejected' so they survive in audit but
-- are non-approved. Add FK constraints + trigger that future inserts only
-- accept 'approved' types.

update entities set entity_type = 'organization' where entity_type = 'company';
update facts set predicate = 'reports_to' where predicate = 'reports_to_emp_id';

insert into entity_type_config (id, config, approval_status, auto_proposed)
values
  ('person',         '{"description":"A human actor","seed":true}'::jsonb, 'approved', false),
  ('communication',  '{"description":"Email/thread/ticket/chat","seed":true}'::jsonb, 'approved', false),
  ('document',       '{"description":"PDF/file/spec","seed":true}'::jsonb, 'approved', false),
  ('organization',   '{"description":"Company/team/department","seed":true}'::jsonb, 'approved', false)
on conflict (id) do update set approval_status = 'approved', config = excluded.config;

update entity_type_config
   set approval_status = 'rejected'
 where id not in ('person', 'communication', 'document', 'organization');

insert into edge_type_config (id, config, approval_status, auto_proposed, from_type, to_type)
values
  ('works_at',       '{"description":"Employment / affiliation"}'::jsonb, 'approved', false, 'person', 'organization'),
  ('reports_to',     '{"description":"Manager / supervisor link"}'::jsonb, 'approved', false, 'person', 'person'),
  ('participant_in', '{"description":"Person took part in a communication"}'::jsonb, 'approved', false, 'person', 'communication'),
  ('authored',       '{"description":"Person created the communication or document"}'::jsonb, 'approved', false, 'person', 'communication')
on conflict (id) do update
   set approval_status = 'approved',
       from_type = excluded.from_type,
       to_type = excluded.to_type,
       config = excluded.config;

update edge_type_config
   set approval_status = 'rejected'
 where id not in ('works_at', 'reports_to', 'participant_in', 'authored');

alter table entities
  drop constraint if exists entities_entity_type_fk;
alter table entities
  add constraint entities_entity_type_fk
    foreign key (entity_type) references entity_type_config(id) on update cascade;

alter table facts
  drop constraint if exists facts_predicate_fk;
alter table facts
  add constraint facts_predicate_fk
    foreign key (predicate) references edge_type_config(id) on update cascade;

create or replace function ensure_entity_type_approved() returns trigger as $$
declare
  state text;
begin
  select approval_status into state
    from entity_type_config where id = new.entity_type;
  if state is null or state <> 'approved' then
    raise exception 'entity_type % is not approved (status=%)', new.entity_type, coalesce(state, '<missing>');
  end if;
  return new;
end; $$ language plpgsql;

drop trigger if exists entities_entity_type_check on entities;
create trigger entities_entity_type_check
  before insert or update of entity_type on entities
  for each row execute function ensure_entity_type_approved();

create or replace function ensure_predicate_approved() returns trigger as $$
declare
  state text;
begin
  select approval_status into state
    from edge_type_config where id = new.predicate;
  if state is null or state <> 'approved' then
    raise exception 'predicate % is not approved (status=%)', new.predicate, coalesce(state, '<missing>');
  end if;
  return new;
end; $$ language plpgsql;

drop trigger if exists facts_predicate_check on facts;
create trigger facts_predicate_check
  before insert or update of predicate on facts
  for each row execute function ensure_predicate_approved();
