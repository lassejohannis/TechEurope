# Workstreams — 48h Build Split

Single Source of Truth für die Build-Aufteilung. Jeder Workstream ist **independent claimable** nach WS-0.

**Format pro Stream:** Owner, Time-Box, Inputs (Contracts die schon stehen müssen), Outputs (was du lieferst), Files (was du anlegst/änderst), Definition of Done.

**Claim-Process:** Trag deinen Namen oben in den Owner-Slot ein. Eine Person kann mehrere Streams claimen, aber nicht gleichzeitig — Streams in *Sequence*, nicht parallel.

---

## Critical Path Diagram

```
Samstag 08:00 ─────────────────────────────────────────── Sonntag 14:00

[WS-0 Foundation] (3h, blocking, 1 Owner)
    │
    ├─> [WS-1 Ingestion]      (6h, Sa 11-17)
    ├─> [WS-2 Resolver]       (8h, Sa 11-19)  
    ├─> [WS-3 Pioneer]        (6h hard cap, Sa 12-18)
    ├─> [WS-8 Eval-Harness]   (5h, Sa 11-16) ← Day 1!
    │
    └─> nach 4h von WS-2:
        ├─> [WS-4 Query-API]    (6h, Sa 15-21)
        │       │
        │       ├─> [WS-5 Neo4j-Projection] (4h hard cap Sa 14, parallel zu WS-4)
        │       ├─> [WS-6 Frontend Core UI] (10h, Sa 17 - So 09)
        │       └─> [WS-7 Revenue App]      (6h, So 06-12)
        │
        └─> [WS-9 Pitch + Polish] (4h, So 08-12)

Sonntag 12:00 — Final Integration + Demo-Run
Sonntag 14:00 — SUBMISSION DEADLINE
```

---

## WS-0 — Foundation (BLOCKING)

**Owner:** _claim_  
**Time-Box:** 3h (Samstag 08:00–11:00)  
**Inputs:** Nichts (kickoff)  
**Outputs:** Alles was Parallel-Streams freischaltet

### Tasks
1. Supabase Projekt up (oder local via `supabase start`)
2. Postgres Schema-Migration (`server/migrations/001_init.sql`):
   - `source_records`, `entities`, `facts`, `resolutions` Tabellen
   - `entity_type_config`, `edge_type_config` für Ontologien
   - bi-temporal `tstzrange + EXCLUDE GIST`-Constraint auf `facts`
   - Supersede-Trigger auf `facts`
   - Indexes (subject_id+predicate, object_id, current-only partial, pgvector HNSW)
   - RLS-Policies (single-tenant, alles read for `authenticated`)
3. YAML-Ontology-Seeds (`config/ontologies/{base,hr,sales,enterprise}.yaml`)
4. Ontology-Loader (`server/src/server/ontology/loader.py`) — bootet YAMLs in Config-Tabellen
5. FastAPI-Skeleton mit:
   - `GET /health` (existiert schon)
   - `POST /admin/reload-ontologies`
   - Supabase-Client-Wiring + Settings via `pydantic-settings`
6. Pydantic-Modelle für SourceRecord, Entity, Fact, Resolution
7. Frontend Project-Bootstrap-Check: `npm run dev` in `web/` läuft

### Definition of Done
- ✅ `psql` zeigt alle Tabellen
- ✅ `select * from entity_type_config` zeigt seed-Daten
- ✅ FastAPI antwortet auf `/health` und `/admin/reload-ontologies`
- ✅ Pydantic-Modelle importierbar in `from server.models import Entity, Fact`
- ✅ Schema in `docs/data-model.md` aktualisiert (final form)

### Hand-off
Drop in Team-Channel: *"WS-0 done. Schema published. Streams 1-3 + 8 unblocked."*

---

## WS-1 — Ingestion Pipeline

**Owner:** _claim_  
**Time-Box:** 6h  
**Inputs:** WS-0 (SourceRecord-Schema, Pydantic-Models)

### Tasks
1. Connector-Base-Class (`server/src/server/connectors/base.py`):
   ```python
   class BaseConnector(ABC):
       source_type: str
       def fetch(self) -> Iterable[SourceRecord]: ...
       def normalize(self, raw: dict) -> SourceRecord: ...
   ```
