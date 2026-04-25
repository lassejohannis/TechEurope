# Technical Product Briefing (Team)

Verbatim from team's Notion. Preserved for Day-1 kickoff reference.

## Context

Wir bauen für den Big Berlin Hack ein zweischichtiges Produkt im Qontext-Track. Die Challenge: Company-Reality wird heute bei jedem AI-Call neu rekonstruiert. Unsere Antwort: Ein horizontaler Context-Layer im Core plus Revenue-Intelligence-App als Proof-of-Value.

Qontext's Direktive an uns: *„Use-case agnostic context layer at the core + revenue intelligence use case on top to visualize value."* Das ist nicht verhandelbar. Wer Revenue-Code im Core-Layer schreibt, hat die Mission verfehlt.

---

## Architektur-Prinzip

Zwei Schichten, hart getrennt. Der Core-Layer weiß nicht was Sales ist. Die Revenue-App konsumiert nur die öffentliche Query-API des Core-Layers.

Lackmus-Test: Wenn wir morgen eine Customer-Success-App, HR-App oder Finance-App oben drauf bauen würden, darf am Core-Layer kein Code geändert werden müssen.

---

## Layer 1: Core Context Engine

### Virtual File System

Abstrakte Schicht die heterogene Datenquellen als einheitlich adressierbare Nodes exponiert. Pfad-Struktur, nicht tabellarische Datenbank.

Beispiel-Pfade:

```
/companies/acme-corp/
/companies/acme-corp/contacts/max-mustermann
/companies/acme-corp/deals/q3-expansion
/companies/acme-corp/deals/q3-expansion/communications/
/companies/acme-corp/deals/q3-expansion/communications/2026-04-18-email-thread
```

Jeder Node hat: Path, Type, Metadata, Content, Source, Timestamp, Attribution.

Consumer-Apps fragen nicht Salesforce oder Gmail direkt. Sie fragen den VFS: „Gib mir alle Nodes unter /companies/acme-corp/deals/ mit Status=active."

### Ingestion-Connectors

**Minimum für MVP: 2 Quellen + Multi-Format-Reader.**

- **Email-Mock (Gmail-Shape):** Threads mit Teilnehmern, Timestamps, Content — aus JSON
- **CRM-Mock (HubSpot-Shape):** Accounts, Contacts, Opportunities, Activities — aus JSON

**Format-Reader (innerhalb der Adapter):** JSON, JSONL, CSV, **PDF** (Text via `pdfplumber`; strukturierte Felder bei Invoices/Resumes via Gemini + `instructor`-Schema). Doclinq als zusätzlicher Adapter falls Zeit bleibt — gleicher Pattern.

**Plug-in-Architektur:** Connector-Interface ist dokumentiert (`docs/connector-template.md`), neuer Connector in <30 Min schreibbar — Skeleton + Beispiel im Repo.

**Idempotent:** `content_hash` + deterministische IDs (`{source_type}:sha256:{hash}`). Mehrfach-Ingest desselben Records = Update, kein Duplikat.

**Gestrichen für 48h:** Slack (OAuth-Hölle), Google Docs/Notion Live-Auth. Mock-Versionen sind die Demo.

Jeder Connector ist stateless und minimal. Er pulled Rohdaten, normalisiert auf ein einheitliches Event-Schema, schiebt in den Layer. Keine Business-Logik im Connector.

Events haben standardisiertes Format:

```json
{
  "event_id": "...",
  "source": "...",
  "source_id": "...",
  "event_type": "...",
  "raw_content": "...",
  "extracted_entities": [],
  "timestamp": "...",
  "metadata": {}
}
```

### Entity Resolution

Erkennt dass dieselbe Person/Company in verschiedenen Quellen mit verschiedenen Identifikatoren auftaucht.

**Tooling-Entscheidung (post-Cowork-Research, 2026-04-25):** **Hand-rolled deterministic-first cascade.** ~150-200 LoC Python + SQL. Kein Splink, kein Zingg, kein Cognee.

Begründung: Probabilistische ER-Libraries optimieren auf große Korpora ODER labeled training pairs. Wir haben weder. 80% unserer Matches resolven deterministisch (`email == email`). Splink-Setup: 6-10h. Hand-rolled: 4h.

**Stack:**

- **Hand-rolled Cascade-Resolver** (200 LoC max) — siehe Pipeline unten
- **Gemini `text-embedding-004`** für Embeddings (Matryoshka auf 768d) — schon im Stack, kein Self-Host-Tax
- **Pre-Normalize vor Embed:** lowercase, Suffix-Strip ("Inc/Ltd/GmbH/BV"), Whitespace-Collapse — gibt mehr Lift als ein besseres Modell
- **pgvector HNSW** mit `m=16, ef_construction=64`, `hnsw.ef_search=100` (ingest) / `40` (query)
- **rapidfuzz** für String-Distance-Fallbacks
- **Pioneer (Fastino) GLiNER2-finetune** für E+R-Extraction am Hot-Path (Tier 3.5, siehe [`partner-tech.md`](partner-tech.md))
- **Gemini Flash** als Resolver-of-last-resort für Ambiguity-Inbox-Pairs (~$0.0001/Pair). Nie als Hot-Path-Matcher.

**Cascade-Pipeline:**

