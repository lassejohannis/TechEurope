# Commercial Product Briefing (Team)

Verbatim from team's Notion. Preserved for Day-1 kickoff reference.

## Executive Summary

Wir bauen eine horizontale Context-Infrastructure für Enterprise-AI. Auf dieser Infrastruktur läuft als erste Application ein Revenue Intelligence Product für B2B-SaaS-Companies. Die Infrastructure ist der langfristige Markt-Hebel, die Revenue App ist der Entry-Point der Adoption und Revenue generiert.

Validierung existiert. Der CRO einer Mid-Market AI-Company hat das Problem als täglich-relevant bestätigt und sechsstelliges Jahresbudget als realistisch bezeichnet. Der Markt für das Underlying-Problem ist explodierend: jede Enterprise-AI-Deployment der nächsten 3-5 Jahre wird einen Context-Layer brauchen.

---

## Das Problem

Knowledge-Workers verlieren Wert weil AI-Tools Company-Reality bei jedem Call neu rekonstruieren. Für den CRO heißt das konkret: Deals sterben mit Signalen die in den Daten waren aber nicht gelesen wurden. Für den CFO: Forecasts basieren auf Rep-Optimismus statt Evidence. Für den CSM: Kunden churnen obwohl Warnsignale seit Wochen sichtbar waren.

Die aktuelle Lösung ist Forward-Deployed Engineering. Große Consultancies und inhouse-Teams bauen Custom-Context-Integrationen pro Use-Case pro Company. Das kostet Millionen, ist nicht portabel, und produziert neue Silos statt sie abzubauen.

Die Marktantwort darauf fragmentiert in zwei Richtungen: (1) Vertikale AI-Tools die jeder ihren eigenen Mini-Context bauen (Clari, Gong, Harvey, Sixfold — dutzende pro Branche), (2) horizontale AI-Infrastructure-Player die meistens auf Retrieval oder Memory reduziert sind (LangChain, Mem, Rewind).

Niemand löst das strukturelle Problem: ein shared, persistent, semantically-resolved company-state den alle AI-Anwendungen konsumieren.

---

## Die Lösung

Zwei Produkt-Ebenen mit klar unterschiedlichen strategischen Rollen.

### Ebene 1: Context Infrastructure

Eine horizontale Platform-Schicht die Company-Reality einmal konsolidiert und allen AI-Applications zur Verfügung stellt. Entity-Resolution über Datenquellen, temporaler State, Source-Attribution, einheitliche Query-API.

Strategische Rolle: Langfristiger Moat. Das ist die Infrastructure auf der die nächste Generation von Enterprise-AI läuft. Vergleichbar mit Databricks für Data, Stripe für Payments, Vercel für Frontend-Deployment.

### Ebene 2: Revenue Intelligence Application

Eine erste Killer-App die auf der Infrastructure läuft. Liefert Sales, Customer Success und Leadership jeden Morgen priorisierte Actions mit Evidence und vorbereiteten Drafts. Kein Dashboard, kein Chat, reiner Output-Stream.

Strategische Rolle: Revenue-Generator und Adoption-Path. Companies kaufen nicht für die Infrastructure — sie kaufen für den konkreten Business-Value. Die Revenue App ist die Eintrittskarte.

### Die Beziehung der beiden

Jedes Revenue-Intelligence-Deployment installiert gleichzeitig die Context Infrastructure beim Kunden. Jede weitere App (CS-spezifisch, Marketing, HR, Finance) kann dann marginal-kosten-niedrig aufgesetzt werden — die Daten sind ja schon da, die Infrastructure läuft ja schon. Das erzeugt Land-and-Expand-Dynamik die klassische Vertical-SaaS nicht hat.

---

## Marktanalyse

### Total Addressable Market

**Context Infrastructure:**
Geschätzt 15-40B global in 5-7 Jahren. Jede Enterprise mit ernsthafter AI-Deployment wird Infrastructure-Spend in dieser Kategorie haben. Vergleichs-Benchmark: Snowflake in Data-Infrastructure bei 50B+ Valuation, Databricks bei 60B+.

**Revenue Intelligence als Entry-Vertical:**
B2B-SaaS-Market hat global 100K+ Companies mit >10 Sales-Reps. Durchschnittlicher RevOps-Budget 50-200K pro Jahr. TAM für Revenue-AI-Tools: 5-10B. Clari hat bei Series F Valuation von 2.6B, Gong bei 7.25B. Der Raum ist groß genug für neue Player mit besserer Architektur.

### Wettbewerbslandschaft

