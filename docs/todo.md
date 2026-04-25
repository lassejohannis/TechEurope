# TODO — was noch zu bauen ist

Workflow von vorne bis hinten. Stumpf. Details im `team-briefing-technical.md`.

## 1. Ingestion
- Generic-PDF-Connector für Policy_Documents (Kathi: erledigt — `connectors/document.py`)
- ITSM-Connector für it_tickets.json (Kathi: erledigt — `connectors/itsm.py`)
- Collaboration-Connector für conversations.json
- Vendors im CRM-Connector
- Resume-PDF-Connector (optional)
- Overflow-Connector für Q&A-Forum (optional)

## 2. Virtual File System
- `vfs_path` in `entity.attrs` beim Resolver-Insert schreiben
- Unique-Index auf `(entity_type, attrs->>'vfs_path')`
- Slug-Mapping aus `entity_type_config` lesen statt hardcoded `_SLUG_TO_TYPE`
- Glob-Search-Endpoint `/api/vfs/_glob`

## 3. Entity Resolution
- T3 Embedding-API-Fix (`embed_text()` 404 auf text-embedding-004 → korrekter Endpoint)
- T4 Logic-Fix in `cascade.py` (relationship_hint statt match)
- Pre-Normalize in `embed_text()` (lowercase, Suffix-Strip, Whitespace-Collapse)
- Resolver schreibt Tier-A-Embedding beim Entity-Insert
- Backfill-Script für die 306 entities ohne Embedding
- `build_inference_text(entity_id)` für Tier B
- Tier-B-Backfill für entities mit ≥5 Facts
- `inference_needs_refresh boolean` + Trigger
- Lazy Re-Embed-Loop CLI
- `communication`-Entity-Typ + Resolver-Modul für Email-Threads
- `document`-Entity-Typ + Resolver-Modul für Policy-PDFs
- Volllauf des Resolvers mit Bulk-Insert (28k records)
- Pioneer-Tier-3.5 scharf schalten sobald Modell ready
- LLM-Fact-Extraction aus Email-Body (`gemini_structured.extract_email_facts`)

## 4. Autonome Ontologie-Evolution
- Migration 008: type_config-Tabellen erweitern (auto_proposed, approval_status, proposed_by_source_id, similarity_to_nearest, from_type, to_type)
- `propose.classify_or_propose_type(payload, kind)` Funktion
- Embedding-Similarity-Reject (Distanz < 0.4 = zu ähnlich)
- Auto-Approve-Threshold (confidence ≥ 0.95 + similarity < 0.3 + ≥3 records)
- Integration in `extract.py` (Tier 2 + 3 Cascade)
- Endpoints `/api/admin/pending-types` + decide
- Frontend Inbox um 2 Tabs erweitern (entity-types, edge-types)
- Synonym-Detection-Pass (async)
- FK-Constraints `entities.entity_type → entity_type_config` + `facts.predicate → edge_type_config`
- Trigger der nur approved-Types akzeptiert

## 5. Cross-Source Merge & Conflict Resolution
- Migration 009: GIST-EXCLUDE durch partial-unique-index ersetzen + `detect_fact_conflict`-Trigger
- `auto_resolve.py` mit 4-Tier-Cascade (Recency / Authority / Confidence / Cross-Confirm)
- CLI `uv run server resolve-conflicts`
- `cross_confirmation_count` View
- Endpoints: `GET /api/resolutions`, `POST /api/resolutions/{id}/decide`
- Endpoints: `GET /api/fact-resolutions`, `POST /api/fact-resolutions/{id}/decide`
- Frontend ConflictInbox auf echte API umstellen
- Trust-Weight-Editor im Frontend (read-only)
- 1-2 echte Demo-Konflikte vor-präparieren

## 6. Hybrid Search
- Stage 1 unblocken (abhängig von Embedding-Fix oben)
- Pioneer-Mention-Extraction in Stage 2 (Fallback Gemini Flash)
- Intersect/Union-Heuristik (≥3+3 → intersect)
- `as_of`-Param in `/api/search` und `search_memory`
- Cross-Encoder-Rerank (optional)