```python
def resolve(record: SourceRecord) -> Resolution:
    # Tier 1: hard IDs (idempotent, deterministic, ~80% der Matches)
    if hit := match_hard_id(record):  # email, domain, salesforce_id, slack_uid
        return Resolution(entity_id=hit, confidence=1.0, tier="hard_id")

    # Tier 2: structured aliases (resolver-table lookup)
    if hit := match_alias(record):
        return Resolution(entity_id=hit, confidence=0.95, tier="alias")

    # Tier 3: embedding kNN over canonical_name + key attrs
    candidates = pgvector_knn(record.embedding, k=10, threshold=0.82)
    if len(candidates) == 1 and candidates[0].score > 0.92:
        return Resolution(entity_id=candidates[0].id, confidence=candidates[0].score, tier="embedding")

    # Tier 3.5: Pioneer-finetuned E+R extractor confirms relationship
    if hit := pioneer_extract_and_match(record, candidates):
        return Resolution(entity_id=hit, confidence=0.90, tier="pioneer")

    # Tier 4: context heuristics (email domain → company etc.)
    if hit := match_context(record, candidates):
        return Resolution(entity_id=hit, confidence=0.85, tier="context")

    # Tier 5: ambiguity inbox (Gemini Flash für Borderline-Cases optional)
    return Resolution(entity_id=None, candidates=candidates, tier="inbox")
```

**Drei Resolver wired by entity type:** ein `resolve()`-Entry, Dispatch nach `entity_type`. Person-Resolver kennt Phonetic-Encodings, Company-Resolver kennt Suffix-Stripping, Product-Resolver ist deterministisch via SKU/GTIN. Cascade-Struktur identisch.

**Schwellwerte:** auto-merge >0.92, ambiguity-inbox 0.82–0.92, reject <0.82. Audit-Log auf jede Auto-Merge-Decision.

Bei Unsicherheit: Candidate-Set vorhalten. Nicht false-positive resolven. Merge ist günstig, Un-Merge ist Hölle.

### Embedding-Strategie (Two-Tier)

Wir embedden **nicht alles gleich**. Zwei Tiers:

**Tier A — Name-Embedding (Default, alle Entities):**
```python
text = normalize(canonical_name + " " + key_attrs)
# normalize: lowercase, strip "Inc/Ltd/GmbH/BV", collapse whitespace
embedding = gemini_embed_004(text, dim=768)  # Matryoshka
```
Billig, schnell, gut genug für Resolution-Blocking.

**Tier B — Inference-Embedding (opt-in, hot entities):**
Für "wichtige" Entities (Companies + Persons mit ≥5 verbundenen Facts) generieren wir zusätzlich ein **kontext-reiches Embedding**:

```python
def inference_embedding(entity: Entity) -> Vector:
    context = collect_graph_neighbors(entity, depth=1)  
    # → role, department, managed_projects, recent_activity, ...
    summary = gemini_flash.summarize(entity, context)
    # → "Max Mustermann is Head of IT, manages Project Alpha + Beta, 
    #    has 2 open tickets, reports to Anna Schmidt."
    return gemini_embed_004(summary, dim=768)
```

Storage: zweite Spalte `inference_embedding VECTOR(768)` auf `entities`. Separater HNSW-Index.

**Warum Two-Tier:**
- Tier A trägt 95% der Resolution-Workload (billig)
- Tier B macht **Semantic Search dramatisch besser** — *"Senior Engineers with high ticket load"* findet auch Personen, deren Titel "Senior" gar nicht enthält
- Tier B ist re-computed nur via `needs_refresh`-Flag, nicht eager bei jedem Edge-Update

**Demo-Wert:** Cross-Domain Discovery — eine Query findet semantisch ähnliche Konzepte über verschiedene Datenquellen hinweg. Das ist sichtbar besser als naive Name-Embeddings.

### Hybrid Search (search_memory MCP-Tool)

`search_memory` ist explicit **3-Stage Hybrid**: Semantic ∩ Structural → Rerank.

```python
def search_memory(query: str, k: int = 10) -> list[Result]:
    # Stage 1: Semantic
    q_emb = gemini_embed_004(query, dim=768)
    semantic = pgvector_knn(
        q_emb, 
        col="inference_embedding",  # Tier-B falls vorhanden, fallback Tier-A
        k=20, 
        threshold=0.7
    )

    # Stage 2: Structural — Entity-Mentions aus Query extrahieren, 1-Hop traversieren
    mentions = pioneer_extract_mentions(query)  # Pioneer-finetuned, 2. Use!
    structural = []
    for m in mentions:
        entity = resolve_mention(m)
        if entity:
            structural += graph_traverse(entity, depth=1)

    # Stage 3: Combine + Rerank
    candidates = intersect_or_union(semantic, structural)  # intersect bei viel signal, union bei wenig
    return rerank_by_confidence_and_recency(candidates)[:k]
```

**Warum Hybrid:**
- Pure Semantic: findet ähnliche Konzepte aber ignoriert Struktur ("alle Senior Engineers" → ja, aber wie viele Tickets haben sie?)
- Pure Graph: präzise Pfade aber keine Fuzzy-Begriffe ("MANAGES → IT_DEPT" findet nichts wenn Query "leitet die IT" sagt)
- Hybrid: **Best of both.** Intersection erhöht Precision, Union erhöht Recall.

**Pioneer-Bonus:** Tier 3.5 wird **zweitgenutzt** für Entity-Mention-Extraction aus der Query. Stärkt den Side-Prize-Claim ("our fine-tuned model is the backbone of both ingestion AND query").

### Graph Construction

