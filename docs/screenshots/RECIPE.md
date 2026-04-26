# Screenshot recipe

Step-by-step to capture the 7 PNGs the main README references. Drop them in this directory under the listed filenames. macOS: ⌘⇧4 then space-bar to capture a window cleanly.

**Setup:** start the dev stack first.

```bash
cd /path/to/TechEurope
make dev    # frontend on :5173, backend on :8000
```

If your DB is empty, run a quick ingest+resolve so the screenshots have data:

```bash
DATA=data/enterprise-bench
uv run server ingest --connector email --path $DATA
uv run server ingest --connector document --path $DATA/Policy_Documents
uv run server ingest --connector crm --path $DATA
uv run server ingest --connector hr_record --path $DATA
uv run server infer-source-mappings
for st in email hr_record collaboration it_ticket doc_policy customer client product; do
  uv run server resolve --source-type $st --limit 10
done
uv run server cleanup-pseudo-entities --no-dry-run
```

---

## 1. `connect-hero.png`

- URL: `http://localhost:5173/connect`
- Setup:
  1. Type `my-claude-desktop` in the Token-Name field.
  2. Click **Generate token**.
  3. Make sure the **"Let an AI agent do it"** tab is active (default).
  4. Click the **Claude Code** tile (default-selected).
- Capture: full window. Should show TokenBar with the generated token + Vibe-Track active + the Markdown prompt visible below.

## 2. `browse-entity.png`

- URL: `http://localhost:5173/browse/organization:inazuma-com`
- Capture: full window. Should show:
  - VFS tree on the left (Organizations expanded, `inazuma-com` highlighted).
  - EntityDetail in the center with `inazuma.com`, trust score (≥ 0.5), 8-12 facts.
  - At least one fact row showing extraction-method badge (`pioneer` or `rule`) and a confidence pill.
  - ActionPanel on the right with Propose/Edit/Flag buttons visible.

## 3. `search-results.png`

- URL: `http://localhost:5173/search`
- Setup: type `compliance policy` in the search bar, hit Enter.
- Capture: full window. Should show:
  - The search input at top with the query.
  - 3-5 result cards beneath, mostly `document` typed.
  - **If the cascade-filter steps panel is implemented**, capture it on the right showing how the query decomposed.

## 4. `review-conflict.png`

- URL: `http://localhost:5173/review`
- Setup: click into one of the pending fact-conflicts in the Inbox (left column).
- Capture: full window. Should show:
  - ConflictInbox on the left with several pending items.
  - ConflictDetail in the center with two competing fact values side-by-side, each showing source + timestamp.
  - DecisionPanel on the right with the action buttons (Pick One / Merge / Reject / Both).
  - TrustWeightsPanel visible if collapsible-open.

## 5. `review-pending-types.png`

- URL: `http://localhost:5173/review` → toggle to PendingTypesInbox view.
- Setup: pick a row showing an AI-proposed type (e.g. `category`, `price`, `sale`) with `auto_proposed=true`.
- Capture: should show:
  - The list of pending entity/edge types.
  - A row expanded showing similarity to nearest existing type + Approve/Reject buttons.

## 6. `workflow-graph.png`

- URL: `http://localhost:5173/workflow`
- Setup: zoom to the inazuma-com cluster (search bar or drag-zoom).
- Capture: should show:
  - 30-50 visible nodes color-coded by type.
  - Edge labels visible on the central edges.
  - One node selected/highlighted (preferably a person or `inazuma.com`).

## 7. `csm-task.png`

- URL: open `csm-app` (separate React build — `cd csm-app && npm run dev`, then http://localhost:5174).
- Navigate to a TaskCard showing the **silent deal** or **champion at risk** pattern.
- Capture the TaskCard with its reasoning + actions visible.

---

## Optional bonus shots

- `aura-graph.png` — Neo4j Browser at https://workspace.neo4j.io with the query `MATCH (o:Entity {entity_type:'organization', canonical_name:'inazuma.com'})-[r*1..2]-(n) RETURN o, r, n LIMIT 100`.
- `csm-accounts.png` — `csm-app/accounts` page showing the list view.
- `connect-vibe-prompt.png` — The full Markdown prompt visible in the Vibe-track CodeBlock.

---

## Tips

- Use Chrome's "Capture Screenshot" devtools (⌘⇧P → "Capture screenshot") for clean window-only shots.
- macOS native: ⌘⇧4 then space → click target window. Saves to Desktop with no shadow if you hold Option.
- Resize browser to 1440×900 before shooting for consistent aspect ratio across the 7 PNGs.
- After capturing, drop all PNGs into this `docs/screenshots/` directory; the README links are already wired.
