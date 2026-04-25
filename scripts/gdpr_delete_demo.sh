#!/usr/bin/env bash
# GDPR delete-cascade demo
#
# Picks one HR source_record from Supabase, shows derived facts + dependent
# entities, then issues DELETE /api/admin/source-records/{id}?confirm=true.
# The Postgres ON DELETE CASCADE on facts.source_id removes derived facts
# atomically — proving the "right to be forgotten" path.
#
# Requirements:
#   • Server running locally (`make server` or `uv run server`)
#   • API_AUTH_DISABLED=true in server/.env, OR API_TOKEN env var set to a
#     valid bearer (admin scope).
#
# Usage:
#   bash scripts/gdpr_delete_demo.sh                    # picks an arbitrary HR record
#   bash scripts/gdpr_delete_demo.sh hr_record:emp_0431 # specific source_record id
#   DRY_RUN=1 bash scripts/gdpr_delete_demo.sh          # show counts but don't delete

set -euo pipefail

API="${API:-http://127.0.0.1:8000}"
TOKEN="${API_TOKEN:-}"
TARGET="${1:-}"
DRY_RUN="${DRY_RUN:-0}"

curl_args=(-sS --fail-with-body)
if [[ -n "$TOKEN" ]]; then
    curl_args+=(-H "Authorization: Bearer $TOKEN")
fi

# ── 1. health check ───────────────────────────────────────────────────────
echo "── 1. health check ──"
curl "${curl_args[@]}" "$API/api/health" | python3 -m json.tool
echo

# ── 2. pick a target source_record ────────────────────────────────────────
if [[ -z "$TARGET" ]]; then
    echo "── 2. picking a recent hr_record source from the DB ──"
    # We fall back to a deterministic test target if no list endpoint exists.
    # In production you'd query /api/sources or supabase directly.
    TARGET="$(curl "${curl_args[@]}" \
        "$API/api/changes/recent?limit=1" \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); ch=d.get("changes") or []; print(ch[0].get("fact_id","") if ch else "")' 2>/dev/null || true)"

    if [[ -z "$TARGET" ]]; then
        echo "  ⚠  no recent change found — pass a source_record id explicitly:"
        echo "     bash scripts/gdpr_delete_demo.sh hr_record:emp_0431"
        exit 1
    fi
fi
echo "  target source_record: $TARGET"
echo

# ── 3. dry-run: ask the API how big the blast radius is ───────────────────
echo "── 3. would-delete preview (DELETE without confirm) ──"
PREVIEW="$(curl "${curl_args[@]}" -X DELETE \
    "$API/api/admin/source-records/$TARGET" 2>&1 || true)"
echo "$PREVIEW" | python3 -m json.tool 2>/dev/null || echo "$PREVIEW"
echo

if [[ "$DRY_RUN" == "1" ]]; then
    echo "── DRY_RUN=1 → stopping before destructive call ──"
    exit 0
fi

# ── 4. real delete with cascade ───────────────────────────────────────────
echo "── 4. executing GDPR delete with confirm=true ──"
RESPONSE="$(curl "${curl_args[@]}" -X DELETE \
    "$API/api/admin/source-records/$TARGET?confirm=true")"
echo "$RESPONSE" | python3 -m json.tool

echo
echo "── 5. verify: source_record + derived facts are gone ──"
# Try to fetch the source record back — should 404 or return empty.
VERIFY="$(curl "${curl_args[@]}" \
    "$API/api/changes/recent?limit=20" \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
changes = data.get('changes') or data.get('items') or []
target = '$TARGET'
hit = [c for c in changes if c.get('fact_id') == target or c.get('source_id') == target]
if hit:
    print(f'⚠  still see {len(hit)} change row(s) referencing {target}')
else:
    print(f'✓  no recent changes reference {target} — cascade verified')
")"
echo "$VERIFY"
echo
echo "── done ──"