Entitäten sind Nodes. Beziehungen zwischen ihnen sind typisierte Edges.

**Node-Types:** `Person`, `Company`, `Product`, `Document`, `Communication` + use-case-spezifische via Config (`Deal`, `Project`, `Ticket`...). Document und Communication sind first-class Entities mit Edges zu Participants/Authors, nicht nur SourceRecords.

**Edge-Types (vollständig):** `works_at`, `manages`, `authored`, `references`, `mentions`, `owns`, `assigned_to`, `participant_in`, `related_to`. Plus use-case-spezifische via Config (`champion_of` etc.).

**Konfigurierbar, nicht hardcoded:** Entity- und Edge-Types werden als **YAML-Ontologien** in `config/ontologies/*.yaml` definiert (dev-friendly, version-controlled, PR-diffbar) und beim Boot in `entity_type_config` / `edge_type_config` Postgres-Tabellen geladen (runtime-changeable, single source of truth). Ingestion validiert dagegen — neuer Use Case = neue YAML-Datei + Reload, kein Code-Change.

```yaml
# config/ontologies/hr.yaml
entities:
  Employee:
    properties:
      - {name: id, type: string}
      - {name: name, type: string}
      - {name: email, type: string}
  Department:
    properties:
      - {name: id, type: string}
      - {name: name, type: string}
relationships:
  works_in:
    from: Employee
    to: Department
    properties:
      - {name: since, type: date}
```

Boot-Loader: `config/ontologies/*.yaml → ontology_loader.py → INSERT INTO {entity,edge}_type_config`. Onthologie-Hot-Reload-Endpoint für Demo (`POST /admin/reload-ontologies`).

Edges tragen Metadata: `source_record_id`, `confidence`, `valid_from`, `valid_to`. Bi-direktional traversierbar (Indexes auf `(subject_id, predicate)` UND `(object_id, predicate)`).

Der Graph wird on-ingestion gebaut und inkrementell aktualisiert. Nicht alles ist ein Graph-Query, aber alles was Beziehungen braucht geht über den Graph.

### Temporal State

Jeder Fakt hat Validity-Span. Nicht nur „Max ist Champion von Deal X" sondern „Max war Champion von 2026-02-01 bis 2026-04-10, danach verifiziert keine Aktivität mehr."

Queries müssen zeitlich parametrisierbar sein: „Was war wahr am Datum Y?" muss funktionieren, nicht nur „Was ist wahr jetzt?"

**Implementierung (Postgres-konkret, post-Cowork):** `tstzrange` + `EXCLUDE USING GIST` + Supersede-Trigger. Keine `temporal_tables`-Extension (Supabase ships sie nicht).

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE facts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id UUID NOT NULL REFERENCES entities(id),
  predicate TEXT NOT NULL,                  -- string, nicht FK; flexibler
  object_id UUID REFERENCES entities(id),   -- nullable: entity-zu-entity
  object_literal JSONB,                     -- nullable: skalare Werte
  confidence NUMERIC(3,2) NOT NULL,
  source_id UUID NOT NULL REFERENCES source_records(id),
  derivation TEXT NOT NULL,                 -- "llm:gemini-2.0-flash", "rule:domain_match", "pioneer:gliner2-v1"
  valid_from TIMESTAMPTZ NOT NULL,
  valid_to TIMESTAMPTZ,                     -- NULL = open-ended (current)
  recorded_at TIMESTAMPTZ DEFAULT NOW(),
  superseded_by UUID REFERENCES facts(id),
  source_hash TEXT,                         -- für lazy re-derivation
  needs_refresh BOOLEAN DEFAULT FALSE
);

ALTER TABLE facts
  ADD CONSTRAINT facts_no_overlap
  EXCLUDE USING GIST (
    subject_id WITH =,
    predicate WITH =,
    tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz)) WITH &&
  );

CREATE INDEX facts_subject ON facts (subject_id, predicate);
CREATE INDEX facts_object ON facts (object_id);
CREATE INDEX facts_current ON facts (subject_id, predicate) WHERE valid_to IS NULL;

-- Supersede trigger: insert auf gleichem (subject, predicate) schließt alten Record
CREATE OR REPLACE FUNCTION supersede_previous_fact()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE facts
     SET valid_to = NEW.valid_from,
         superseded_by = NEW.id
   WHERE subject_id = NEW.subject_id
     AND predicate = NEW.predicate
     AND valid_to IS NULL
     AND id <> NEW.id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER facts_supersede
  BEFORE INSERT ON facts
  FOR EACH ROW EXECUTE FUNCTION supersede_previous_fact();
```

**Lazy Re-Derivation (statt eager Triggers):**

```sql
-- on ingest pipeline:
UPDATE facts SET needs_refresh = TRUE
 WHERE source_id = $1 AND source_hash <> $2;

