-- FactResponse model declares valid_from as a required datetime; ensure the
-- column has a default + NOT NULL so resolver inserts (which don't set it
-- explicitly) succeed and API responses validate.
alter table facts alter column valid_from set default now();
update facts set valid_from = recorded_at where valid_from is null;
alter table facts alter column valid_from set not null;