## 7. Graph Construction
- `participant_in`-Edges für Email-Threads (abhängig von communication-Entity)
- `manages`-Edges aus `reports_to_emp_id`-Literal-Facts
- `mentions`-Edges aus LLM-Email-Body-Extract
- Self-loop-CHECK-Constraint
- `entities.fact_count` Cache-Spalte mit Trigger
- `derivation text` Spalte in facts (z.B. "rule:email_domain")

## 8. Temporal State
- `/api/entities/{id}?as_of=<ts>` Endpoint
- `supersede_fact()`-Helper im App-Code
- `POST /api/entities/{id}/timeline` (optional)
- Demo-Daten: 1-2 historische Supersedes vor-präparieren

## 9. Source Attribution
- `source_id NOT NULL` Migration
- `derivation` Spalte mit Backfill aus `extraction_method`
- Multi-Source-Confirmation View `fact_evidence`
- `trust_weight` in Provenance-Response

## 10. Neo4j Projection
- `POST /admin/projection/replay` Endpoint
- Initial-Replay live triggern (Aura ist leer)
- Demo-Queries auf reale Entity-IDs anpassen (Inazuma statt Acme)
- Cypher-Wow-Query fürs Pitch-Skript
- Whitelist auf `/api/query/cypher` (read-only enforce)
- `last_synced_event_id` Tracking + Health-Indicator

## 11. Change Streams
- Frontend Streaming Ingestion Log Component
- Filtered-Channel-Beispiele im UI
- `entity_changes` Audit-Tabelle + Trigger
- `docs/realtime-channels.md` für externe Konsumenten

## 12. Update Propagation
- `supersede_fact()`-Helper (siehe Temporal State)
- CLI `uv run server reprocess` (re-derive needs_refresh facts)
- Webhook-Endpoint `POST /api/admin/reingest`
- FS-Watch-Daemon (optional)

## 13. UI Surfaces
- VfsTree → echte API
- EntityDetail → echte API + Trust-Pill
- Validate / Flag / Edit Buttons pro FactRow
- TimeSlider Component
- GraphExplorer Page (react-flow)
- IngestionStream Bottom-Drawer
- ConflictInbox-Wire (siehe Conflict Resolution)
- SearchPage → echte API
- Bi-temporal-Toggle im TimeSlider
- Pioneer-vs-Gemini Comparison-View
- GDPR-Demo-Flow (DELETE-Source + Live-Cascade)
- Source-Record-Detail-Modal
- Trust-Weight-Editor
- Loading-Skeletons + Error-Boundaries
- Trust-Score-Pill als Hero-Element

## 14. Schnittstelle für Software & AI
- `/api/entities/{id}?as_of=` (siehe Temporal State)
- `/api/facts/{id}/validate`, `/flag`, `/edit`
- `/api/graph/neighborhood/{entity_id}`
- `/api/admin/reingest` (siehe Update Propagation)
- `/api/admin/pending-types` (siehe Autonome Ontologie)
- JWT-Auth-Middleware für `/api/*` (Supabase)
- MCP-Token-Auth (`agent_tokens`-Tabelle + Header-Check)
- Rate Limiting (`slowapi`)
- Cursor-Pagination
- Webhook-Outbound (HMAC-signed)
- `docs/api-consumer-guide.md`
- TypeScript / Python SDK (optional)
- Postman / Bruno Collection (optional)
- MCP stdio-Transport zusätzlich zu SSE (optional)

## 15. Eval Harness
- Resolver auf alle hr_records laufen lassen (check Raj Patel + Engineering Director)
- `uv run server-eval` Run + HTML-Report (≥6/8 PASS)
- Live-Test gegen `search_memory` MCP-Tool
- GDPR-Demo-Script `scripts/gdpr_delete_demo.sh`

## 16. Demo + Submission
- 1-2 Customer + Inazuma Daten konsistent vor-resolven
- `docs/pitch.md` Slide-Outline
- Demo-Choreographie testen (Akt 1 Layer + Akt 2 Revenue + Akt 3 Second-App)
- Akt 3 Second-App: minimaler HR-View auf Core-Daten
- Loom Video Recording
- Submission-Forms ausfüllen
- Aikido onboarden (Account → Repo → Screenshot)
- Pioneer-Submission-Text + Comparison-Tabelle
- Entire-Submission-Text (Coding-Workflow-Story)
