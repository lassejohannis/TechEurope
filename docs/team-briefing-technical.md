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

#### VFS — Status (2026-04-25)

**Was steht:**

| Komponente | Status |
|---|---|
| `GET /api/vfs/{path:path}` Endpoint | ✅ live (`server/src/server/api/vfs.py`) |
| `POST /api/vfs/propose-fact` | ✅ live (Agent-Schreibpfad) |
| `DELETE /api/vfs/{path:path}` | ✅ live (mark-fact-invalid) |
| `_SLUG_TO_TYPE`-Mapping (`/companies` → `company`, `/persons` → `person`, …) | ✅ in vfs.py — 6 Slugs gemappt |
| Pfad-zu-Children-Resolution (`/companies/{slug}/contacts` → Personen mit `works_at` zur Company) | ✅ live über Edge-Joins |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| **Forward-Lookup `vfs_path` in attrs** | 0 von 306 Entities haben `attrs.vfs_path` gesetzt. Die Reverse-Direction (`entity_id → kanonischer Pfad`) ist heute durch String-Konstruktion implizit, aber nicht persistiert. Heißt: zwei Personen mit gleichem Namen haben den gleichen Pfad und kollidieren |
| **Slug-Eindeutigkeit nicht enforced** | `companies/{slug}` könnte mehreren entities matchen wenn `canonical_name` kollidiert. Heute kein Unique-Index auf `(entity_type, slug(canonical_name))` |
| **Type-Slug-Mapping hardcoded** | `_SLUG_TO_TYPE` ist Code-festverdrahtet, nicht aus `entity_type_config` gelesen. Neuer Type via YAML → VFS rendert ihn nicht |
| **Glob-Search** (Req 2.3) | `/companies/**/deals` ist nicht implementiert |
| **VFS-Tree-Frontend** | Apo's Skeleton, mock data — wired in [Plan A](#human-facing-ui-surfaces-plan-a--vollausbau-todo) als P0 |
| **VFS-as-Write-Surface** | aktuell nur `propose-fact` und `delete`. Kein direktes "Edit-Node-Content" — Edit geht über `/api/facts/{id}/edit` (auch TODO) |

**Anforderung (Req 2):** Pfad-basiertes Adressing mit List/Read/Write/Delete/Glob, jeder Node klickbar mit Full-Detail-View.

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **Resolver schreibt `vfs_path`** in entity.attrs beim Insert: `f"/{entity_type_plural}/{slug}"`. Slug aus `canonical_name` normalisiert; bei Kollision suffix `-2`, `-3` | WS-2 | 30min |
| 🟡 P1 | **Unique-Index `(entity_type, attrs->>'vfs_path')`** — DB-side Konsistenz | WS-0/2 | 15min |
| 🟡 P1 | **Type-Slug-Mapping aus entity_type_config lesen** statt hardcoded `_SLUG_TO_TYPE` (Lookup beim VFS-Request, gecacht via @lru_cache) | WS-4 | 45min |
| 🟢 P2 | **Glob-Search-Endpoint** `GET /api/vfs/_glob?pattern=/companies/**/deals` mit `LIKE`/`SIMILAR TO` Postgres-Query | WS-4 | 1h |

**Pitch-Story:** "Salesforce, Gmail, Slack hatten nie eine gemeinsame Pfad-Struktur. Wir geben dem Business eine — `/companies/inazuma/deals/q3-renewal`. Filesystem-Metapher für Geschäftsdaten."

### Ingestion-Connectors

**Anforderung:** Jegliche Art von Dokument muss einspeisbar sein, oder Connector zu einer App, die Daten liefert. Generalization (Req 9) heißt: ein neuer Source-Type = ein neuer Connector, kein Code-Change im Core. Das Set unten ist Demo-Coverage für EnterpriseBench, das Pattern ist generisch.

**Plug-in-Architektur (✅ steht):** `BaseConnector(ABC)` mit zwei abstract-methods (`discover(path)` → Iterator, `normalize(raw)` → SourceRecord) plus `ingest(path, db, batch_size)`. Registry per `register()`-Decorator. Neuer Connector = Subclass + 2 Methoden + register. Skeleton: `server/src/server/connectors/base.py`. Connector-Template-Doc: `docs/connector-template.md`.

**Idempotent (✅ steht):** Connectors hashen den raw payload (sha256), bilden deterministische `id` aus `source_type + content_hash`, und upserten via Postgres. Mehrfach-Ingest desselben Records = no-op. Bei Hash-Drift markiert `diff.py` abhängige Facts als `needs_refresh` → Lazy Re-Derivation.

**SourceRecord-Schema (Postgres `source_records`):**

```sql
id              text PRIMARY KEY     -- {source_type}:sha256:{hash}
source_type     text NOT NULL        -- 'email' | 'crm' | 'hr_record' | …
source_uri      text                 -- file path / URL / API endpoint
source_native_id text                -- IDs from source system
payload         jsonb NOT NULL       -- raw, normalized JSON
content_hash    text NOT NULL        -- for diff/idempotency
ingested_at     timestamptz          -- when we wrote it
extraction_status enum('pending'|'extracted'|'failed')
superseded_by   text                 -- diff chain
```

**Connectors heute (2026-04-25):**

| Connector | source_type | Status | Records ingest'ed |
|---|---|---|---|
| `EmailConnector` | `email` | ✅ live | 11,928 (`Enterprise_mail_system/emails.json`) |
| `CRMConnector` (umbrella) | `crm` → spezialisiert auf `customer`/`client`/`product`/`sale` | ✅ live | 13,510 sale + 1,351 product + 400 client + 90 customer |
| `HRConnector` | `hr_record` | ✅ live | 1,260 (`Human_Resource_Management/Employees/employees.json`) |
| `InvoicePDFConnector` | `invoice_pdf` | ⚠️ Code da, aber pattern-restricted auf `invoice_*.pdf` — nicht generisch | 0 (Workspace hat keine Invoice-PDFs unter dem Pattern) |

CLI: `uv run server ingest --connector all --path data/enterprise-bench/`. Aktuell ingest-fähig: 28,539 records.

**EnterpriseBench Source-Coverage (was geht, was fehlt):**

| Folder | Format | Inhalt | Status |
|---|---|---|---|
| `Enterprise_mail_system/` | JSON | Emails (11.9k threads) | ✅ ingest'd |
| `Customer_Relation_Management/` | JSON | customers, products, sales | ✅ ingest'd |
| `Business_and_Management/` | JSON | clients, vendors | ✅ ingest'd (clients) — **vendors fehlen** |
| `Human_Resource_Management/Employees/` | JSON | employees.json | ✅ ingest'd |
| `Collaboration_tools/` | JSON | conversations.json (6.3 MB Slack-like chat) | ❌ kein Connector |
| `Enterprise Social Platform/` | JSON | posts.json (1.7 MB social-feed) | ❌ kein Connector |
| `Inazuma_Overflow/` | JSON | overflow.json (13 MB Q&A platform) | ❌ kein Connector |
| `IT_Service_Management/` | JSON | it_tickets.json (~190 KB tickets) | ❌ kein Connector |
| `Policy_Documents/` | PDF (×25) | Corporate Governance, AUP, Code of Ethics, Data Protection, … | ❌ PDF-Connector matcht nur `invoice_*.pdf`, nicht generische Policy-PDFs |
| `Workspace/GitHub/GitHub.json` | JSON | ReAct-Agent-Tasks (issues, repo-meta) | ❌ Sonderfall (Agent-Transkript) — niedrige Demo-Priorität |
| `tasks.jsonl` | JSONL | Agent-Tasks Demo-Set | ❌ Sonderfall — niedrige Demo-Priorität |

**Format-Reader-Status:**

| Format | Status | Wo |
|---|---|---|
| JSON / JSONL | ✅ Standard via `json.load` in jeder Connector | `crm.py`, `email.py`, `hr.py` |
| CSV | ⚠️ Kein Connector ingest'd CSV — nur `Inazuma_Overflow/.cache/raw_employees.csv` als source-of-source vorhanden | nicht relevant |
| PDF Text | ✅ `pdfplumber` integriert in `connectors/pdf.py` | nur für invoices |
| PDF strukturierte Extraktion | ✅ `gemini_extract_invoice` via `extractors/gemini_structured.py` (Pydantic schema) | nur invoice — Resume / Policy-Doc fehlen |
| Markdown / TXT | ❌ kein Reader | n/a |
| Audio | ❌ — Gradium würde dafür sein, nicht im Stack | n/a |

**Lücken-Liste (priorisiert für den 48h-Hack):**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **Generic-PDF-Connector** für `Policy_Documents/*.pdf` — Text-Extract via pdfplumber, structured Gemini-Extract auf Schema `{title, scope, effective_date, parties, sections[]}` | Kathi | 1h |
| 🔥 P0 | **CollaborationConnector** für `conversations.json` — Slack-Style mit thread_id, participants, message_text | Kathi | 30min (gleiches Pattern wie Email) |
| 🟡 P1 | **ITSMConnector** für `it_tickets.json` — sehr ähnlich CRM-Pattern, gibt SLA + assigned_to-Beziehungen | Kathi | 30min |
| 🟡 P1 | **Vendors** in CRM-Connector hinzufügen (gleiche Datei, anderer Tab) | Kathi | 15min |
| 🟢 P2 | **Resume-PDF-Connector** — falls Demo den HR-Aspekt vertiefen will | optional | 1h |
| 🟢 P2 | **OverflowConnector** für Q&A-Platform — interessant für Knowledge-Graph aber 13 MB raw, evtl. nicht demo-kritisch | optional | 1h |
| ⚪ P3 | Slack/Notion/GoogleDocs Live-Connectors | gestrichen für 48h | — |

**Nicht-Anforderungen (dokumentiert weil oft gefragt):**
- Live-OAuth zu Slack/Notion/Google Docs — gestrichen für 48h (Mock-Versionen erfüllen die Demo-Anforderung "any document or app connector"). Plug-in-Architektur erlaubt diese später ohne Core-Änderung.
- Audio/Video-Ingest — wäre Gradium-Spielwiese, nicht im aktuellen Stack.

**Pitch-Story für Connectors:** "Jeder neue Datensilo ist ein 50-Zeilen-Connector. Wir zeigen 4 verschiedene Source-Types in der Demo, das Repo enthält das Plug-in-Template. Die Architektur ist use-case-agnostic — der Core kennt nur SourceRecord, nicht Email vs. CRM vs. PDF."

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

#### Resolution + Fact Extraction — Status (2026-04-25)

**Was die Anforderung verlangt (Req 3 + 4 + 5):** Source-Records → resolved Entities (Cross-Source-Match) → Facts (typisierte Edges) mit Provenance, Confidence, Validity. Edge-Types: `works_at, manages, authored, references, mentions, owns, assigned_to, participant_in, related_to` plus use-case-spezifische via Config. Entity-Types: `person, company, product, document, communication` als first-class.

**Pipeline heute:**

```
source_records → extract.py (per source_type) → CandidateEntity[] + PendingFact[]
                                                ↓
                                       cascade.resolve()
                                                ↓
                                  ┌─────────────┴─────────────┐
                                  ↓                            ↓
                          existing entity_id          new entity_id (deterministic
                              (merge)                  `{type}:{slug}`)
                                  ↓                            ↓
                                  └──────────┬─────────────────┘
                                             ↓
                              upsert entity → write fact → done
```

CLI-Entry: `uv run server resolve --limit N --source-type X`. Idempotent durch deterministische IDs.

**Cascade-Tiers — Ist-Status:**

| Tier | Code | Live? | Bemerkung |
|---|---|---|---|
| **T1 Hard-ID** | `cascade._tier1_hard_id` (email/emp_id/tax_id/product_id) | ✅ | trägt heute den Großteil der Matches |
| **T2 Alias** | `cascade._tier2_alias` (normalisierter `canonical_name` in `aliases[]`) | ✅ | greift auf wiederholte Mentions |
| **T3 Embedding kNN** | `cascade._tier3_embedding` ruft `match_entities`-RPC | ⚠️ **Silent fail**: Gemini-Embedding-API antwortet 404 NOT_FOUND auf `models/text-embedding-004` (Modell-Name veraltet). Try/except verschluckt's, Resolver fällt durch zu T4. **Heißt:** keine Fuzzy-Matches, niedriger Recall bei Tippfehlern / Suffix-Variationen |
| **T3.5 Pioneer** | `cascade._tier35_pioneer` Stub | ⏳ wartet auf Lasse's Fine-Tuned-Modell |
| **T4 Context** | `cascade._tier4_context` (email-domain → company) | ⚠️ **Logik-Bug**: returnt company-ID als Match für *person*-Candidate — würde Personen in Companies kollabieren. CLI hat Workaround (nur `tier in (hard_id, alias, embedding, pioneer)` als Merge-trigger). Eigentlicher Fix gehört in `cascade.py`: T4 sollte einen Relationship-Hint emit'ten, kein Match-Result |
| **T5 Ambiguity Inbox** | `cascade._write_inbox` schreibt Pending-Pair in `resolutions`-Tabelle | ⚠️ Code ok, **Tabelle leer** — wird nur gefüllt wenn T3 Borderline-Scores liefert (0.82–0.92). T3 ist tot → T5 feuert nie |

**Per-Type-Module-Status:**

| Type | Modul | Status |
|---|---|---|
| `person` | `resolver/types/person.py` | ✅ HARD_ID = email, emp_id; context = email_domain |
| `company` | `resolver/types/company.py` | ✅ HARD_ID = domain, tax_id |
| `product` | `resolver/types/product.py` | ✅ deterministic via product_id/sku |
| `document` | — | ❌ **Modul fehlt** — Req 3.2 verlangt first-class. Brauchen `_get_type_module("document")`-Eintrag |
| `communication` | — | ❌ **Modul fehlt** — Email-Threads sollten als `communication`-Entity existieren mit Edges zu Participants. Aktuell sind Emails nur SourceRecords ohne Entity-Repräsentation |
| `organization`/`role`/`department`/`policy`/`ticket`/… | — | ❌ Ontologie kennt 14 Types (`config/ontologies/*.yaml`), Resolver kennt 3 |

**Fact-Extraction (`server/src/server/resolver/extract.py`):**

| Source-Type | Connector ingest'd | Extract-Pattern in extract.py | Edge-Types emit'ted |
|---|---|---|---|
| `email` | ✅ 11.9k | ✅ Person (sender + recipient) + Company (domain) | `works_at` |
| `client` | ✅ 400 | ✅ Company (business_name) + Person (contact_person) | `works_at` |
| `customer` | ✅ 90 | ✅ Person (customer_name) | — |
| `hr_record` | ✅ 1.3k | ✅ Person + Company (domain) | `works_at`, `reports_to_emp_id` (literal — sollte später zu `reports_to` Entity-Edge resolved werden) |
| `product` | ✅ 1.3k | ✅ Product entity | — |
| `sale` | ✅ 13.5k | ⚠️ Code da, generiert `purchased`-Fact wenn customer_name + product_name vorhanden — heute meist leere Felder, daher 0 Sales-Facts geschrieben | `purchased` (geplant) |

**Was komplett fehlt:**
- **LLM-Fakt-Extraktion aus Email-Body / Policy-Doc** — `extractors/gemini_structured.py` hat nur `gemini_extract_invoice`. Keine Funktion die "Max said he'd drive the approval" → `champion_of(Max, DealX)` macht. **Demo-relevanter Wow-Faktor** (siehe Hybrid Search, Pitch).
- **Document-Entity** für Policy-PDFs (Inazuma Code of Ethics, Risk Mgmt etc.)
- **Communication-Entity** für Email-Threads — `thread_id`-basiert mit Edges zu allen Participants

**Aktuelle DB-Statistik (Stand 2026-04-25 nach ~500 resolved records):**

| Maß | Zahl | Anforderungs-Soll |
|---|---|---|
| Entities total | 306 | — |
| · person | 243 | erwartet >1.300 (alle hr_records + email-Sender + customer) wenn Volllauf |
| · company | 63 | erwartet ~50–100 (clients + email-Domains) |
| · document | 0 | Req 3.2 verlangt first-class |
| · communication | 0 | Req 3.2 verlangt first-class |
| Facts total | 183 | — |
| · `works_at` | 154 | erwartet >1.000 nach Volllauf |
| · `reports_to_emp_id` | 29 | sollte zu echtem `reports_to` (Entity-Edge) resolved werden |
| · andere predicates | 0 | Req 4.2 verlangt 9 Edge-Types — nur 1 echter Edge-Type heute |
| Resolutions (Inbox) | 0 | sollte > 0 nach T3-Fix für Demo der Ambiguity-Review-UI |
| extraction_method = `rule` | 100% | OK für deterministischen Hot-Path |
| extraction_method = `gemini` / `pioneer` | 0% | LLM-Pfad noch nicht aktiv |

**Source-Attribution-Coverage:**

| Anforderung (Req 5) | Status |
|---|---|
| 5.1 Jeder Fact hat `source_id` | ✅ alle 183 Facts haben `source_id` (NOT NULL nicht enforced — Migration 008 könnte das tightenen) |
| 5.2 source_reference enthält `system, path/endpoint, record_id, timestamp, method` | ⚠️ teilweise — `source_id` zeigt auf source_records-Row die `source_uri` + `source_native_id` + `ingested_at` hat. Die Methode steckt im Fact (`extraction_method` enum). Kein dediziertes "method"-Feld pro Fact — könnte dazu (z.B. "rule:email-domain", "llm:gemini-2.5-flash") |
| 5.3 Confidence Pflicht bei LLM-Extraktion | ✅ `confidence numeric NOT NULL` mit `[0,1]`-Check |
| 5.4 Provenance via API: `get_fact_provenance` MCP-Tool | ✅ live |
| 5.5 Rückverfolgbar bis Original-SourceRecord | ✅ JOIN `facts.source_id = source_records.id` |