2. **Email-Mock-Connector** (`connectors/email_mock.py`) — liest `data/enterprise-bench/emails/*.jsonl`
3. **CRM-Mock-Connector** (`connectors/crm_mock.py`) — liest `data/enterprise-bench/crm/*.json`
4. **PDF-Adapter** (`connectors/pdf.py`) — `pdfplumber` für Text + Gemini+`instructor` für 1 Schema (Invoice ODER Resume)
5. Idempotent-Persist-Logic: `INSERT ... ON CONFLICT (id) DO UPDATE SET content_hash, ingested_at, ...`
6. Hash-Diff-Detection: bei `content_hash != last_hash`, dependent Facts auf `needs_refresh=true`
7. Connector-Template-Doc (`docs/connector-template.md`) — Skeleton + Beispiel für neuen Connector
8. CLI: `uv run server ingest --connector email --path data/enterprise-bench/emails/`

### Definition of Done
- ✅ `uv run server ingest --connector email` lädt SourceRecords in DB
- ✅ Re-running same command = no duplicates (idempotent)
- ✅ PDF-Adapter extrahiert mindestens Text + 1 strukturiertes Feld-Set
- ✅ Connector-Template-Doc readable für Stranger

### Files
```
server/src/server/connectors/
  __init__.py
  base.py
  email_mock.py
  crm_mock.py
  pdf.py
docs/connector-template.md
```

---

## WS-2 — Entity Resolution Cascade

**Owner:** _claim_  
**Time-Box:** 8h  
**Inputs:** WS-0 (Schema), WS-1 (SourceRecords flowing)

### Tasks
1. Pre-Normalize-Step (`server/src/server/resolver/normalize.py`):
   - lowercase, strip "Inc/Ltd/GmbH/BV", whitespace-collapse
2. Embedding-Layer (`resolver/embed.py`):
   - **Tier A:** `gemini-embed-004` auf `canonical_name + key_attrs`
   - **Tier B (opt-in):** Inference-Embedding für hot entities (Companies + Persons mit ≥5 Facts)
3. pgvector HNSW-Setup (Migration in WS-0 ergänzen falls fehlt): `m=16, ef_construction=64`, `ef_search=100/40`
4. Cascade-Resolver (`resolver/cascade.py`) — alle 5 Tiers
   - Tier 1: hard ID match (per entity_type unterschiedliche Felder)
   - Tier 2: alias-table lookup
   - Tier 3: embedding kNN über pgvector, threshold-Logik
   - Tier 3.5: Pioneer-Hook (Stub bis WS-3 fertig, fällt zurück auf Gemini Flash)
   - Tier 4: context-heuristics (email-domain → company)
   - Tier 5: ambiguity-inbox-write
5. Per-Type-Resolver (`resolver/types/{person,company,product}.py`)
6. Audit-Log: jede Auto-Merge-Decision in `resolution_signals: jsonb`

### Definition of Done
- ✅ `resolve(record)` für alle 5 Entity-Types testbar
- ✅ Test-Suite mit ≥10 known pairs (precision-at-1)
- ✅ Audit-Log in DB sichtbar pro Decision
- ✅ Threshold-Konstanten in `config.py` einstellbar (0.92/0.82)

### Files
```
server/src/server/resolver/
  __init__.py
  cascade.py
  normalize.py
  embed.py
  types/{person,company,product}.py
tests/test_resolver.py  (≥10 fixture pairs)
```

---

## WS-3 — Pioneer Fine-Tune (Hard-Cap 6h)

**Owner:** _claim_  
**Time-Box:** 6h, Hard-Cap Samstag 18:00  
**Inputs:** WS-0 (Schema), WS-1 (SourceRecords als Trainings-Input)  
**Fallback-Plan:** wenn Hard-Cap reißt → Tier 3.5 nutzt Gemini Flash mit `instructor`-Schema, Pioneer als "Day 2"-Story im Pitch.

### Tasks
1. Pioneer-Account + CLI auth (~30min)
2. Synthetic-Data-Pipeline (`server/scripts/gen_pioneer_training.py`):
   - Input: SourceRecords aus EnterpriseBench
   - Gemini 2.5 Pro generiert Trainingspaare `(text_chunk, structured_output)` als JSONL
   - Target: 200-500 Pairs