-- on read or background batch:
SELECT id FROM facts WHERE needs_refresh = TRUE LIMIT 100;
```

**Hash:** `hash(source_content_hash + extractor_version)` — sonst triggert ein Prompt-Change keine Re-Derivation.

**Foot-guns:**
- Immer `tstzrange`, niemals `tsrange` (Mixed-Timezone-Bugs sind silent killers)
- "As-of"-Query nutzt GIST-indexable `@>` Containment
- Postgres 18 hat `WITHOUT OVERLAPS` nativ — Supabase ist auf PG15/16, also EXCLUDE-Pattern bleiben

**Demo-Scope:** **Time-Travel-Slider in der Entity-Detail-View** (siehe Demo-Killer-Features). UI-Slider pin't `recorded_at` und `tstzrange @>`, Entity-Card-State updated live. *Single feature outweighs three of your other planned demos.*

### Source Attribution

Jeder Fakt im Layer trägt Herkunft. Downstream-Consumer kann auf Attribution zugreifen.

Beispiel-Response auf Query „Ist Max Champion von Deal X?":

```json
{
  "answer": true,
  "confidence": 0.87,
  "evidence": [
    {
      "source": "gong_transcript_2026-03-15",
      "timecode": "00:23:45",
      "quote": "Max said he would drive the approval process"
    },
    {
      "source": "salesforce_opportunity_456",
      "field": "primary_contact",
      "value": "Max Mustermann"
    }
  ]
}
```

### Query API

Einheitliche Schnittstelle für alle Downstream-Apps. Zwei Access-Patterns:

**Path-based (VFS-Style):**

```
GET /nodes/companies/acme-corp/deals/q3-expansion
GET /nodes/companies/acme-corp/deals?filter=active
```

**Graph-based (Traversal-Style):**

```
QUERY: Find all Persons where champion_of relates to Deal
       with status=active and last_activity > 14_days_ago
```

Beide Patterns returnen strukturierte JSON mit Attribution.

### Neo4j Read-only Projection (post 2026-04-25)

Postgres bleibt Source-of-Truth. Neo4j ist eine **read-only Projection**, gepflegt via Supabase-Realtime.

**Architektur:**
```
[Postgres facts/entities INSERT]
    │
    ▼ Supabase Realtime
[server/sync/neo4j_projection.py]
    │
    ▼ idempotent MERGE-Cypher
[Neo4j Aura Free-Tier]
    │
    ▼ Cypher
