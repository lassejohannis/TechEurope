# Team Brainstorm — Pain Points, Ideas, Market

Raw notes from the team (shared via Notion). Preserved verbatim as reference for the Day-1 kickoff.

---

## Pain Points / Needs

### Pain Point 1 — Context-Fragmentierung

„Dasselbe Wissen lebt in Slack, HubSpot, Notion, Drive, im Kopf von Mitarbeitern." → Jedes Hack-Projekt, das heterogene Quellen zu einem kohärenten Live-Graph verschmilzt und einem Agent zugänglich macht, trifft den Kern.

### Pain Point 2 — „Reinvent-per-Use-Case"

Jeder neue Agent rebuildet Kontext. → Baue ein Projekt, das **eine einzige Qontext-Vault zweimal oder dreimal wiederverwendet** (z. B. für Sales-Agent + Support-Agent + Marketing-Content) und zeige, wie ein Update an der Quelle alle drei konsistent hält. Das ist Qontexts Kern-Value-Prop live demonstriert.

### Pain Point 3 — Entity Resolution / „Same Person, different Tool"

„Ist John aus HubSpot derselbe wie John in Slack und der Unterzeichner im Drive-PDF?" → Ein Projekt, das Entity Resolution über Quellen hinweg zeigt, spricht direkt das Manifesto-Problem an.

### Pain Point 4 — Governance + Agent Access Control

„Welcher Agent darf welchen Kontext sehen?" → Bonus-Richtung, passt auch perfekt zum Side-Challenge-Partner **Aikido (Security)**.

### Pain Point 5 — Agent Onboarding Time

„Setup eines neuen AI-Tools dauert Monate." → Zeige einen neuen Agent, der in Minuten produktiv ist, weil er in eine bestehende Vault eingeklinkt wird.

### Pain Point 6 — Tribal Knowledge

Entscheidungen und „Why"-Logik leben in Köpfen. → Projekt, das reasoning aus Calls, Slack-Threads, Commits extrahiert und als strukturierten Kontext wieder verfügbar macht.

---

## ICP (Hergeleitet aus Testimonials + Positionierung)

- **Company Stage:** Schnell wachsende Scale-Ups (Series A–C) bis Mid-Market
- **Geografie:** Deutschland / EU-Fokus (GDPR, Made in Germany), US als Sekundärmarkt
- **Tech-Stack:** Bereits multi-tool (HubSpot, Notion, Slack, Drive); haben mehrere AI-Pilots laufen
- **Teams im Fokus:** GTM (Sales, Marketing, Support) + Operations
- **Rollen-Käufer:** AI Lead, Head of Automation, Head of GTM Ops, CTO
- **Schmerz-Signal:** „Wir haben 10 AI-Workflows und keinen Überblick mehr. Jeder Agent wiederholt Kontext-Setup."

---

## Marktumfeld und Competition

### Kategorien im Wettbewerbsfeld

1. **„Context Layer" direkte Player**
   - **Contextual AI** (US) — Enterprise Context Engineering Platform, fokussiert auf „advanced industries" (Technical Docs, Compliance). Größer, reifer, US-lastig.
   - **Workfabric AI** (Rohan Narayana Murty) — „Context Engineering Company". Sehr ähnlich positioniert; HBR-Artikel vom Feb 2026, den Nikita Kowalski selbst als Validierung teilt.
   - **Context.ai** — Agent-Plattform mit Connectors, geht eher Richtung verticalized Agents.

2. **Enterprise Search / Knowledge AI**
   - **Glean** — Enterprise Search mit „Enterprise Graph"; am ehesten vergleichbar, aber fokussiert auf Human-Search
   - **Notion AI, Microsoft Copilot** — embedded Assistants, keine echte Kontextschicht

3. **RAG & Vektor-DBs**
   - LlamaIndex, Pinecone, Weaviate, Chroma — das ist genau das, was Qontext als „nicht ausreichend" abgrenzt

4. **Graph-DBs & Data Stack**
   - Neo4j (Angel-Investor!), Snowflake, Databricks — Qontext sitzt logisch *darauf*, nicht *dagegen*

5. **Agent-Platforms mit eigenem Context**
   - Decagon, Cognigy, Glean Agents — Qontext Mission: *unter* ihnen liegen statt neben ihnen

