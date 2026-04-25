# Qontext API Consumer Guide

Two consumer classes are first-class:

- **AI agents** → MCP server at `/mcp/sse` (or stdio).
- **External software** → REST under `/api/*` + outbound webhooks.

Same auth surface: bearer tokens, scoped (`read` / `write` / `admin`).

---

## 1. Auth

### 1.1 Supabase JWT (UI / human users)

The web app obtains a Supabase session JWT via `supabase-js` and sends it on
every request:

```
Authorization: Bearer <supabase_jwt>
```

Decoded with `SUPABASE_JWT_SECRET` (HS256). `service_role` JWTs get all
scopes; `authenticated` JWTs get `read,write`.

### 1.2 Agent tokens (MCP / programmatic)

Issue a token from the CLI:

```bash
uv run server token issue "demo-agent" --scopes read,write
# id:     7a4f1c…
# scopes: read,write
# token:  qx_7a4f1c…_b3e2…   ← save now, never shown again
```

Use it as a bearer:

```
Authorization: Bearer qx_7a4f1c…_b3e2…
```

Revoke:

```bash
uv run server token revoke 7a4f1c…
```

### 1.3 Dev bypass

`API_AUTH_DISABLED=true` in `server/.env` (default for local dev) lets all
requests through with an anonymous admin principal. **Flip to `false` for
the demo run.**

---

## 2. Endpoints (selected)

| Method | Path | Scope |
|---|---|---|
| GET | `/api/entities/{id}?as_of=<iso>` | read |
| POST | `/api/facts/{id}/validate` | write |
| POST | `/api/facts/{id}/flag` | write |
| POST | `/api/facts/{id}/edit` | write |
| GET | `/api/graph/neighborhood/{entity_id}?depth=1&edge_types=…` | read |
| POST | `/api/admin/reingest` | admin |
| GET / POST | `/api/admin/pending-types[/{id}/decide]` | admin |
| GET / POST / DELETE | `/api/admin/webhooks` | admin |
| GET | `/api/changes/recent?limit=…&cursor=…` | read |

Full surface lives in `/docs` (FastAPI's OpenAPI UI) once the server is up.

### `as_of` time-travel

```bash
curl -H "Authorization: Bearer $TOK" \
  "localhost:8000/api/entities/person:jane-doe?as_of=2026-04-01T00:00:00Z"
```

Returns the entity as it stood at that timestamp — facts whose
`valid_from ≤ as_of < valid_to` are included.

### Editing a fact

`POST /api/facts/{id}/edit` does **not** mutate the original. It writes a
new fact and lets the Postgres supersede pipeline close the prior one. The
response carries the *new* fact id.

---

## 3. Pagination

Cursor-based on the change feed and pending-types. Cursors are opaque
base64 JSON; treat as strings.

```bash
curl ".../api/changes/recent?limit=10"
# → { "items":[…], "next_cursor":"eyJ0cyI6Ij…" }

curl ".../api/changes/recent?limit=10&cursor=eyJ0cyI6Ij…"
```

---

## 4. Outbound webhooks

Subscribe to events:

```bash
curl -XPOST -H "Authorization: Bearer $ADMIN_TOK" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/hook","event_types":["fact.created","entity.merged"]}' \
  localhost:8000/api/admin/webhooks
# { "id":"…","secret":"…", … }   ← save the secret
```

Supported events: `fact.created`, `fact.superseded`, `entity.created`,
`entity.merged`.

Each delivery carries:

```
X-Qontext-Event: fact.created
X-Qontext-Signature: sha256=<hmac>
Content-Type: application/json
```

Verify in Python:

```python
import hmac, hashlib
sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
assert hmac.compare_digest(sig, header.split("=", 1)[1])
```

Retries: up to 5 with exponential backoff (1.5 ^ attempt seconds).

---

## 5. Rate limits

Default `60/minute` per IP, `600/minute` per token. Exceeding returns `429`
with `{"detail": "Rate limit exceeded: …"}`.

---

## 6. MCP transports

### SSE (default)

```json
{
  "mcpServers": {
    "qontext": {
      "url": "http://localhost:8000/mcp/sse",
      "headers": { "Authorization": "Bearer qx_…" }
    }
  }
}
```

### stdio (Claude Desktop)

```json
{
  "mcpServers": {
    "qontext": {
      "command": "uv",
      "args": ["run", "server", "mcp-stdio"],
      "cwd": "/path/to/TechEurope/server"
    }
  }
}
```

stdio inherits OS-level trust — no token check.

---

## 7. SDKs

- **TypeScript:** `cd web && npm run gen:sdk` regenerates
  `web/src/lib/qontext-sdk.ts` from the running server's `/openapi.json`.
- **Python SDK:** intentionally not provided — use `httpx` directly against
  the OpenAPI schema at `/docs`.

---

## 8. Bruno collection

`docs/api/qontext-bruno/` is a Bruno workspace. Open it in Bruno, point the
environment at your local server, and walk through the demo requests.