**Was noch gebaut werden muss (priorisiert):**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **T3-Embedding-Fix**: `embed_text()` in `db.py` ruft `models/text-embedding-004` → 404. Auf neue API umstellen (`gemini-embedding-001` oder via `genai.Client.models.embed_content` mit korrekt nested config). Ohne T3 keine Fuzzy-Matches, keine Inbox-Demo | WS-2 | 30min |
| 🔥 P0 | **T4-Logik-Fix in `cascade.py`**: T4 sollte `relationship_hint`-Result emit'ten statt `match`. CLI-Workaround entfernt sich, sauberer Datafluss | WS-2 | 1h |
| 🔥 P0 | **`communication`-Entity** für Email-Threads — pro `thread_id` ein Entity, Edges `participant_in` zu allen sender/recipient-Personen. **Demo-Wert hoch** — macht den Graph erst dicht | WS-2 | 1.5h |
| 🟡 P1 | **`document`-Entity** für Policy-PDFs (Req 3.2) — kommt aus dem Generic-PDF-Connector (Stage 1, Kathi). Resolver-Modul `resolver/types/document.py` mit HARD_ID = `source_uri` | WS-2 | 30min nach PDF-Connector |
| 🟡 P1 | **LLM-Fact-Extraction aus Email-Body** — neue Funktion `gemini_structured.extract_email_facts(body, sender, recipient) → list[PendingFact]` mit Pydantic-Schema `{predicate, object_name, confidence, quote}`. Liefert die "Max sagte er treibt die Approval"-Style Facts. Hot für Pitch ("der Fakt ist nicht in einem Feld, er ist im Fließtext") | WS-3 / Lasse | 2h |
| 🟡 P1 | **Volllauf des Resolvers** mit T3 reaktiviert — Ziel: alle 1.260 hr_records + alle 11.928 emails. Brauchen Batch-Reads + Bulk-Insert (heute pro candidate ~4 DB-Roundtrips). Geschätzt: 1h Refactor, dann ~30min Run | WS-2 | 1.5h |
| 🟢 P2 | **Mehr Edge-Types**: `manages` (aus `reports_to_emp_id` resolven), `participant_in` (aus communication-entity), `mentions` (aus LLM-extract), `purchased` (aus sales — fixen sobald data-shape stabil), `assigned_to` (aus IT-Tickets) | WS-2 | je 30min, summa ~2h |
| 🟢 P2 | **`source_id` als NOT NULL constraint** + `method`-Feld in Fact-Schema (`text` mit Format `"<extractor>:<version>"`) — schärft Req 5.2 | WS-0/2 | 30min Migration |
| 🟢 P2 | **resolution_signals jsonb** auf jeder Auto-Merge-Decision (Req 3.4 — Traceability). Heute leer | WS-2 | 30min |
| ⚪ P3 | Per-Type Phonetic-Match (Soundex / Double-Metaphone) — nur falls Time | optional | 1h |

**Demo-Hard-Cap:** Wenn die drei P0-Tasks bis Sa 21:00 nicht stehen → bleiben wir bei dem deterministischen-only-Ergebnis. Das reicht für die Pipeline-Demo, aber Ambiguity-Inbox kann dann nicht live demonstriert werden (Inbox = leer). Pitch-Story muss dann ohne T3-Wow auskommen.

**Pitch-Story für Resolution + Extraction:** "Der Resolver ist bewusst hand-rolled — 80% unserer Matches resolven deterministisch (`email == email`). Probabilistische Libraries würden Labeled-Pairs brauchen, die wir in 48h nicht haben. Pioneer-Fine-Tune ist für die schwierigen 20% (Tier 3.5) — und wird zweitgenutzt für Mention-Extraction in Search-Queries (siehe Hybrid Search). Jeder Fakt trägt Source, Confidence, Validity — Provenance ist nicht ein Add-on, sie ist DB-Constraint."

### Autonome Ontologie-Evolution (TODO — Pitch-Multiplier)

> **Status: nicht gebaut. Geparkt als TODO.** Pitch-relevant — würde Req 9 (Generalization) auf einer fundamentaleren Ebene einlösen als nur "neue YAML-Datei einchecken". Build-Plan unten.

**Was die Architektur tun soll:** Wenn ein Source-Record auf keinen existierenden Entity-Type oder Edge-Type passt, soll der Agent **einen neuen Type proposen** statt den Record zu droppen oder in einen Catch-all-Bucket zu schmeißen. Mensch reviewed (oder Auto-Threshold approved), neuer Type wandert in `entity_type_config` / `edge_type_config`, ab da ist er Bestandteil der Ontologie.

**Heißt:** die Ontologie evolviert mit den Daten, nicht andersherum. Wir schreiben das Schema nicht im Voraus, das System lernt es.

#### Architektur-Prinzip: 3-Tier-Cascade (parallel zu Entity-Resolution)

```
Source-Record / Free-Text-Snippet
            ↓
Tier 1: Deterministisches Match
        Hardcoded-Heuristiken pro Source-Type (heute: extract.py)
        "Hat es email + emp_id? → person"
        "Hat es business_name + tax_id? → company"
            ↓ (kein klares Match)
Tier 2: LLM klassifiziert gegen bekannte Types
        Prompt mit dynamischem Pydantic-Schema:
            allowed = Literal[*config_table.id]
            confidence ≥ 0.7 → use existing
            sonst → "novel"
            ↓ (LLM sagt "novel")
Tier 3: LLM proposed neuen Type
        Output: { type_id, parent_type, attributes/edge_constraints,
                  semantic, proposed_by_source }
        → Embedding-Similarity-Check vs. existierende Types
        → wenn Distance > 0.4: schreibt in config-Tabelle mit
           approval_status='pending'
        → sonst: rejected, fällt zurück auf "best fit existing"
            ↓
Approval (Mensch oder Auto-Threshold)
        approval_status='approved' → Type ist offizieller Teil der Ontologie
        approval_status='rejected' → in Audit-Log, kein Effect
```

#### Symmetrie: gleiche Cascade für Entity-Types UND Edge-Types

**Entity-Types** brauchen: `id, parent_type, attributes[], description`.
**Edge-Types** brauchen das gleiche **plus**: `from_type, to_type` (referenzieren `entity_type_config`).

Die zusätzliche `(from_type, to_type)`-Constraint macht Edge-Types anfälliger für Synonym-Inflation:
- LLM neigt dazu Synonyme zu erfinden ("manages", "supervises", "leads", "is_manager_of")
- Mitigation siehe nächster Block.

#### Mitigations gegen Type-Proliferation

| Mechanismus | Wirkt auf | Detail |
|---|---|---|
| **Embedding-Similarity-Reject** vor Insert | Entity + Edge | Neuer Type-Vorschlag wird gegen existierende Types embedded; Distanz < 0.4 → rejected (zu ähnlich, nutze existing) |
| **Approval-Queue** statt direkter Insert | Entity + Edge | Neuer Type landet als `approval_status='pending'` — Mensch klickt approve im Frontend (Reuse von ConflictInbox-Pattern) |
| **Auto-Approve-Threshold** | Entity + Edge | confidence ≥ 0.95 + Similarity < 0.3 + Anzahl Records die für diesen Type gepushed wurden ≥ 3 → auto-approve, kein Mensch nötig |
| **Synonym-Detection-Pass** (nach Approval) | nur Edge | Asynchroner Job: LLM bekommt Liste aller approved Predicates, fragt "are any of these synonyms?". Output → Migration-Vorschlag (rename + alias) |
| **`(from_type, to_type)`-Validation** | nur Edge | LLM-Vorschlag muss valide Type-Binding angeben; FK-Constraint zu `entity_type_config.id`; sonst Insert rejected |

#### Approval-Queue-Schema

Reuse der bestehenden `resolutions`-Tabelle ist nicht clean (anderes Konzept). Sauberer:

```sql
-- Migration 008 (TODO):
alter table entity_type_config
  add column auto_proposed boolean not null default false,
  add column proposed_by_source_id text references source_records(id),
  add column approval_status text not null default 'approved'
    check (approval_status in ('pending','approved','rejected')),
  add column approved_by text,
  add column approved_at timestamptz,
  add column similarity_to_nearest float,
  add column proposal_rationale text;

alter table edge_type_config
  add column auto_proposed boolean not null default false,
  add column proposed_by_source_id text references source_records(id),
  add column approval_status text not null default 'approved'
    check (approval_status in ('pending','approved','rejected')),
  add column approved_by text,
  add column approved_at timestamptz,
  add column similarity_to_nearest float,
  add column proposal_rationale text,
  add column from_type text references entity_type_config(id),
  add column to_type text references entity_type_config(id);

-- View für Frontend:
create view pending_type_approvals as
  select 'entity' as kind, id, proposal_rationale, similarity_to_nearest, proposed_by_source_id
  from entity_type_config where approval_status = 'pending'
  union all
  select 'edge', id, proposal_rationale, similarity_to_nearest, proposed_by_source_id
  from edge_type_config where approval_status = 'pending';
```

Bestehende 14 Entity-Types und 11 Edge-Types werden auf `approval_status='approved'` gesetzt (Default), keine Demo-Disruption.

#### Validation: code muss ab Implementierung gegen die Config validieren

Heute: `INSERT INTO entities (entity_type, ...)` mit beliebigem String funktioniert. Nach Migration 008:

```sql
-- Auch Migration 008:
alter table entities
  add constraint entities_type_must_be_approved
  check (entity_type in (select id from entity_type_config where approval_status = 'approved'));

alter table facts
  add constraint facts_predicate_must_be_approved
  check (predicate in (select id from edge_type_config where approval_status = 'approved'));
```

Postgres CHECK-Constraints können keine Subqueries — also stattdessen FK + Trigger:

```sql
alter table entities
  add constraint entities_type_fk
  foreign key (entity_type) references entity_type_config(id);

create trigger entities_check_type_approved
  before insert or update on entities
  for each row execute function ensure_type_is_approved();
```

Damit kann Code keine Entities mit unapproved-Type schreiben → der "novel"-Pfad **muss** durch propose+approve laufen.

#### Build-Plan (Vollversion)

| Schritt | Was | Owner | Effort |
|---|---|---|---|
| 1 | **Migration 008** — type_config-Tabellen erweitern (auto_proposed, approval_status, proposed_by_source_id, similarity_to_nearest, proposal_rationale, from_type, to_type), pending-View, FK-Constraints, Trigger | WS-0 / WS-2 | 45min |
| 2 | **`server/src/server/ontology/propose.py`** (NEU) — `classify_or_propose_type(payload, kind: 'entity'\|'edge', context: dict) → ProposalResult`. Eine Funktion für beide Kinds; intern dispatchet sie auf zwei Pydantic-Schemas. Ruft Gemini Flash mit dynamisch-gebauten `Literal`-Types aus aktueller Config | WS-2 | 2h |
| 3 | **Embedding-Similarity-Reject**: `propose.py` embedded den Vorschlag, vergleicht gegen alle existierenden Types desselben Kinds, schreibt `similarity_to_nearest`, rejected wenn < 0.4 (= zu ähnlich) | WS-2 | 30min |
| 4 | **Auto-Approve-Threshold**: nach Insert in `pending` checkt ein Helper (in `propose.py`), ob confidence ≥ 0.95 UND similarity < 0.3 UND mindestens 3 source_records denselben Type proposen → setzt `approval_status='approved'` automatisch | WS-2 | 30min |
| 5 | **Integration in `extract.py`** — bei Source-Type ohne deterministischen Match, bei Free-Text-Hint ohne klaren Predicate → Tier-2/3-Cascade nutzen statt droppen | WS-2 | 1h |
| 6 | **`/api/admin/pending-types` GET + `/api/admin/pending-types/{id}/decide` POST** — Approval-Endpoints | WS-4 | 45min |
| 7 | **Frontend ConflictInbox erweitern** — heute 1 Tab (entity-pairs), wird 3 Tabs: Pairs / Pending Entity-Types / Pending Edge-Types. Approve/Reject-Buttons je Card. Re-use des bestehenden DecisionPanel-Pattern | Apo (WS-6) | 1.5h |
| 8 | **Synonym-Detection-Pass** (Async, nach Approval) — Cron-style Helper `detect_synonyms(kind='edge')` ruft Gemini mit Liste aller approved Predicates: "any synonyms?". Output schreibt Migration-Vorschlag (`rename predicate X to Y, add X as alias`) in eine `pending_synonym_merges`-Tabelle. UI-Integration optional | WS-2 | 1.5h |
| 9 | **Demo-Choreographie** — Source-Type live ingest'en der neuen Entity-Type triggert (z.B. `data/enterprise-bench/Inazuma_Overflow/overflow.json`), dann ein Email-Snippet das einen neuen Predicate proposed. Live im Pitch approven. Skript schreiben | wer Sonntag-Demo macht | 30min |

**Total ~9h.** Damit echte Vollversion mit Approval-Queue + Similarity-Check + Synonym-Detection.

#### Pitch-Demo

> "Watch — wir feeden eine Datenquelle, die das System nie gesehen hat: ein internes Q&A-Forum (Stack-Overflow-style). Tier 1 deterministisch findet keinen passenden Type. Tier 2 Gemini-Klassifizierung sagt 'kein bestehender Type passt > 70%'. Tier 3 proposed `forum_thread` als neuen Type, mit Attributen `[topic, author, answers, accepted_answer]`. Embedding-Similarity-Check: 0.31 zu `communication` — okay, klar neu. Approval-Inbox feuert. Wir klicken approve. Der Type ist live, der Resolver ingest'd den Rest, der Graph hat eine neue Knotenfarbe.
> 
> Zweite Szene: ein Email sagt 'Sarah will sign-off vom VP-Finance einholen'. Tier 1+2 finden keinen passenden Predicate. Tier 3 proposed `requires_signoff_from`, with type-binding `(person → person)`. Wir approven. Der Edge erscheint. Synonym-Pass im Hintergrund flaggt 'similar to manages?' — entweder mergen wir, oder behalten beide als unterschiedliche Semantik. Das Schema schrieb sich selbst."

#### Risiken

| Risiko | Mitigation |
|---|---|
| **Type-Inflation** trotz Mitigation | Auto-Approve-Threshold konservativ (3 records minimum), Similarity-Schwelle eng (0.4 statt 0.3), regelmäßiger Synonym-Pass |
| **Hallucinated Types** mit unsinnigen Attributen | Pydantic-Schema in Tier 3 zwingt strukturierten Output; bei Validation-Fail → 1× retry, sonst skip Source-Record |
| **Cost** — pro novel-Record ein LLM-Call | Tier 1 (deterministisch) trägt 80%+ → LLM nur am Long-Tail, billig (~$0.0001/Call mit Gemini Flash) |
| **Approval-Backlog** wächst, niemand klickt durch | Auto-Approve-Threshold + Pitch-Demo only-feature: für Production später Slack-Notification-Hook |
| **9h Aufwand übersteigt Hackathon-Slot** | **Mini-Version-Fallback** dokumentiert: nur Tier 1+3, ohne Approval-Queue, alles auto-approved. ~3h Aufwand. Verlust: kein Human-in-the-Loop-Visual im Pitch |

#### Hard-Cap-Decision

Wenn niemand bis Sa 18:00 die 9h committed → Mini-Version-Fallback (3h, Lasse hat nach Pioneer-Done evtl. Kapazität). Wenn auch nicht → nur Briefing-Eintrag bleibt, kein Code, Pitch-Story um diesen Wow-Faktor reduziert.

### Cross-Source Merge & Conflict Resolution (Req 6)

> **Status: Stufe 1 partiell live, Stufe 2+3 nicht gebaut.** Geparkt als großer TODO-Block. Demo-kritisch: ohne Stufe 3 kein "Human-in-the-Loop"-Visual, ohne Stufe 2 keine Auto-Resolution-Story im Pitch.

**Was die Anforderung verlangt:** Wenn mehrere Quellen die *gleiche* Person/Company beschreiben → eine Entity. Wenn Quellen *Unterschiedliches* über dieselbe Entity behaupten → automatisch lösen wo möglich, sonst Mensch entscheidet. Audit-Trail über jede Decision.

#### Drei Stufen, drei separate Probleme

```
Source-Records (28k, multiple)
     │
     ▼
┌────────────────────────────────────────────────────────────┐
│  Stufe 1 — ENTITY-MERGE                                    │
│  "Mehrere Quellen reden über DIESELBE Person/Company"      │
│  → eine Entity, aliases akkumuliert                        │
│  Wo: cascade.resolve(candidate, db) im Resolver            │
└────────────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────────┐
│  Stufe 2 — FACT-CONFLICT-RESOLUTION (auto)                 │
│  "Quellen behaupten VERSCHIEDENES über dieselbe Entity"    │
│  → Cascade Recency/Authority/Confidence/Cross-Confirm      │
│  → klarer Sieger: auto-merge, Loser supersededt            │
│  Wo: post-insert Pass auf disputed-Facts                   │
└────────────────────────────────────────────────────────────┘
     │
     ▼ (kein klarer Sieger)
┌────────────────────────────────────────────────────────────┐
│  Stufe 3 — HUMAN-IN-THE-LOOP (Inbox)                       │
│  Frontend listet pending fact_resolutions + entity-pairs   │
│  Mensch klickt: pick-A / pick-B / merge-w-qualifier / reject │
│  Decision schreibt audit-trail, supersededt loser          │
└────────────────────────────────────────────────────────────┘
```