3. Pioneer-Fine-Tune-Job submitten — GLiNER2 auf E+R-Task
4. Inference-Wrapper (`server/src/server/extractors/pioneer.py`):
   ```python
   def extract(text: str) -> tuple[list[Entity], list[Fact]]: ...
   ```
5. Pioneer-vs-Gemini-Comparison-Eval (`server/scripts/compare_extractors.py`):
   - 10 fixture-chunks aus held-out EnterpriseBench
   - Run beide Modelle, output `comparison.json`
   - Frontend zeigt Tabelle (siehe WS-6)

### Definition of Done
- ✅ Fine-Tune-Job läuft oder ist durch
- ✅ `extract(text)` returnt strukturierten Output
- ✅ Comparison-Eval-JSON existiert mit 10 Beispielen

### Hard-Cap-Decision-Point: Samstag 18:00
- Wenn Modell läuft → Tier 3.5 wird scharf geschaltet
- Wenn nicht → `pioneer_extract_and_match()` returnt None, Cascade fällt durch zu Tier 4

### Files
```
server/src/server/extractors/
  __init__.py
  pioneer.py
  gemini_fallback.py    # für den Fall der Fälle
server/scripts/
  gen_pioneer_training.py
  compare_extractors.py
```

---

## WS-4 — Query API + MCP Tools

**Owner:** _claim_  
**Time-Box:** 6h  
**Inputs:** WS-2 (Entities + Facts populated), WS-0 (Schema)

### Tasks
1. **REST-Endpoints** (`server/src/server/api/`):
   - `GET /entities/{id}` — Entity + Trust-Score + Facts
   - `GET /facts/{id}/provenance` — Evidence-Chain
   - `POST /search` — Hybrid-Search (Semantic ∩ Structural)
   - `POST /query/cypher` (proxy zu Neo4j, falls WS-5 läuft, sonst 503)
   - `GET /vfs/{path:path}` — VFS-Read (List/Read/Glob)
   - `POST /vfs/propose-fact` — VFS-Write (intern propose_fact)
   - `DELETE /vfs/{path:path}` — VFS-Delete (intern mark_invalid)
2. **MCP-Server** (`server/src/server/mcp/`):
   - `search_memory(query, k)` — 3-Stage Hybrid
   - `get_entity(id)` — full entity card
   - `get_fact(id)` — single fact + provenance
   - `get_fact_provenance(fact_id)` — on-demand evidence chain
   - `list_recent_changes(since)` — change-feed
   - `propose_fact(...)` — agent fact submission, schreibt Resolution-as-SourceRecord
3. **Hybrid-Search-Implementation:**
   ```python
   def search_memory(query):
       semantic = pgvector_knn(gemini_embed(query), col="inference_embedding", k=20)
       mentions = pioneer_extract_mentions(query) or gemini_fallback_mentions(query)
       structural = sum([graph_traverse(resolve_mention(m), depth=1) for m in mentions], [])
       return rerank(intersect_or_union(semantic, structural))
   ```
4. **Trust-Score-View** in Postgres (Migration ergänzen):
   ```sql
   CREATE VIEW entity_trust AS
   SELECT e.id, e.canonical_name,
          AVG(f.confidence) * COUNT(DISTINCT f.source_id) * recency_decay(MAX(f.recorded_at)) AS trust_score
   FROM entities e JOIN facts f ON f.subject_id = e.id
   WHERE f.valid_to IS NULL
   GROUP BY e.id;
   ```

### Definition of Done
- ✅ Alle 6 MCP-Tools antworten auf Test-Calls
- ✅ Alle REST-Endpoints in OpenAPI sichtbar
- ✅ Hybrid-Search-Eval-Score auf Demo-Questions ≥80% (siehe WS-8)
- ✅ Trust-Score auf jeder Entity zurückgegeben

### Files
```
server/src/server/api/
  entities.py, facts.py, search.py, vfs.py, cypher_proxy.py
server/src/server/mcp/
  server.py, tools.py
```

---

## WS-5 — Neo4j Read-only Projection (Hard-Cap 4h)

**Owner:** _claim_  
**Time-Box:** 4h, Hard-Cap Samstag 14:00  
**Inputs:** WS-0 (Postgres-Schema), WS-2 (entities/facts ingestible)  
**Fallback-Plan:** wenn Cap reißt → `/query/cypher` returnt 503 mit ehrlichem Banner, im Pitch als "Day 2" framen.

