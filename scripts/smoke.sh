#!/usr/bin/env bash
# Smoke-test a running ServeTrace: the page, the version, a demo check, a PDF, the store.
#
#   scripts/smoke.sh                         # http://localhost:8000
#   scripts/smoke.sh https://servetrace.onrender.com
#
# Uses only the bundled synthetic demo case, sends it marked as a demo (so a live store
# counts it apart), and needs curl and python3. Exits non-zero on the first failure.
set -euo pipefail

BASE="${1:-http://localhost:8000}"
BASE="${BASE%/}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CASE="$ROOT/fixtures/demo_cases/maria_contradicted"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; exit 1; }

echo "ServeTrace smoke test against $BASE"

# 1. Health, and the version the code says it is.
want=$(sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' "$ROOT/backend/app/config.py")
health=$(curl -fsS --max-time 90 "$BASE/api/health") || fail "health did not answer (a cold start can take a minute)"
got=$(printf '%s' "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin)["app_version"])')
[ "$got" = "$want" ] && pass "health: version $got" || fail "health says $got, code says $want"

# 2. The pages are served, with the security headers.
for page in / /check /methodology /changelog /attorneys /privacy; do
  code=$(curl -s -o "$WORK/page" -w '%{http_code}' "$BASE$page")
  [ "$code" = 200 ] || fail "GET $page -> $code"
done
pass "pages: / /check /methodology /changelog /attorneys /privacy"
headers=$(curl -fsSI "$BASE/")
for h in x-content-type-options referrer-policy x-frame-options; do
  printf '%s' "$headers" | grep -qi "^$h:" || fail "missing header $h on /"
done
pass "security headers on /"

# 3. A demo check: confirmed affidavit + its windowed fixes -> a verdict.
python3 - "$CASE" > "$WORK/analyze.json" <<'PY'
import json, sys, pathlib
case = pathlib.Path(sys.argv[1])
affidavit = json.loads((case / "affidavit.json").read_text())
affidavit["user_confirmed"] = True
print(json.dumps({"affidavit": affidavit, "fixes": json.loads((case / "fixes.json").read_text())}))
PY
curl -fsS -H 'content-type: application/json' -H 'x-servetrace-demo: 1' \
  --data @"$WORK/analyze.json" "$BASE/api/analyze" > "$WORK/analysis.json" || fail "analyze refused the demo case"
overall=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["overall"])' "$WORK/analysis.json")
[ "$overall" = contradicted ] && pass "analyze: demo case is $overall" || fail "demo case came back $overall"

# 4. The evidence packet renders as a PDF carrying the version.
python3 -c 'import json,sys; print(json.dumps({"analysis": json.load(open(sys.argv[1])), "fixes": []}))' \
  "$WORK/analysis.json" > "$WORK/packet.json"
type=$(curl -sS -o "$WORK/packet.pdf" -w '%{content_type}' -H 'content-type: application/json' \
  -H 'x-servetrace-demo: 1' --data @"$WORK/packet.json" "$BASE/api/documents/packet")
case "$type" in application/pdf*) ;; *) fail "packet came back as $type" ;; esac
head -c 5 "$WORK/packet.pdf" | grep -q '%PDF-' || fail "packet is not a PDF"
pass "packet: $(wc -c < "$WORK/packet.pdf" | tr -d ' ') byte PDF"

# 5. An oversized body is refused at the door.
code=$(head -c 20000000 /dev/zero | curl -s -o /dev/null -w '%{http_code}' \
  -H 'content-type: application/json' --data-binary @- "$BASE/api/analyze")
[ "$code" = 413 ] && pass "a 20 MB body is refused (413)" || fail "a 20 MB body got $code"

# 6. The store: answers either way, and says whether it is on.
enabled=$(curl -fsS "$BASE/api/stats" | python3 -c 'import json,sys; print(json.load(sys.stdin)["enabled"])')
pass "stats: store enabled = $enabled"

echo "all checks passed"
