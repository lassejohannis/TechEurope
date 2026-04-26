# Architecture diagrams

Mermaid sources for the diagrams embedded in the main [README](../../README.md). Kept here so they are diff-able and editable without scrolling the README.

---

## 1. System overview — two-layer architecture

```mermaid
flowchart LR
    subgraph SOURCES[Source systems]
        EM[Email]
        CRM[CRM / Sales]
        HR[HR records]
        ITSM[IT tickets]
        COL[Collaboration / chat]
        DOC[Policy PDFs]
        INV[Invoice PDFs]
    end

    subgraph CORE[Core Context Engine — horizontal, use-case agnostic]
        ING[Connectors<br/>idempotent · content_hash]
        RES[Resolution Cascade<br/>T1 hard-id · T2 alias · T3 kNN<br/>T3.5 Pioneer · T4 context · T5 inbox]
        ONT[Autonomous Ontology<br/>YAML + auto-extension]
        PG[(Postgres<br/>source-of-truth<br/>bi-temporal facts)]
        N4J[(Neo4j Aura<br/>read-only projection<br/>via Realtime)]
        REST[REST API<br/>50+ endpoints]
        MCP[MCP server<br/>5 agent tools<br/>SSE + Bearer]
    end

    subgraph CONSUMERS[Consumers]
        WEB[Web UI<br/>Browse · Search · Review · Workflow · Connect]
        CSM[Revenue Intelligence App<br/>Morning Action Feed]
        AGENT[External AI agents<br/>Claude · Cursor · OpenAI · ...]
        AUTO[n8n / Zapier / webhooks]
    end

    SOURCES --> ING
    ING --> RES
    RES --> ONT
    ONT --> PG
    PG -. async MERGE .-> N4J
    PG --> REST
    PG --> MCP
    REST --> WEB
    REST --> CSM
    MCP --> AGENT
    REST --> AUTO

    classDef coreNode fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef storeNode fill:#fef3c7,stroke:#d97706,color:#451a03
    classDef sourceNode fill:#fce7f3,stroke:#be185d,color:#500724
    classDef consumerNode fill:#dcfce7,stroke:#16a34a,color:#052e16

    class ING,RES,ONT,REST,MCP coreNode
    class PG,N4J storeNode
    class EM,CRM,HR,ITSM,COL,DOC,INV sourceNode
    class WEB,CSM,AGENT,AUTO consumerNode
```

The horizontal Core never imports vertical-app concepts. Adding a second vertical app (HR, Finance) requires zero Core changes — only a new client of the public Query API.

---

## 2. Data model — what flows through the engine

```mermaid
erDiagram
    SOURCE_RECORD ||--o{ FACT : "derived_from"
    SOURCE_RECORD {
        text id PK
        text source_type
        text source_uri
        jsonb payload
        text content_hash
        timestamptz ingested_at
    }

    ENTITY ||--o{ FACT : "subject_id"
    ENTITY ||--o{ FACT : "object_id"
    ENTITY {
        text id PK
        text entity_type FK
        text canonical_name
        text_array aliases
        jsonb attrs
        text_array provenance
        timestamptz deleted_at
    }

    FACT {
        uuid id PK
        text subject_id FK
        text predicate FK
        text object_id FK
        jsonb object_literal
        float confidence
        tstzrange validity
        text status
        text source_id FK
        text_array derived_from
        text extraction_method
    }

    ENTITY_TYPE_CONFIG ||--o{ ENTITY : "approves type"
    ENTITY_TYPE_CONFIG {
        text id PK
        text approval_status
        bool auto_proposed
    }

    EDGE_TYPE_CONFIG ||--o{ FACT : "approves predicate"
    EDGE_TYPE_CONFIG {
        text id PK
        text from_type
        text to_type
        text approval_status
    }

    RESOLUTION ||--o{ ENTITY : "ambiguous candidates"
    RESOLUTION {
        uuid id PK
        text status
        text entity_id_1
        text entity_id_2
        float confidence
    }
```

Every `FACT` carries `derived_from` (NOT NULL invariant). Every API response surfaces `{value, confidence, evidence: [...]}`. **Attribution is non-optional.**

---

## 3. Resolution cascade — sequence of decisions per source record

```mermaid
sequenceDiagram
    participant Connector
    participant Mapping as JSONata mapping
    participant Cascade as Resolution Cascade
    participant Pioneer
    participant Inbox as HITL Inbox
    participant DB as Postgres

    Connector->>Mapping: SourceRecord with payload
    Mapping->>Cascade: CandidateEntity[]<br/>+ PendingFact[]

    loop per candidate
        Cascade->>DB: Tier 1 — hard-ID match<br/>(email, emp_id, tax_id)
        alt deterministic hit
            DB-->>Cascade: existing entity
            Cascade->>DB: MERGE (write fact)
        else miss
            Cascade->>DB: Tier 2 — alias match<br/>(case-folded canonical_name)
            alt alias hit
                DB-->>Cascade: matched entity
                Cascade->>DB: MERGE
            else miss
                Cascade->>DB: Tier 3 — pgvector kNN<br/>(text-embedding-004, cosine ≥ 0.92)
                alt high-confidence
                    DB-->>Cascade: nearest entity
                    Cascade->>DB: MERGE
                else 0.86–0.92 ambiguous
                    Cascade->>Pioneer: Tier 3.5 — GLiNER2 disambiguation
                    alt Pioneer agrees
                        Cascade->>DB: MERGE
                    else
                        Cascade->>Inbox: Tier 5 — write pending resolution
                    end
                else <0.86
                    Cascade->>DB: Tier 4 — create new entity
                end
            end
        end
    end
```

Tiers 1–3 are deterministic and fast (sub-100ms p50). Tier 3.5 + 4 only fire when needed. Tier 5 hands off to a human.

---

## 4. Ingest → Resolve flow (per source record)

```mermaid
flowchart TD
    A[Source file<br/>JSON / PDF / CSV] -->|Connector.normalize| B[SourceRecord<br/>idempotent via content_hash]
    B -->|insert into source_records| C[(Postgres)]
    C -->|resolve CLI<br/>or webhook trigger| D[apply_mapping<br/>JSONata extraction]
    D -->|free-text path ≥200 chars| E[Pioneer<br/>GLiNER2 free-text mining]
    D -->|JSONata-derived| F[CandidateEntity<br/>+ PendingFact]
    E -->|materialised| F
    F -->|cascade tiers 1–5| G[Entities + Facts<br/>persisted]
    G -->|Supabase Realtime| H[(Neo4j Aura<br/>idempotent MERGE)]
    G -->|fact_changes_outbox| I[Outbound Webhooks<br/>HMAC-signed]
```

The `resolve` step is **lazy**: it processes whatever sits in `source_records` with `extraction_status='pending'`. There is no cron — re-derivation happens on demand via the `needs_refresh` flag.
