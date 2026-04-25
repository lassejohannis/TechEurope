# Partner Tech — Allokation & Wire-up

Single Source of Truth für die Nutzung der Hack-Partner. Entscheidung: 2026-04-25.

| Partner | Rolle | Zählt für Pflicht-3? | Side-Prize |
|---|---|---|---|
| **Google DeepMind (Gemini)** | Im Produkt: Embeddings, Reasoning, Multimodal | ✅ Ja | — |
| **Pioneer (Fastino)** | Im Produkt: Fine-tuned E+R-Extractor am Hot-Path | ✅ Ja | 700€ (Mac Mini) |
| **Entire** | Dev-Tool: Coding-Provenance + Checkpoints | ✅ Ja (assumed; Day-1 mit Orga validieren) | $1000 Apple Gift Card + Konsolen |
| **Aikido** | Security-Scan auf Repo | ❌ explizit ausgeschlossen | 1000€ |

**Total Side-Prize-Stack:** 700€ + $1000 + 1000€ = ~2700€/$1k goodies.

---

## 1. Pioneer (Fastino) — Fine-tuned Entity + Relation Extractor

### Was wir trainieren

GLiNER2-Modell für **Entity- und Relation-Extraction** aus heterogenen SourceRecords (Email-Bodies, CRM-Notes, PDF-Excerpts).

**Input/Output:**

```
Input:  "Hi Alice, just confirming Acme's renewal for 2026-06-15.
         Their volume should hit 150k EUR. - Bob"

Output: {
  entities: [
    {span: "Alice", type: "person"},
    {span: "Acme", type: "company"},
    {span: "Bob", type: "person"}
  ],
  facts: [
    {subject: "Acme", predicate: "renewal_date", object: "2026-06-15"},
    {subject: "Acme", predicate: "volume_eur", object: 150000}
  ]
}
```

### Wo es im Code sitzt

Cascade-Tier 3.5 im Resolver (siehe [`team-briefing-technical.md`](team-briefing-technical.md) → Entity Resolution).

```python
# server/resolver/cascade.py
def resolve(record: SourceRecord) -> Resolution:
    # ... Tiers 1-3 (deterministic + embedding) ...
    
    # Tier 3.5: Pioneer-finetuned E+R extractor
    if hit := pioneer_extract_and_match(record, candidates):
        return Resolution(entity_id=hit, confidence=0.90, tier="pioneer")
    
    # ... Tier 4-5 ...
```

Plus: **Fact-Extraction** läuft primär durch Pioneer, fällt zurück auf Gemini Flash + `instructor` falls Pioneer down.

### Synthetic Data Pipeline (erfüllt Side-Prize-Kriterium)

```
EnterpriseBench raw → Gemini 2.5 Pro generiert Trainingspaare 
                     (input chunk + structured output) 
                   → Pioneer fine-tunes GLiNER2 darauf
                   → Eval gegen held-out chunks
```

**Demo-Story:** *"Wir generieren Synthetic Data aus dem Sample-Datensatz, fine-tunen GLiNER2 in Pioneer, und schlagen Gemini am Hot-Path um Faktor X bei Y Latency."*

### Side-Prize-Kriterien (Side-by-Side-Check)

| Kriterium | Wie wir es erfüllen |
|---|---|
| Outperforms generic LLM | Comparison-View Tabelle: 10 Beispiele, Pioneer X/10 vs Gemini Y/10 |
| Synthetic data generation | Gemini-basierte Trainingspaar-Generation aus EnterpriseBench |
| Eval against frontier models | Eval-Harness vergleicht Pioneer vs Gemini Flash auf den 10 Beispielen |
| Adaptive inference | Cascade nutzt Pioneer nur in Tier 3.5; Tier 1-2 sind cheaper deterministic |
| GLiNER2-Bonus | Wir nutzen wörtlich GLiNER2 |

### Time-Box & Fallback

**6h hard cap** (Samstag 12:00–18:00, ein Owner).

| Phase | Zeit | Output |
|---|---|---|
| Setup Pioneer-Account, CLI auth | 30min | Working Pioneer-Connection |
| Synthetic-Data-Generation via Gemini | 90min | 200-500 Trainingspaare als JSONL |
| Fine-Tune-Job submit | 30min | Job läuft, ggf. iterieren |
| Inference-Wrapper in `server/extractors/pioneer.py` | 90min | `extract(text) → entities, facts` |
| Eval-Vergleich Pioneer vs Gemini | 60min | Comparison-View-Datenbasis |
| Buffer | 60min | Polish |

