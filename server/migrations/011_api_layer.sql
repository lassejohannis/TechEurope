-- WS-API #14 — Schnittstelle für Software & AI
-- Adds: agent_tokens, pending_types, webhooks, webhook_deliveries, NOTIFY-driven
-- event bus on facts + entities, helper RPCs for cursor pagination.
-- Idempotent: every object guarded with IF NOT EXISTS / DO blocks.

-- 1) agent_tokens — bearer tokens for MCP / programmatic API consumers
create table if not exists agent_tokens (
    id           text primary key,
    name         text not null,
    token_hash   text not null,
    scopes       text[] not null default array['read']::text[],
    created_at   timestamptz not null default now(),
    last_seen_at timestamptz,
    revoked_at   timestamptz
);

create index if not exists agent_tokens_active_idx
    on agent_tokens (id) where revoked_at is null;

-- 2) pending_types — autonomous ontology proposals awaiting human decision
create table if not exists pending_types (
    id              text primary key,
    kind            text not null check (kind in ('entity_type','edge_type')),
    proposed_id     text not null,
    sample_payload  jsonb not null default '{}'::jsonb,
    rationale       text,
    proposed_by     text,
    proposed_at     timestamptz not null default now(),
    decided_at      timestamptz,
    decided_by      text,
    decision        text check (decision in ('approved','rejected'))
);

create index if not exists pending_types_open_idx
    on pending_types (proposed_at desc) where decided_at is null;

-- 3) webhooks — outbound subscriptions (HMAC-signed)
create table if not exists webhooks (
    id           text primary key,
    url          text not null,
    secret       text not null,
    event_types  text[] not null,
    created_by   text,
    created_at   timestamptz not null default now(),
    active       boolean not null default true
);

create index if not exists webhooks_active_idx
    on webhooks (active) where active = true;

create table if not exists webhook_deliveries (
    id            bigserial primary key,
    webhook_id    text not null references webhooks(id) on delete cascade,
    event_type    text not null,
    event_payload jsonb not null,
    status        text not null default 'pending',
    attempts      int not null default 0,
    last_error    text,
    delivered_at  timestamptz,
    queued_at     timestamptz not null default now()
);

create index if not exists webhook_deliveries_pending_idx
    on webhook_deliveries (queued_at) where status in ('pending','failed');

-- 4) NOTIFY trigger — publishes events to the 'qontext_events' channel.
-- Worker (server.sync.webhook_dispatcher) LISTENs and fans out to subscribers.
create or replace function notify_qontext_event() returns trigger language plpgsql as $$
declare
    event_type text;
    payload    jsonb;
begin
    if tg_table_name = 'fact_changes' then
        if new.kind = 'insert' then
            event_type := 'fact.created';
        elsif new.kind = 'update' and (new.new_value->>'superseded_by') is not null
              and (new.old_value->>'superseded_by') is null then
            event_type := 'fact.superseded';
        else
            return new;  -- generic update, not interesting yet
        end if;
        payload := jsonb_build_object(
            'event_type', event_type,
            'fact_id', new.fact_id,
            'at', new.at,
            'value', new.new_value
        );
    elsif tg_table_name = 'entities' then
        if tg_op = 'INSERT' then
            event_type := 'entity.created';
            payload := jsonb_build_object(
                'event_type', event_type,
                'entity_id', new.id,
                'entity_type', new.entity_type,
                'canonical_name', new.canonical_name,
                'at', new.created_at
            );
        elsif tg_op = 'UPDATE' and (new.aliases is distinct from old.aliases
              and array_length(new.aliases, 1) > coalesce(array_length(old.aliases, 1), 0)) then
            event_type := 'entity.merged';
            payload := jsonb_build_object(
                'event_type', event_type,
                'entity_id', new.id,
                'aliases', new.aliases,
                'at', new.updated_at
            );
        else
            return new;
        end if;
    else
        return new;
    end if;
    perform pg_notify('qontext_events', payload::text);
    return new;
end; $$;

drop trigger if exists fact_changes_notify on fact_changes;
create trigger fact_changes_notify
    after insert or update on fact_changes
    for each row execute function notify_qontext_event();

drop trigger if exists entities_notify on entities;
create trigger entities_notify
    after insert or update on entities
    for each row execute function notify_qontext_event();

-- 5) Service-role RLS (consistent with 001_init.sql)
alter table if exists agent_tokens enable row level security;
alter table if exists pending_types enable row level security;
alter table if exists webhooks enable row level security;
alter table if exists webhook_deliveries enable row level security;

do $$ begin execute $pol$
create policy service_all_agent_tokens on agent_tokens for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$pol$;
exception when duplicate_object then null; end $$;

do $$ begin execute $pol$
create policy service_all_pending_types on pending_types for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$pol$;
exception when duplicate_object then null; end $$;

do $$ begin execute $pol$
create policy service_all_webhooks on webhooks for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$pol$;
exception when duplicate_object then null; end $$;

do $$ begin execute $pol$
create policy service_all_webhook_deliveries on webhook_deliveries for all
    using (auth.role() = 'service_role') with check (auth.role() = 'service_role');$pol$;
exception when duplicate_object then null; end $$;

-- End of 009_api_layer.sql