**Wichtigste Regel:** *Merge ist günstig, Un-Merge ist Hölle.* Lieber konservativ auto-mergen (im Zweifel Inbox) als zwei verschiedene Personen zu einer kollabieren — das kriegt man nie wieder auseinander.

#### Stufe 1 — Entity-Merge (cross-source same-thing detection)

**Was sie tut:** Resolver kriegt eine Candidate-Entity aus dem Extract-Pfad, sucht ob sie schon existiert.

**Schwellwerte:**
- Embedding-Score `> 0.92` → Auto-Merge
- `0.82 – 0.92` → Inbox (an Stufe 3 weiterreichen)
- `< 0.82` → als neue Entity behandeln

**Status (heute):**

| Tier | Code | Live |
|---|---|---|
| T1 Hard-ID (email/emp_id/tax_id) | ✅ in `cascade.py` | trägt 80% der Matches |
| T2 Alias (normalisierter canonical_name in aliases[]) | ✅ in `cascade.py` | wiederholte Mentions |
| T3 Embedding kNN | ⚠️ Code da, ❌ **Embedding-API broken** (siehe Resolution-Status oben) — niedriger Recall bei Tippfehlern + Suffix-Variationen |
| T4 Context (email-domain → company) | ⚠️ logic-bug (mergt Person in Company), Workaround in CLI |
| T3.5 Pioneer | ⏳ Lasse parallel |

**Was fehlt:** T3-Fix unblockt automatisch Tier 5 (Inbox) — der schreibt 0.82-0.92-Pairs in `resolutions`-Tabelle. Heute: 0 Rows weil T3 tot.

#### Stufe 2 — Fact-Conflict-Resolution (auto)

**Was sie tun soll:** Beim INSERT eines neuen Facts checken ob `(subject_id, predicate)` schon einen offenen Fact hat. Wenn ja, vergleichen:

| Sub-Tier | Regel |
|---|---|
| **Recency** | Neuere `valid_from` schlägt ältere bei *gleicher* Source-Authority |
| **Authority** | Höherer `source_trust_weight` (`config/source_trust_weights.yaml`) gewinnt — aktuelle Werte: crm_contact 1.0, hr_record 0.95, email 0.8, it_ticket 0.7, chat 0.6, social_post 0.5 |
| **Confidence** | Höhere `confidence` gewinnt bei gleicher Authority |
| **Cross-Confirmation** | Fact mit `≥2 unabhängige source_id`-Werte schlägt Single-Source — gespeichert via Multi-Insert mit gleichem object, summed signal |

**Wenn klarer Sieger:** Loser kriegt `valid_to=now() + status='superseded' + superseded_by=winner.id`. Audit in `fact_changes`-Trigger.
**Wenn unklar:** beide bleiben mit `status='disputed'`, Pair wird in `fact_resolutions` geschrieben → Stufe 3.

**Status (heute):**

| Komponente | Status |
|---|---|
| Authority-Helper `trust.authority_score(confidence, source_type)` | ✅ in `server/src/server/trust.py` |
| `source_trust_weights.yaml` | ✅ 6 Source-Types geweighted |
| `disputed` enum-value in `fact_status` | ✅ |
| `fact_resolutions` table (renamed by Migration 003) | ✅ schema da, leer |
| **Auto-Resolution-Cascade-Code** | ❌ 0 Zeilen |
| **Conflict-Detection bei INSERT** | ❌ heute crasht GIST-EXCLUDE, CLI catched silent — neue Quellen-Info geht verloren |
| `cross_confirmation_count` Spalte oder View | ❌ fehlt |

#### Stufe 3 — Human-in-the-Loop Inbox

**Was sie tun soll:**
- Frontend zeigt `fact_resolutions WHERE decision IS NULL` und `resolutions WHERE status='pending'` (Entity-Pairs)
- Pro Card: Side-by-side beide Versionen, Source-Chips, Confidence, Trust-Weights
- Buttons: pick-A / pick-B / merge-with-qualifier / reject
- Decision-Click → API-Call schreibt `decided_at + decided_by + decision`, supersededt Loser, fact_changes audit-trigger feuert

**Status (heute):**

| Komponente | Status |
|---|---|
| Frontend `web/src/pages/review/ConflictInbox.tsx` | ⚠️ existiert, **3 Mock-Disputes hartcodiert**, kein API-Call |
| `web/src/pages/review/ConflictDetail.tsx` | ⚠️ Side-by-side-Layout fertig, mock data |
| `web/src/pages/review/DecisionPanel.tsx` | ⚠️ Buttons da, click-handler dummy |
| **`GET /api/resolutions?status=pending`** Endpoint | ❌ fehlt |
| **`POST /api/resolutions/{id}/decide`** Endpoint | ❌ fehlt |
| **`POST /api/fact-resolutions/{id}/decide`** Endpoint | ❌ fehlt |
| Audit-Hinweis "decided_by={user}" via header | ❌ fehlt |

#### GIST-Constraint umstellen: Migration 009 (TODO)

Aktuell blockt `no_temporal_overlap` (GIST-EXCLUDE) zwei facts mit gleichem (subject, predicate, validity-overlap). Das verhindert Conflict-Detection — wir brauchen "allow with disputed" stattdessen.

```sql
-- Migration 009 (TODO):
-- Drop strict exclusion, replace with conditional rule:
-- - allow multiple LIVE facts with same (subject, predicate) wenn beide
--   status='disputed' (Conflict)
-- - block nur wenn status='live' und der existierende noch valid (valid_to IS NULL)
alter table facts drop constraint if exists no_temporal_overlap;

-- Ersatz: partial unique index auf nur 'live' + open-ended Validity
create unique index facts_one_live_per_subject_predicate
  on facts (subject_id, predicate)
  where status = 'live' and valid_to is null;

-- Trigger: bei INSERT auf bereits existierenden (subject, predicate) mit
-- status='live' → setze beide auf 'disputed' und schreibe ein
-- fact_resolutions-Pending-Row
create or replace function detect_fact_conflict() returns trigger as $$
declare
  existing_id text;
begin
  select id into existing_id
  from facts
  where subject_id = new.subject_id
    and predicate = new.predicate
    and status = 'live'
    and valid_to is null
    and id <> new.id
  limit 1;

  if existing_id is not null then
    update facts set status = 'disputed' where id in (existing_id, new.id);
    insert into fact_resolutions (id, conflict_facts, decision, rationale)
    values (
      gen_random_uuid()::text,
      array[existing_id, new.id],
      'pending',
      'auto-detected conflict on (subject, predicate)'
    );
  end if;
  return new;
end; $$ language plpgsql;

create trigger facts_detect_conflict
  before insert on facts
  for each row execute function detect_fact_conflict();
```

Das macht den **CLI-`no_temporal_overlap`-Workaround obsolet** — Conflict-Detection wird DB-native, keine Code-Pfad-Sonderbehandlung mehr.

#### Build-Plan (Vollversion)

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **Migration 009** — GIST-EXCLUDE durch partial-unique-index ersetzen, `detect_fact_conflict`-Trigger anlegen, fact_resolutions auto-fill bei Conflict | WS-0/2 | 45min |
| 🔥 P0 | **`server/src/server/resolver/auto_resolve.py`** (NEU) — `auto_resolve_disputed_facts(db)` Funktion: liest `WHERE status='disputed'` Facts, gruppiert nach (subject, predicate), läuft Recency→Authority→Confidence→Cross-Confirm-Cascade, supersededt Loser oder lässt für Inbox | WS-2 | 2.5h |
| 🔥 P0 | **CLI-Subcommand `uv run server resolve-conflicts`** — invoked auto_resolve, zeigt Stats: `auto_merged: N, sent_to_inbox: M, no_change: K` | WS-2 | 30min |
| 🔥 P0 | **Conflict-API-Endpoints**: `GET /api/resolutions`, `POST /api/resolutions/{id}/decide`, `GET /api/fact-resolutions`, `POST /api/fact-resolutions/{id}/decide` | WS-4 | 1h |
| 🔥 P0 | **Frontend wire-up**: ConflictInbox/Detail/DecisionPanel auf echte API umstellen, Decision-Click feuert POST | Apo (WS-6) | 1.5h |
| 🟡 P1 | **`cross_confirmation_count`-View**: aggregiert wie viele unabhängige source_records denselben (subject, predicate, object) bestätigen — wird in Tier 4 der Auto-Cascade gelesen | WS-2 | 30min |
| 🟡 P1 | **T3-Embedding-Fix** (siehe Resolution-Status oben) — unblockt Stufe-1-Inbox-Pairs, sonst hat die Inbox nur Fact-Conflicts zu zeigen, keine Entity-Pairs | WS-2 | 30min |
| 🟢 P2 | **Trust-Weight-Editor** im Frontend (read-only ist OK fürs Pitch, write nice-to-have) | Apo | 45min |
| 🟢 P2 | **Demo-Daten kuratieren**: 1-2 echte Konflikte vor-präparieren — z.B. HR sagt Engineering, Email-Signatur sagt Sales → Inbox zeigt's beim Pitch sofort | wer Sonntag-Demo macht | 30min |

**Total ~7-8h.**

#### Hard-Cap-Decision

Wenn die fünf P0-Tasks bis Sonntag 09:00 nicht stehen → Pitch-Story muss ohne Live-Conflict-Demo auskommen. Fallback: ein vor-präpariertes statisches Beispiel im Slide-Deck. Akt 2 (Revenue) und Akt 3 (HR-View) sind nicht abhängig davon.

#### Pitch-Story für Conflict-Resolution

> "Watch — wir haben drei Quellen die widersprüchliche Sachen sagen über Ravi Kumar's Department. HR sagt Engineering, eine Email-Signatur sagt Sales, ein Slack-Profile sagt Engineering. Das System detected den Konflikt automatisch beim Insert, läuft die Cascade: Cross-Confirmation 2-zu-1 für Engineering, Authority HR > Email, Recency Email ist neuer aber Confidence niedriger. Klarer Winner Engineering, Email-Fact wird supersededt mit `valid_to=jetzt`. **Aber** — wir haben einen anderen Konflikt wo's nicht klar ist: zwei Trust-1.0-Quellen sagen unterschiedliche Sachen. Inbox feuert. Du klickst pick-A. Audit-Trail festgeschrieben. Der Graph spiegelt's binnen 2s wider."

Die Demo zeigt damit beide Modi: automatische Resolution **und** Human-Override — auf einen Schlag.

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

#### Embedding-Strategie — Status (2026-04-25)

**Was steht:**

| Komponente | Status |
|---|---|
| `entities.embedding vector(768)` Spalte (Tier A) | ✅ Migration 001 |
| `entities.inference_embedding vector(768)` Spalte (Tier B) | ✅ Migration 003 |
| HNSW-Indexes auf beiden Embedding-Spalten | ✅ Migrations 001 + 003 |
| `match_entities(query_embedding, threshold, count, use_inference_embedding)` RPC | ✅ Migration 005 — funktional, aber leere DB-Side |
| `embed_text(text, dim=768)` Helper in `db.py` | ⚠️ existiert, aber API-Call schlägt fehl (siehe unten) |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| 🔥 **0 entities haben Tier A Embedding** | `entities.embedding IS NULL` für alle 306 entities. Resolver schreibt's nie weil `embed_text()` 404 NOT_FOUND auf `models/text-embedding-004` wirft. **Heißt: Tier 3 des Cascade-Resolvers tot, Hybrid Search Stage 1 returnt nichts** |
| 🔥 **0 entities haben Tier B Inference-Embedding** | `entities.inference_embedding IS NULL` überall. Niemand baut den Inference-Text + embedded — der Code-Pfad existiert nicht |
| ⚠️ **`embed_text()` API-Endpoint veraltet** | Aktuell `client.models.embed_content(model="models/text-embedding-004", ...)` → 404. Korrekter Call (google-genai SDK 1.x): `model="gemini-embedding-001"` ODER alter Pfad mit `genai.embed_content(model=...)`-Top-Level statt nested |
| ⚠️ **`embed_text()` blockiert** | Synchroner HTTP-Call pro Entity → bei Volllauf-Resolver 13k Calls á 200ms = 45min nur für Embeddings. Brauchen Batching (Gemini API unterstützt `contents=[texts]`) |
| ⚠️ **Pre-Normalize fehlt** | Briefing sagt "lowercase, strip Inc/Ltd/GmbH/BV, whitespace-collapse" — Funktion `normalize_for_embedding()` nicht implementiert. Heute embedden wir raw-Strings → schlechtere Match-Quality |
| ❌ **Inference-Text-Builder fehlt** | Kein Code der "Max Mustermann is Head of IT, manages Project Alpha + Beta, has 2 open tickets, reports to Anna Schmidt" aus den Facts zusammenbaut. Funktion `build_inference_text(entity_id, db)` muss neu |
| ❌ **`needs_refresh`-Flag auf inference_embedding** | Konzept dokumentiert (re-compute lazy bei graph-changes), aber Schema hat keinen Flag. Brauchen `entities.inference_needs_refresh boolean` und Trigger der's setzt wenn neue Facts attached werden |

**Anforderung:** Two-Tier System wo (a) jede Entity ein billiges Name-Embedding hat (Resolver-Blocking), (b) "hot" entities (≥5 Facts) zusätzlich ein kontext-reiches Embedding für Cross-Domain-Discovery haben.

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **`embed_text()` API-Fix**: korrigieren auf `gemini-embedding-001` oder `genai.embed_content(...)`-Top-Level. Live-Probe gegen `print(embed_text("test"))` muss 768-float-Liste returnen | WS-2 | 30min |
| 🔥 P0 | **Pre-Normalize** in `embed_text()` — `normalize_for_embedding(text) → str` mit lowercase, suffix-strip, whitespace-collapse | WS-2 | 30min |
| 🔥 P0 | **Resolver schreibt Tier A** beim Entity-Create: nach `_persist_entity(...)` ein `embed_text(canonical_name + " | " + key_attrs)` und `db.table('entities').update({embedding: vec}).eq('id', eid)` | WS-2 | 45min |
| 🔥 P0 | **Backfill-Script** `uv run server backfill-embeddings --tier=A` — geht durch alle entities ohne embedding, embedded in Batches á 50 (Gemini API supports array input) | WS-2 | 1h |
| 🟡 P1 | **`build_inference_text(entity_id, db)`** — JOIN entities + facts (wo subject = entity), formatiert als natural-language summary, max 500 token | WS-2 | 1h |
| 🟡 P1 | **Tier-B Backfill-Script** `--tier=B` — nur für entities mit fact_count ≥ 5, builds inference_text, embeds, schreibt | WS-2 | 30min |
| 🟡 P1 | **`inference_needs_refresh boolean` + Trigger** — bei INSERT/UPDATE auf facts setze flag auf zugehöriger entity | WS-0/2 | 30min |
| 🟢 P2 | **Lazy Re-Embed-Loop** — CLI `uv run server reembed` reads `WHERE inference_needs_refresh=true LIMIT 50`, rebuilds inference_text + embedding | WS-2 | 45min |

**Hard-Cap:** Wenn die drei P0-Tasks bis Sa 21:00 nicht stehen → Hybrid Search Stage 1 bleibt tot. Entity-Resolution-Tier-3 bleibt tot. **Stark eingeschränkter Demo** — nur Hard-ID-Matches sichtbar, kein "Senior Engineers with ticket load"-Wow.

**Pitch-Story:** "Wir embedden zwei-stufig. Jede Entity hat ein billiges Name-Embedding für Schreib-Pfad-Resolution. Hot entities haben zusätzlich ein Inference-Embedding aus ihrem ganzen Kontext. Bei der Query *'Senior Engineers with high ticket load'* hilft das zweite — es matched Personen deren Titel das Wort 'Senior' nicht enthält, aber deren Kontext es nahelegt. Cross-Domain-Discovery zum Anfassen."

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

#### Hybrid Search — Status (2026-04-25)

**Was steht:**

| Komponente | Status |
|---|---|
| `POST /api/search` Endpoint mit `SearchRequest` | ✅ live (`server/src/server/api/search.py`) |
| `search_memory` MCP-Tool | ✅ live (mappt auf `run_hybrid_search()`) |
| **Stage 1 — Semantic via pgvector** Code-Pfad | ⚠️ Code ruft `embed_text(query) → match_entities`-RPC. Aber: 0 Embeddings in DB → Stage 1 returnt immer `[]` |
| **Stage 2 — Structural Mention-Extraction** | ❌ **fehlt**. Code-Stub ruft heute `re.findall` für Capitalized Words als naive Mention-Heuristik. Pioneer-Hook für E+R-Extraction nicht angeschlossen |
| **Stage 3 — Rerank** | ⚠️ partiell: kombiniert Stage1+Stage2 mit Union, sortiert nach `confidence × recency_decay`. Echtes Rerank (z.B. cross-encoder) fehlt |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| 🔥 **Stage 1 produktiv machen** — abhängig von Embedding-Fix in vorigem Block | Sobald `entities.embedding` befüllt ist, läuft Stage 1 automatisch. Ohne Embeddings = leere Suche |
| 🔥 **Pioneer-Mention-Extractor** für Stage 2 | `pioneer_extract_mentions(query) → list[entity_name]` ist Stub. Bei Pioneer-Done: anschließen. Fallback: Gemini Flash mit JSON-Schema `{mentions: [str]}` |
| 🟡 **Graph-Traverse für Stage 2** | `for mention in mentions: resolve_to_entity(mention) → graph_traverse(entity, depth=1)` — Code stub vorhanden, muss gegen Live-Daten getestet |
| 🟡 **Intersect vs Union Logik** | Briefing sagt "intersect bei viel Signal, union bei wenig" — heute immer Union. Heuristik: wenn `len(structural) ≥ 3 AND len(semantic) ≥ 3` → intersect, sonst union |
| 🟢 **Cross-Encoder-Rerank** | google-genai bietet Cohere-Rerank-API nicht; alternativ Gemini Flash mit Pair-Wise-Scoring. Optional, niedrige Priorität |
| 🟢 **`as_of`-Param** für Time-Travel-Search | Wenn Time-Travel-Endpoint steht, search auch mit `as_of` filtern |