**Fallback (wenn um 18:00 nichts läuft):**
- Pipeline läuft mit `gemini-2.0-flash` + `instructor` für E+R
- Pitch-Sprache: *"Pioneer-Integration ist Day-2 — die Architektur ist agnostisch über den Extractor"*
- Side-Prize-Submission: ehrlich erwähnen + zeigen was läuft (Synthetic-Data-Pipeline funktioniert auch ohne Fine-Tune)

### Risiken

| Risiko | Mitigation |
|---|---|
| Fine-Tune-Job hängt in Pioneer-Queue | Submit Samstag 12:00 spätestens. Job-Watcher in Background. |
| Modell schlägt Gemini nicht | Comparison-View zeigt Cost/Latency-Vorteile statt Quality. Pioneer wins on inference cost. |
| GLiNER2 unterstützt unsere Predicate-Vocab nicht | Mapping-Layer in Wrapper. Predicate-Vocab klein halten. |

---

## 2. Google DeepMind (Gemini) — General Workhorse

### Konkrete Touchpoints

| Stelle | Modell | API |
|---|---|---|
| Embeddings (Entity-Resolution-Blocking) | `text-embedding-004` (Matryoshka 768d) | Vertex AI |
| Embeddings (`search_memory` Tool) | `text-embedding-004` | Vertex AI |
| Ambiguity-Resolution (Cascade-Score 0.82–0.92) | `gemini-2.0-flash` | Direct API |
| **Fallback E+R-Extraction** wenn Pioneer down | `gemini-2.0-flash` + `instructor` | Direct API |
| PDF-Strukturextraktion (Invoice/Resume) | `gemini-2.5-pro` (multimodal) | Direct API |
| Draft-Generation in Revenue App | `gemini-2.5-pro` (lange Context) | Direct API |
| Eval-Harness Expected-Answers | `gemini-2.5-pro` | Direct API |
| Synthetic Data für Pioneer-Training | `gemini-2.5-pro` | Direct API |

### Hard rules

- **Niemals** Gemini im Hot-Path als Matcher (das ist Cascade-Job)
- **Immer** strukturierter Output via `instructor` — kein Raw-JSON-Mode
- Token-Budget pro Call gegrenzt: Evidence-Truncation auf 160 chars/snippet, top-k=3

### Onboarding

Temp-Account vom Hackathon-Orga vor Ort. URL: https://goo.gle/hackathon-account

---

## 3. Entire — Dev-Tool für Coding-Provenance

### Was wir damit machen

**Nicht im Produkt verbaut.** Wir nutzen Entire während des Hacks für:

1. **Provenance-Forensik** für AI-generierten Code — Checkpoints zeigen welcher Prompt zu welchem Code-Block geführt hat
2. **Agent-Onboarding** — neue Sessions kriegen Repo-Historie + Entscheidungen, nicht nur Diff
3. **Safe Rewind** — Files aus Checkpoint restoren ohne Git-History zu manipulieren

### Setup

```bash
# Day 1, alle Team-Mitglieder
curl -fsSL https://docs.entire.io/install.sh | sh
entire login
entire init  # im Repo-Root
```

Time-Box: 30min für das ganze Team.

### Was wir submitten

Ehrlicher Submission-Text: *"Wir haben Entire während des Hackathons als Coding-Provenance-Tool genutzt — jeder AI-generierte Commit hat einen Checkpoint mit Prompt-Historie. Das hat uns bei XY-Bug geholfen den Root-Cause in 5 Minuten zu finden statt 30."*

### Risiko

Side-Prize-Submission ist explizit *"Use Entire. Confirm in submission."* — das deckt Dev-Tool-Nutzung. **Aber:** mit Hackathon-Orga am Tag 1 validieren ob Entire damit auch für Pflicht-3 zählt. Falls nicht → Tavily als 3. Pflicht-Partner einbauen (ist als zusätzlicher SourceRecord-Producer trivial nachträglich machbar, ~3h).

---

## 4. Aikido — Security-Scan

