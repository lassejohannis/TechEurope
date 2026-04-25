"""End-to-end Pioneer fine-tune pipeline — generate → upload → train → eval.

Uses Pioneer's own endpoints exclusively. No Gemini in the loop.

Subcommands
-----------
  generate      Synthetic NER data via POST /generate (Pioneer's own LLM teacher)
  label         Auto-label our raw EnterpriseBench chunks via POST /generate/ner/label-existing
  upload        Upload a local NER JSONL to Pioneer (presigned S3 + process)
  datasets      List datasets we have on Pioneer
  train         POST /felix/training-jobs — start a fine-tune
  jobs          List recent training jobs
  status        Poll /felix/training-jobs/:id status (and /generate/jobs/:id for gen jobs)
  eval          POST /felix/evaluations on a finished training job
  evals         List evaluations
  evalresult    GET /felix/evaluations/:id

Examples
--------
    # 1. Generate 500 synthetic NER examples for our entity vocabulary
    uv run python scripts/pioneer_pipeline.py generate \\
        --dataset-name enterprise-ner-v4-synth --num-examples 500

    # 2. (optional) Auto-label 200 raw EnterpriseBench chunks
    uv run python scripts/pioneer_pipeline.py label \\
        --dataset-name enterprise-ner-v4-real --max 200

    # 3. Train on the dataset Pioneer just created
    uv run python scripts/pioneer_pipeline.py train \\
        --dataset enterprise-ner-v4-synth --model-name enterprise-ner-gliner2-v4

    # 4. Evaluate on a held-out dataset
    uv run python scripts/pioneer_pipeline.py eval \\
        --training-job <UUID> --dataset enterprise-ner-v4-synth
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from server.config import settings  # noqa: E402
from server.extractors.prompt import ENTITY_TYPES  # noqa: E402

# Reuse our chunk loaders for label-existing.
from gen_pioneer_training import LOADERS  # noqa: E402

API = "https://api.pioneer.ai"
LABELS = list(ENTITY_TYPES)
DOMAIN_DESCRIPTION = (
    "Internal enterprise communications: emails between employees, HR records "
    "and resumes, customer support tickets and chats, sales orders and invoices, "
    "team-collaboration messages, and policy documents. Texts mix English, "
    "internal jargon, employee IDs, project codes, and product/customer names. "
    "Entities to extract: person (employees, customer contacts), customer (external "
    "company), vendor (external supplier), product, org_unit (internal department/team), "
    "process (recurring workflow), policy (named rule/guideline), project (initiative), "
    "task (action item), ticket (support/incident), repo (codebase). "
    "Skip pronouns, generic role nouns, signatures, dates, URLs."
)


# --------------------------------------------------------------------------- #
# HTTP helpers                                                                #
# --------------------------------------------------------------------------- #


def _headers(json_body: bool = True) -> dict[str, str]:
    if not settings.pioneer_api_key:
        sys.exit("PIONEER_API_KEY missing in env")
    h = {"X-API-Key": settings.pioneer_api_key}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _request(method: str, path: str, **kw) -> dict:
    """Pioneer call with friendly error reporting."""
    url = path if path.startswith("http") else f"{API}{path}"
    headers = _headers(json_body=("json" in kw))
    if "headers" in kw:
        headers.update(kw.pop("headers"))
    resp = httpx.request(method, url, headers=headers, timeout=120.0, **kw)
    if resp.status_code >= 400:
        sys.exit(f"{method} {path} → HTTP {resp.status_code}\n{resp.text[:600]}")
    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.json()
    return {"raw": resp.text}


# --------------------------------------------------------------------------- #
# Subcommands                                                                 #
# --------------------------------------------------------------------------- #


def cmd_generate(a: argparse.Namespace) -> None:
    """POST /generate — Pioneer creates synthetic NER training data for us."""
    body = {
        "task_type": "ner",
        "dataset_name": a.dataset_name,
        "num_examples": a.num_examples,
        "labels": LABELS,
        "domain_description": DOMAIN_DESCRIPTION,
    }
    print(f"POST /generate  dataset={a.dataset_name}  n={a.num_examples}  labels={LABELS}")
    resp = _request("POST", "/generate", json=body)
    print(json.dumps(resp, indent=2))
    job_id = resp.get("job_id") or resp.get("id")
    if a.wait and job_id:
        _poll_generate_job(job_id)


def _poll_generate_job(job_id: str) -> None:
    print(f"\npolling /generate/jobs/{job_id} ...")
    while True:
        r = _request("GET", f"/generate/jobs/{job_id}")
        status = r.get("status") or r.get("normalized_status") or "?"
        progress = r.get("progress_percent")
        print(f"  status={status}  progress={progress}")
        if status in {"complete", "completed", "failed", "error"} or r.get("is_terminal_status"):
            print(json.dumps(r, indent=2))
            return
        time.sleep(10)


def cmd_label(a: argparse.Namespace) -> None:
    """POST /generate/ner/label-existing on raw EnterpriseBench chunks.

    Pioneer's GLiNER2 produces (text, entities) pairs which we save as a
    local JSONL. Then upload via `upload` subcommand.
    """
    domains = a.domains.split(",")
    inputs: list[str] = []
    for d in domains:
        loader = LOADERS.get(d)
        if not loader:
            print(f"  ! unknown domain {d}", file=sys.stderr)
            continue
        per = max(1, a.max // len(domains))
        for chunk in list(loader(limit=per * 2))[:per]:
            inputs.append(chunk[3])  # text only
    inputs = inputs[: a.max]
    print(f"labeling {len(inputs)} inputs ...")

    # Pioneer caps at 1000 inputs per call; chunk if needed.
    batch_size = 100
    all_results: list[dict] = []
    for i in range(0, len(inputs), batch_size):
        batch = inputs[i : i + batch_size]
        body = {"labels": LABELS, "inputs": batch}
        r = _request("POST", "/generate/ner/label-existing", json=body)
        results = r.get("results") or r.get("data") or r
        if isinstance(results, list):
            all_results.extend(results)
        else:
            all_results.append(results)
        print(f"  batch {i // batch_size + 1}: {len(batch)} done")

    # Convert each Pioneer label result into Pioneer-NER format ({"text", "entities"}).
    out_path = ROOT.parent / "data" / "training" / f"{a.dataset_name}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for src_text, item in zip(inputs, all_results):
            entities = _flatten_pioneer_entities(item)
            row = {"text": src_text, "entities": entities}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nwrote {out_path}  rows={len(inputs)}")


def _flatten_pioneer_entities(item: dict) -> list[list]:
    """Pioneer returns either flat list of {text,label,start,end} or grouped {label: [...]}.
    Convert to Pioneer's training format: [[span, label], ...]."""
    out: list[list] = []
    ents = item.get("entities") or item.get("result", {}).get("entities") or {}
    if isinstance(ents, dict):
        for label, mentions in ents.items():
            for m in mentions:
                span = m["text"] if isinstance(m, dict) else m
                out.append([span, label])
    elif isinstance(ents, list):
        for m in ents:
            span = m.get("text", m.get("span", ""))
            out.append([span, m.get("label", "?")])
    return out


