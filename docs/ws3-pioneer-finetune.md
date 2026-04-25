# WS-3 — Pioneer Fine-Tune Runbook

Companion to [`docs/workstreams.md`](workstreams.md#ws-3--pioneer-fine-tune-hard-cap-6h). What this doc covers:

1. How to generate the training JSONL (Task 2 — automated)
2. How to submit the fine-tune to Pioneer (Task 3 — manual, you run this)
3. How to wire the resulting model into the cascade (Task 4)
4. How to run the comparison eval (Task 5)

**Hard-cap:** Saturday 18:00. If submission misses the cap → flip Tier 3.5 to Gemini-only and ship Pioneer as "Day 2" in the pitch.

---

## 0. Prerequisites

- `server/.env` has `GEMINI_API_KEY=...` (Day-1 setup; same key works for `aistudio.google.com` keys and DeepMind temp accounts).
- Pioneer account active + CLI authed (the on-site onboarding page has both).
- EnterpriseBench is at `data/enterprise-bench/` (already committed).

---

## 1. Generate training pairs

Default produces 300 pairs across all 5 domains:

```bash
uv --directory server run python scripts/gen_pioneer_training.py --target 300
```

Selectable subsets:

```bash
# Just emails + employees, 100 total
uv --directory server run python scripts/gen_pioneer_training.py \
    --target 100 --domains emails,employees

# Sanity-check before burning Gemini credits
uv --directory server run python scripts/gen_pioneer_training.py --dry-run --target 5
```

**Idempotent.** Re-running skips chunks already present in `data/training/pioneer_training.jsonl`. Safe to abort + resume.

**Hold-out:** the comparison eval (`compare_extractors.py`) reuses the trailing N rows of the JSONL as fixtures. Either:

- **Pragmatic path:** stop generation 10 rows early, run eval against those.
- **Strict path:** split before submitting — `head -n -10 ... > train.jsonl; tail -n 10 ... > fixtures.jsonl`.

---

## 2. Submit fine-tune to Pioneer

**Pioneer is conversational, not a CLI.** You drive it through the chat agent at `agent.pioneer.ai` and authenticate with an API key from `gliner.pioneer.ai`.

### 2a. Convert our JSONL to GLiNER2 format

Pioneer's GLiNER2 wants a different shape than ours (entities grouped by type, relations as `{predicate: {head, tail}}`). Run the converter:

```bash
uv --directory server run python scripts/convert_to_gliner2.py
# → data/training/gliner2_training.jsonl   (~294 rows for fine-tune)
# → data/training/gliner2_holdout.jsonl    (10 rows for local eval)
```

### 2b. Get the API key

1. Visit https://gliner.pioneer.ai
2. Log in with your Pioneer account
3. Copy the API key into `server/.env`:
   ```
   PIONEER_API_KEY=...
   ```

### 2c. Talk to the agent

Open https://agent.pioneer.ai and paste a prompt like:

> Fine-tune a GLiNER2 model for entity and relation extraction on enterprise text. I'll upload `gliner2_training.jsonl` (294 examples from emails, employee profiles, support tickets, sales records, and chat conversations). Entity types: person, customer, product, org_unit, process, policy, project, task, ticket, vendor, repo. Top relations: works_for, purchased, discusses, sent_email_to, is_part_of. If 294 is too few, generate synthetic data to bring the corpus to ~1500. Run an eval against base GLiNER2 and report precision/recall per entity type. Deploy when done and give me the inference endpoint.

Upload the JSONL when the agent asks. Per Fastino's docs, GLiNER2 fine-tunes 5k examples in ~20 minutes — our 294 (or augmented to ~1.5k) should be quick.

### 2d. Capture the result

Pioneer returns:

- a **model id** (something like `gliner2-ft-...`)
- an **inference endpoint** URL
- optionally **downloadable weights**

Add them to `server/.env`:

```
PIONEER_MODEL_ID=gliner2-ft-...
PIONEER_ENDPOINT=https://...
```

`extractors.pioneer.AVAILABLE` flips to `True` automatically once `PIONEER_MODEL_ID` is set — restart the server / re-run the eval.

**Decision point — Saturday 18:00:**

| Outcome | Action |
|---|---|
| Model deployed, endpoint in hand | Continue to step 3 |
| Job submitted, still training | Wait, but don't block downstream — Tier 3.5 stays on Gemini meanwhile |
| Pioneer didn't accept the job | Tier 3.5 = Gemini-only. Update pitch deck slide to "Pioneer integration: Day 2" |

---

## 3. Wire inference

`server/src/server/extractors/pioneer.py` is a stub. Once you have an endpoint + key:

1. Implement `_call_pioneer(model_id, text, source_type)` — POST to `PIONEER_ENDPOINT` with the auth header, parse the GLiNER2 response (entities-by-type + relations) back into our `ExtractionResult` (entities + facts). The mapping is the inverse of `convert_to_gliner2.py`.
2. The cascade (WS-2 Tier 3.5) imports `pioneer.extract`; no other change needed.

The call signature is intentionally identical to `gemini.extract` so the cascade can swap them transparently.

### Alternative: self-host with the GLiNER2 Python lib

If Pioneer is unavailable / over-quota, you can train locally instead. Add `gliner2` to `server/pyproject.toml` and run something like:

```python
from gliner2 import GLiNER2
from gliner2.training.data import InputExample
from gliner2.training.trainer import GLiNER2Trainer, TrainingConfig

# load JSONL → InputExample list, train, save weights
model = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
trainer = GLiNER2Trainer(model, TrainingConfig(output_dir="./pioneer_ft", num_epochs=10))
trainer.train(train_data=examples)

# inference
model = GLiNER2.from_pretrained("./pioneer_ft/best")
```

Loses the side-prize ($700, "Best use of Pioneer") but keeps the technical story intact.

---

## 4. Run the comparison eval

```bash
uv --directory server run python scripts/compare_extractors.py
# → data/training/comparison.json
```

The eval:

- Picks the last 10 rows of `pioneer_training.jsonl` as held-out fixtures (override with `--fixtures path.jsonl`).
- Runs Gemini + Pioneer on each.
- Diffs both against the gold output (the same Gemini result from training-pair generation — imperfect proxy, but it's what we have for the hack).
- Writes `data/training/comparison.json` with per-row entity / predicate diffs and latencies.

The frontend (WS-6) reads this JSON to render the comparison table that goes on the demo screen and into the side-prize submission.

---

## 5. Side-prize checklist (Pioneer / Fastino)

For the **"Best use of Pioneer"** category ($700, see [side-challenges.md](side-challenges.md)):

- [ ] Fine-tuned model produces structured output that Gemini Flash didn't, or matches Gemini Pro at lower latency / cost.
- [ ] `comparison.json` exists, demonstrates the win.
- [ ] Synthetic data generation is mentioned in the submission (Pioneer cares about this).
- [ ] Bonus angle: GLiNER2 extraction on long-tail entities (e.g. internal product names, project codes) where general LLMs hallucinate.