**Direkte Konkurrenz auf Infrastructure-Layer:**

- Qontext (der Track-Partner selbst)
- LangChain (primär Orchestration, nicht State)
- Mem, Rewind, Personal.ai (Consumer-Memory, nicht Enterprise)
- Einige Stealth-Startups die in ähnlichen Richtungen bauen

Wir positionieren nicht gegen Qontext, sondern als Early-Adopter der horizontalen Vision mit erstem produktivem Showcase. Luca's Feedback bestätigt: es gibt noch keinen Market-Leader, das Fenster ist offen.

**Direkte Konkurrenz auf Revenue-App-Layer:**

- Clari (Forecasting, 2.6B Valuation)
- Gong (Revenue Intelligence, 7.25B)
- Outreach/Salesloft (Sales Engagement, jeweils 4-5B)
- People.ai, Scratchpad, Dooly (CRM-Hygiene)
- Salesforce Agentforce (incumbent mit massiver Distribution)

Das ist ein überfüllter Markt. Unsere Differenzierung ist architektonisch: während alle anderen vertikale Silos mit eigenen Mini-Contexten sind, sind wir eine App auf einer horizontalen Infrastructure. Das heißt:

- Schnellere Feature-Entwicklung (kein eigenes Data-Integration-Rebuild)
- Crossfunktionale Views die Silo-Tools nicht liefern können
- Land-and-Expand über Apps hinweg auf derselben Infrastructure

### Warum jetzt

Drei strukturelle Tailwinds:

1. LLM-Capabilities erreichen Produktionsreife für autonome Prozesse
2. Enterprise-AI-Budgets explodieren (Gartner: 300B global in 2027)
3. FDE-Costs werden als nicht-skalierbar erkannt — der Markt sucht aktiv nach Alternativen

---

## Ideal Customer Profile

### Primary ICP für Revenue App

**Firmographics:**

- B2B-SaaS-Companies
- 10-50M ARR
- 20-100 Mitarbeiter im Revenue-Team (Sales + CS kombiniert)
- Komplexer Sales-Cycle (3-12 Monate, Enterprise oder komplexes Mid-Market)
- Multi-Stakeholder-Deals (5+ Personen auf Kundenseite)
- Existing Tool-Stack: Salesforce oder HubSpot, Gong oder Chorus, mindestens ein CSP

**Behaviorals:**