def cmd_upload(a: argparse.Namespace) -> None:
    """3-step S3 upload then trigger processing."""
    path = Path(a.file)
    if not path.exists():
        sys.exit(f"missing file {path}")
    fmt = "jsonl" if path.suffix == ".jsonl" else "json"

    # 1. presigned URL
    body = {"dataset_name": a.dataset_name, "dataset_type": "ner", "format": fmt}
    pre = _request("POST", "/felix/datasets/upload/url", json=body)
    presigned = pre.get("presigned_url") or pre.get("upload_url") or pre.get("url")
    dataset_id = pre.get("dataset_id") or pre.get("id")
    if not presigned:
        print(json.dumps(pre, indent=2))
        sys.exit("no presigned URL in response")
    print(f"got presigned url; dataset_id={dataset_id}")

    # 2. PUT to S3
    print(f"uploading {path.stat().st_size} bytes ...")
    put = httpx.put(
        presigned,
        content=path.read_bytes(),
        headers={"Content-Type": "application/octet-stream"},
        timeout=300.0,
    )
    if put.status_code >= 400:
        sys.exit(f"S3 PUT failed: {put.status_code}\n{put.text[:300]}")
    print("uploaded.")

    # 3. trigger processing
    proc = _request(
        "POST",
        "/felix/datasets/upload/process",
        json={"dataset_id": dataset_id, "format": fmt, "dataset_type": "ner"},
    )
    print(json.dumps(proc, indent=2))


