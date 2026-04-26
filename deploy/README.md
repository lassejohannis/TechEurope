# Deploy — chickentendr.club

Single-host docker-compose deploy for `chickentendr.club`. Postgres + Neo4j stay on Supabase / Aura — only the FastAPI server + the React frontend run on the Vultr box. Caddy handles TLS via Let's Encrypt automatically.

## Prerequisites on the Vultr server

- Ubuntu 22.04 / 24.04 LTS (any recent distro with Docker works)
- Docker Engine + Docker Compose plugin (see [docs](https://docs.docker.com/engine/install/ubuntu/))
- Ports `80` and `443` open (Caddy needs both for ACME + serving)
- DNS: `chickentendr.club` and `www.chickentendr.club` A/AAAA records pointing at the Vultr IP

```bash
# Quick install (Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

## First deploy

```bash
# 1. Clone the repo
git clone https://github.com/lassejohannis/TechEurope.git
cd TechEurope

# 2. Create the production .env from the template
cp deploy/.env.production.example .env
# Edit .env — fill in SUPABASE_*, GEMINI_API_KEY, PIONEER_API_KEY, NEO4J_*, WEBHOOK_SECRET_PEPPER, etc.
# DO NOT commit this file — it's already in .gitignore via ".env"
nano .env

# 3. Build + run
docker compose up -d --build

# 4. Watch logs
docker compose logs -f caddy server web
```

First run takes ~3-5 min because Caddy provisions the Let's Encrypt cert and `Dockerfile.server` builds Python deps (uv + docling + pdfplumber).

## Verify

```bash
# Backend health
curl https://chickentendr.club/api/health

# Frontend
curl -I https://chickentendr.club/

# MCP SSE (should immediately return event-stream headers)
curl -N -H "Accept: text/event-stream" https://chickentendr.club/mcp/sse
```

## Update

```bash
git pull
docker compose up -d --build
```

`docker compose up -d --build` only rebuilds the layers that changed — typically <1 min for code-only changes.

## Common tweaks

- **Switch to demo-mode (auth off)** — set `API_AUTH_DISABLED=true` in `.env`, then `docker compose up -d server`.
- **Add CORS origins** — edit `API_CORS_ORIGINS` in `docker-compose.yml` `server.environment` block.
- **Change domain** — search-replace `chickentendr.club` in `deploy/Caddyfile` and `docker-compose.yml`, then `docker compose up -d caddy`.
- **Mount `.env` into a different path** — Compose uses repo-root `.env` by default. Override via `--env-file path/to/file`.

## Rollback

```bash
git log --oneline | head -5            # find the previous commit
git checkout <prev_sha>
docker compose up -d --build
```

Caddy data (`caddy_data` volume) survives rebuilds, so TLS certs are not re-issued and the rate-limit isn't hit.

## Resource expectations

| | RAM | Disk | CPU |
|---|---|---|---|
| caddy | 50 MB | 100 MB | tiny |
| web (nginx) | 30 MB | 50 MB | tiny |
| server | 700 MB-1.5 GB (varies with active resolves) | 600 MB image + 200 MB working | 0.5-2 cores during ingest+resolve |

Sizing target: **2 GB RAM minimum, 25 GB SSD, 2 vCPU**. The Vultr "High Performance 2 GB" tier ($12/mo) hits this comfortably.

## Troubleshooting

**Caddy keeps retrying ACME**
- Check DNS: `dig +short chickentendr.club` should return your Vultr IP.
- Ports 80 + 443 open in Vultr firewall.
- Look at logs: `docker compose logs caddy | grep -i acme`.

**Server can't reach Aura (Neo4j)**
- `SSL_CERT_FILE` is baked into the Dockerfile via certifi-bundle path; Linux doesn't need extra env in `.env`.
- Verify `NEO4J_PASSWORD` is correct: `docker compose exec server uv run python -c "from server.config import settings; print(settings.neo4j_uri)"`.

**SSE / MCP connection drops**
- Caddyfile already sets `flush_interval -1` and `read_timeout 0s`. If you put a CDN in front (Cloudflare etc.), make sure SSE/streaming is allowed.

**Out-of-memory during PDF ingest**
- pdfplumber + docling are memory-heavy. Bump to 4 GB RAM if you ingest big PDF batches in production.
