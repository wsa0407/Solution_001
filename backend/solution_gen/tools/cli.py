from __future__ import annotations

import argparse
import asyncio
import json
import sys

from solution_gen.tools.dispatch import ACTIONS, dispatch


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m solution_gen.tools",
        description="方案生产 skill 工具。硬门在本进程，没有 skip-qa。",
    )
    parser.add_argument("action", help="工具名")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--doc-type", default="")
    parser.add_argument("--owner", default="dsh")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--place", default="")
    parser.add_argument("--construction-unit", default="")
    parser.add_argument("--budget", default="")
    parser.add_argument("--construction-period", default="")
    parser.add_argument("--industry", default="")
    parser.add_argument("--need", default="")
    parser.add_argument("--kind", default="")
    parser.add_argument("--placement", default="")
    parser.add_argument("--reference", default="")
    parser.add_argument("--chapter-id", default="")
    parser.add_argument("--instruction", default="")
    parser.add_argument("--material-title", default="")
    parser.add_argument("--op", default="")
    parser.add_argument("--json", default="", help="原始 JSON 载荷，覆盖其余参数")
    return parser


def _payload(ns: argparse.Namespace) -> dict:
    if ns.json:
        data = json.loads(ns.json)
        if not isinstance(data, dict):
            raise ValueError("--json 必须是对象")
        return data
    body = {
        "job_id": ns.job_id,
        "text": ns.text,
        "doc_type": ns.doc_type or None,
        "owner": ns.owner,
        "project_name": ns.project_name or None,
        "place": ns.place or None,
        "construction_unit": ns.construction_unit or None,
        "industry": ns.industry or None,
        "need": ns.need or None,
        "kind": ns.kind,
        "placement": ns.placement,
        "reference": ns.reference,
        "chapter_id": ns.chapter_id,
        "instruction": ns.instruction,
        "material_title": ns.material_title,
        "op": ns.op,
    }
    if ns.budget:
        body["budget"] = float(ns.budget)
    if ns.construction_period:
        body["construction_period"] = int(ns.construction_period)
    return {k: v for k, v in body.items() if v not in (None, "")}


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    ns = parser.parse_args(argv)
    try:
        payload = _payload(ns)
        result = asyncio.run(dispatch(ns.action, payload))
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        _parser().print_help()
        print("\n允许的 action:", ", ".join(sorted(ACTIONS)))
        print("没有 skip-qa。")
        raise SystemExit(0)
    raise SystemExit(main())