### Tasks
1. Neo4j Aura Free-Tier setup (~30min): URI + Bolt-Credentials in `.env`
2. Sync-Worker (`server/src/server/sync/neo4j_projection.py` — Skeleton existiert, fertigstellen):
   - Supabase-Realtime-Subscription auf `entities` + `facts` Tabellen
   - Idempotente MERGE-Cypher pro Event
   - Retry mit exponential backoff bei Neo4j-Failure
3. Bootstrap/Replay-Function: `replay_all()` für initiale Sync nach Schema-Boot
4. Konstanten: `CREATE CONSTRAINT entity_id IF NOT EXISTS ...`
5. Drei vordefinierte Demo-Queries (existieren als Skeleton in `neo4j_projection.py`):
   - `acme_3hop_neighborhood`
   - `shortest_path_persons`
   - `champions_with_open_threads`

### Definition of Done
- ✅ INSERT in Postgres `entities` → erscheint in Neo4j innerhalb von <2s
- ✅ DELETE in Postgres → vanished in Neo4j
- ✅ `replay_all()` erfolgreich nach DB-Reset
- ✅ Mind. 1 Demo-Cypher returnt sinnvolle Ergebnisse

### Hard-Cap-Decision-Point: Samstag 14:00
- Wenn Sync-Worker stable → wird Demo-Feature
- Wenn nicht → Stream-Owner pausiert, hilft bei WS-4 oder WS-6

---

## WS-6 — Frontend Core UI

**Owner:** _claim_ (möglicherweise 2 Owner)  
**Time-Box:** 10h  
**Inputs:** WS-4 (REST-API definiert)

### Tasks
1. **VFS-Browser** (`web/src/pages/VfsExplorer.tsx`):
   - Tree-View mit Pfad-Struktur (`/companies/<id>/...`)
   - Klickbar pro Node → Detail-View
2. **Entity-Detail-View** (`web/src/pages/EntityDetail.tsx`):
   - Header: Name, Type-Badge, **Trust-Score-Pill**
   - Facts-List mit Confidence + Source-Chips
   - Validate-Buttons ("looks correct" / "flag wrong") pro Fact
   - Edit-Button → Modal mit Pydantic-validated Form
3. **Time-Travel-Slider** (`web/src/components/TimeSlider.tsx`):
   - Slider auf `recorded_at`, refetched Entity mit `?as_of=<ts>` Param
   - Entity-Card-State updated live
4. **Graph-Explorer** (`web/src/pages/GraphExplorer.tsx`):
   - react-flow Canvas
   - Custom EntityNode-Component (Avatar/Logo, Type-Badge, Trust-Pill)
   - Custom FactEdge mit Predicate-Label und Confidence-Strichstärke
   - Layout via dagre
   - onNodeClick → navigate to Entity-Detail
5. **Pending-Review-Queue** (`web/src/pages/AmbiguityInbox.tsx`):
   - Liste aller `Resolutions` mit `status=pending`
   - Pro Pair: Pick-One / Merge / Reject Buttons → POST to `/resolutions/{id}/decide`
6. **Streaming Ingestion Log** (`web/src/components/IngestionStream.tsx`):
   - Subscribed to Supabase-Realtime auf `source_records`, `facts`, `resolutions`
   - Live-Tail-View mit Color-Coded Events
7. **Volltext + Graph-Search** (`web/src/components/SearchBar.tsx`):
   - Single Input-Field, calls `/search` (hybrid)
   - Result-Cards mit Source-Chips + Trust-Score
8. **Pioneer-vs-Gemini Comparison-View** (`web/src/pages/ExtractorCompare.tsx`):
   - Lädt `comparison.json` aus WS-3
   - Side-by-side Tabelle (10 Examples × 2 Models × Quality + Latency + Cost)

### Definition of Done
- ✅ Alle 8 Views renderbar mit Demo-Daten
- ✅ Time-Slider live auf 1 Demo-Entity (Acme)
- ✅ Realtime-Stream zeigt mind. 5 verschiedene Event-Types
- ✅ Graph-Explorer rendert ≥30 Nodes mit Edges sauber