---

## Makro-Trends, die Qontext helfen

- 2025–2026: Breite Erkenntnis, dass AI-Pilots scheitern und Context der Bottleneck ist (HBR-Cover-Story Feb 2026)
- MCP-Adoption als Standard für Tool-Kontext
- Enterprise-Anforderungen an Governance, EU-Souveränität, GDPR
- Agent-Stacks werden real; jeder braucht Datenzugang

---

## Ideen

### Idee A — „The Context-Native Sales Copilot"

Multi-Source-Sales-Agent, der aus HubSpot, Gmail, Call-Transcripts (via Gradium STT) und Produkt-Docs eine Qontext-Vault baut. Vor jedem Call: Briefing-Dashboard. Während des Calls: Live-Suggestions. Nach dem Call: automatisches CRM-Update + Folge-Tasks.
**Partner:** Qontext + Gradium (Voice) + Gemini/DeepMind + Tavily (Research über Lead-Company).

### Idee B — „Entity Resolver Live"

Visuell spannend: Baue einen Graph-Viewer, der live zeigt, wie John-in-HubSpot, John-in-Slack und John-in-Drive zur selben Entität konsolidiert werden. Lade 2–3 messy Datenquellen hoch, demonstriere die Resolution, zeige Impact auf Agent-Antworten. Sehr technisch und sehr on-topic zum Manifesto.
**Partner:** Qontext + Gemini + optional Aikido (Access Control).

### Idee C — „One Vault, Many Faces"

Zeige Qontexts Kern-Versprechen end-to-end: Eine Vault powered (1) einen Support-Chat (Frontend via Lovable), (2) einen Sales-Agent (n8n-Workflow), (3) einen Marketing-Content-Generator. Update an einer Quelle reflektiert in allen dreien live. Extrem narrativ für die 5-Min-Pitch.
**Partner:** Qontext + Lovable + n8n + Gemini.

### Idee D — „Context for Agents-at-Scale"

Baue einen Multi-Agent-Orchestrator, der Qontext als Shared Memory zwischen Agenten benutzt. Ein Research-Agent (Tavily) füttert die Vault, ein Analyse-Agent nutzt sie, ein Report-Agent baut daraus einen Output. Fokus auf Governance: welcher Agent sieht welchen Vault-Scope.
**Partner:** Qontext + Tavily + Entire (Developer Platform) + Aikido.

### Idee E — „The Onboarding Compressor"

Demo: Neue Firma wird onboarded. Plug in Notion + Drive + HubSpot → 2 Minuten später: funktionsfähiger AI-Agent für Kunden-Support, inklusive firmenspezifischer Policies. Story: „Agents live at day zero." Schließt direkt am Lorenz-Zitat an.
**Partner:** Qontext + Lovable (UI) + Gemini + telli (Voice-Support-Demo).

---

## Knowledge Work — "Chief of Staff for Everyone"

Reference: https://a16z.com/ai-copilots-and-the-future-of-knowledge-work/

### Problemraum B: „Jeder Knowledge-Worker bekommt einen Chief of Staff, aber nur 1% der Welt kann sich einen leisten"

**Die These:** Top-Performer in jedem Feld (CEOs, Partner, Senior Researcher, Spitzen-Sales) haben einen Chief of Staff oder Executive Assistant. Der Leverage ist gewaltig — jemand der Context hält, priorisiert, koordiniert, vorausdenkt. 99% der Knowledge-Workers haben das nicht. AI kann das für alle bauen, aber keines der aktuellen Tools löst das wirklich (ChatGPT ist reaktiv, Copilot ist oberflächlich, Rewind ist nur Memory).

**Der Marktmechanismus:** Es gibt 1+ Milliarde Knowledge-Worker weltweit. Der Markt für „Executive Assistant pro Knowledge-Worker" ist strukturell riesig. Aktuelle Tools sind Features, nicht Assistants.

**Warum jetzt:** Long-Context-Modelle (1M+ Tokens), Multi-Modal, persistente Memory, und Tool-Use zusammen ermöglichen erstmals einen echten proaktiven Assistant. 2023 nicht möglich, 2026 möglich.