**Anforderung:** 3-Stage Hybrid: Semantic ∩ Structural → Rerank, mit Source-Chips + Trust-Score auf jedem Result. Sub-second Latency.

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **Stage 1 unblocken** — ergibt sich automatisch aus Embedding-P0s oben | (siehe Embedding) | — |
| 🔥 P0 | **Pioneer-Mention-Extraction in Stage 2 anschließen** — sobald Pioneer-Modell ready, ersetzt `re.findall`-Stub. Fallback Gemini Flash | Lasse | 30min |
| 🟡 P1 | **Intersect/Union-Heuristik** mit Threshold (`≥3+3` triggers intersect) | WS-4 | 20min |
| 🟡 P1 | **Live-Test gegen Eval-Harness** — `uv run server-eval` muss search_memory rufen, Score ≥6/8 PASS | Paul | nach #41 |
| 🟢 P2 | **Cross-Encoder-Rerank** mit Gemini Flash Pair-Wise-Scoring | optional | 1.5h |
| 🟢 P2 | **`as_of` Param in `/api/search` und `search_memory` MCP-Tool** | WS-4 | 30min |

**Hard-Cap:** Wenn Stage 1 bis Sa 23:00 nicht funktioniert (Embedding-Fix dependent) → Hybrid Search ist nur Stage-2-Naive (Capitalized-Word-Matching) — Pitch-Story muss runtergeschraubt von "Hybrid Semantic+Structural" auf "Graph-Traversal-Search".

**Pitch-Demo-Beat:** Im Search-Tab Query *"Senior Engineers with high ticket load"* eintippen. Stage 1 findet 5 senior-titled Personen aus Inference-Embedding. Stage 2 traversiert deren Tickets (Pioneer extracts "Senior Engineers" als role-mention, "ticket load" als facet). Intersect = 2 Personen die beide Kriterien erfüllen. Result-Card zeigt Trust-Score + Source-Chips. **15 Sekunden, riesiger Effekt** wenn alles steht.

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

#### Graph Construction — Status (2026-04-25)

**Was steht:**

| Komponente | Status |
|---|---|
| `entities`-Tabelle als Nodes | ✅ 306 Rows (243 person, 63 company) |
| `facts`-Tabelle als reified Edges (subject_id, predicate, object_id) | ✅ 183 Rows (154 works_at, 29 reports_to_emp_id) |
| Forward-Index `facts (subject_id, predicate)` | ✅ Migration 003 |
| Reverse-Index `facts (object_id) WHERE object_id IS NOT NULL` | ✅ Migration 003 |
| `edge_type_config`-Tabelle mit 11 seeded Edge-Types | ✅ Ontologie geladen |
| `entity_type_config`-Tabelle mit 14 seeded Entity-Types | ✅ |
| Boot-Loader für YAML-Ontologien | ✅ `server/src/server/ontology/loader.py` |
| `POST /admin/reload-ontologies` Hot-Reload | ✅ live |
| Inkrementeller Build beim `uv run server resolve` | ✅ jeder neue Fact-Insert ist Edge-Add |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| 🔥 **Edge-Type-Coverage**: nur 2 von 9 Pflicht-Edge-Types live (`works_at`, `reports_to_emp_id`) | Aus Resolution-Section: `manages, authored, references, mentions, owns, assigned_to, participant_in, related_to` fehlen. `participant_in` (Email-Thread → Person) bringt am meisten Demo-Wert weil's den Graph dicht macht |
| 🔥 **Validation gegen edge_type_config nicht enforced** | Code könnte `predicate='banana'` schreiben und DB sagt OK. Brauchen FK-Constraint `facts.predicate REFERENCES edge_type_config(id)` (siehe Autonome Ontologie-Section TODO) |
| 🟡 **Edge-Metadaten unvollständig** | Schema hat `confidence`, `valid_from`, `valid_to`, `source_id`. Briefing sagt zusätzlich `extraction_method` ✓, aber `derivation` (z.B. "rule:email_domain", "llm:gemini-2.5") fehlt — nur grobes enum `extraction_method ∈ {rule, gemini, pioneer, human}` |
| 🟡 **Bi-direktional getestet?** | Indexes existieren ✓. Aber kein Test/Query der von `object_id` rückwärts traversiert. `/api/graph/neighborhood` (Plan A TODO) wäre der erste echte Konsument |
| 🟢 **Edge-Counts pro Entity als Cache-Spalte** | `entities.fact_count` würde Trust-Score-Berechnung beschleunigen (heute via JOIN) — micro-optimization |
| 🟢 **Self-loops verboten?** | Heute kein Constraint gegen `subject_id = object_id` — sollte rejected werden |