[FastAPI /query/cypher endpoint]
```

**Routing-Regel in der Query-API:**
| Query-Type | Backend |
|---|---|
| `get_entity`, `get_fact`, `propose_fact`, Provenance-Joins, Time-Travel | Postgres |
| Multi-Hop-Pattern (`MATCH (a)-[*..3]->(b)`), Shortest-Path, GDS-Algos | Neo4j |
| Hybrid Search (`search_memory`) | Postgres pgvector ∩ Neo4j edges → Postgres rerank |

**Skalierbarkeits-Argument (Pitch-Antwort):** *"Postgres skaliert transaktional zu Milliarden Rows — Episode-Store, Audit-Log, Provenance bleiben hier. Neo4j skaliert Graph-Traversal zu 100M+ Edges — Multi-Hop-Queries und Pattern-Matching gehen dort. Jeder Layer skaliert in seinem Domain."*

**Failure-Mode:** Sync-Crash = Neo4j-Projection wird stale, **nichts korrumpiert**. Re-Sync via Replay aus Postgres möglich. Kein Dual-Write-Risiko weil Postgres die einzige Schreibseite ist.

**Hard-Cap:** Samstag 14:00. Wenn Sync-Worker bis dahin nicht stabil → Neo4j wird im Pitch als "Day 2" gestreamt, Demo läuft auf Postgres-only.

### Change Streams

Apps können auf Events subscriben:

```
SUBSCRIBE: entity_status_change where type=Deal
SUBSCRIBE: new_fact where category=champion_activity
```

Downstream-Apps reagieren reactive, ohne zu pollen.

### Was der Layer NICHT tut

- Keine Business-Logik (Was ein „guter Deal" ist, ist App-Wissen)
- Keine Notifications
- Keine Action-Generation
- Keine domain-spezifischen Begriffe (keine „Opportunities", „Champions", „Stages" als eingebaute Konzepte)
- **Kein Background-Worker für Re-Derivation.** `source_hash` + `extractor_version` werden gespeichert, Re-Derivation läuft on-demand bzw. bei Re-Ingest desselben Records. Kein Cron.

Der Layer kennt nur Entitäten, Beziehungen, Zeit, Attribution.

> **Note (2026-04-25):** frühere Cuts auf "VFS read-only" und "keine Ambiguity-Inbox-UI" wurden zurückgenommen. Vollständige Anforderungs-Abdeckung in [Full Requirements Coverage](#full-requirements-coverage-option-a) unten.

---

## Layer 2: Revenue Intelligence App

Läuft als normaler Client gegen die Query-API des Core-Layers. Importiert nichts Internes.

### Business-Logik (hier, nicht im Core)

Alle Revenue-Semantik ist App-Code:

- Pattern-Definitions (Was ist ein At-Risk-Deal? Was ist Churn-Signal?)
- Priorisierungs-Heuristiken
- Action-Templates und Draft-Generation
- User-Preference-Learning

### Kern-Features für Demo

**Morning Action Feed:**
Cron-Job läuft vor Demo-Zeit. Queried den Core-Layer nach Patterns. Generiert priorisierte Action-Liste. Jede Action hat Finding, Evidence, Hypothesis, Recommended Action, Prepared Artifact.

**Deal Evidence View:**
Single-Deal-Drilldown. Zeigt alle Facts die den Deal-Status begründen, mit Attribution zum Core-Layer. Demonstriert dass die App nur zusammenträgt was der Layer liefert.

**Multi-Role-Views:**
Drei UI-Sichten (Sales, CS, Leadership) die alle auf derselben Core-Layer-Data operieren. Beweis der Horizontalität.

### Draft-Generation

LLM-basiert mit Context vom Core-Layer. Bei Draft-Generation wird explizit Attribution mitgegeben:

- Welche Facts aus Layer wurden genutzt
- Welche Stakeholder-Context
- Welche historischen Communications als Style-Template

---

## Layer 3: Second App (nur für Demo)

Minimale zweite App, die am Pitch-Ende live gestartet wird. Zeigt dass der Core-Layer wirklich horizontal ist.

Vorschlag: Eine simple HR-Onboarding-View oder eine Finance-Briefing-View. Zeigt dieselben Core-Layer-Daten durch eine komplett andere Brille.

Minimal in UI, minimal in Logic. Zweck: beweisen dass neue Apps in Stunden schreibbar sind wenn Core-Layer existiert.

Nicht vorher hyped — Demo-Moment kommt als Überraschung am Ende.

---

## Tech-Stack-Empfehlungen (vom Team)

> **Note (2026-04-24):** diese Team-Empfehlungen wurden bereits teilweise durch gemeinsame Entscheidungen aktualisiert — siehe [`docs/stack.md`](stack.md) für den finalen Stack (Vite+React, Supabase als Single-DB statt Neo4j+Qdrant, Gemini als LLM).

**Core Layer:**

- Runtime: Node.js oder Python (was das Team schneller kann)
- Graph-DB: Neo4j (hat die beste Node.js/Python-Integration) oder Postgres mit recursive CTEs als Fallback
- Vector-Store für Entity-Resolution: Qdrant oder pgvector (wenn Postgres eh da ist)
- API-Layer: GraphQL oder REST — was schneller geht, beides ist akzeptabel

**Revenue App:**

- Frontend: Next.js mit Lovable für UI-Speed
- Backend: API-Client gegen Core-Layer
- LLM: Claude via Anthropic API (längerer Context besser für Draft-Generation)

**Ingestion:**

- Mock-Connectors die aus JSON-Files ingestieren statt echte APIs abzugreifen
- Spart Setup-Zeit, für Demo irrelevant ob Mock oder Real

**Deployment:**

- Vercel für Frontend
- Supabase oder Railway für Backend + DB

---

## Build-Priorisierung für 48h

> **Note (2026-04-25, Option A — voll erfüllen):** Verteilung neu gewichtet. Alle 10 Anforderungs-Sektionen werden gecovered. Revenue App gekürzt zugunsten Core-Vollständigkeit + Human-UI.

**45% Zeit auf Core Layer (Vollständig):**

1. Hand-rolled Cascade-Resolver für Person + Company + Product (Pioneer-Tier 3.5)
2. VFS mit Read **+ Write/Delete** (Write/Delete intern via `propose_fact` / `mark_fact_invalid`)
3. Query API (REST + 5 MCP-Tools + `get_fact_provenance`)
4. Graph Construction für die 9 Edge-Types, konfigurierbar via YAML-Ontologien
5. Source Attribution durchgängig (system/path/record-id/timestamp/method + confidence)
6. Bi-temporal Schema (tstzrange + EXCLUDE + Supersede-Trigger), eine "as-of"-Query
7. Auto-Resolution-Rules (Recency / Authority / Confidence / Cross-Confirmation)
8. Resolution-Decision Traceability (`resolution_signals: jsonb`)
9. PDF-Adapter mit Text + 1 strukturiertem Schema (Invoice oder Resume)
10. Diff in Change-Events (über `superseded_by` Pointer)
11. Document/Communication als first-class Entity-Types
12. Two-Tier Embeddings (Name-default + Inference-rich für hot entities)
13. Hybrid Search (`search_memory` als Semantic ∩ Structural → Rerank)

**5% Zeit auf Neo4j-Projection (NEU, Tag 1 hard-cap Samstag 14:00):**

1. Neo4j Aura Free-Tier setup
2. `server/sync/neo4j_projection.py` — Supabase-Realtime-Listener → idempotent MERGE-Cypher
3. Cypher-Query-Endpoint in FastAPI für Demo-Queries
4. Eine Cypher-Wow-Demo-Query getestet (3-Hop-Pattern)

**Hard-Cap-Regel:** Wenn Samstag 14:00 nicht steht → Postgres-only weiter, Neo4j wird "Day 2" im Pitch.

**20% Zeit auf Human-Facing UI (NEU, Pflicht):**

1. **VFS-Browser** mit Detail-Views pro Node (klickbar, full-detail)
2. **Pending-Review-Queue** für Ambiguity-Pairs + Conflicts (Pick-One / Merge / Reject Buttons)
3. **Validate-UI:** "Looks correct" / "Flag as wrong" Buttons pro Fact-Card
4. **Edit-UI:** Manuelle Korrekturen mit Edit-History (schreibt SourceRecord)
5. **Volltext + Graph-Search**

**15% Zeit auf Revenue App (gekürzt):**

1. Sales Action Feed mit **3** prebuilt Patterns (statt 5-7)
2. Deal Evidence View für **1** Demo-Deal
3. Draft-Generation für **2** Action-Types

**Gestrichen:** CS-View, Leadership-View, mehrere Patterns. Eine glasklare Sales-Story reicht.

**10% Zeit auf Eval-Harness + Demo-Killer-Features (Tag 1!):**

1. **Eval-Harness** mit 6-8 reproduzierbaren Demo-Questions (`question → expected facts → cited sources`)
2. **Time-Travel-Slider** in der Entity-Detail-View — UI-Slider pin't `recorded_at`, Entity-Card-State updated live. *Single feature outweighs three of your other planned demos.*
3. **Trust-Score auf jeder Entity-Card:** `trust = avg(confidence) × source_diversity × recency_decay`. Drei Zeilen SQL, riesige perceived sophistication. Erfüllt direkt Per-Source Trust-Weighting (Req 6.2).
4. **Streaming Ingestion Log** via Supabase Realtime (SourceRecord → Facts → Resolutions live tail)
5. **GDPR Source-Delete-Cascade** (~30 Zeilen, Killer für Enterprise-Judges)
6. **Pioneer-vs-Gemini Comparison-View** — side-by-side Tabelle für 10 Beispiele. Belegt den Pioneer-Side-Prize claim glaubhaft.
7. **Cypher-Wow-Query auf Neo4j-Projection** — z.B. *"Find all Persons connected to Acme within 3 hops, group by relationship type"* oder *"Shortest path between Alice and any Customer"*. Pitch-Story: "Postgres skaliert transaktional, Neo4j skaliert Multi-Hop — jeder Layer in seinem Domain."

**5% Zeit auf Second App + Pitch-Integration:**
Minimal. HR-View auf denselben Core-Daten. Demo-Transitions testen.

---

## Demo-Flow (Technical View)

Der Demo-Moment muss beide Layer zeigen.

**Akt 1: Layer Live-Demo (90 Sekunden)**
Browser-Tab mit Core-Layer-UI (minimal debug-View). Live-Ingestion von 2-3 Quellen sichtbar. Entity-Resolution-Visualisierung („Max in Source A wurde resolved zu Entity X"). Eine Query-API-Demonstration im Browser-DevTools oder simpler Admin-UI.

**Akt 2: Revenue App (120 Sekunden)**
Neuer Browser-Tab. Revenue-App zeigt Morning-Feed. Jury-Member interagiert. Draft wird generiert. Evidence-Chain wird gezeigt. Alle Daten kommen beweisbar aus Query-API-Calls (Network-Tab könnte gezeigt werden).

**Akt 3: Second App (45 Sekunden)**
Dritter Browser-Tab. Zweite App läuft, zeigt dieselben Daten in anderer Brille. Betonung: Core-Layer unverändert.

---

## Risiken und Mitigationen

**Risiko: Entity Resolution funktioniert live schlecht.**
Mitigation: Pre-resolved Demo-Daten mit explizit getesteten Fällen. Live-Resolution nur für 1-2 hochkontrollierte Beispiele.

**Risiko: Core-Layer sieht aus wie Database-Wrapper.**
Mitigation: Explizit VFS-Path-Struktur und Graph-Visualisierung in UI zeigen. Nicht nur „wir haben eine DB mit API" sondern „wir haben einen structured state mit navigierbarer Ontologie."

**Risiko: Revenue-App wirkt wie Main-Product und Layer als Nebenwerk.**
Mitigation: In Demo-Choreografie den Layer als Hero-Element framen, Revenue-App als Proof. Pitch-Sprache: „Wir haben die Infrastruktur gebaut. Die Revenue-App ist der erste Beweis."

**Risiko: Zu viele Features, keins funktioniert richtig.**
Mitigation: Scope-Brutalität. Was nicht auf der obigen Prioritäts-Liste steht, wird verworfen. Lieber 4 Features die glänzen als 8 die stottern.

**Risiko: Wir bauen Splink/Cognee/Graphiti von Grund auf nach.**
Mitigation: Splink in Hour 1 pip-install + minimal-pipeline. Cognee-Schema vor erstem Migration-File lesen. Graphiti-Extraction-Prompts kopieren + auf Gemini umschreiben. Wer "ich schreib das schnell selbst" sagt, wird overruled.

**Risiko: Option-A-Scope (alle 10 Requirements) frisst Demo-Polish.**
Mitigation: Revenue App ist auf 3 Patterns / 1 Deal-View / 2 Action-Types reduziert. Eval-Harness auf 6-8 Questions. Second App auf nackte HR-View. Wenn am Sonntag 8:00 noch was wackelt: Revenue-Patterns weiter cutten, niemals Core- oder Human-UI-Requirements.

**Risiko: Human-UI wird Klick-Demo statt funktional.**
Mitigation: Validate/Pending-Review-Queue/Edit ALLE schreiben echte SourceRecords — keine Fake-Buttons. Eval-Harness testet, dass Edit→Re-Query den geänderten Fact zurückgibt.

---

## Full Requirements Coverage (Option A)

Verbindliche Coverage der 10 Anforderungs-Sektionen aus dem externen Requirements-Brief. Status: **alles must-build**, nichts mehr "nice-to-have".

### 1. Data Ingestion
- **1.1** Multi-Format: JSON, JSONL, CSV, **PDF** (text via `pdfplumber`, structured fields via Gemini + `instructor` für ≥1 Doc-Type). Doclinq als optionaler Adapter.
- **1.2** Plug-in-Connector-Architektur. Interface dokumentiert in `docs/connector-template.md`. Neuer Connector in <30 Min.
- **1.3** PDF-Strukturextraktion: ein Pydantic-Schema pro Doc-Type (Invoice oder Resume für Demo).
- **1.4** Idempotent: `content_hash` + deterministische IDs. Re-Ingest = Update, kein Duplikat.

### 2. Virtual File System
- **2.1** Hierarchische Pfade `/companies/<id>/deals/<id>/...`
- **2.2** Jeder Node: path, type, content, metadata, source_reference, timestamps.
- **2.3** Operations: List, Read, **Write, Delete, Glob-Search**. Write/Delete intern via `propose_fact` / `mark_fact_invalid` — Markdown bleibt deterministische Projection, aber API erfüllt Anforderung.
- **2.4** Browser-UI als Product-Surface, jeder Node klickbar mit Full-Detail-View.

### 3. Entity Resolution
- **3.1** Cross-Source via Splink + pgvector-Blocking.
- **3.2** Entity-Types: `Person`, `Company`, `Product`, **`Document`, `Communication`** (alle first-class).
- **3.3** Signale: ID-Match → Structured-IDs → Embedding-Similarity → Context-Heuristics.
- **3.4** Resolution-Decisions traceable: Splink-Match-Weights pro Comparison-Column werden in `resolution_signals: jsonb` gespeichert. Decision-View zeigt "warum hat das System gemerged".
- **3.5** Pending-Review-Queue (UI!) statt Auto-Merge bei Score 0.5–0.95.

### 4. Graph Construction
- **4.1** Resolved Entities = Nodes, Beziehungen = typisierte Edges.
- **4.2** Edge-Types: `works_at`, `manages`, `authored`, `references`, `mentions`, `owns`, `assigned_to`, `participant_in`, `related_to`. + use-case-spezifische via Config.
- **4.3** Edge-Metadata: source, confidence, valid_from/to.
- **4.4** Bi-direktional: Indexes auf `(subject_id, predicate)` UND `(object_id, predicate)`.
- **4.5** Inkrementell beim Ingest aufgebaut.

### 5. Source Attribution
- **5.1** Jeder Fact zwingend attribuiert. DB-Constraint: `derived_from` NOT NULL und non-empty.
- **5.2** Source-Reference enthält: `system`, `path/endpoint`, `record_id`, `timestamp`, **`method`** (z.B. "regex_extract", "llm_gemini_2.0", "human_input").
- **5.3** Confidence-Score Pflicht bei LLM/Inferenz-Extraktion (DB-Constraint: `method LIKE 'llm_%'` → `confidence IS NOT NULL`).
- **5.4** Provenance über Query-API: dediziertes MCP-Tool `get_fact_provenance(fact_id)` + REST-Endpoint.
- **5.5** Rückverfolgbar bis Original-SourceRecord (über `derived_from` → SourceRecord-Row mit `source_uri`).

### 6. Conflict Detection & Resolution
- **6.1** Auto-Detection bei (subject, predicate)-Kollision mit unterschiedlichem `object`. EXCLUDE-Constraint triggert; conflicting Facts bekommen `status: disputed`.
- **6.2** Auto-Resolution-Rules als Cascade:
  1. **Recency:** neuere `valid_from` schlägt ältere bei gleicher Source-Authority
  2. **Authority:** `source_trust_score` aus Per-Source-Trust-Weighting-Tabelle
  3. **Confidence:** höhere Confidence gewinnt
  4. **Cross-Confirmation:** Fact mit ≥2 unabhängigen `derived_from` schlägt Single-Source
- **6.3** Pending-Review-Queue mit UI (Liste, Pick-One, Merge, Reject).
- **6.4** Manual Resolutions als Audit-Trail in SourceRecord(`type=human_resolution`).

### 7. Query API
- **7.1** Path-based: `GET /nodes/{path}` + Glob.
- **7.2** Graph-Traversal: `POST /query/traverse` mit Cypher-ähnlichem JSON-DSL.
- **7.3** Jede Response: `{value, confidence, evidence: [{source, ...}]}`.
- **7.4** REST + JSON. MCP-Tools auf gleiche Funktionen mappable.

### 8. Human-Facing UI (Pflicht-Sektion, vorher gestrichen, jetzt in)
- **8.1** Inspect: VFS-Browser mit Detail-Views.
- **8.2** Validate: "Looks correct" / "Flag as wrong" Buttons pro Fact-Card → schreiben Validation-SourceRecord.
- **8.3** Edit: Manuelle Korrekturen mit Edit-History (jede Edit = neuer SourceRecord).
- **8.4** Conflict-Review-Queue (= 6.3).
- **8.5** Volltext + Graph-Search.

### 9. Generalization (Qontext-kritisch)
- **9.1** Kein Code hartcoded auf EnterpriseBench. Datenpfade in Config.
- **9.2** Connector-Interface dokumentiert (<30 Min für neuen Connector). Skeleton + Beispiel im Repo.
- **9.3** Entity-/Edge-Types konfigurierbar via `entity_type_config` / `edge_type_config` Tabellen, init via JSON-Seed.
- **9.4** Keine Use-Case-Semantik im Core. Review-Kriterium für jeden PR.

### 10. Update Propagation
- **10.1** Source-Changes: Polling (für Mock-Files via FS-Watch) und Webhook-Endpoint vorbereitet.
- **10.2** Change-Events subscribebar via Supabase Realtime auf `facts` und `entities`.
- **10.3** Diff-Information in Events: über `superseded_by`-Pointer kann Pre-Fact mitgeladen werden; API-Layer komponiert `{old, new}` payload.

### Engineer-Entscheidungen
- **Mit Rückfrage:** Tech-Stack, Scope-Cuts, Default-Sets für Entity-/Edge-Types.
- **Selbst:** Implementation-Details, Code-Struktur, Library-Choices, Testing-Approach.

### Nicht mehr verhandelbar
Kein "we can ship this without UI" mehr. Kein "ambiguity inbox is data-only" mehr. Kein "VFS read-only" mehr. Diese Cuts wurden 2026-04-25 zurückgenommen.

---

## Adopted OSS — nicht selbst nachbauen

Aus der Cowork-Research (2026-04-25). Wer "ich schreib das schnell selbst" sagt, wird overruled. **Wer "ich integriere noch schnell Cognee/Splink" sagt, wird auch overruled.**

**Pip install:**
- **[instructor](https://github.com/instructor-ai/instructor)** — strukturierte Gemini-Outputs für Fact-Extraction. **Hard must.** Rettet vor JSON-Parsing-Hell.
- **rapidfuzz** — String-Distance-Fallback in C++.
- **pdfplumber** — PDF-Text-Extraktion.
- **pgvector + HNSW** — schon im Stack.

**Steal patterns, do NOT import:**
- **[Cognee](https://github.com/topoteretes/cognee)** — DataPoints-Idee (typed Pydantic + Postgres-Mirror) klauen. Nicht runtime-integrieren — Postgres-only-Retrofit kostet 6h.
- **[Graphiti](https://github.com/getzep/graphiti)** (Zep) — Edge-Property-Pattern + Bi-temporal-Invalidation + Extraction-Prompts ansehen. **Nicht installieren**, auch nicht jetzt wo wir Neo4j haben. Begründung: End-to-End-Pipeline (würde 60% unserer Architektur ersetzen), Bi-temporal-Konflikt (Postgres EXCLUDE vs Graphiti App-Logic), Pioneer-Story kaputt, 48h-Lernkurve. Patterns klauen, Runtime nicht. **Hard rule:** wer am Samstag "lass mal Graphiti einbauen" sagt → 60min Begründungs-Pflicht oder overruled.
- **[LightRAG](https://github.com/HKUDS/LightRAG)** — Dual-Level-Retrieval-Pattern in `search_memory` MCP-Tool replizieren (entity-mention + topical phase). Lib nicht ziehen.

**Don't even click the docs (Traps):**
- **[Splink](https://github.com/moj-analytical-services/splink)** — Will Labeled-Pairs + EM-Training. 6-10h Time-to-Value, hand-rolled Cascade ist 4h. **Zurückgenommen 2026-04-25.**
- **Senzing** — closed-source, Demo-opaque, Lizenz-Trap.
- **Zingg** — Spark-Setup eats 3h.
- **OpenLineage/Marquez** — falsche Abstraktionsebene (Dataset-level statt Fact-level).
- **LangChain Graph** — Toy-Abstraktion.
- **GraphRAG** (Microsoft) — Leiden-Communities + per-Community-LLM-Summaries. $500-650 Indexing-Cost auf Real-Benchmarks. Demo-Slide-Candy.
- **temporal_tables** — C-Extension, Supabase ships sie nicht.
- **HippoRAG / PPR** — needs in-memory graph. Faken via Two-Hop-SQL falls überhaupt.

## Partner-Tech-Allokation

Vollständige Spec in [`partner-tech.md`](partner-tech.md). Kurzform:

| Partner | Wofür | Time-Box |
|---|---|---|
| **Pioneer (Fastino)** | GLiNER2-finetune für E+R-Extraction am Hot-Path (Cascade Tier 3.5). Synthetic Data aus EnterpriseBench via Gemini. | **6h hard cap.** Fallback = Gemini Flash. |
| **Google DeepMind (Gemini)** | Embeddings (`text-embedding-004`), Ambiguity-Resolution (`gemini-2.0-flash`), Draft-Generation + multimodal PDF (`gemini-2.5-pro`), Eval-Harness | drüber verteilt |
| **Entire** | Dev-Tool: Provenance + Checkpoints fürs Coding-Workflow. **Nicht im Produkt verbaut.** | Day-1 CLI-Setup, ~30min |
| **Aikido** | Repo-Security-Scan, Side-Prize 1000€ | Day-1 Connect, ~30min |

---

## Was Engineers wissen müssen bevor sie Code schreiben

1. Core-Layer-Code darf keine Revenue-Terminologie enthalten. Review-Kriterium.
2. Alle Revenue-App-Daten kommen über Query-API, nie direct DB-Access. Review-Kriterium.
3. Attribution muss in jedem API-Response enthalten sein. Nicht optional.
4. Temporal-State kann im MVP simpler sein (nur `valid_from`/`valid_to`), aber darf nicht komplett fehlen.
5. Wenn ihr vor einer Design-Entscheidung steht die „für Revenue wäre es so einfacher" sagt: Die horizontale Variante gewinnt.

---

## Offene technische Entscheidungen — RESOLVED (2026-04-25)

1. ~~Graph-DB vs Postgres~~ → **Postgres mit reified Facts in einer Tabelle** (siehe Temporal-State-Schema oben). Keine Neo4j.
2. ~~GraphQL vs REST~~ → **REST + MCP-Server** (5 Tools). Siehe [`docs/mcp-tools.md`](mcp-tools.md).
3. ~~LLM-Provider~~ → **Gemini Flash**, ausschließlich für Ambiguity-Resolution (post-Splink) und Draft-Generation. **Nicht Hot-Path-Matcher.**
4. ~~Mock vs Real Connectors~~ → **Mock-from-JSON, max 2 Sources** (Email + CRM).
