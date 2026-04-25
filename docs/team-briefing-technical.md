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

Minimum für MVP:

- **Gmail/Outlook:** Threads mit Teilnehmern, Timestamps, Content
- **CRM (Salesforce oder HubSpot, wähle eines):** Accounts, Contacts, Opportunities, Activities
- **Slack:** Channels, Messages, Thread-Relationships
- **Docs:** Google Docs oder Notion-Pages, Full-Text

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

Resolution-Signale in Priorität:

1. Exakte ID-Matches (Email-Adresse, Domain)
2. Structured Metadata (Salesforce-IDs, Slack-User-IDs)
3. Fuzzy-Name-Matching mit Embedding-Similarity
4. Kontext-basierte Validation (wenn Max Müller in Acme-Email-Domain, ist er wahrscheinlich Acme-Mitarbeiter)

Bei Unsicherheit: Candidate-Set vorhalten, mit mehr Signal auflösen. Nicht false-positive resolven.

### Graph Construction

Entitäten sind Nodes. Beziehungen zwischen ihnen sind typisierte Edges.

Node-Types (minimum): Company, Person, Deal, Document, Communication, Event
Edge-Types (minimum): works_at, champion_of, participant_in, authored, references, related_to

Der Graph wird on-ingestion gebaut und inkrementell aktualisiert. Nicht alles ist ein Graph-Query, aber alles was Beziehungen braucht geht über den Graph.

### Temporal State

Jeder Fakt hat Validity-Span. Nicht nur „Max ist Champion von Deal X" sondern „Max war Champion von 2026-02-01 bis 2026-04-10, danach verifiziert keine Aktivität mehr."

Queries müssen zeitlich parametrisierbar sein: „Was war wahr am Datum Y?" muss funktionieren, nicht nur „Was ist wahr jetzt?"

Implementierung: Bi-temporal schema mit `valid_from`, `valid_to`, `recorded_at`. Keine Destructive-Updates auf Facts.

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

### Change Streams

Apps können auf Events subscriben:

```
SUBSCRIBE: entity_status_change where type=Deal
SUBSCRIBE: new_fact where category=champion_activity
```

Downstream-Apps reagieren reactive, ohne zu pollen.

### Was der Layer NICHT tut

- Keine Business-Logik (Was ein „guter Deal" ist, ist App-Wissen)
- Keine UI
- Keine Notifications
- Keine Action-Generation
- Keine domain-spezifischen Begriffe (keine „Opportunities", „Champions", „Stages" als eingebaute Konzepte)

Der Layer kennt nur Entitäten, Beziehungen, Zeit, Attribution.

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

**50% Zeit auf Core Layer:**
Der Layer muss die substantielle Engineering-Demo sein. Qontext-Judges checken genau hier.

Prioritäts-Reihenfolge:

1. VFS mit 2 Connectors
2. Entity Resolution für People und Companies
3. Query API (simple Version, 3-4 Endpoints reichen)
4. Graph Construction für 3-4 Edge-Types
5. Source Attribution durchgängig
6. Temporal State falls Zeit bleibt

**35% Zeit auf Revenue App:**
Die visuelle Demo-Schicht. Muss slick aussehen und smooth funktionieren.

Prioritäts-Reihenfolge:

1. Sales Action Feed mit 5-7 prebuilt Patterns
2. Deal Evidence View für 1-2 Demo-Deals
3. Draft-Generation für 3 Action-Types
4. CS-View (secondary)
5. Leadership-View (nur falls Zeit)

**10% Zeit auf Second App:**
Klein, minimal. Zeigt nur dass es geht.

**5% Zeit auf Pitch-Integration:**
Demo-Daten laden, Transitions testen, Fallback-Pläne.

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

---

## Was Engineers wissen müssen bevor sie Code schreiben

1. Core-Layer-Code darf keine Revenue-Terminologie enthalten. Review-Kriterium.
2. Alle Revenue-App-Daten kommen über Query-API, nie direct DB-Access. Review-Kriterium.
3. Attribution muss in jedem API-Response enthalten sein. Nicht optional.
4. Temporal-State kann im MVP simpler sein (nur `valid_from`/`valid_to`), aber darf nicht komplett fehlen.
5. Wenn ihr vor einer Design-Entscheidung steht die „für Revenue wäre es so einfacher" sagt: Die horizontale Variante gewinnt.

---

## Offene technische Entscheidungen (vor Hack-Start klären)

1. Graph-DB vs Postgres: Entscheidung nach Team-Skill
2. GraphQL vs REST für Query-API: Entscheidung nach Team-Skill
3. LLM-Provider für Entity-Resolution und Draft-Generation: Claude empfohlen für längeren Context
4. Connectors als Mock-from-JSON oder echter API-Call: Mock empfohlen für Zeitersparnis, kein Demo-Unterschied

Diese Entscheidungen sollten vor Tag 1 des Hacks stehen.
