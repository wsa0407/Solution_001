#!/usr/bin/env bash
# Start skill backend (8002) and pinned dsh web (3080). Do not fork harness into git.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="$ROOT/dsh-profile"
BACKEND="${SOLUTION_BACKEND_URL:-http://127.0.0.1:8002}"
DSH_PKG="${DSH_NPM:-@deepseek-ai/dsh@0.1.0-rc.6}"
PY="$ROOT/backend/.venv/bin/python"
PATCH="$PROFILE/cordis.patch.yml"

if [[ ! -x "$PY" ]]; then
  echo "缺少 $PY 。先：cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dsh]'" >&2
  exit 1
fi

mkdir -p "$ROOT/.dsh"
if [[ ! -e "$ROOT/.dsh/skills" ]]; then
  ln -sfn "../dsh-profile/skills" "$ROOT/.dsh/skills"
fi

"$PY" - "$PROFILE/cordis.patch.yml.tmpl" "$PROFILE/agents/main.md" "$PROFILE" "$PATCH" <<'PY'
from pathlib import Path
import sys

tmpl, main_md, profile, dest = map(Path, sys.argv[1:5])
persona = "\n".join(("      " + line) if line else "      " for line in main_md.read_text(encoding="utf-8").splitlines())
text = tmpl.read_text(encoding="utf-8")
text = text.replace("__MAIN_PERSONA__", persona)
text = text.replace("__PROFILE_ROOT__", str(profile))
text = text.replace("__PLUGIN_TS__", str(profile / "src" / "plugin.ts"))
dest.write_text(text, encoding="utf-8")
PY

if ! curl -sf "$BACKEND/api/health" >/dev/null; then
  echo "启动 skill 后端 $BACKEND ..."
  (cd "$ROOT/backend" && "$PY" -m uvicorn solution_gen.gateway.app:app --host 127.0.0.1 --port 8002) &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -sf "$BACKEND/api/health" >/dev/null && break
    sleep 0.5
  done
fi

export SOLUTION_BACKEND_URL="$BACKEND"
echo "前端: http://127.0.0.1:3080  （唯一页面，workspace: ${ROOT}）"
echo "skill 后端: ${BACKEND}"
exec npx --yes "$DSH_PKG" web --patch "$PATCH" "$@"