- CRO oder VP Revenue als zentraler Decision-Maker
- CFO als Co-Signatory bei sechsstelligen Deals
- Hat aktiv nach Revenue-Intelligence-Lösungen evaluiert
- Frustriert mit existierenden Tools („Dashboards ohne Actions")

**Trigger-Events:**

- Post Series B/C mit neuem CRO-Hire
- Forecast-Miss in letzten zwei Quartalen
- Churn-Spike oder Net-Revenue-Retention-Drop
- Kommende Re-Evaluation des Salesforce-Stacks

**Beispiel-Firma die exakt passt:** Hypatos. Luca's Feedback war nicht Zufall, das ist der Archetyp.

### Secondary ICPs (nicht primärer Focus, aber Expansion-Vektoren)

- AI-native Companies (Typ Hypatos) mit hohem Self-Awareness und Budget für AI-Tools
- Fintech-Companies mit komplexen Sales-Cycles
- Developer-Tools-Companies (Self-selection für AI-Early-Adoption)

### Anti-ICP

- B2C-Companies
- SMB mit unter 10 Reps (zu klein, zu wenig Daten, zu wenig Budget)
- Enterprise über 500M ARR (zu politisch, zu lange Sales-Cycles, Incumbent-Lock-in)
- Industries mit heavy Compliance-Last (Healthcare, Finance) — erst nach Product-Market-Fit

---

## Go-to-Market

### Phase 1: Design Partners (Monate 0-6)

**Ziel:** 3-5 Design-Partner die gratis-zu-subsidiert das Produkt nutzen, detailliertes Feedback geben, und Case-Studies enablen.

**Akquisition:**

- Luca und seinen Netzwerk direkt angehen
- Warm-Intros über bestehende Netzwerk-Verbindungen
- Berlin/München AI-Community und Revenue-Communities

**Commitment vom Design-Partner:**

- Zugang zu Sales-Data und Revenue-Team für 3 Monate
- Wöchentliche Feedback-Sessions
- Reference-Bereitschaft wenn Produkt funktioniert
- Im Gegenzug: Gratis oder symbolic-priced erstes Jahr

**Success Metric:** Mindestens 2 Design-Partner die unabhängig sagen „das würde ich jederzeit kaufen."

### Phase 2: Early Revenue (Monate 6-12)

**Ziel:** Erste 10 zahlende Customers, 1M ARR.

**Channels:**

- Warm-Outbound von Design-Partner-Network
- Content-Marketing um Thought-Leadership (Essays von Luca-ähnlichen Insights)
- Selective AI-Community-Events (Pavilion, Revenue-Leader-Networks)
- Opportunistic: Hackathons und AI-Conferences als Demo-Surface

**Pricing-Approach:**

- Keine aggressiven Discounts
- Deal-Size 80K-150K Ziel
- Multi-Year-Commitments bevorzugt (10-15% Discount für 2-Jahr)

### Phase 3: Scale (Year 2+)

**Ziel:** Product-Market-Fit bestätigt, dedicated Sales-Team aufbauen, 5M ARR als Ziel für Ende Year 2.

**Channels:**

- Inbound über Content und SEO
- Outbound via Dedicated SDRs
- Partner-Channels (Systemintegratoren, RevOps-Consultants)
- Second Application-Layer: Launch Customer-Success-spezifische App, HR-App etc. — Expand-Motion über bestehende Accounts

---

## Differenzierung

### Gegen Clari/Gong/Agentforce

Sie sind vertikale Silos mit eigenen Mini-Contexten. Output ist deskriptive Dashboards und Meeting-Transcripts. Nutzer müssen Insights selbst synthesisieren und in Actions übersetzen.

Wir liefern direkt prioritisierte Actions mit vorbereiteten Drafts. Der Mensch entscheidet nur was er tun will. Strukturell anderes Produkt.

Außerdem: unsere Infrastructure-Layer ist wiederverwendbar. Clari-Kunden zahlen für ein Tool, unsere Kunden zahlen für eine Plattform auf der weitere Tools entstehen.

### Gegen Salesforce Agentforce

Salesforce hat massive Distribution und ist default-choice für CRO-Stacks. Wir werden nicht auf Distribution-Basis gewinnen.

Differenzierung über:

- Qualitäts-Lead bei AI-generierten Actions (Salesforce's AI ist noch generic)
- Cross-Stack-Integration (wir lesen Gong, Slack, Docs, nicht nur Salesforce-Daten)
- Best-of-breed-Appeal für Companies die Salesforce nicht vendor-lock-in wollen

### Gegen Custom-Build-FDE

Forward-Deployed-Engineering von Consultancies oder Inhouse-Teams ist die größte Konkurrenz. Companies können das Problem theoretisch selbst lösen.

Wir gewinnen weil:

- Time-to-Value: 4-6 Wochen statt 6-12 Monate
- Kosten: 100K/Jahr statt 500K-1M Implementation
- Up-to-date: wir shippen Features, interne Teams maintain existing code
- Infrastructure ist portabel über Use-Cases, FDE-Code ist typisch monolithisch

---

## Business-Story für den Pitch

### In einem Satz

*We're building the first real context infrastructure for enterprise AI — and proving its value with a revenue intelligence app that a CRO already told us he'd pay six figures for.*

### In drei Minuten

Die Insight ist: jede AI-Welle erforderte eine neue Infrastructure. Mobile brauchte Cloud. Deep-Learning brauchte GPUs. Enterprise-AI braucht jetzt den Context-Layer. Der Spieler der das strukturell löst wird die Infrastructure-Player dieser Welle.

Gleichzeitig wissen wir: niemand kauft Infrastructure abstrakt. Companies kaufen Outcomes. Also wählen wir einen ersten Vertical wo Context-Problem und Revenue direkt korrelieren: B2B-Sales-Teams die Millionen in vermeidbaren Deals verlieren weil sie ihre eigenen Daten nicht lesen können.

Wir bauen beides parallel. Die Revenue-App verkauft sich selbst und generiert Cashflow. Die Infrastructure ist der langfristige Moat. Jedes Revenue-App-Deployment installiert gleichzeitig die Infrastructure beim Customer. Zweite App, dritte App folgen marginal-kosten-niedrig.

Die Validierung ist nicht theoretisch. Luca (CRO bei Hypatos, Top-20 AI-Startup Europa) hat das Problem als täglich-akut bestätigt und sechsstelliges Budget als realistisch beziffert. Sein direktes Zitat: *„Eine zentrale Daten-/Aktions-Ebene die Sales UND CSM bedient wäre bei uns sofort im sechsstelligen Bereich diskutabel."*

### Key Messages für verschiedene Stakeholder

**Für Investoren:**
Wir sind Infrastructure-Play mit SaaS-Economics. Platform-TAM ist 15-40B. Erste App hat validierten Product-Market-Fit mit Potential-Customer. Team hat Track-Record in Hackathon-Wins und Builder-DNA.

**Für potenzielle Kunden:**
Wir geben eurem Revenue-Team 3-5 Stunden pro Woche zurück und verhindern messbar die Deals die ihr sonst verliert. Implementation in Wochen statt Monaten. Pricing: 80-200K abhängig von Team-Size.

**Für Partner (Qontext-Founder, potentielle Design-Partner):**
Wir bauen die Use-Cases die eure Platform brauchbar machen für Nicht-Forward-Deployed-Engineering-Customers. Ihr bekommt einen Early-Reference-Case der horizontale Vision demonstriert.

---

## Metrics & Success Criteria

### Product-Metriken

- **Time-to-Action:** Zeit von Signal zu CTA im Tool. Ziel: <10 Minuten. Heute: Tage oder nie.
- **Action Acceptance Rate:** Anteil vom User akzeptierter CTAs. Ziel: >60% nach 3 Monaten Nutzung.
- **Deal Rescue Rate:** At-Risk-Deals gerettet durch CTA-Intervention. Ziel: 15-25% Uplift über Baseline.
- **Forecast Accuracy:** Delta Forecast vs Actual. Ziel: unter 10%.

### Business-Metriken

- **ACV:** Ziel 80-150K im ersten Jahr
- **Gross Retention:** Ziel >90% nach 12 Monaten
- **Net Revenue Retention:** Ziel >120% nach 18 Monaten durch Seat-Expansion und Second-App-Adoption
- **Time-to-Revenue:** Design-Partner zu erstem paid Customer in 6 Monaten
- **CAC Payback:** Ziel unter 18 Monaten

### Validation-Milestones

- **Monat 3:** 2 Design-Partner signed
- **Monat 6:** Erster paid Customer, 1 Second-App-Prototype
- **Monat 12:** 10 Customers, 1M ARR, bewiesene Second-App-Adoption bei mindestens 3 Customers
- **Monat 18:** Series A Raise positioniert mit 3-5M ARR

---

## Strategic Risks

### Risiko: Qontext wird zum direkten Konkurrent

Lorenz baut dieselbe horizontale Infrastructure. Wenn unser Produkt zu infrastructure-nah positioniert wird, treten wir gegen sie an.

Mitigation: Klar als Application-Player auf Infrastructure-Layer positionieren. Potentielle Partnership mit Qontext explorieren statt Kompetition. Wenn Qontext's Platform ausgereift ist, migrieren wir unsere Infrastructure auf ihre Platform.

### Risiko: Incumbent-Response

Salesforce oder Clari bauen ähnliche Cross-Tool-Action-Features in 12-18 Monaten.

Mitigation: Speed in Feature-Development. Horizontal-Architecture als strukturelle Differenzierung die Incumbents aufgrund Legacy nicht schnell kopieren können. Vertikal-Depth durch erste Apps aufbauen als Lock-in.

### Risiko: ICP-Market-Saturation

Revenue-AI-Space ist sehr überfüllt (Luca's Zitat: „sehr, sehr, sehr überfüllt"). Differenzierung schwer kommunizierbar.

Mitigation: Narrow ICP-Fokus auf AI-Native-Companies in ersten 12 Monaten. Dort ist Differenzierung leichter verständlich und Buying-Cycle schneller. Expansion in klassische B2B-SaaS erst nach ersten Case-Studies.

### Risiko: Single-Customer-Dependency

Wenn wir zu sehr auf Hypatos als ersten Design-Partner setzen, entsteht Overfit-Risiko.

Mitigation: Parallel mindestens 2-3 weitere Design-Partner in Pipeline halten. Product-Features müssen für alle Design-Partner wertvoll sein, nicht nur einer.

---

## Long-term Vision

In 5 Jahren: Wir sind die Context-Infrastructure auf der Enterprise-AI läuft. Revenue-App ist eine von 5-10 Apps in unserem eigenen Ecosystem. Drittanbieter bauen eigene Apps auf unserer Infrastructure. Valuation-Pfad: 2-5B durch Infrastructure-Leadership plus SaaS-Revenue aus Apps.

In 10 Jahren: Acquisition-Kandidat für Salesforce, Microsoft, oder Google — oder Independent Public Company. Die „Stripe für Enterprise-AI-Context".

Das ist die Vision. Der erste Schritt ist ein Hack in Berlin.

---

> **Note:** Pricing section from the team's Notion was crossed out (not final). Skipped here; decide with team.