### Files
```
web/src/
  pages/{VfsExplorer,EntityDetail,GraphExplorer,AmbiguityInbox,ExtractorCompare}.tsx
  components/{TimeSlider,IngestionStream,SearchBar,EntityNode,FactEdge}.tsx
  hooks/{useEntity,useFacts,useGraph,useRealtime}.ts
```

---

## WS-7 — Revenue Intelligence App

**Owner:** _claim_  
**Time-Box:** 6h  
**Inputs:** WS-4 (Query-API), WS-6 (Component-Library)

### Tasks
1. **Sales-Action-Feed** (`web/src/revenue/ActionFeed.tsx`):
   - 3 Patterns prebuilt:
     - `silent_deal` (no activity in N days)
     - `champion_at_risk` (champion has left thread)
     - `expansion_signal` (positive feedback + usage uptick)
   - Pro Action: Finding, Evidence, Hypothesis, Recommended Action, Prepared Artifact
   - **Alle Daten via Query-API**, kein direct DB-Access (Review-Kriterium!)
2. **Deal-Evidence-View** (`web/src/revenue/DealDetail.tsx`):
   - 1 Demo-Deal (z.B. Acme Renewal 2026)
   - Zeigt alle Facts die Deal-Status begründen mit Source-Chips
3. **Draft-Generation** (`web/src/revenue/DraftModal.tsx`):
   - 2 Action-Types mit Gemini 2.5 Pro
   - Style-Template aus historischen Communications (3 latest emails)
   - Attribution wird mit-prompt'ed: "based on [fact-1, fact-2, ...]"

### Definition of Done
- ✅ Action-Feed zeigt 3 Patterns mit echten EnterpriseBench-Daten
- ✅ Deal-Evidence-View klickbar, Source-Chips funktional
- ✅ 2 Draft-Generation-Buttons funktionieren end-to-end

### Files
```
web/src/revenue/
  ActionFeed.tsx, DealDetail.tsx, DraftModal.tsx
  patterns/{silent_deal,champion_at_risk,expansion_signal}.ts
```

---

## WS-8 — Eval-Harness + Killer Features (Tag 1!)

**Owner:** _claim_  
**Time-Box:** 5h  
**Inputs:** WS-0 (Schema), WS-2 (mind. partial Resolver für Test-Daten)  
**Wichtig:** Tag-1-Asset, nicht Polish! Eval-Tabelle ist was Judges lesen.

### Tasks
1. **Eval-Harness** (`server/eval/harness.py`):
   - 6-8 Demo-Questions als YAML:
     ```yaml
     - question: "What is Acme's current renewal date?"
       expected_facts:
         - subject: "customer:acme-gmbh"
           predicate: "renewal_date"
           object: "2026-06-15"
       expected_sources: ["email:acme-renewal-2026", "crm:acme-opp-456"]
       confidence_min: 0.8
     ```
   - Test-Runner: ruft `search_memory` für jede Frage auf, vergleicht
   - HTML-Report-Output: Question | Expected | Actual | ✅/❌ | Sources cited
2. **GDPR-Source-Delete-Cascade**:
   - DB-Migration mit `ON DELETE CASCADE` auf `source_records → facts`
   - Backend-Endpoint `DELETE /admin/source-records/{id}` mit Confirmation
   - Demo-Script: lösche Source-Record → Facts verschwinden → Frontend updates live
3. **Per-Source Trust-Weighting** (`server/src/server/trust.py`):
   - Config: `source_trust_weights.yaml` (`{email: 0.8, crm_contact: 1.0, hr_record: 0.95, ...}`)
   - Trust-Computation in Auto-Resolution-Cascade nutzen (Authority-Tier)
4. **Time-Machine-Query-Endpoint** (Backend):
   - `GET /entities/{id}?as_of=<ts>` — bi-temporal mit `tstzrange @>`-Filter
   - Returns Entity + active Facts at that timestamp

### Definition of Done
- ✅ `uv run server eval` läuft Eval-Harness und gibt HTML-Report
- ✅ Mind. 6 von 8 Questions PASS
- ✅ GDPR-Demo-Script ist scriptbar reproduzierbar
- ✅ Trust-Weight-Tabelle YAML-konfigurierbar

### Files
```
server/src/server/eval/
  harness.py
  questions.yaml
  reporter.py
config/source_trust_weights.yaml
```

---

