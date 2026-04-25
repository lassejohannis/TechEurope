-- API code (search.py, entities.py, facts.py, mcp/server.py) reads `recorded_at`
-- from facts rows but the original schema named the column `ingested_at`.
-- Renaming aligns schema to existing API/MCP code.
alter table facts rename column ingested_at to recorded_at;