### Setup (Day 1, 30min)

1. Account erstellen auf [app.aikido.dev](https://app.aikido.dev/login)
2. Git-Provider connecten (GitHub)
3. Repo verbinden
4. Erste Scan-Runde laufen lassen

### Submission

Bei Final-Submission: Screenshot des Security-Reports (Issue-Counts + Categories) ans Submission-Form anhängen.

### Was wir NICHT machen

- Keine Security-Issues fixen während des Hacks (außer was Aikido als "trivial" markiert)
- Keine Security-Architektur erfinden — wir nehmen den Stack-Default (Supabase RLS, Pydantic-Validation auf Boundaries)

---

## Day-1-Checklist (alle Partner)

```
[ ] Gemini temp account claimed (Hackathon-Orga)
[ ] Pioneer account + CLI authenticated  
[ ] Entire CLI installed + repo init'd (alle Team-Mitglieder)
[ ] Aikido repo connected + first scan running
[ ] Mit Orga validiert: Entire als Dev-Tool zählt für Pflicht-3
[ ] Falls nein: Tavily als Backup-Plan vorbereitet
```

## Stack-Components (kein Partner, aber relevant)

### Neo4j Aura (Free-Tier) — Read-only Graph-Projection
- **Nicht Hack-Partner**, aber Stack-Component für Skalierbarkeits-Story
- Postgres bleibt SoT, Neo4j wird via Supabase-Realtime Sync-Worker gepflegt
- Free-Tier: 200k Nodes / 400k Relationships — reicht massiv für EnterpriseBench
- Setup-Zeit: 30min Aura-Account + Connection-String, 3-4h Sync-Worker
- **Hard-Cap Samstag 14:00.** Bei Nicht-Stabilität → Postgres-only, Neo4j als "Day 2"
- Implementation: [`server/sync/neo4j_projection.py`](../server/sync/neo4j_projection.py)

## Decision-Log

- **2026-04-25 — Splink raus, hand-rolled Cascade rein.** Cowork-Research zeigte: Splink will Labeled-Pairs + EM-Training, 6-10h Time-to-Value. Hand-rolled ist 4h.
- **2026-04-25 — Pioneer fokussiert auf E+R-Extraction (nicht ER-Matching).** ER-Matching ist deterministic-first, keine ML-Aufgabe. E+R ist High-Volume Hot-Path mit klarer Cost/Latency-Story.
- **2026-04-25 — Entire ist Dev-Tool, kein Produkt-Feature.** Vorherige HITL-Allokation revidiert. Pending-Review-Queue läuft als FastAPI-Form, nicht via Entire.
- **2026-04-25 — Tavily als Backup für Pflicht-3.** Aktivieren falls Orga Dev-Tool-Nutzung nicht akzeptiert.
- **2026-04-25 — Neo4j als Read-only Projection re-adoptiert.** Postgres bleibt SoT, Neo4j ist Read-Layer für Multi-Hop. Skalierbarkeits-Story (transaktional/graph) + Pitch-Narrative gewichtiger als +4h Setup-Tax. Sync via Supabase-Realtime, Failure-Mode: stale Projection, nichts korruptes. Hard-Cap Samstag 14:00.
- **2026-04-25 — Graphiti runtime trotz Neo4j-Adoption NICHT adoptiert.** Argument der Versuchung: "wir haben eh Neo4j, lass mal Graphiti einbauen". Widerlegt durch 4 Punkte:
  1. Graphiti ist End-to-End-Pipeline (Episode-Store, Extraction, bi-temporal, Search), nicht augmentierbare Library — würde 60% unserer Architektur ersetzen
  2. Bi-temporal-Konflikt: Postgres-EXCLUDE-Constraint vs Graphiti's App-Logic in Neo4j → zwei konkurrierende Engines
  3. Pioneer-Side-Prize-Story zerschossen (Graphiti macht Extraction, Pioneer raus)
  4. Library-Lernkurve in 48h, nullte Erfahrung im Team
  Patterns weiter klauen (Edge-Properties, Invalidation-Logic, Extraction-Prompts auf Gemini portieren) — Runtime nicht. **Wer am Samstag "sollten wir Graphiti einbauen?" sagt, hat 60min, das selbst zu widerlegen, sonst overruled.**