## WS-9 — Pitch + Polish + Submission

**Owner:** _claim_ (Sonntag-Owner)  
**Time-Box:** 4h, Sonntag 08:00–12:00  
**Inputs:** Alle vorigen Streams sollten am Sonntag-Morgen funktional sein

### Tasks
1. **Demo-Daten finalisieren**: 
   - Sample-Set aus EnterpriseBench gewählt (z.B. Acme + 2 weitere Customers)
   - Vor-Ingest aller Records, vor-resolved alle Entities
   - Bekannte ambiguous-Pairs in Inbox vorbereitet (1-2 für Demo)
2. **Demo-Choreografie**:
   - Akt 1: Layer Live-Demo (90s) — Streaming Ingestion Log + Pioneer-vs-Gemini-Comparison + Time-Travel-Slider
   - Akt 2: Revenue App (120s) — Action-Feed → Drill-into Deal → Draft-Generate
   - Akt 3: Second App (45s) — HR-View auf gleichen Core-Daten
3. **Architecture-Diagram** in `README.md` updaten (mermaid)
4. **Aikido-Screenshot** machen (Security-Report)
5. **Entire-Submission-Text** vorbereiten (Coding-Provenance-Story)
6. **Pioneer-Submission-Text** mit Comparison-Tabelle
7. **Pitch-Slide-Outline** in `docs/pitch.md`:
   - Slide 1: Problem (Context-Reconstruction-Tax)
   - Slide 2: Solution (2-Layer-Architecture)
   - Slide 3: Demo-Akts
   - Slide 4: Tech-Stack-Slide (Postgres SoT + Neo4j Projection + Pioneer + Gemini)
   - Slide 5: Side-Prize-Stack (Pioneer + Entire + Aikido)
   - Slide 6: Roadmap (Day 2 features: real connectors, Cognee-style ECL pipeline, etc.)
8. **Final-Submission**: Form ausfüllen, Repo-Link, Video-Recording

### Definition of Done
- ✅ Submission abgegeben vor 14:00
- ✅ Demo-Run mind. 1x komplett ohne Fehler durchgespielt
- ✅ Alle 4 Side-Prize-Submissions abgegeben (Aikido, Pioneer, Entire, Qontext-Track)

---

## Workstream-Owner-Tabelle (zu claimen)

| Stream | Time | Hard-Cap | Claim |
|---|---|---|---|
| WS-0 Foundation | 3h Sa 08-11 | 11:00 (blocking) | _____ |
| WS-1 Ingestion | 6h Sa 11-17 | — | _____ |
| WS-2 Resolver | 8h Sa 11-19 | — | _____ |
| WS-3 Pioneer | 6h Sa 12-18 | **18:00** | _____ |
| WS-4 Query-API | 6h Sa 15-21 | — | _____ |
| WS-5 Neo4j-Projection | 4h Sa 10-14 | **14:00** | _____ |
| WS-6 Frontend Core | 10h Sa 17-So 09 | — | _____ |
| WS-7 Revenue App | 6h So 06-12 | — | _____ |
| WS-8 Eval + Killer | 5h Sa 11-16 | — | _____ |
| WS-9 Pitch + Polish | 4h So 08-12 | **12:00** | _____ |

## Suggested Allocation für 4 Personen

```
Person A (Backend-Core):       WS-0 → WS-2 → (helps WS-4)
Person B (Backend-Pipeline):   WS-1 → WS-4 → WS-9
Person C (ML/Partner):         WS-3 → WS-5 → WS-8
Person D (Frontend/Demo):      WS-6 → WS-7 → WS-9
```

(WS-9 hat 2 Owner: Person B owned die Submission-Tasks, Person D die Demo-Choreografie.)

## Synchronisations-Punkte

- **Sa 11:00** — WS-0 Hand-off ("Schema published")
- **Sa 14:00** — WS-5 Hard-Cap (Go/No-Go für Neo4j)
- **Sa 18:00** — WS-3 Hard-Cap (Go/No-Go für Pioneer)
- **Sa 21:00** — End-of-Day-1 Sync, Backend-Streams müssen integrierbar sein
- **So 09:00** — Frontend-Core fertig, Revenue + Polish kann starten
- **So 12:00** — Final-Run-Through, dann Submission
- **So 14:00** — DEADLINE