def cmd_datasets(_: argparse.Namespace) -> None:
    r = _request("GET", "/felix/datasets")
    items = r.get("datasets") or r.get("data") or r
    if isinstance(items, list):
        for d in items:
            print(f"  {d.get('name', d.get('id', '?'))}  status={d.get('status', '?')}  type={d.get('dataset_type', '?')}")
    else:
        print(json.dumps(r, indent=2))


def cmd_train(a: argparse.Namespace) -> None:
    body = {
        "model_name": a.model_name,
        "base_model": a.base_model,
        "datasets": [{"name": a.dataset}],
        "training_type": a.training_type,
        "nr_epochs": a.epochs,
        "learning_rate": a.lr,
        "batch_size": a.batch_size,
    }
    print("POST /felix/training-jobs")
    print(json.dumps(body, indent=2))
    r = _request("POST", "/felix/training-jobs", json=body)
    print(json.dumps(r, indent=2))


def cmd_jobs(_: argparse.Namespace) -> None:
    r = _request("GET", "/felix/trained-models")
    for j in r.get("training_jobs", []):
        m = j.get("metrics") or {}
        print(
            f"  {j['model_name']:<32} id={j['id']}  "
            f"status={j['status']:<10}  "
            f"f1={m.get('eval_f1_score', '—')}  "
            f"created={j['created_at'][:19]}"
        )


def cmd_status(a: argparse.Namespace) -> None:
    r = _request("GET", f"/felix/training-jobs/{a.id}")
    print(json.dumps(r, indent=2))


def cmd_eval(a: argparse.Namespace) -> None:
    body = {"base_model": a.training_job, "dataset_name": a.dataset}
    print("POST /felix/evaluations")
    print(json.dumps(body, indent=2))
    r = _request("POST", "/felix/evaluations", json=body)
    print(json.dumps(r, indent=2))


def cmd_evals(_: argparse.Namespace) -> None:
    r = _request("GET", "/felix/evaluations")
    for e in r.get("evaluations", r.get("data", [])):
        print(f"  {e.get('id'):<40}  status={e.get('status'):<10}  base={e.get('base_model')}  dataset={e.get('dataset_name')}")


def cmd_evalresult(a: argparse.Namespace) -> None:
    r = _request("GET", f"/felix/evaluations/{a.id}")
    print(json.dumps(r, indent=2))


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Pioneer-side synthetic NER data generation")
    g.add_argument("--dataset-name", required=True)
    g.add_argument("--num-examples", type=int, default=500)
    g.add_argument("--wait", action="store_true", help="Poll until job finishes.")
    g.set_defaults(fn=cmd_generate)

    lab = sub.add_parser("label", help="Auto-label raw EnterpriseBench chunks via GLiNER2")
    lab.add_argument("--dataset-name", required=True)
    lab.add_argument("--max", type=int, default=200)
    lab.add_argument("--domains", default="emails,employees,support,sales,chat")
    lab.set_defaults(fn=cmd_label)

    up = sub.add_parser("upload", help="Upload a local NER JSONL to Pioneer")
    up.add_argument("--dataset-name", required=True)
    up.add_argument("--file", required=True)
    up.set_defaults(fn=cmd_upload)

    sub.add_parser("datasets", help="List Pioneer datasets").set_defaults(fn=cmd_datasets)

    tr = sub.add_parser("train", help="Start a training job")
    tr.add_argument("--dataset", required=True)
    tr.add_argument("--model-name", required=True)
    tr.add_argument("--base-model", default="fastino/gliner2-base-v1")
    tr.add_argument("--training-type", default="lora", choices=["lora", "full"])
    tr.add_argument("--epochs", type=int, default=10)
    tr.add_argument("--lr", type=float, default=5e-5)
    tr.add_argument("--batch-size", type=int, default=8)
    tr.set_defaults(fn=cmd_train)

    sub.add_parser("jobs", help="List trained models").set_defaults(fn=cmd_jobs)

    st = sub.add_parser("status", help="Poll a training job")
    st.add_argument("--id", required=True)
    st.set_defaults(fn=cmd_status)

    ev = sub.add_parser("eval", help="Run a Pioneer eval")
    ev.add_argument("--training-job", required=True)
    ev.add_argument("--dataset", required=True)
    ev.set_defaults(fn=cmd_eval)

    sub.add_parser("evals", help="List evaluations").set_defaults(fn=cmd_evals)

    er = sub.add_parser("evalresult", help="Get one evaluation's result")
    er.add_argument("--id", required=True)
    er.set_defaults(fn=cmd_evalresult)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
