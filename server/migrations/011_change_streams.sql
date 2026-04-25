-- WS-Kathi: Change Streams for entities

create table if not exists entity_changes (
    id           bigserial primary key,
    kind         text not null, -- 'insert' | 'update' | 'delete'
    entity_id    text,
    old_value    jsonb,
    new_value    jsonb,
    triggered_by text,
    at           timestamptz not null default now()
);

create or replace function log_entity_changes() returns trigger language plpgsql as $$
declare
    who text := coalesce(current_setting('request.jwt.claim.sub', true), auth.uid()::text);
begin
    if tg_op = 'INSERT' then
        insert into entity_changes(kind, entity_id, old_value, new_value, triggered_by)
        values ('insert', new.id, null, to_jsonb(new), who);
        return null;
    elsif tg_op = 'UPDATE' then
        insert into entity_changes(kind, entity_id, old_value, new_value, triggered_by)
        values ('update', new.id, to_jsonb(old), to_jsonb(new), who);
        return null;
    elsif tg_op = 'DELETE' then
        insert into entity_changes(kind, entity_id, old_value, new_value, triggered_by)
        values ('delete', old.id, to_jsonb(old), null, who);
        return null;
    end if;
    return null;
end; $$;

drop trigger if exists entities_log_changes on entities;
create trigger entities_log_changes
after insert or update or delete on entities
for each row execute function log_entity_changes();