**Anforderung (Req 4):** Resolved entities = nodes, typisierte edges, Bi-direktional traversierbar, Inkrementell beim Ingest, 9 default edge-types + use-case via Config.

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **`participant_in`-Edges für Email-Threads** — abhängig von #5 (communication-Entity). Sobald `communication`-Entities existieren, schreibt der Resolver `participant_in(person, communication)` für sender + recipient. **Wichtigster Edge-Type-Add für Demo, macht Graph dicht** | WS-2 | 30min nach #5 |
| 🟡 P1 | **`manages`-Edge** aus `reports_to_emp_id`-Literal-Facts — Post-Processing-Job: für jeden `reports_to_emp_id`-Fact, lookup target person, schreibe `manages(target, source)` Edge. Erzeugt symmetrische manages/reports_to-Beziehungen im Graph | WS-2 | 45min |
| 🟡 P1 | **`mentions`-Edges** — Output von LLM-Email-Body-Extract (#28); `mentions(communication, person)` wenn Email-Body Personen erwähnt die nicht Sender/Recipient sind | Lasse | 30min nach #28 |
| 🟡 P1 | **FK-Constraint `facts.predicate → edge_type_config(id)`** | WS-0/2 | 15min — überlappt mit Autonome-Ontologie-Migration 008 |
| 🟢 P2 | **Self-loop CHECK-Constraint** auf facts | WS-0 | 5min |
| 🟢 P2 | **`entities.fact_count` Cache-Spalte** mit Trigger-Update | WS-0/2 | 30min |
| 🟢 P2 | **`derivation text` Spalte** in facts (semantischer Pfad — "rule:email_domain", etc.) | WS-0/2 | 20min Migration |

**Hard-Cap:** Wenn `participant_in`-Edges (#1 oben) bis Sa 23:00 nicht stehen → Graph bleibt sparse (nur works_at + reports_to). GraphExplorer-Demo (Plan A) zeigt dann fast keine Verbindungen über Companies/Personen-Star-Topologie hinaus. **Massiver Demo-Verlust**.

**Pitch-Story:** "Wir haben keinen separaten Graph-Store gebaut — Postgres ist der Graph. `facts` sind reified edges, indexes sind bi-directional, Edge-Types sind YAML-Ontologie. Neo4j ist eine read-only Projection für Multi-Hop-Patterns die Postgres mühsam macht. Single source of truth, zwei Lese-Surfaces."

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

> **Status (2026-04-25):** Schema + Marker sind da, aber der Re-Derivation-Loop ist nicht implementiert. Vollständige Status-Übersicht inklusive bekannter Lücken siehe Abschnitt **[Update Propagation (Req 10)](#update-propagation-req-10)** weiter unten.

**Foot-guns:**
- Immer `tstzrange`, niemals `tsrange` (Mixed-Timezone-Bugs sind silent killers)
- "As-of"-Query nutzt GIST-indexable `@>` Containment
- Postgres 18 hat `WITHOUT OVERLAPS` nativ — Supabase ist auf PG15/16, also EXCLUDE-Pattern bleiben

**Demo-Scope:** **Time-Travel-Slider in der Entity-Detail-View** (siehe Demo-Killer-Features). UI-Slider pin't `recorded_at` und `tstzrange @>`, Entity-Card-State updated live. *Single feature outweighs three of your other planned demos.*

#### Temporal State — Status (2026-04-25)

**Was steht:**

| Komponente | Status |
|---|---|
| `facts.valid_from timestamptz NOT NULL DEFAULT now()` | ✅ Migration 006 |
| `facts.valid_to timestamptz` (NULL = open-ended) | ✅ |
| `facts.recorded_at timestamptz` (renamed from ingested_at) | ✅ Migration 004 |
| `facts.superseded_by text REFERENCES facts(id)` | ✅ |
| `facts.validity tstzrange GENERATED ALWAYS AS ...` Spalte | ✅ Migration 001 |
| `set_superseded_at()` Trigger (bei UPDATE auf `superseded_by`) | ✅ Migration 001 |
| GIST-EXCLUDE-Constraint `no_temporal_overlap` | ⚠️ aktuell — wird durch Migration 009 (Conflict-Resolution-Section TODO) durch partial-unique-index + Conflict-Trigger ersetzt |
| `pg_extension btree_gist` für tstzrange-Excludes | ✅ Migration 001 |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| 🔥 **0 Facts wurden je supersededt** — bi-temporal-Mechanik nie live geübt | Heißt: kein einziger Time-Travel-fähiger Datenpunkt existiert. Demo zeigt heute nur "current state" — der Slider hat nichts Wahres zum Wechseln. **Demo-blocker** für Time-Travel-Akt |
| 🔥 **Kein "as-of"-Query-Pfad** | `/api/entities/{id}?as_of=<ts>` fehlt (Plan A P0). Konzeptionell trivial: `WHERE validity @> $1::timestamptz` — aber Endpoint existiert nicht |
| 🔥 **`supersede_fact()`-Helper fehlt in App-Code** | Update Propagation TODO. Ohne den läuft jeder neue Fact-Insert mit existierender (subject, predicate) gegen Constraint |
| 🟡 **Demo-Daten ohne historischen Fact** | Selbst mit `as_of`-Endpoint: wenn nichts supersededt wurde, hat Time-Slider nichts zu zeigen. Brauchen 1-2 manuell vor-präparierte Supersede-Cases (z.B. Ravi's Department wechselte 2024 von Engineering zu Sales) |
| 🟢 **`recorded_at` vs `valid_from` Unterschied** wird im UI nicht visuell markiert | `recorded_at = wann wir's erfahren haben`, `valid_from = wann es real wurde`. Time-Slider sollte beides differenzieren |
| 🟢 **Bi-temporal-Demo-Query** fehlt | "Was wussten wir am 2026-03-01 über Inazuma?" vs "Wer war am 2026-03-01 bei Inazuma?" — zwei verschiedene Slider-Modi (recorded_at vs valid_from) |

**Anforderung:** Jeder Fact hat Validity-Span. Queries sind zeitlich parametrisierbar — "was war wahr am Datum X?" muss funktionieren, nicht nur "was ist wahr jetzt?".

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **`/api/entities/{id}?as_of=<ts>` Endpoint** (Plan A) — Filter `WHERE validity @> $1::timestamptz` auf facts | WS-4 | 45min |
| 🔥 P0 | **Time-Travel-Slider Frontend** (Plan A) — UI-Slider auf `recorded_at` (default) oder `valid_from` (toggle) | Apo | 1.5h |
| 🔥 P0 | **`supersede_fact()` Helper** (Update Propagation) — alten Fact `valid_to=now()` setzen, neuen einfügen | WS-2/4 | 1h |
| 🔥 P0 | **Demo-Daten vor-präparieren**: 1-2 historische Supersedes injizieren — z.B. Ravi.Engineering (2024-01 → 2025-06), Ravi.Sales (2025-06 → now). Manuell via SQL-Insert oder Test-Script | Sonntag-Demo | 30min |
| 🟡 P1 | **`as_of`-Param in `search_memory` MCP-Tool** und `/api/search` — siehe Hybrid-Search-Section | WS-4 | 30min |
| 🟡 P1 | **Bi-temporal-Toggle im Slider** — switch `recorded_at` ↔ `valid_from` mit visueller Erklärung | Apo | 30min |
| 🟢 P2 | **`POST /api/entities/{id}/timeline`** Endpoint returnt allen historischen State — schöne Pitch-API für externe Konsumenten | WS-4 | 45min |

**Hard-Cap:** Wenn keine Demo-Daten supersededt sind bis Sonntag 11:00 → Time-Travel-Slider funktional aber zeigt einen "konstanten" State. **Demo-Akt 2 (Time-Travel) wird wertlos.** Mitigation: pre-baked Demo-Script muss laufen.

**Pitch-Story:** "Bi-temporal heißt: wann hat es gegolten **und** wann haben wir's erfahren. Eine Email aus 2024-06 sagte 'Sarah ist neu im Sales-Team' — gilt ab Juni 2024 (valid_from), wir haben's aber erst 2025-03 ingest'd (recorded_at). Der Slider trennt beide. **Audit-fähig im wahren Sinn.**"

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

#### Source Attribution — Status (2026-04-25)

**Was steht:**

| Komponente | Status |
|---|---|
| `facts.source_id text REFERENCES source_records(id)` | ✅ Migration 003. Alle 183 Facts haben source_id ✓ |
| `facts.confidence numeric(3,2) NOT NULL CHECK [0,1]` | ✅ Migration 001 |
| `facts.extraction_method enum(rule, gemini, pioneer, human)` | ✅ Migration 001 |
| `source_records` mit `source_uri`, `source_native_id`, `payload`, `ingested_at` | ✅ Migration 001 |
| `get_fact_provenance_json(p_fact_id)` SQL-Function | ✅ Migration 005 |
| `GET /api/facts/{id}/provenance` REST-Endpoint | ✅ live |
| `get_fact_provenance` MCP-Tool | ✅ live |
| API-Responses returnen `evidence: [{source, ...}]` Array | ✅ live |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| 🟡 **`source_id` ist nullable** | DB erlaubt heute `source_id IS NULL`. Sollte NOT NULL sein damit Req 5.1 strict erfüllt ist (jeder Fact hat Provenance) |
| 🟡 **`derivation`-Feld pro Fact fehlt** | Req 5.2 verlangt `method` als Detail-String: `"rule:email_domain"`, `"llm:gemini-2.5-flash:v3"`, `"human:edit:user@..."`. Heute nur grobes enum. Brauchen `facts.derivation text NOT NULL` mit Konvention "<extractor>:<sub-type>:<version>" |
| 🟡 **Multi-Source-Confirmation** als first-class | Briefing zeigt im JSON-Beispiel `evidence: [...]` Array mit zwei Items (gong + salesforce). Heute hat aber jeder Fact nur **einen** `source_id`. Cross-Confirmation lebt nur im Auto-Resolution-Cascade über separate Facts, nicht als Multi-Source-Pointer auf einem Fact |
| 🟢 **Source-Trust-Score in Provenance-Response** | `get_fact_provenance_json` gibt source_record raw zurück. Sollte `source_type` durch `source_trust_weights.yaml` schicken und `trust_weight` mitliefern für UI |
| 🟢 **`extracted_at` vs `recorded_at`** | Heute nur `recorded_at` (= ingested in DB). Falls LLM-Extract läuft viel später als Source-Ingest, wäre `extracted_at` separat informativ — niedrige Priorität |

**Anforderung (Req 5):** Jeder Fact attribuiert (NOT NULL), source_reference enthält system+path+record_id+timestamp+method, Confidence Pflicht bei LLM, Provenance via API rückverfolgbar bis Original-SourceRecord.

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🟡 P1 | **`source_id NOT NULL`** Migration | WS-0 | 10min |
| 🟡 P1 | **`derivation text NOT NULL DEFAULT 'unknown'`** Spalte + Backfill aus existing extraction_method | WS-0/2 | 30min |
| 🟢 P2 | **Multi-Source-Confirmation** als Cross-Reference-View `fact_evidence` (subject, predicate, object → list of {source_id, confidence}) statt Multi-Insert. Komplizierter — könnte auch Day-2 werden | WS-2/4 | 1.5h |
| 🟢 P2 | **`trust_weight` in Provenance-Response** mit JOIN auf yaml-data | WS-4 | 20min |

**Hard-Cap:** Source Attribution ist **am wenigsten kritisch von den 8 Restsections**. Alle P1+P2 sind nice-to-have für Pitch-Story-Schärfe, kein Demo-Blocker.

**Pitch-Story:** "Provenance ist nicht ein Add-on — sie ist DB-Constraint. Jeder Fact muss eine Source haben (NOT NULL), jeder LLM-extracted Fact muss eine Confidence haben (CHECK), jeder Edit ist ein neuer SourceRecord (Audit-Trail). **Compliance auditors love this.**"

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

#### Schnittstelle für Software & AI — die volle Surface (TODO-Block)

> **Status: REST + MCP-Server live, aber ohne Auth, ohne Pagination, ohne Webhook-Outbound, mit ~6 fehlenden Endpoints.** Diese Sektion konsolidiert alle Lücken auf der Consumer-Seite — was Software-Apps und AI-Agents brauchen, was wir liefern, was fehlt.

**Vier Consumer-Klassen — vier Wege rein:**

| Consumer | Transport | Auth (heute) | Auth (TODO) |
|---|---|---|---|
| **Frontend (Web/Mobile)** | REST + Supabase Realtime | nichts (open CORS auf localhost:5173) | Supabase Auth JWT, RLS auf entities/facts pro Tenant |
| **AI-Agents (Claude/Cursor/custom)** | MCP via SSE auf `/mcp/sse` | nichts | Token-based — `Authorization: Bearer <agent_key>` |
| **Externe Integrationen (Slack-Bot, Zapier, Partner)** | REST + Webhook-Outbound | nichts | API-Key-Header `X-API-Key`, scoped permissions |
| **Internal Scripts / CLIs** | REST direkt + `uv run server …` | service_role-Key in `.env` | bleibt — service-side OK |

#### REST-API — vollständige Endpoint-Matrix

Auto-generiert via FastAPI auf `/openapi.json` und `/docs` (Swagger-UI). Live-Endpoints heute (Stand 2026-04-25):

| Method | Path | Status | Owner | Notes |
|---|---|---|---|---|
| GET | `/api/health` | ✅ | core | service status |
| GET | `/api/hello` | ✅ | core | sanity ping |
| POST | `/admin/reload-ontologies` | ✅ | WS-0 | hot-reload YAML configs |
| POST | `/api/admin/reload-ontologies` | ✅ | WS-0 | duplicate path for /api scope |
| DELETE | `/api/admin/source-records/{id}` | ✅ | WS-8 | GDPR cascade delete |
| GET | `/api/entities/{id}` | ✅ | WS-4 | Entity card + trust + facts |
| GET | `/api/entities/{id}?as_of=<ts>` | ❌ TODO | WS-4 | bi-temporal time-travel — siehe Plan A |
| GET | `/api/facts/{id}/provenance` | ✅ | WS-4 | full evidence chain |
| POST | `/api/facts/{id}/validate` | ❌ TODO | WS-4 | "looks correct" — siehe Plan A |
| POST | `/api/facts/{id}/flag` | ❌ TODO | WS-4 | "flag wrong" — siehe Plan A |
| POST | `/api/facts/{id}/edit` | ❌ TODO | WS-4 | manual override — siehe Plan A |
| GET | `/api/vfs/{path:path}` | ✅ | WS-4 | List/Read VFS path |
| POST | `/api/vfs/propose-fact` | ✅ | WS-4 | agent-submitted fact |
| DELETE | `/api/vfs/{path:path}` | ✅ | WS-4 | mark fact invalid |
| POST | `/api/search` | ✅ | WS-4 | Hybrid Search (semantic only — structural-stage TODO) |
| GET | `/api/changes/recent` | ✅ | WS-5 | fact_changes audit feed |
| GET | `/api/graph/neighborhood/{entity_id}?depth=N` | ❌ TODO | WS-4 | für GraphExplorer — siehe Plan A |
| POST | `/api/query/cypher` | ✅ | WS-4 | generic Cypher proxy (returns 503 wenn Neo4j down) |
| GET | `/api/query/cypher/named` | ✅ | WS-4 | List of named queries |
| POST | `/api/admin/reingest` | ❌ TODO | WS-4 | Webhook für externe Re-Ingest-Trigger — siehe Update Propagation |
| GET | `/api/resolutions` | ❌ TODO | WS-4 | Pending entity-pair inbox — siehe Conflict Resolution |
| POST | `/api/resolutions/{id}/decide` | ❌ TODO | WS-4 | Human decision — siehe Conflict Resolution |
| GET | `/api/fact-resolutions` | ❌ TODO | WS-4 | Pending fact-conflict inbox — siehe Conflict Resolution |
| POST | `/api/fact-resolutions/{id}/decide` | ❌ TODO | WS-4 | Decide fact-conflict — siehe Conflict Resolution |
| GET | `/api/admin/pending-types` | ❌ TODO | WS-4 | Auto-proposed entity/edge types (siehe Autonome Ontologie-Evolution) |
| POST | `/api/admin/pending-types/{id}/decide` | ❌ TODO | WS-4 | approve/reject new type |

**WS-5 Aura-Sub-Surface** (separater Prefix `/query/cypher/`):

| Method | Path | Status | Notes |
|---|---|---|---|
| GET | `/query/cypher/_health` | ✅ | Aura-Connectivity-Probe |
| GET | `/query/cypher/demo` | ✅ | List 3 baked Demo-Queries |
| GET | `/query/cypher/demo/{name}` | ✅ | Run named Demo-Query |

#### MCP-Server — die AI-Schnittstelle

**Live unter `/mcp/sse`**, gemounted via `FastMCP.sse_app()`. Name: `qontext-context-engine`.

**Sechs Tools (alle live, `server/src/server/mcp/server.py`):**

| Tool | Was es tut | Pendant in REST | Maturity |
|---|---|---|---|
| `search_memory(query, k, as_of?)` | 3-Stage Hybrid Search | `POST /api/search` | ⚠️ **Structural-Stage TODO** (semantic-only heute) |
| `get_entity(id, as_of?)` | Entity-Card + Trust + Facts | `GET /api/entities/{id}` | ✅ |
| `get_fact(id)` | Single Fact + Subject-Predicate-Object | (kein REST-Pendant) | ✅ |
| `get_fact_provenance(fact_id)` | On-demand Evidence-Chain | `GET /api/facts/{id}/provenance` | ✅ |
| `list_recent_changes(since?, limit)` | Change-Feed | `GET /api/changes/recent` | ✅ |
| `propose_fact(...)` | Agent submits a fact | `POST /api/vfs/propose-fact` | ✅ |

**Beispiel-Aufruf (Claude Desktop config):**
```json
{
  "mcpServers": {
    "qontext": {
      "url": "https://your-domain.com/mcp/sse",
      "transport": "sse"
    }
  }
}
```

**Tool-Discovery:** Der MCP-Client kann `mcp.list_tools()` rufen — alle sechs sind dann sichtbar mit Pydantic-Input-Schemata + Docstrings. **Demo-Wert:** im Pitch ein zweites Fenster öffnen (Claude Desktop oder Cursor mit MCP-Client), den Agent live nach "Wer ist Engineering Director bei Inazuma?" fragen — Antwort kommt aus unserem Layer mit Source-Chips.

#### Realtime-Subscription-Surface (Live-Push)

Supabase Realtime auf der `supabase_realtime`-Publication (Migration 007 hat `entities`, `facts`, `fact_changes` rein-genommen). Consumer subscriben via `supabase-js`:

```typescript
supabase.channel('fact_changes-tail')
  .on('postgres_changes', {event: '*', table: 'fact_changes'}, payload => {
    console.log('audit event:', payload)
  })
  .subscribe()
```

**Live-Channels:**

| Channel-Topic | Tabellen-Source | Consumer (geplant) |
|---|---|---|
| `entities-changes` | INSERT/UPDATE/DELETE auf `entities` | Frontend (Live-VFS-Refresh), WS-5 Neo4j Projection |
| `facts-changes` | INSERT/UPDATE/DELETE auf `facts` | Frontend (Live-Facts-List), WS-5 Neo4j Projection |
| `fact_changes-tail` | INSERT auf `fact_changes` (audit-Trigger) | Frontend (StreamingLog) |

**Status:** Backend-Side ✅ live (Publikation aktiv, RLS read-policy für authenticated). Frontend-Subscription noch nicht wired (Plan A Phase 2 P0).

#### Was an Schnittstellen-Infra fehlt (TODO)

**Authentication & Authorization:**

| Layer | Heute | TODO |
|---|---|---|
| **REST API** | offen, jeder kann zugreifen | Supabase JWT Middleware (`fastapi-supabase-auth`) für `/api/*` (außer `/health`, `/hello`); RLS-Policies auf entities/facts gelten dann pro user |
| **MCP-Server** | offen | `Authorization: Bearer <agent_key>` Header-Check auf `/mcp/sse`; Token-Tabelle `agent_tokens (token_hash, agent_name, scopes[], created_by, expires_at)`; Pro Tool-Call Audit-Log |
| **Webhook-Outbound** | nicht implementiert | Pro Webhook-Subscriber: shared HMAC-Secret, signed payload, retry-with-backoff |
| **Service-Role** (CLI, internal) | `SUPABASE_SECRET_KEY` in `.env` | bleibt OK |

**Throughput / Stability:**

| Sache | Heute | TODO |
|---|---|---|
| **Rate Limiting** | keins | `slowapi` Middleware: 100 req/min/IP für REST, 1000 req/min für authenticated, 50 calls/min für MCP per Token |
| **Pagination** | partial — `/api/search?k=N` ist max-limit, kein Offset | Cursor-based Pagination: `?cursor=<opaque>&limit=20` über `entities`, `facts`, `changes` |
| **Streaming Responses** | keins | für Bulk-Graph-Traversal `?stream=true` mit NDJSON statt Single-Response-Body |
| **Bulk Operations** | keins | `POST /api/facts/bulk` (Array-Body) für Tools die viel auf einmal proposen |
| **Versioning** | implizit "v1" via Pfade | falls Breaking-Change: `/api/v2/...` parallel |
| **Error-Format** | inconsistent (FastAPI default + custom) | RFC 7807 Problem-Details JSON: `{type, title, status, detail, instance}` einheitlich |
| **CORS** | nur `localhost:5173` (config) | per-Env: production = explicit allowlist, dev = wildcards |

**Webhooks Outbound (System pusht raus):**

| Use-Case | TODO |
|---|---|
| **Slack-Notification** bei `disputed`-Fact | Subscriber-Tabelle `webhook_subscriptions(url, event_filter, secret)` + Worker der bei matching-events POST'd |
| **Zapier / Make.com Integration** | Generic webhook-trigger auf `entity_created`, `fact_added`, `resolution_decided` |
| **Custom Endpoints** | per Subscriber Pydantic-Schema definierbar via `event_filter` (z.B. `entity_type=customer AND fact.predicate='renewal_date'`) |

**Documentation für externe Consumers:**

| Asset | Heute | TODO |
|---|---|---|
| `/docs` (Swagger-UI) | ✅ auto-generiert | OK fürs Hackathon |
| `/redoc` (Redoc) | ✅ auto-generiert | OK |
| `/openapi.json` | ✅ auto-generiert | OK |
| MCP Tool-Discovery | ✅ via `mcp.list_tools()` | OK |
| **README für Externals** (`docs/api-consumer-guide.md`) | ❌ fehlt | "How to integrate with the Context Layer" — Auth, Endpoints, MCP-Setup, Realtime-Subscribe-Howto |
| **Postman Collection / Bruno** | ❌ fehlt | Sammlung mit pre-baked Requests für Demo + Onboarding |
| **TypeScript SDK** | ❌ fehlt | `npm install @qontext/sdk` — typed wrapper über REST + Realtime. Optional fürs 48h |
| **Python SDK** | ❌ fehlt | `pip install qontext-sdk` — wrapper. Optional |

#### Build-Plan (Vollversion)

**Phase 1 — Fehlende Endpoints (~5h, durch Plan A + Conflict + Update-Propagation Sections schon spezifiziert):**

> Diese Liste ist die Konsolidierung aller bisher dokumentierten fehlenden Endpoints aus den anderen Sections. Nicht nochmal Aufwand-zählen — schon woanders gerechnet.

| Endpoint | Wo dokumentiert |
|---|---|
| `/api/entities/{id}?as_of=<ts>` | Plan A — UI Surfaces |
| `/api/facts/{id}/{validate,flag,edit}` | Plan A — UI Surfaces |
| `/api/graph/neighborhood/{entity_id}` | Plan A — UI Surfaces |
| `/api/admin/reingest` | Update Propagation |
| `/api/resolutions` + decide | Conflict Resolution |
| `/api/fact-resolutions` + decide | Conflict Resolution |
| `/api/admin/pending-types` + decide | Autonome Ontologie-Evolution |

**Phase 2 — Schnittstellen-Härtung (Auth, Limits, Webhooks):**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🟡 P1 | **JWT-Auth-Middleware** für `/api/*` via Supabase, RLS aktivieren — production-readiness | WS-4 | 1.5h |
| 🟡 P1 | **MCP-Token-Auth** — `agent_tokens`-Tabelle + Header-Check auf SSE-Endpoint, basic per-tool audit | WS-4 | 1h |
| 🟢 P2 | **Rate Limiting** via `slowapi` — 100 req/min für anonymous, 1000 für authed | WS-4 | 30min |
| 🟢 P2 | **Cursor-Pagination** auf `entities`, `facts`, `changes` Listings | WS-4 | 1.5h |
| 🟢 P2 | **Webhook-Outbound** — `webhook_subscriptions`-Tabelle + Worker, HMAC-Signed | WS-4 | 2h |
| 🟢 P2 | **`docs/api-consumer-guide.md`** — Integrations-Guide für Externals | wer Sonntag-Doku | 45min |
| ⚪ P3 | **TypeScript SDK** | optional | 2h |
| ⚪ P3 | **Python SDK** | optional | 1h |
| ⚪ P3 | **Postman / Bruno Collection** | optional | 30min |
| ⚪ P3 | **MCP stdio-Transport** zusätzlich zu SSE — für lokale Agents ohne HTTP-Setup | optional | 30min |
| ⚪ P3 | **NDJSON Streaming Responses** für Bulk-Graph-Queries | optional | 1.5h |
| ⚪ P3 | **`POST /api/facts/bulk`** Batch-Endpoint | optional | 45min |
| ⚪ P3 | **Versioning** `/api/v1` als Prefix | optional, breaking-Change-Vorbereitung | 30min |
| ⚪ P3 | **RFC 7807 Error-Format** vereinheitlichen | optional | 1h |

**Total Phase 2: ~12h für komplette Härtung, davon nur 2.5h P1-Tasks die im Pitch zählen.**

#### Hard-Cap-Decision

| Wenn bis … | Dann |
|---|---|
| Sa 21:00 keine MCP-Auth | bleibt offen — fürs Hackathon-Pitch akzeptabel weil "internal" |
| So 06:00 kein Webhook-Outbound | dokumentiert als "Day 2" — Pitch-Sentence: "the system supports webhook subscriptions; we shipped MCP and REST today" |
| Bis Demo-Time keiner der Phase-1-Endpoints (Plan A / Conflict / Update-Prop) | Pitch-Story um die abhängigen Demo-Akte beschnitten |

#### Pitch-Story für die Schnittstellen

> "Vier Wege in unseren Layer rein. Frontend nutzt REST + Realtime. AI-Agents nutzen MCP — wir mounten sechs Tools auf einer Standard-Spec, jeder Claude-Desktop oder Cursor kann sich connecten und live unseren Graph queryen, ohne dass wir den Frontend bauen. Externe Systeme können REST nutzen oder Webhook-Subscriber für Events. Und Postgres Realtime ist die Live-Push-Seite. **Eine** Datenquelle, **vier** Konsumenten-Klassen, **eine** API-Spec auf `/docs`. Use-case-agnostic im wahrsten Sinn."

#### Demo-Beat (in der gesamten Choreographie eingebettet)

Innerhalb von Akt 1 (Layer-Demo, 90s) den **MCP-Beat** unterbringen:

> Nach dem Streaming-Log/Time-Travel-Bit: Browser-Tab wechselt zu Cursor (oder Claude Desktop). Agent fragt im Chat: *"What does Qontext know about Ravi Kumar?"* — Tool-Call sichtbar (`get_entity` → `search_memory`), Antwort kommt mit Source-Chips. **15 Sekunden, riesiger Effekt:** "wir haben den Frontend gar nicht gebraucht — der Layer ist auch ohne UI nutzbar".



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

#### Neo4j Projection — Status (2026-04-25)

**Was steht (Hard-Cap Sa 14:00 ✅ erfüllt):**

| Komponente | Status |
|---|---|
| Aura Free-Tier Instance `TechEurope` (`3cd05345`) | ✅ live, RUNNING |
| `server/src/server/sync/neo4j_projection.py` mit `start/stop/listen/replay_all/healthcheck` | ✅ alle ausimplementiert |
| Idempotente MERGE-Cypher für `Entity` Nodes + typed Edges | ✅ |
| `attrs` JSONB-serialisiert vor MERGE (Neo4j akzeptiert keine nested Maps als props) | ✅ Bug gefixt |
| Realtime-Subscription auf `entities`+`facts`+`fact_changes` Channels | ✅ Migration 007 hat Publication erweitert |
| `replay_all()` tolerant gegen fehlende Tables (PGRST205 → skip+warn) | ✅ |
| 4 Demo-Queries als `DEMO_QUERIES`-Dict (`acme_3hop_neighborhood`, `shortest_path_persons`, `champions_with_open_threads`) | ✅ |
| `GET /query/cypher/_health`, `/demo`, `/demo/{name}` REST-Endpoints | ✅ live |
| `POST /api/query/cypher` Generic Cypher-Proxy (returnt 503 wenn Neo4j down) | ✅ live |
| 4 Live-Aura-Tests (upsert, idempotency, delete, demo-query-syntax) | ✅ alle grün |
| FastAPI-Lifespan startet/stoppt Worker automatisch bei NEO4J_URI gesetzt | ✅ |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| 🟡 **Aura ist leer** — 0 Nodes, 0 Edges aktuell | Resolver hat 306 entities + 183 facts geschrieben **bevor** Realtime-Publication via Migration 007 aktiviert wurde — diese Rows wurden also nicht gemirrort. Worker muss `replay_all()` einmal triggered werden (entweder auf-restart oder via Admin-Endpoint) |
| 🔥 **Replay-Trigger-Endpoint fehlt** | Heute läuft replay_all nur beim FastAPI-Boot. Brauchen `POST /admin/projection/replay` für Demo + Recovery |
| 🟡 **Demo-Queries gegen reale Daten ungetestet** | `acme_3hop_neighborhood` hardcoded `id='customer:acme-gmbh'` — unsere realen Entity-IDs sind `company:inazuma`, `person:ravi-kumar`. Demo-Queries müssen parametrisiert oder auf reale IDs angepasst |
| 🟢 **Stale-Detection** | Wenn Worker crasht: kein Health-Indicator wie weit hinter Postgres die Aura ist. `last_synced_event_id`-Tracking wäre nice |
| 🟢 **Cypher-Proxy mit Whitelist** für Read-only | `/api/query/cypher` POST nimmt heute beliebigen Cypher entgegen. Sollte CALL/CREATE/MERGE/DELETE rejecten und nur MATCH/RETURN/WITH erlauben |
| 🟢 **Multi-Hop-Demo gegen reale Daten** noch nicht im Pitch-Skript | Time-Travel-Akt + Conflict-Akt sind im Pitch dominant — Neo4j-Akt braucht eigene Choreographie |

**Anforderung:** Read-only Aura-Projection als Multi-Hop-Surface, idempotent, Postgres bleibt SoT. Hard-Cap Sa 14:00 — wenn nicht stabil, "Day 2" im Pitch.

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **Replay-Endpoint** `POST /admin/projection/replay` — invoked `projection.replay_all()` on demand | WS-5 (Lasse) | 20min |
| 🔥 P0 | **Replay live triggern** — initial-mirror der bestehenden 306+183 Rows in Aura | Lasse | 5min |
| 🔥 P0 | **Demo-Queries auf reale IDs anpassen** — `acme_3hop_neighborhood` → `inazuma_3hop_neighborhood`, IDs wo bekannt | Lasse | 15min |
| 🟡 P1 | **Cypher-Pitch-Beat-Skript** — eine wirklich beeindruckende 3-Hop-Query pre-formuliert die im Live-Demo schick aussieht | Sonntag-Demo | 30min |
| 🟢 P2 | **Whitelist auf `/api/query/cypher`** (read-only enforce) | WS-5 / WS-4 | 30min |
| 🟢 P2 | **`last_synced_event_id` Tracking** + Health-Indicator "Aura X events behind" | Lasse | 45min |

**Hard-Cap:** Worker bereits stabil, Hard-Cap erfüllt. Neue Hard-Cap: wenn Replay bis Sa 22:00 nicht durch ist (sollte 30s dauern), wird Aura im Pitch als "Day 2" geframed — Backup ist Postgres-Cypher-Polyfill via recursive CTEs.

**Pitch-Story:** *(steht schon im Original-Briefing-Block oben)* "Postgres skaliert transaktional, Neo4j skaliert Multi-Hop. Jeder Layer in seinem Domain. Read-only Projection — kein Dual-Write-Risk."

### Change Streams

Apps können auf Events subscriben:

```
SUBSCRIBE: entity_status_change where type=Deal
SUBSCRIBE: new_fact where category=champion_activity
```

Downstream-Apps reagieren reactive, ohne zu pollen.

#### Change Streams — Status (2026-04-25)

**Was steht:**

| Komponente | Status |
|---|---|
| Supabase Realtime auf `supabase_realtime`-Publication | ✅ aktiv |
| Tables in Publication: `entities`, `facts`, `fact_changes` | ✅ Migration 007 |
| `fact_changes`-Audit-Trigger (log_fact_changes) | ✅ Migration 001 |
| `GET /api/changes/recent?limit=N` REST-Endpoint | ✅ live |
| `list_recent_changes(since, limit)` MCP-Tool | ✅ live |
| WS-5 Neo4j-Projection subscribed auf entities + facts Channels | ✅ live |
| RLS-Read-Policy für `authenticated` auf relevanten Tables | ✅ |

**Was fehlt:**

| Lücke | Detail |
|---|---|
| 🔥 **Frontend Streaming Ingestion Log** | Apo's IngestionStream-Component fehlt komplett (Plan A P0). Realtime-Channel ist publication-side ready, supabase-js-Subscription ist nicht wired |
| 🟡 **Filtered Subscriptions** | Supabase Realtime erlaubt `filter` per Channel — z.B. `table=entities, filter='entity_type=eq.deal'`. Briefing-Beispiel "subscribe entity_status_change where type=Deal" — heute nur via clientside-Filter machbar, weil unsere Channels alle Events feuern |
| 🟡 **Event-Schema-Konsistenz** | supabase-js feuert `payload.eventType, payload.new, payload.old`. Unser MCP `list_recent_changes` returnt `{kind, fact_id, old_value, new_value, triggered_by, at}` aus fact_changes-Tabelle. Beide Wege sind nutzbar, aber nicht klar dokumentiert für externe Konsumenten welcher wann |
| 🟢 **Webhook-Outbound** für externe Subscriber | siehe Schnittstelle-Section TODO |
| 🟢 **Change-Diff in Events** | fact_changes hat `old_value` + `new_value` JSONB ✓. Aber für entity-Updates fehlt vergleichbarer Audit (nur Realtime-postgres_changes liefert old_record). Konsistenter wäre: separater `entity_changes`-Trigger mit gleicher Struktur |

**Anforderung (Req 10.2):** Apps können auf Change-Events subscriben, ohne zu pollen, mit Diff-Information im Event.

**Build-Plan:**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **Frontend IngestionStream** (überlappt mit Plan A P0 #17) | Apo | 1.5h |
| 🟡 P1 | **`docs/realtime-channels.md`** — kurze Doc für externe Konsumenten welche Channels existieren, welche Filter sie nutzen können, Beispiel-Code | wer Sonntag-Doku | 30min |
| 🟢 P2 | **`entity_changes` Audit-Tabelle + Trigger** symmetrisch zu fact_changes | WS-0 | 30min |
| 🟢 P2 | **Filtered-Channel-Beispiele im UI** — z.B. "show only person events", "show only inazuma-related events" — Toggle in StreamingLog | Apo | 30min |
| ⚪ P3 | **Webhook-Outbound** (siehe Schnittstelle-Section P2) | WS-4 | 2h |

**Hard-Cap:** Wenn IngestionStream bis So 09:00 nicht steht → Akt 1 zeigt statisches `/api/changes/recent`-Snapshot statt Live-Tail. Verlust: das Wow-Moment "schau, das System antwortet in Echtzeit" fehlt.

**Pitch-Story:** "Apps müssen unseren Layer nicht pollen. Postgres Realtime feuert Events binnen 200ms an alle Subscriber — Frontend, Neo4j-Mirror, externe Webhooks. Audit-Trail ist Teil davon, nicht ein Add-on. **Reactive Architecture, kein Cron.**"

### Update Propagation (Req 10)

**Was die Anforderung verlangt:** Wenn sich eine Quelle ändert oder neue Information reinkommt, muss alles "downstream" automatisch nachziehen — Source-Records → Facts → Graph → Mirrors → Subscribers — ohne manuelles Re-Run der ganzen Pipeline.

**Zwei Szenarien:**

| | Szenario A — bestehende Quelle ändert sich | Szenario B — neue Quelle kommt rein |
|---|---|---|
| Trigger | HR-Record edit, neue Email-Antwort, Customer-Status-Update | neue Email, neuer Sales-Datensatz |
| Detection | `content_hash` drift beim Re-Ingest | neuer SourceRecord wird ingest'd |
| Effect | Abgeleitete Facts werden `needs_refresh`, alter Fact bekommt `valid_to=jetzt`, neuer Fact mit gleichem (subject, predicate) supersededt | Resolver schreibt neue Entities/Facts an existierende oder neue Subjects |
| Downstream | Realtime-Event → Neo4j-Mirror → Frontend live-tail | dito |

**Schritt-für-Schritt-Status (2026-04-25 nach Migration 007):**

| # | Schritt | Status | Wo / Bemerkung |
|---|---|---|---|
| 1 | **Hash-Drift-Detection** beim Re-Ingest | ✅ live | `BaseConnector._upsert_batch` lädt vorhandene `content_hash`, schreibt nur was sich geändert hat. Mehrfach-Ingest = no-op |
| 2 | **source_records UPSERT** mit neuem Payload | ✅ live | `upsert(on_conflict='id')` |
| 3 | **Dependent facts → `status='needs_refresh'`** markieren | ✅ live (gefixt 2026-04-25) | SQL-Function `mark_facts_needs_refresh(text[])` jetzt auf `source_id`-Spalte. Connector ruft sie nach jedem Upsert. War vorher broken durch Migration 003 (referenzierte gedroppte `derived_from`-Spalte) — Migration 007 hat's korrigiert |
| 4 | **Re-Derivation-Loop**: Resolver/Extractor läuft erneut auf `WHERE status='needs_refresh'` | ❌ **fehlt komplett** | Niemand picked stale Facts auf. `cli.py resolve` iteriert nur source_records, kein refresh-Pfad |
| 4a | **Bi-temporal Supersede**: alten Fact mit `valid_to=now()` schließen, neuen mit `valid_from=now()` öffnen | ⚠️ Schema steht (GIST-EXCLUDE + `set_superseded_at`-Trigger), App-Code-Helper fehlt | Naive `INSERT` eines neuen Facts mit gleichem (subject, predicate) crashed gegen `no_temporal_overlap`-Constraint. Brauchen `supersede_fact(subject, predicate, new_object, source_id)`-Helper der erst alten schließt, dann neuen anlegt |
| 5 | **Realtime-Events** an Subscriber | ✅ live (gefixt 2026-04-25) | Migration 007 `ALTER PUBLICATION supabase_realtime ADD TABLE entities, facts, fact_changes`. Vorher waren keine Tables in der Publication → Neo4j-Sync subscribed sauber, bekam aber nie Events. Jetzt fließen INSERT/UPDATE/DELETE durch |
| 6 | **Neo4j-Mirror** updated automatisch | ✅ wartet auf Events | Idempotente MERGE/DETACH DELETE schon getestet — sobald Resolver-Lauf Rows schreibt, sieht Aura sie binnen <2s |
| 7 | **`fact_changes` Audit-Trail** | ✅ live | Trigger schreibt old_value+new_value JSONB pro INSERT/UPDATE; 366 Rows existieren aus den Resolver-Läufen |
| 8 | **`/api/changes/recent`** Endpoint | ✅ live | Liest fact_changes — Frontend kann pollen oder via Realtime-Channel auf `fact_changes`-Events subscriben |
| 9 | **Frontend "Streaming Ingestion Log"** Live-Tail | ❌ Component fehlt | War als Demo-Killer-Feature geplant. supabase-js Realtime-Subscription auf `fact_changes` + Color-Coded Event-List |
| 10 | **Webhook für externe Trigger** ("source X changed, re-ingest jetzt") | ❌ kein Endpoint | Req 10.1 erwähnt's. Würde z.B. von einem Slack-Bot oder Zapier-Integration genutzt werden |
| 11 | **FS-Watch / Polling-Daemon** | ❌ `uv run server ingest` ist one-shot | Niedrige Demo-Priorität, weil Source-Files in `data/enterprise-bench/` statisch sind |

**Was an Code im Repo schon da ist (Stand 2026-04-25):**

```
server/src/server/connectors/diff.py         # mark_needs_refresh helper
server/migrations/001_init.sql               # mark_facts_needs_refresh function (broken, fixed in 007)
server/migrations/007_update_propagation_fixes.sql  # function fix + publication add
server/src/server/api/changes.py             # /api/changes/recent endpoint
server/src/server/sync/neo4j_projection.py   # Realtime listener subscribed to entities/facts
```

**Was noch gebaut werden muss (priorisiert):**

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **`supersede_fact(...)`-Helper** in `server/src/server/facts.py` (NEW): erstes UPDATE alter Fact `valid_to=now() + status='superseded' + superseded_by=new_id`, dann INSERT neuer Fact. Resolver muss diesen Pfad nutzen wenn `(subject_id, predicate)` schon existiert | WS-2/4-Owner | 1h |
| 🔥 P0 | **Re-Derivation CLI-Command** `uv run server reprocess` — liest `WHERE status='needs_refresh' LIMIT N`, läuft pro Fact den passenden Extractor neu, ruft `supersede_fact` an | WS-2-Owner | 2h |
| 🟡 P1 | **Frontend Streaming Ingestion Log** — supabase-js `channel('fact_changes-tail').on('postgres_changes', ...)`. Live-tail mit Color-Coded Event-Types (insert/update/delete/supersede) | Apo (WS-6) | 1.5h |
| 🟡 P1 | **Demo-Storyboard für Akt 1** — eine Source live editieren (Email-Threading): JSON file ändern → re-ingest → live im UI sehen wie Fact geupdated wird | Wer Sonntag-Demo macht | mit Above 1.5h zusammen |
| 🟢 P2 | **Webhook-Endpoint** `POST /api/admin/reingest` mit `{source_ids: [...]}` Body — triggert Re-Run des Connectors für die IDs | WS-4-Owner | 30min |
| ⚪ P3 | **FS-Watch-Daemon** für `data/enterprise-bench/` — `watchdog`-Library, schiebt geänderte Files in `ingest`-Pipeline | optional | 1h |

**Pitch-Story für Update Propagation:** "Die Pipeline ist nicht eine einmalige ETL — sie ist reaktiv. Wenn sich ein Source-Document ändert, propagiert die Änderung in unter 2 Sekunden bis in Frontend und Graph-Projection. Die Demo zeigt das live: ein Email-File wird editiert, der Stream-Log feuert, der Fact wird supersededt, das Trust-Score updated, der Knoten in Neo4j bekommt einen neuen Edge."

> **Demo-Hard-Cap:** wenn (P0-Tasks) bis Sonntag 10:00 nicht stehen, droppen wir Akt 1's "live-edit"-Bit aus der Choreographie. Stream-Log selbst (P1) ist auch ohne Re-Derive-Loop wertvoll — neue Source-Records via `ingest --connector ...` triggern bereits Realtime-Events.

### Human-Facing UI Surfaces (Plan A — Vollausbau, TODO)

> **Status: Skeleton da (TopNav + 3-Mode-Routing), keine Surface ist live wired.** Plan A = Vollausbau aller drei Sichten + Cross-cutting-Features (Time-Travel, Streaming-Log, Validate/Edit/Flag-Buttons). Geparkt als großer TODO-Block — Demo-kritisch.

**Was die Anforderung verlangt:** Req 2 (VFS als Product-Surface, jeder Node klickbar mit Full-Detail-View), Req 4 (typisierter Graph mit bi-direktionaler Traversal), Req 8 (Inspect, Validate, Edit, Conflict-Review, Volltext + Graph-Search). Das ist die Brücke zwischen "Daten sind in der DB" und "Mensch kann sie verstehen, prüfen, korrigieren".

#### Drei komplementäre Sichten — die Architektur

| Surface | Antwortet auf | Wann nutzt der Mensch das |
|---|---|---|
| **VFS-Browser** (Datei-Explorer-Style) | "Was weiß das System über X?" | Strukturierte Inspektion einer Entity. Wie ein Filesystem mit hierarchischen Pfaden. |
| **Graph-Explorer** (react-flow Canvas) | "Wer hängt mit wem zusammen?" | Multi-Hop-Patterns, Beziehungs-Visualisierung. Pitch-Wow. |
| **Entity-Detail-Card** (eingebettet in beide) | "Alles über diese eine Entity, mit Edit-Möglichkeit." | Validate, Edit, Time-Travel, Trust-Score, Source-Chips. |

Plus zwei **Cross-cutting-Features** die in mehreren Sichten leben:
- **Time-Travel-Slider** im Entity-Detail
- **Streaming Ingestion Log** als globaler Bottom-Sheet / Sidebar

#### Aktueller Frontend-Stand (vor Plan A)

| Component | File | Status |
|---|---|---|
| TopNav + Routing (Browse/Search/Review) | `web/src/components/layout/TopNav.tsx` + `App.tsx` | ✅ funktioniert, Mode-Switch live |
| 3-Column-Layout | `web/src/components/layout/ThreeColumnLayout.tsx` | ✅ |
| VfsTree | `web/src/pages/browse/VfsTree.tsx` | ⚠️ Skeleton, **mock data**, kein API-Call |
| EntityDetail | `web/src/pages/browse/EntityDetail.tsx` | ⚠️ Skeleton, **mock**, kein API-Call |
| ActionPanel (Right Sidebar) | `web/src/pages/browse/ActionPanel.tsx` | ⚠️ Skeleton — propose-fact-Dialog vorbereitet |
| SearchPage | `web/src/pages/search/SearchPage.tsx` | ⚠️ Mock |
| ConflictInbox + Detail + DecisionPanel | `web/src/pages/review/*.tsx` | ⚠️ Mock (siehe Cross-Source Merge & Conflict Resolution oben) |
| EntityNode-Component (für react-flow) | — | ❌ fehlt |
| FactEdge-Component | — | ❌ fehlt |
| GraphExplorer Page | — | ❌ fehlt |
| TimeSlider Component | — | ❌ fehlt |
| IngestionStream Component | — | ❌ fehlt |
| API-Hooks: useEntity / useFact / useSearch / useRecentChanges (TanStack Query) | `web/src/hooks/*.ts` | ✅ Stubs vorhanden, müssen an echte Endpoints |
| API-Client `web/src/lib/api.ts` | ✅ vorhanden | typed wrappers für alle 5 MCP-Tools |
| `npm run build` | ✅ clean (TS-Errors gefixt) | — |

#### Backend-Endpoints — was die Surfaces brauchen

| Endpoint | Status | Konsumiert von |
|---|---|---|
| `GET /api/vfs/{path}` | ✅ live | VFS-Tree, EntityDetail |
| `GET /api/entities/{id}` | ✅ live | EntityDetail |
| `GET /api/entities/{id}?as_of=<ts>` | ❌ **fehlt** (Time-Travel) | TimeSlider |
| `POST /api/search` | ✅ live | SearchPage |
| `GET /api/changes/recent` | ✅ live | StreamingLog (initial fetch) |
| Realtime-Channel auf `fact_changes` | ✅ Publication aktiv (Migration 007) | StreamingLog (live tail) |
| `POST /api/facts/{id}/validate` (looks correct) | ❌ **fehlt** | EntityDetail Validate-Buttons |
| `POST /api/facts/{id}/flag` (flag wrong) | ❌ **fehlt** | EntityDetail Flag-Buttons |
| `POST /api/facts/{id}/edit` (manual override) | ❌ **fehlt** | Edit-Modal |
| `POST /api/vfs/propose-fact` | ✅ live | ActionPanel propose-fact-Dialog |
| `GET /api/graph/neighborhood/{entity_id}?depth=N` | ❌ **fehlt** | GraphExplorer (oder Cypher-Proxy nutzen) |
| `GET /api/resolutions` + decide endpoints | ❌ **fehlt** (siehe Conflict-Resolution-Section) | ConflictInbox |

#### Plan A — Vollausbau (Build-Plan)

**Phase 1 — Backend-Endpoints fertigstellen** (~3h, parallel zu Frontend möglich)

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **`GET /api/entities/{id}?as_of=<ts>`** — bi-temporal Query mit `tstzrange @>`-Filter, returnt Entity + Facts die zu diesem Zeitpunkt valid waren | WS-4 | 45min |
| 🔥 P0 | **`POST /api/facts/{id}/validate`** — schreibt validation-SourceRecord (`source_type='human_validation'`, `payload={fact_id, decision: 'correct'}`); fact bleibt unverändert, audit fließt mit | WS-4 | 30min |
| 🔥 P0 | **`POST /api/facts/{id}/flag`** — schreibt flag-SourceRecord, optional setzt fact.status='disputed' wenn Flag-Threshold (z.B. ≥2 Flags) erreicht | WS-4 | 30min |
| 🟡 P1 | **`POST /api/facts/{id}/edit`** — supersededt alten fact (valid_to=now), neuer fact mit `extraction_method='human'`, source_record vom Edit | WS-4 | 45min |
| 🟡 P1 | **`GET /api/graph/neighborhood/{entity_id}?depth=N`** — recursive CTE oder Cypher-Proxy. Returnt `{nodes: [...], edges: [...]}` für react-flow | WS-4 | 1h |
| 🟢 P2 | **`POST /api/admin/source-records/{id}` (DELETE)** ist schon ✓ — für GDPR-Cascade-Demo | — | — |

**Phase 2 — Frontend-Surfaces wiren** (~5h, Apo + evtl. zweiter Helper)

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🔥 P0 | **VfsTree → echte API**: useTanStackQuery auf `GET /api/vfs/{path}`, lazy-load children, expand-collapse persisted via zustand store | Apo | 1h |
| 🔥 P0 | **EntityDetail → echte API**: ` useEntity(id)` ruft `/api/entities/{id}`, rendert Trust-Score-Pill, Facts-Liste mit ConfidencePill, Source-Chips (klickbar → SourceRecord-Detail-Modal) | Apo | 1h |
| 🔥 P0 | **Validate / Flag / Edit Buttons** pro FactRow: useTanStackMutation auf die drei Endpoints, optimistic-update + invalidate query on success, Toast-Feedback | Apo | 1h |
| 🔥 P0 | **TimeSlider Component** in EntityDetail-Header: Slider von `min(facts.valid_from)` bis now(); on-change refetched mit `?as_of=`; Card-State + Trust-Score updaten live | Apo | 1.5h |
| 🔥 P0 | **GraphExplorer Page** — neuer Mode-Tab "Graph": react-flow mit Custom EntityNode (Avatar/Type-Badge/Trust-Pill) + FactEdge (Predicate-Label, Confidence-Strichstärke). Lädt `/api/graph/neighborhood/{rootId}?depth=2`. onNodeClick → navigate zu EntityDetail | Apo / Helper | 2h |
| 🔥 P0 | **IngestionStream Bottom-Drawer**: supabase-js Channel `.on('postgres_changes', {table:'fact_changes'}, ...)` + `{table:'entities'}` + `{table:'facts'}`. Color-coded Event-Liste mit Timestamp + Entity-Link | Apo | 1.5h |
| 🟡 P1 | **SearchPage → echte API**: `POST /api/search` mit Hybrid Search Output, Result-Cards mit Source-Chips + Trust-Score | Apo | 30min |
| 🟡 P1 | **ConflictInbox → echte API** (siehe Conflict-Resolution-Section, P0 dort) | Apo | 1.5h (überlapp mit Conflict-Section) |
| 🟢 P2 | **Source-Record-Detail-Modal**: Klick auf Source-Chip in EntityDetail öffnet Modal mit raw payload, JSON-Viewer, Re-Ingest-Button | Apo | 45min |
| 🟢 P2 | **Pioneer-vs-Gemini-Comparison-View** (separate Page): Lädt `data/training/comparison.json` + Side-by-Side-Tabelle 10×2×{quality, latency, cost} | Apo | 1h |

**Phase 3 — Polish + Demo-Integration** (~1.5h)

| Priorität | Task | Owner | Effort |
|---|---|---|---|
| 🟡 P1 | **Trust-Score-Pill als Hero-Element** auf EntityDetail-Header — visuelle Skala mit Tooltip "warum 0.87?" (avg confidence × source diversity × recency-decay) | Apo | 30min |
| 🟡 P1 | **GDPR-Demo-Flow** — DELETE-Source-Record-Button im SourceDetail-Modal mit Confirmation; live in der UI sehen wie abhängige Facts verschwinden | Apo | 30min |
| 🟢 P2 | **Loading-Skeletons + Error-Boundaries** über alle Pages — vermeidet visuell schlechte Demo-Momente | Apo | 30min |

**Total Plan A: ~9-10h verteilbar.** Phase 1 (Backend) parallel zu Phase 2 (Frontend) möglich, halbiert echte Wallclock-Zeit.

#### Demo-Choreographie für Plan A

> **Akt 1 — Browse (30s):** TopNav → Browse-Mode. VfsTree links: `/companies/inazuma/`. Klick auf Entity → EntityDetail rechts: Header zeigt Trust-Score 0.87, drei Source-Chips, sechs Facts. Validate-Button auf einem Fact, Toast feuert. **Streaming-Log unten** zeigt das `validate`-Event live.
> 
> **Akt 2 — Time-Travel (15s):** TimeSlider in EntityDetail rauf-runter — der Department-Fact wechselt von "Sales" (Email-Sig 2025) zu "Engineering" (HR-Record 2024) je nach Position. Trust-Score updated mit. **"Bi-temporal isn't a buzzword."**
> 
> **Akt 3 — Graph (20s):** Mode-Switch auf Graph. Force-directed Canvas, Inazuma in der Mitte, 10 Personen-Knoten drumrum, Edges in unterschiedlichen Farben (works_at, manages, participant_in). Click-and-drag durch die Topologie. **"Postgres ist Source of Truth, Neo4j macht Multi-Hop."**
> 
> **Akt 4 — Conflict-Inbox (20s):** Mode-Switch Review. Eine pending-Card. Side-by-side die zwei disputed Facts. Pick-A-Klick. Card verschwindet, Streaming-Log feuert `resolution_decided`. **Audit-Trail wird gezeigt.**
> 
> **Akt 5 — Live-Edit (15s, falls Update-Propagation P0 fertig):** SourceRecord-Modal öffnet, edit, Save. Streaming-Log feuert `source_changed → facts_marked_refresh → resolver_reran → fact_superseded`. Time-Slider auto-jumped zur neuen Position.

Total Demo-Akt 1 ≈ 100s — passt in die geplanten 90s mit etwas Tempo.

#### Hard-Cap-Decisions

| Wenn bis … | Dann |
|---|---|
| Sa 21:00 keiner der Phase-1-Endpoints fertig | Plan-A wird zu Plan-B (kein Time-Travel, kein Graph-Explorer, nur VFS+Detail+Search wired) |
| So 03:00 GraphExplorer nicht steht | Tab "Graph" zeigt statt Free-Browse die 3 Cypher-Demo-Queries als statische Visualisierung — react-flow rendert das Output |
| So 09:00 IngestionStream nicht steht | Bottom-Drawer wird statisch gefüllt mit `/api/changes/recent`-Snapshot, kein Realtime-Tail. Pitch-Story für Akt 1 anpassen |
| So 11:00 Conflict-Inbox nicht wired | Akt 4 mit pre-recordetem Loom-Insert ersetzen oder ganz droppen — Akt 2 (Time-Travel) hat genug Wow auch ohne Inbox |

#### Pitch-Story für die UI-Surfaces

> "Wir haben nicht ein Dashboard gebaut, wir haben drei. **Browse** für strukturierte Inspektion — wie ein Filesystem für Geschäftsdaten. **Graph** für Beziehungen — Multi-Hop-Patterns die in Tabellen versteckt blieben. **Review** für die Stellen wo das System unsicher ist — Mensch entscheidet, Audit-Trail festgeschrieben. Plus ein Streaming-Log unten der Live-Events von der ganzen Pipeline tail't. Alle drei Sichten sind read-write — Validate, Edit, Flag, Approve. Daten sind nicht ein Output, sie sind ein Material das man bearbeitet."

### Was der Layer NICHT tut

- Keine Business-Logik (Was ein „guter Deal" ist, ist App-Wissen)
- Keine Notifications
- Keine Action-Generation
- Keine domain-spezifischen Begriffe (keine „Opportunities", „Champions", „Stages" als eingebaute Konzepte)
- **Kein Background-Worker für Re-Derivation.** Stale Facts werden via `status='needs_refresh'` markiert, ein on-demand CLI-Command (`reprocess`) räumt sie auf. Kein Cron, kein eager Trigger. Vollständige Mechanik + Status siehe [Update Propagation (Req 10)](#update-propagation-req-10).

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

---

## Appendix: Master-TODO-Liste — alle offenen Tasks konsolidiert

> **Stand 2026-04-25.** Diese Liste konsolidiert jeden TODO aus allen vorigen Sections in **einer** Source-of-Truth. Jede Zeile referenziert zurück auf die Detail-Section. Wer einen Task übernimmt, trägt seinen Namen in die Owner-Spalte ein. Reihenfolge zur Demo: P0 zuerst, dann P1, dann P2 wenn Zeit, P3 nur falls jemand komplett frei ist.

### Kritischer Pfad — was bis zur Demo (So 14:00) stehen MUSS

Diese Reihe definiert die Mindest-Demo. Jeder weggefallene P0 schwächt einen Pitch-Akt.

| # | Section | Task | Owner | Effort | Hard-Cap | Status |
|---|---|---|---|---|---|---|
| 1 | Ingestion | Generic-PDF-Connector (Policy_Documents) | Kathi | 1h | Sa 21:00 | ⏳ |
| 2 | Ingestion | CollaborationConnector (conversations.json) | Kathi | 30min | Sa 21:00 | ⏳ |
| 3 | Resolution | T3-Embedding-API-Fix (`models/text-embedding-004` → korrekter Endpoint) | WS-2 | 30min | Sa 21:00 | ⏳ |
| 4 | Resolution | T4-Logic-Fix in `cascade.py` (relationship_hint statt match) | WS-2 | 1h | Sa 21:00 | ⏳ |
| 5 | Resolution | `communication`-Entity für Email-Threads (thread_id-basiert + participant_in-edges) | WS-2 | 1.5h | Sa 21:00 | ⏳ |
| 6 | Conflict | Migration 009 (GIST replacement + detect_fact_conflict trigger) | WS-0/2 | 45min | Sa 21:00 | ⏳ |
| 7 | Conflict | `auto_resolve.py` mit 4-Tier-Cascade + CLI `resolve-conflicts` | WS-2 | 3h | So 03:00 | ⏳ |
| 8 | Conflict | 4 API-Endpoints (`/api/{resolutions,fact-resolutions}` GET+decide) | WS-4 | 1h | So 03:00 | ⏳ |
| 9 | UI Plan A | `/api/entities/{id}?as_of=` (Time-Travel) | WS-4 | 45min | So 03:00 | ⏳ |
| 10 | UI Plan A | `/api/facts/{id}/{validate,flag,edit}` Endpoints | WS-4 | 2h | So 03:00 | ⏳ |
| 11 | UI Plan A | `/api/graph/neighborhood/{entity_id}` | WS-4 | 1h | So 03:00 | ⏳ |
| 12 | UI Plan A | VfsTree → echte API | Apo | 1h | So 06:00 | ⏳ |
| 13 | UI Plan A | EntityDetail → echte API + Trust-Pill | Apo | 1h | So 06:00 | ⏳ |
| 14 | UI Plan A | Validate/Flag/Edit Buttons pro FactRow | Apo | 1h | So 06:00 | ⏳ |
| 15 | UI Plan A | TimeSlider Component (Killer-Feature) | Apo | 1.5h | So 09:00 | ⏳ |
| 16 | UI Plan A | GraphExplorer Page (react-flow) | Apo / Helper | 2h | So 09:00 | ⏳ |
| 17 | UI Plan A | IngestionStream Bottom-Drawer (supabase-js Realtime) | Apo | 1.5h | So 09:00 | ⏳ |
| 18 | UI Plan A | ConflictInbox → echte API (überlappt mit #8) | Apo | 1.5h | So 11:00 | ⏳ |
| 19 | Update Prop | `supersede_fact()`-Helper | WS-2/4 | 1h | So 10:00 | ⏳ |
| 20 | Update Prop | CLI `uv run server reprocess` (re-derive needs_refresh facts) | WS-2 | 2h | So 10:00 | ⏳ |
| 21 | Demo | Demo-Daten kuratieren (Inazuma + 1-2 echte Konflikte vor-präparieren) | Sonntag-Demo-Owner | 30min | So 11:00 | ⏳ |
| 22 | Demo | Pitch-Slide-Outline (`docs/pitch.md`) | wer Sonntag | 1h | So 11:00 | ⏳ |
| 23 | Demo | Loom Video Recording + Submission-Forms | wer Sonntag | 1.5h | So 13:30 | ⏳ |
| 24 | Side Prize | Aikido — Account + Repo connect + Screenshot | _claim_ | 30min | So 12:00 | ⏳ |
| 25 | VFS | Resolver schreibt `vfs_path` in entity.attrs (path-Forward-Lookup) | WS-2 | 30min | Sa 23:00 | ⏳ |
| 26 | Embedding | `embed_text()` API-Fix (gemini-embedding-001 oder Top-Level-Call) | WS-2 | 30min | Sa 21:00 | ⏳ |
| 27 | Embedding | Pre-Normalize in embed_text (lowercase, suffix-strip, ws-collapse) | WS-2 | 30min | Sa 22:00 | ⏳ |
| 28 | Embedding | Resolver schreibt Tier A beim Entity-Create (embedding-Spalte) | WS-2 | 45min | Sa 23:00 | ⏳ |
| 29 | Embedding | Backfill-Script `uv run server backfill-embeddings --tier=A` (batch) | WS-2 | 1h | Sa 23:00 | ⏳ |
| 30 | Search | Pioneer-Mention-Extraction in Stage 2 anschließen (oder Gemini-Fallback) | Lasse | 30min | So 03:00 | ⏳ |
| 31 | Graph | `participant_in`-Edges für Email-Threads (abhängig von #5 communication-Entity) | WS-2 | 30min | Sa 23:00 | ⏳ |
| 32 | Temporal | Demo-Daten vor-präparieren (1-2 historische Supersedes für Time-Travel-Demo) | Sonntag-Demo | 30min | So 11:00 | ⏳ |
| 33 | Neo4j | `POST /admin/projection/replay` Endpoint + initial-replay live triggern | Lasse | 25min | Sa 22:00 | ⏳ |
| 34 | Neo4j | Demo-Queries auf reale Entity-IDs anpassen (Inazuma statt Acme) | Lasse | 15min | Sa 22:00 | ⏳ |

**Wenn alle 34 P0 stehen:** Vollständige Demo mit allen 5 Akten + 3 Side-Prize-Submissions + voll funktionsfähige Search/VFS/Time-Travel/Graph. Wenn ≤28 P0 stehen: Plan-B (Hard-Caps unten).

### P1 — wertet die Demo merklich auf, aber nicht blocking

| # | Section | Task | Owner | Effort |
|---|---|---|---|---|
| 25 | Ingestion | ITSMConnector (it_tickets.json) | Kathi | 30min |
| 26 | Ingestion | Vendors-Tab im CRM-Connector | Kathi | 15min |
| 27 | Resolution | `document`-Entity für Policy-PDFs (nach #1) | WS-2 | 30min |
| 28 | Resolution | LLM-Fact-Extraction aus Email-Body (`gemini_structured.extract_email_facts`) | Lasse | 2h |
| 29 | Resolution | Volllauf des Resolvers (alle 1.260 hr_records + 11.928 emails) mit Bulk-Insert | WS-2 | 1.5h |
| 30 | Conflict | T3-Embedding (überlappt mit #3) — unblockt Stufe-1-Inbox-Pairs | WS-2 | — |
| 31 | Conflict | `cross_confirmation_count`-View | WS-2 | 30min |
| 32 | UI Plan A | SearchPage → echte API | Apo | 30min |
| 33 | UI Plan A | Trust-Score-Pill als Hero-Element + Tooltip | Apo | 30min |
| 34 | UI Plan A | GDPR-Demo-Flow (DELETE-Source + Live-Cascade) | Apo | 30min |
| 35 | UI Plan A | Loading-Skeletons + Error-Boundaries | Apo | 30min |
| 36 | Update Prop | Frontend Streaming Ingestion Log (überlappt mit #17) | Apo | — |
| 37 | Update Prop | Demo-Storyboard für live-edit | Sonntag-Demo | mit #17 |
| 38 | Schnittstelle | JWT-Auth-Middleware für `/api/*` (Supabase) | WS-4 | 1.5h |
| 39 | Schnittstelle | MCP-Token-Auth (agent_tokens-Tabelle + Header-Check) | WS-4 | 1h |
| 40 | Eval | Resolver auf alle hr_records → check Raj Patel + Engineering Director resolved | Paul | 30min |
| 41 | Eval | `uv run server-eval` Run + HTML-Report; Ziel ≥6/8 PASS | Paul | 1.5h |
| 42 | Eval | Pioneer-vs-Gemini Comparison-View (Frontend Page) | Apo | 1h |
| 43 | Side Prize | Pioneer-Submission-Text + Comparison-Tabelle | Lasse | 45min |
| 44 | Side Prize | Entire-Submission-Text (Coding-Workflow-Story) | _claim_ | 30min |
| 45 | VFS | Unique-Index `(entity_type, attrs->>'vfs_path')` für DB-Konsistenz | WS-0/2 | 15min |
| 46 | VFS | Type-Slug-Mapping aus entity_type_config lesen (statt hardcoded `_SLUG_TO_TYPE`) | WS-4 | 45min |
| 47 | Embedding | `build_inference_text(entity_id, db)` Helper für Tier B | WS-2 | 1h |
| 48 | Embedding | Tier-B Backfill-Script (entities mit fact_count ≥ 5) | WS-2 | 30min |
| 49 | Embedding | `inference_needs_refresh boolean` + Trigger bei facts-INSERT | WS-0/2 | 30min |
| 50 | Search | Intersect/Union-Heuristik in Hybrid Search (≥3+3 → intersect) | WS-4 | 20min |
| 51 | Search | Eval-Harness gegen search_memory live testen, ≥6/8 PASS | Paul | nach #41 |
| 52 | Graph | `manages`-Edge aus reports_to_emp_id (post-processing) | WS-2 | 45min |
| 53 | Graph | `mentions`-Edges aus LLM-Email-Body-Extract (#28) | Lasse | 30min nach #28 |
| 54 | Graph | FK `facts.predicate REFERENCES edge_type_config(id)` | WS-0/2 | 15min |
| 55 | Temporal | `as_of`-Param in `/api/search` und `search_memory` MCP-Tool | WS-4 | 30min |
| 56 | Temporal | Bi-temporal-Toggle im TimeSlider (recorded_at ↔ valid_from) | Apo | 30min |
| 57 | Attribution | `source_id NOT NULL` Migration (Req 5.1 strict) | WS-0 | 10min |
| 58 | Attribution | `derivation text NOT NULL` Spalte + Backfill | WS-0/2 | 30min |
| 59 | Change Streams | `docs/realtime-channels.md` für externe Konsumenten | wer Sonntag-Doku | 30min |

### P2 — wenn Zeit übrig ist (Polish + Vollständigkeit)

| # | Section | Task | Owner | Effort |
|---|---|---|---|---|
| 45 | Ingestion | Resume-PDF-Connector (HR-Vertiefung optional) | optional | 1h |
| 46 | Ingestion | OverflowConnector (Inazuma_Overflow Q&A) | optional | 1h |
| 47 | Resolution | Mehr Edge-Types: `manages` resolven (aus reports_to_emp_id), `mentions`, `purchased`, `assigned_to` | WS-2 | 2h |
| 48 | Resolution | `source_id` als NOT NULL constraint + `method`-Feld in Fact-Schema | WS-0/2 | 30min |
| 49 | Resolution | `resolution_signals`-jsonb-Audit auf jeder Auto-Merge-Decision (Req 3.4) | WS-2 | 30min |
| 50 | Conflict | Trust-Weight-Editor im Frontend (read-only) | Apo | 45min |
| 51 | UI Plan A | Source-Record-Detail-Modal mit JSON-Viewer + Re-Ingest-Button | Apo | 45min |
| 52 | Update Prop | Webhook-Endpoint `POST /api/admin/reingest` | WS-4 | 30min |
| 53 | Schnittstelle | Rate Limiting via `slowapi` | WS-4 | 30min |
| 54 | Schnittstelle | Cursor-Pagination | WS-4 | 1.5h |
| 55 | Schnittstelle | Webhook-Outbound (HMAC-signed Slack/Zapier) | WS-4 | 2h |
| 56 | Schnittstelle | `docs/api-consumer-guide.md` | wer Sonntag | 45min |
| 57 | Eval | GDPR Demo-Script `scripts/gdpr_delete_demo.sh` | Paul | 30min |
| 58 | Demo | Akt 3 Second App (HR-View) — minimal, auf gleichen Core-Daten | _claim_ | 2h |
| 60 | VFS | Glob-Search-Endpoint `GET /api/vfs/_glob?pattern=...` | WS-4 | 1h |
| 61 | Search | Cross-Encoder-Rerank via Gemini Flash Pair-Wise | optional | 1.5h |
| 62 | Graph | Self-loop CHECK + `entities.fact_count` Cache + `derivation` Spalte | WS-0/2 | 1h |
| 63 | Temporal | `POST /api/entities/{id}/timeline` Historical-State-Endpoint | WS-4 | 45min |
| 64 | Attribution | Multi-Source-Confirmation-View `fact_evidence` | WS-2/4 | 1.5h |
| 65 | Attribution | `trust_weight` in Provenance-Response (JOIN auf yaml-data) | WS-4 | 20min |
| 66 | Neo4j | Whitelist-Check auf `/api/query/cypher` (read-only enforce) | WS-5/4 | 30min |
| 67 | Neo4j | `last_synced_event_id` Tracking + Health-Indicator | Lasse | 45min |
| 68 | Change Streams | `entity_changes` Audit-Tabelle + Trigger (symmetrisch zu fact_changes) | WS-0 | 30min |
| 69 | Change Streams | Filtered-Channel-Beispiele in StreamingLog UI | Apo | 30min |

### P3 — nice-to-have, NICHT für Demo (Day-2-Items)

| # | Section | Task | Owner | Effort |
|---|---|---|---|---|
| 59 | Update Prop | FS-Watch-Daemon für `data/enterprise-bench/` | optional | 1h |
| 60 | Resolution | Per-Type Phonetic-Match (Soundex / Double-Metaphone) | optional | 1h |
| 61 | Schnittstelle | TypeScript SDK + Python SDK | optional | 3h |
| 62 | Schnittstelle | Postman / Bruno Collection | optional | 30min |
| 63 | Schnittstelle | MCP stdio-Transport (zusätzlich zu SSE) | optional | 30min |
| 64 | Schnittstelle | NDJSON Streaming Responses | optional | 1.5h |
| 65 | Schnittstelle | `POST /api/facts/bulk` Batch-Endpoint | optional | 45min |
| 66 | Schnittstelle | API Versioning `/api/v1/...` | optional | 30min |
| 67 | Schnittstelle | RFC 7807 Error-Format vereinheitlichen | optional | 1h |

### Autonome Ontologie-Evolution (großer Block, separat)

> **Status:** komplett TODO. Nicht in P0-Liste oben weil 9h Aufwand und allein zu groß für einen Owner. Falls **eine** Person sich dieser Section voll commited (z.B. Lasse nach Pioneer-Done), dann sind das die 9 Sub-Tasks aus Section [Autonome Ontologie-Evolution](#autonome-ontologie-evolution-todo--pitch-multiplier).

**Mini-Version-Fallback (3h)** falls niemand die volle 9h findet:
- Migration 008 light (auto_proposed boolean only)
- `propose_or_match_type()` einfache Funktion ohne Approval-Queue
- Auto-Approve immer (Type-Proliferation tolerieren)
- Demo-Skript für **einen** neuen Type-Vorschlag (z.B. `qa_post` aus Inazuma_Overflow)

### Aufgabenverteilung — pro Owner sortiert

#### Lasse (parallel WS-3 Pioneer + WS-5 Neo4j)
- Pioneer Fine-Tune fertig → Tier 3.5 scharfschalten
- #28 LLM-Fact-Extraction aus Email-Body (P1, 2h)
- #30 Pioneer-Mention-Extraction in Hybrid Search (P0, 30min)
- #33 Neo4j Replay-Endpoint + initial-replay (P0, 25min)
- #34 Demo-Queries auf reale IDs anpassen (P0, 15min)
- #43 Pioneer-Submission-Text + Comparison-Tabelle (P1, 45min)
- #53 mentions-Edges (P1, 30min nach #28)
- #67 last_synced_event_id Tracking (P2, 45min)
- (optional) Autonome Ontologie-Evolution Vollversion oder Mini

#### Kathi (WS-1 Ingestion)
- #1 Generic-PDF-Connector (P0, 1h)
- #2 CollaborationConnector (P0, 30min)
- #25 ITSMConnector (P1, 30min)
- #26 Vendors-Tab (P1, 15min)
- ggf. #45/#46 (P2)

#### WS-2-Owner (Resolver)
- #3 T3-Embedding-Fix (P0, 30min)
- #4 T4-Logic-Fix (P0, 1h)
- #5 communication-Entity (P0, 1.5h)
- #7 auto_resolve.py + CLI (P0, 3h)
- #20 reprocess CLI (P0, 2h)
- #25 Resolver schreibt vfs_path (P0, 30min)
- #26 embed_text() API-Fix (P0, 30min)
- #27 Pre-Normalize in embed_text (P0, 30min)
- #28 Resolver schreibt Tier A Embedding (P0, 45min)
- #29 Tier-A Backfill-Script (P0, 1h)
- #31 participant_in-Edges (P0, 30min nach #5)
- #29 Volllauf Resolver (P1, 1.5h — alter ID, jetzt #29 und #29 — siehe Liste)
- #27 document-Entity (P1, 30min)
- #31 cross_confirmation-View (P1, 30min)
- #47 build_inference_text Helper (P1, 1h)
- #48 Tier-B Backfill (P1, 30min)
- #49 inference_needs_refresh Trigger (P1, 30min)
- #52 manages-Edge aus reports_to_emp_id (P1, 45min)
- #54 FK predicate→edge_type_config (P1, 15min)
- #57 source_id NOT NULL (P1, 10min)
- #58 derivation Spalte (P1, 30min)
- (siehe Master-Liste oben für volle Owner-Verteilung — manche Tasks haben Doppel-IDs durch das Erweitern)

#### WS-4-Owner (API + MCP)
- #8 Conflict-API-Endpoints (P0, 1h)
- #9 Time-Travel-Endpoint (P0, 45min)
- #10 Validate/Flag/Edit-Endpoints (P0, 2h)
- #11 Graph-Neighborhood-Endpoint (P0, 1h)
- #19 supersede_fact-Helper (P0, 1h)
- #38 JWT-Auth-Middleware (P1, 1.5h)
- #39 MCP-Token-Auth (P1, 1h)
- #46 Type-Slug-Mapping config-driven (P1, 45min)
- #50 Hybrid Search Intersect/Union-Heuristik (P1, 20min)
- #55 as_of-Param in /api/search (P1, 30min)
- #52 Reingest-Webhook (P2, 30min)
- #53 Rate Limiting (P2, 30min)
- #54 Cursor-Pagination (P2, 1.5h)
- #55 Webhook-Outbound (P2, 2h)
- #60 VFS Glob-Search (P2, 1h)
- #63 timeline-Endpoint (P2, 45min)
- #65 trust_weight in provenance (P2, 20min)
- #66 cypher-whitelist (P2, 30min)

#### Apo (WS-6 Frontend)
- #12 VfsTree-Wire (P0, 1h)
- #13 EntityDetail-Wire (P0, 1h)
- #14 Validate/Flag/Edit-Buttons (P0, 1h)
- #15 TimeSlider (P0, 1.5h)
- #16 GraphExplorer (P0, 2h)
- #17 IngestionStream (P0, 1.5h)
- #18 ConflictInbox-Wire (P0, 1.5h)
- #32 SearchPage-Wire (P1, 30min)
- #33 Trust-Pill-Hero (P1, 30min)
- #34 GDPR-Flow (P1, 30min)
- #35 Loading-Skeletons (P1, 30min)
- #42 Pioneer-vs-Gemini-View (P1, 1h)
- #50 Trust-Weight-Editor (P2, 45min)
- #51 Source-Record-Modal (P2, 45min)
- #56 Bi-temporal-Toggle im TimeSlider (P1, 30min)
- #69 Filtered-Channel-Beispiele in StreamingLog (P2, 30min)

#### Paul (WS-8 Eval + Killer-Features)
- #40 Resolver-Pre-Run check (P1, 30min)
- #41 Eval-Run + Report ≥6/8 PASS (P1, 1.5h)
- #51 Eval gegen search_memory (P1, depends on #41)
- #57 GDPR-Demo-Script (P2, 30min)

#### WS-0/Schema (Migrations)
- #6 Migration 009 (P0, 45min — kann Lasse oder WS-2 mitnehmen)
- #45 vfs_path Unique-Index (P1, 15min)
- #54 FK facts.predicate (P1, 15min — überlappt mit Migration 008 Autonome Onto)
- #62 Self-loop CHECK + fact_count + derivation (P2, 1h)
- #68 entity_changes Audit-Tabelle (P2, 30min)

#### Sonntag-Demo-Owner (TBD, evtl. zwei Personen)
- #21 Demo-Daten kuratieren (P0, 30min)
- #22 Pitch-Slide-Outline (P0, 1h)
- #23 Loom Video + Submission (P0, 1.5h)
- #24 Aikido onboarden (P0, 30min)
- #32 Historical-Supersedes für Time-Travel-Demo präparieren (P0, 30min)
- #44 Entire-Submission-Text (P1, 30min)
- #59 realtime-channels.md Doc (P1, 30min)
- #56 api-consumer-guide.md (P2, 45min)
- #58 Akt 3 Second App HR-View (P2, 2h)

### Gesamt-Aufwand (Auswertung für Capacity-Planning)

| Klasse | Anzahl | Total Effort |
|---|---|---|
| **P0 (34 Tasks)** | 34 | **~31h** verteilbar (10 neue P0 aus VFS/Embedding/Graph/Temporal/Neo4j/Search) |
| **P1 (20 Tasks)** | 20 | ~17h |
| **P2 (14 Tasks)** | 14 | ~13h |
| **P3 (9 Tasks)** | 9 | ~10h |
| **Autonome Ontologie (sep. Block)** | 9 | 9h (oder 3h Mini) |

**Pro Person ~6-7 Stunden P0** mit den neuen 10 Tasks (großer Teil davon WS-2 — Embedding-Fix + Backfill ~3h zusätzlich), mit Phase-1 (Backend) und Phase-2 (Frontend) parallel realistisch in der verbleibenden Zeit zu schaffen. **WS-2-Owner ist jetzt der heißeste Bottleneck** — Embedding-Fix unblockt Hybrid Search Stage 1 + Resolver Tier 3 + Inbox-Pairs in einem.

### Hard-Cap-Decisions konsolidiert

| Wenn bis Zeitpunkt … | Dann |
|---|---|
| **Sa 18:00** kein Pioneer-Modell | Tier 3.5 fällt zurück auf Gemini Flash, Lasse pivotet auf #28 LLM-Email-Extraction |
| **Sa 21:00** P0 #1-#5 (Resolver-Verbesserung) nicht stehen | Resolver bleibt mit niedrigem Recall, Inbox demoliert um Stufe-1-Pairs |
| **So 03:00** P0 #6-#11 (Conflict + Endpoints) nicht stehen | Akt 4 (Conflict-Inbox-Demo) gestrichen; Plan-B-UI ohne Conflict-Page |
| **So 06:00** P0 #12-#14 (UI-Wiring) nicht stehen | Demo zeigt nur Mock-Daten — Pitch-Story muss "skeleton" sagen statt "live" |
| **So 09:00** P0 #15-#17 (TimeSlider + Graph + Stream) nicht stehen | Akt 1 verkürzt, kein Time-Travel-Wow, statisches Graph-Image fallback |
| **So 10:00** P0 #19-#20 (Update-Propagation) nicht stehen | Live-edit-Bit aus Akt 1 raus; pre-resolved Demo-Daten reichen |
| **So 11:00** P0 #18 (ConflictInbox-Wire) nicht steht | Akt 4 mit pre-recordetem Loom-Insert ersetzen oder droppen |
| **So 13:30** P0 #21-#24 (Demo-Daten + Slides + Video + Aikido) nicht fertig | Submission ist trotzdem möglich (Repo + README), aber ohne Video → schwächere Pre-Selection-Chance |

### Priorisierungs-Faustregeln

1. **Daten-Pipeline vor UI** — wenn entities/facts dünn sind, hilft kein noch so schönes Frontend
2. **Plan A nicht starten ohne Backend-Endpoints** — Apo blockiert sich sonst auf Mocks
3. **Inbox vor Time-Travel** — Conflict-Inbox erfüllt Req 8 (Pflicht), Time-Travel ist Demo-Wow (nice-to-have)
4. **Eval-Run früh** — wenn 0/8 Questions pass, brauchen wir noch Resolver-Tweaks → Eval ist der early-warning-System
5. **Hard-Cap respektieren** — wer um 06:00 noch an einem P0 sitzt, bricht ab und wechselt zur nächsten verfügbaren Aufgabe