**Was ihr bauen könntet:** Ein Agent der jeden Tag mit dem User startet („here's what matters today, here's what I did for you while you slept, here's what needs your decision"), alle Tools (Mail, Calendar, Notion, Slack, Browser) integriert, proaktiv arbeitet, nicht nur reaktiv antwortet. Demo: Time-lapse eines Arbeitstages mit vs. ohne.

**Verticals wo das zuerst landet:** Founders (kleine Teams, hoher Leverage-Bedarf), Solo-Consultants, VC Associates, Sales Directors.

**Company-Upside:** Horizontal SaaS, potenziell jeder Knowledge-Worker. Martin Casado (a16z) hat öffentlich gesagt das wird ein 100B+ Markt. Rewind, Personal AI, Mem — alle haben es versucht, keiner hat es gelöst.

**Ehrliche Risiken:** Sehr vieles muss zusammen funktionieren. Als Hack-Demo: zu ambitioniert für 48h, muss scope-kontrolliert werden. Konkurrenz von den Großen (Google, Microsoft, OpenAI) wenn sie aufwachen.

---

## Reality Layer

### Problemraum F: „Die Reality-Layer — AI-Agents brauchen einen gemeinsamen Wahrheits-Layer über Unternehmen"

**Die These:** Heute lebt jede AI-App in ihrer eigenen Realität. ChatGPT weiß nicht was Notion weiß, Notion weiß nicht was Salesforce weiß, Salesforce weiß nicht was der Calendar weiß. Jede App hat eine lokale Sicht auf „was ist wahr in diesem Unternehmen." Wenn Agents autonomer werden, führt das zu Konflikten: Agent A bucht ein Meeting, Agent B weiß nicht dass der Kunde bereits gekündigt hat. In 2-3 Jahren wird das zum Hauptproblem der Enterprise-AI-Adoption.

Die Lösung ist nicht „noch eine Integration" — sondern ein **persistenter, konfliktfreier, quellen-attribuierter Wahrheits-Layer** den alle AI-Apps konsumieren. Wie eine Event-Sourced Database aber für semantische Wahrheit.

**Technische Komplexität:** Sehr hoch und interessant. Kern-Probleme:

- Context-Resolution bei Konflikten zwischen Quellen („Notion sagt X, Salesforce sagt Y, welches gilt?")
- Temporale Validität (was war wahr *wann*?)
- Source-Attribution und Trust-Scoring
- Realtime-Sync vs Eventual-Consistency
- Embedding-based Semantic-Deduplication (2 Entries die dasselbe meinen aber anders geschrieben sind)

Das ist *echte* Distributed-Systems + ML-Arbeit, nicht nur Wrapping.

**Business-Mechanismus — wer zahlt und warum:**

- **Wer:** Mid-Market und Enterprise-Companies die AI-Agents produktiv nutzen. Primary Buyer: CTO oder VP Engineering.
- **Was:** €5K-50K/Monat Enterprise-SaaS basierend auf Volumen + integrierten Quellen.
- **Warum bezahlen sie:** Weil jeder AI-Agent den sie deployen schneller wird und weniger Fehler macht wenn er auf einen konsolidierten Layer zugreift statt auf 15 Quellen einzeln. ROI: Weniger AI-Incidents + schnellere Agent-Deployments.
- **Warum jetzt:** Unternehmen deployen gerade 5-10 AI-Tools parallel und merken dass sie kollidieren. Das ist ein akuter Schmerz der 2024 nicht existiert hat.

**Company-Upside:** Infrastruktur-Play. Wenn Enterprise-AI-Adoption exponentiell wächst (was klar der Fall ist), wird jemand der Wahrheits-Layer. Palantir-ähnliches Potenzial, aber für AI-Native Enterprises. 10B+ TAM.

**Demo-Moment beim Hack:** Ihr zeigt 3 Agents (Sales-Agent, Support-Agent, Ops-Agent) die auf dieselbe Realität zugreifen. Ihr stellt einen Konflikt her live (Support-Agent ändert Kunden-Status) — die anderen Agents sehen es sofort und passen Verhalten an. Kontrast zu „klassisch isolierten" Agents die widersprüchlich handeln.

**Risiken:** In 48h nur angedeutet bauen können. Ihr müsst Scope radikal begrenzen: nicht „Wahrheits-Layer für alles", sondern „Wahrheits-Layer für Customer-Context across 3 Systeme."
