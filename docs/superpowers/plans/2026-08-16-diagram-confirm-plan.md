# 出图确认 + diagram-design Implementation Plan

> **状态：已完成（2026-08-16）。** 下面勾选是当时的施工单，不要再按「未做」执行。现行行为以 [出图规格](../specs/2026-08-16-diagram-confirm-design.md) 为准。栅格为 cairosvg 优先、PyMuPDF 兜底。

**Goal:** 正文齐后先问要哪些图；每张图先出文字说明并经操作者确认，再用 diagram-design 画自包含 HTML，8002 抽 SVG 成 PNG 写入 Word。未确认不能画。

**Architecture:** 不改 `machine.py` 的 `TRANSITIONS`。`draft-diagram-spec` / `confirm-diagram-spec` / `attach-diagram` 都发生在 `DIAGRAM_ASK`。全部要的图 `drawn` 之后才 `emit-diagrams`（`DIAGRAM_SPEC_DONE` → 质检）。`skip-diagrams` 保留已画出的图。画图风格来自 `dsh-profile/skills/diagram-design/`（MIT 子集），不是 `charts.py` 色块 SVG。

**Tech Stack:** FastAPI skill 后端、`cairosvg`（优先）+ `pymupdf`（兜底）栅格、官方 `skill()` + `solution_skill`、pytest。仓库若尚无 `.git`，所有 Commit 步跳过。

**Spec:** [docs/superpowers/specs/2026-08-16-diagram-confirm-design.md](../specs/2026-08-16-diagram-confirm-design.md)

---

## File map

| 文件 | 职责 |
|---|---|
| `backend/solution_gen/domain.py` | `DiagramRequest.spec_text`；status：`selected` / `spec_pending` / `confirmed` / `drawn` |
| `backend/solution_gen/skills/svghtml.py` | 从 HTML 抽内联 SVG；拒绝外链 script |
| `backend/solution_gen/skills/raster.py` | SVG → `{chapter_id}.png`（cairosvg） |
| `backend/solution_gen/tools/diagram.py` | `draft_diagram_spec` / `confirm_diagram_spec` / `attach_diagram`；收紧 `emit` / `skip` |
| `backend/solution_gen/tools/dispatch.py` | 注册新 action |
| `backend/solution_gen/tools/result.py` | snapshot 带出图单 |
| `backend/solution_gen/service.py` | `skip_diagrams` 保留 drawn；`run_diagrams` 不再用色块 SVG 顶替未确认图 |
| `backend/solution_gen/chat/intent.py` + `service.py` | `DIAGRAM_ASK` 下「确认」确认图说明，不触发目录/终稿 |
| `dsh-profile/src/plugin.ts` | action 列表 + `html` 参数 |
| `dsh-profile/skills/emit-diagrams/SKILL.md` | 问图 → 说明 → 确认 → 再画 |
| `dsh-profile/skills/diagram-design/**` | 三种类型的画法说明书 |
| `dsh-profile/agents/proposal.md` + `feasibility.md` | 出图步骤与 emit-diagrams 对齐 |
| `backend/pyproject.toml` | `cairosvg` |
| `backend/tests/test_diagrams.py` | 硬门与顺序 |
| `backend/tests/test_skill_docs.py` | 新 skill 与禁止项 |
| `backend/tests/test_machine.py` | 不改边（已有用例，回归即可） |

不改：`backend/solution_gen/pipeline/machine.py`。

---

### Task 1: 出图单字段

**Files:**
- Modify: `backend/solution_gen/domain.py`
- Test: `backend/tests/test_diagrams.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_diagrams.py` 追加：

```python
from solution_gen.domain import DiagramKind, DiagramRequest


def test_diagram_request_has_spec_text_and_selected_status() -> None:
    req = DiagramRequest(kind=DiagramKind.ARCHITECTURE)
    assert req.spec_text == ""
    assert req.status == "selected"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_diagram_request_has_spec_text_and_selected_status -v
```

Expected: FAIL（`spec_text` 不存在，或默认 status 仍是 `draft`）

- [ ] **Step 3: Write minimal implementation**

`DiagramRequest` 改为：

```python
class DiagramRequest(BaseModel):
    kind: DiagramKind
    chapter_id: str = ""
    placement: str = ""
    reference: str = ""
    spec_text: str = ""
    status: str = "selected"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_diagram_request_has_spec_text_and_selected_status tests/test_machine.py -q
```

Expected: PASS（`TRANSITIONS` 回归也过）

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add backend/solution_gen/domain.py backend/tests/test_diagrams.py
git commit -m "feat: diagram request stores spec text and selected status"
```

---

### Task 2: HTML 抽 SVG 与禁脚本

**Files:**
- Create: `backend/solution_gen/skills/svghtml.py`
- Test: `backend/tests/test_svghtml.py`

- [ ] **Step 1: Write the failing test**

```python
from solution_gen.skills.svghtml import extract_inline_svg, HtmlDiagramError


def test_extract_first_svg() -> None:
    html = "<!doctype html><html><body><svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'><rect width='8' height='8'/></svg></body></html>"
    svg = extract_inline_svg(html)
    assert "<svg" in svg
    assert "rect" in svg


def test_reject_external_script() -> None:
    html = "<html><script src='https://evil.example/x.js'></script><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    try:
        extract_inline_svg(html)
        raise AssertionError("should reject")
    except HtmlDiagramError as exc:
        assert "脚本" in str(exc) or "script" in str(exc).lower()


def test_missing_svg_fails() -> None:
    try:
        extract_inline_svg("<html><body>no figure</body></html>")
        raise AssertionError("should reject")
    except HtmlDiagramError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_svghtml.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`backend/solution_gen/skills/svghtml.py`：

```python
from __future__ import annotations

import re

class HtmlDiagramError(ValueError):
    pass

_SVG = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)
_EXT_SCRIPT = re.compile(r"<script\b[^>]*\bsrc\s*=", re.IGNORECASE)

def extract_inline_svg(html: str) -> str:
    raw = html or ""
    if _EXT_SCRIPT.search(raw):
        raise HtmlDiagramError("禁止外链脚本。")
    m = _SVG.search(raw)
    if not m:
        raise HtmlDiagramError("HTML 里没有内联 SVG。")
    return m.group(0)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/python -m pytest tests/test_svghtml.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add backend/solution_gen/skills/svghtml.py backend/tests/test_svghtml.py
git commit -m "feat: extract inline svg and reject external scripts"
```

---

### Task 3: 未确认不能 attach / emit

**Files:**
- Modify: `backend/solution_gen/tools/diagram.py`
- Modify: `backend/solution_gen/tools/dispatch.py`
- Test: `backend/tests/test_diagrams.py`

- [ ] **Step 1: Write the failing tests**

用 Task 1 的 `_ask_job` 辅助函数，追加：

```python
import asyncio
from solution_gen.tools.dispatch import dispatch


def test_attach_without_confirm_fails() -> None:
    _, jid = _ask_job()
    asyncio.run(dispatch("request-diagram", {"job_id": jid, "kind": "architecture"}))
    result = asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": "<svg xmlns='http://www.w3.org/2000/svg'></svg>"}))
    assert result["ok"] is False
    assert "确认" in result["error"]


def test_emit_without_drawn_fails() -> None:
    _, jid = _ask_job()
    result = asyncio.run(dispatch("emit-diagrams", {"job_id": jid}))
    assert result["ok"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_attach_without_confirm_fails tests/test_diagrams.py::test_emit_without_drawn_fails -v
```

Expected: FAIL（`attach-diagram` 未知工具，或 emit 仍走旧「ready 即可画」）

- [ ] **Step 3: Write minimal implementation**

`request_diagram`：`status="selected"`（不要再设 `ready`）。无 placement 时仍 `resolve_chapter` 填默认章，但 status 保持 `selected`。

新增：

```python
def _req(job, kind: str):
    dk = DiagramKind(kind)
    return next((r for r in job.diagram_requests if r.kind is dk), None)

def confirm_diagram_spec(job_id: str, kind: str) -> dict:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("仅正文齐后可出图。", job)
    req = _req(job, kind)
    if req is None or not (req.spec_text or "").strip():
        return fail("请先生成文字说明。", job)
    req.status = "confirmed"
    save_job(job)
    return snapshot(job, replies=["说明已确认。请按 diagram-design 出 HTML 后 attach-diagram。"], next="attach_diagram")

def attach_diagram(job_id: str, kind: str, html: str = "") -> dict:
    job = _svc.get(job_id)
    if job.status is not JobStatus.DIAGRAM_ASK:
        return fail("仅正文齐后可出图。", job)
    req = _req(job, kind)
    if req is None or req.status != "confirmed":
        return fail("未确认说明，不能出图。", job)
    return fail("栅格未接好。", job)  # Task 4 接 PNG；本步先让未确认失败
```

`emit_diagrams`：若没有 `status=="drawn"` 的请求，`fail("还没有已出图。先确认说明并 attach-diagram，或 skip-diagrams。")`。不要再把 `ready` 当可画。

`dispatch.py` 的 `ACTIONS` 加入 `draft-diagram-spec`、`confirm-diagram-spec`、`attach-diagram`。`confirm` / `attach` 先接到上面两个函数。`draft-diagram-spec` 可先 `fail("未实现")`（Task 4 实现）。

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_attach_without_confirm_fails tests/test_diagrams.py::test_emit_without_drawn_fails -q
```

Expected: PASS

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add backend/solution_gen/tools/diagram.py backend/solution_gen/tools/dispatch.py backend/tests/test_diagrams.py
git commit -m "feat: reject diagram attach and emit before confirm"
```

---

### Task 4: 出说明、确认、attach 成 PNG

**Files:**
- Create: `backend/solution_gen/skills/raster.py`
- Modify: `backend/solution_gen/tools/diagram.py`
- Modify: `backend/pyproject.toml`（加 `cairosvg>=2.7.0`）
- Modify: `backend/solution_gen/tools/result.py`
- Test: `backend/tests/test_diagrams.py`

- [ ] **Step 1: Write the failing test**

```python
def test_draft_confirm_attach_stays_diagram_ask(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster
    from solution_gen.store import output_dir

    def fake_png(svg: str, dest: Path) -> None:
        dest.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
            b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    monkeypatch.setattr(raster, "svg_to_png", fake_png)
    _, jid = _ask_job()
    drafted = asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    assert drafted["ok"]
    assert drafted["status"] == "diagram_ask"
    reqs = drafted["diagram_requests"]
    assert reqs[0]["status"] == "spec_pending"
    assert reqs[0]["spec_text"]
    confirmed = asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    assert confirmed["ok"]
    html = "<html><body><svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'><rect width='8' height='8' fill='#000'/></svg></body></html>"
    attached = asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    assert attached["ok"]
    assert attached["status"] == "diagram_ask"
    assert attached["diagram_requests"][0]["status"] == "drawn"
    png = output_dir(jid) / "c4.png"
    assert png.exists()
```

`snapshot` 若还没有 `diagram_requests`，本测试会在 drafted 处失败。

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_draft_confirm_attach_stays_diagram_ask -v
```

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`raster.py`：

```python
from __future__ import annotations
from pathlib import Path

def svg_to_png(svg: str, dest: Path) -> None:
    import cairosvg
    dest.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(dest))
```

`draft_diagram_spec(job_id, kind, text="", placement="")`：
- 非 `DIAGRAM_ASK` 则 fail。
- 解析 `DiagramKind`。
- 找到或追加该 kind 的 `DiagramRequest`。
- `chapter_id = resolve_chapter(job, placement or text, dk)`。
- `spec_text`：若 `text` 非空且不是「按正文生成」，用操作者的 `text`；否则用「【图类型】挂在《章名》后。根据正文：{excerpt[:400]}」拼一段中文说明（无密钥也可工作；有密钥时可再 `complete()` 润色，失败则保留拼接稿）。
- `status = "spec_pending"`，`save_job`。
- `snapshot(..., replies=[spec_text], next="wait_confirm_diagram")`。

`attach_diagram`：`extract_inline_svg` → `svg_to_png(output_dir(job.id) / f"{req.chapter_id}.png")` → 写 `{chapter_id}-{kind}.html` → 章 `diagram=True`，正文追加 `【图 {id}】`（已有则不重复）→ `req.status="drawn"`。任务保持 `DIAGRAM_ASK`。

`result.snapshot` 增加：

```python
"diagram_requests": [
    {
        "kind": r.kind.value if hasattr(r.kind, "value") else str(r.kind),
        "status": r.status,
        "chapter_id": r.chapter_id,
        "placement": r.placement,
        "spec_text": r.spec_text,
    }
    for r in job.diagram_requests
],
```

`dispatch`：接通 `draft-diagram-spec` / `confirm-diagram-spec` / `attach-diagram`（`html` 从 body 取）。

安装：`cd backend && .venv/bin/pip install cairosvg`。

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_draft_confirm_attach_stays_diagram_ask tests/test_svghtml.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add backend/pyproject.toml backend/solution_gen/skills/raster.py backend/solution_gen/tools/diagram.py backend/solution_gen/tools/dispatch.py backend/solution_gen/tools/result.py backend/tests/test_diagrams.py
git commit -m "feat: draft confirm and attach diagrams without leaving diagram_ask"
```

---

### Task 5: 第二张图仍要说明；skip 保留已画；emit 收口

**Files:**
- Modify: `backend/solution_gen/tools/diagram.py`
- Modify: `backend/solution_gen/service.py`（`skip_diagrams`、`run_diagrams`）
- Test: `backend/tests/test_diagrams.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_second_kind_cannot_attach_before_its_confirm(monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster

    monkeypatch.setattr(raster, "svg_to_png", lambda svg, dest: Path(dest).write_bytes(b"PNG"))
    _, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    html = "<html><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    result = asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "gantt", "html": html}))
    assert result["ok"] is False


def test_skip_keeps_drawn(monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster
    from solution_gen.domain import JobStatus

    monkeypatch.setattr(raster, "svg_to_png", lambda svg, dest: Path(dest).write_bytes(b"PNG"))
    _, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    html = "<html><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    skipped = skip_diagrams(jid)
    assert skipped["ok"]
    job = skipped["job"] if "job" in skipped else None
    # snapshot 用 status 字符串
    assert skipped["status"] == "qa_running"
    assert any(r["status"] == "drawn" for r in skipped["diagram_requests"])


def test_emit_after_drawn_enters_qa(monkeypatch) -> None:
    from pathlib import Path
    from solution_gen.skills import raster

    monkeypatch.setattr(raster, "svg_to_png", lambda svg, dest: Path(dest).write_bytes(b"PNG"))
    _, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    asyncio.run(dispatch("confirm-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    html = "<html><svg xmlns='http://www.w3.org/2000/svg'></svg></html>"
    asyncio.run(dispatch("attach-diagram", {"job_id": jid, "kind": "architecture", "html": html}))
    emitted = asyncio.run(dispatch("emit-diagrams", {"job_id": jid}))
    assert emitted["ok"]
    assert emitted["status"] == "qa_running"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_second_kind_cannot_attach_before_its_confirm tests/test_diagrams.py::test_skip_keeps_drawn tests/test_diagrams.py::test_emit_after_drawn_enters_qa -v
```

Expected: FAIL（skip 仍清空 requests；emit 仍要 ready；run_diagrams 仍画色块）

- [ ] **Step 3: Write minimal implementation**

`skip_diagrams`（tools + `JobService.skip_diagrams`）：
- `apply(SKIP_DIAGRAMS)`。
- `job.diagram_requests = [r for r in job.diagram_requests if r.status == "drawn"]`。
- 未 drawn 的章：若该章没有 drawn 请求，则 `diagram=False` 并清 json。已 drawn 的章保留 PNG 与【图】。
- 不要 `job.diagram_requests = []` 无条件清空。

`emit_diagrams`：
- `drawn = [r for r in job.diagram_requests if r.status == "drawn"]`，否则 fail。
- `job.diagram_requests = drawn`；`begin_diagrams`；`run_diagrams`。

`run_diagrams`：若请求均为 `drawn`，不再调用 `charts.attach_image` / `enrich_spec`。只 `DIAGRAMS_DONE` 并进入 `run_qa`。禁止用色块 SVG 给未确认的 kind 出图。

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py tests/test_machine.py tests/test_svghtml.py -q
```

Expected: PASS。删除或改写旧用例 `test_full_spec_starts_diagrams`（「按正文生成」不得进 `DIAGRAM_RUNNING`）和 `test_architecture_request_writes_chapter_image`（不再用 `status=ready` + `run_diagrams` 色块）。`test_want_diagram_without_placement_stays_ask` 可保留：要架构图后仍是 `diagram_ask`。

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add backend/solution_gen/tools/diagram.py backend/solution_gen/service.py backend/tests/test_diagrams.py
git commit -m "feat: keep drawn diagrams on skip and emit only after attach"
```

---

### Task 6: handle_chat 的「确认」只确认图说明

**Files:**
- Modify: `backend/solution_gen/chat/intent.py`
- Modify: `backend/solution_gen/chat/service.py`
- Test: `backend/tests/test_diagrams.py`

- [ ] **Step 1: Write the failing test**

```python
def test_chat_confirm_confirms_diagram_spec_not_deliver() -> None:
    svc, jid = _ask_job()
    asyncio.run(dispatch("draft-diagram-spec", {"job_id": jid, "kind": "architecture"}))
    result = asyncio.run(handle_chat(svc, jid, "确认"))
    assert result["job"].status is JobStatus.DIAGRAM_ASK
    assert result["job"].diagram_requests[0].status == "confirmed"
    assert result.get("start_diagrams") is not True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_chat_confirm_confirms_diagram_spec_not_deliver -v
```

Expected: FAIL（`pending` 为空时「确认」不是 CONFIRM，或 `_do_confirm` 说现在不能确认）

- [ ] **Step 3: Write minimal implementation**

`classify`：在现有 `pending and t in _CONFIRM_EXACT` 之外，若 `status is DIAGRAM_ASK` 且 `t in _CONFIRM_EXACT`，返回 `Intent.CONFIRM`。

`_do_confirm` 开头：若 `job.status is JobStatus.DIAGRAM_ASK`，找 `status=="spec_pending"` 的请求，调用 `confirm_diagram_spec`，把 `replies` 转成 `_reply`；**不要** `deliver`，不要 `start_generation`。

`_diagram_talk`：`Intent.WANT_DIAGRAM` 时对每个 kind 调 `draft_diagram_spec`（不要再走「按这些出图」进 `begin_diagrams`）。`wants_emit` 若无 drawn，回复「请先确认说明并出图」，`start_diagrams=False`。

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py tests/test_chat_gates.py -q
```

Expected: PASS（目录确认用例不受影响：那些不在 `DIAGRAM_ASK`）

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add backend/solution_gen/chat/intent.py backend/solution_gen/chat/service.py backend/tests/test_diagrams.py
git commit -m "feat: confirm during diagram_ask accepts the figure spec"
```

---

### Task 7: plugin 与 skill 说明书

**Files:**
- Modify: `dsh-profile/src/plugin.ts`
- Modify: `dsh-profile/skills/emit-diagrams/SKILL.md`
- Create: `dsh-profile/skills/diagram-design/SKILL.md`
- Create: `dsh-profile/skills/diagram-design/NOTICE`
- Create: `dsh-profile/skills/diagram-design/references/style-guide.md`（从上游拷）
- Create: type 参考三份（从上游拷）
- Modify: `dsh-profile/agents/proposal.md`、`feasibility.md`
- Test: `backend/tests/test_skill_docs.py`

- [ ] **Step 1: Write the failing assertions**

`test_skill_docs.py`：
- `test_five_skills...` 改名为技能清单测试，额外断言存在 `diagram-design/SKILL.md`，且 `name: diagram-design`。
- `emit-diagrams` 正文含 `draft-diagram-spec`、`confirm-diagram-spec`、`attach-diagram`，且含「确认」。
- `proposal.md` / `feasibility.md` 含 `diagram-design` 或「文字说明」。
- `plugin.ts` 的 ACTIONS 字符串含 `draft-diagram-spec` 与 `attach-diagram`。
- `diagram-design` 的 SKILL 不得出现 `skip-qa` 作为可用工具；可出现「不要 skip-qa」。
- `diagram-design/NOTICE` 含 `cathrynlavery/diagram-design`。

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && .venv/bin/python -m pytest tests/test_skill_docs.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the files**

`plugin.ts`：`ACTIONS` 追加 `draft-diagram-spec, confirm-diagram-spec, attach-diagram`。parameters 增加 `html: { type: 'string', description: 'attach-diagram 的自包含 HTML' }`。

`emit-diagrams/SKILL.md` 按 spec 第 3 节重写：先问要哪些图（建议框架图+甘特）；都不要 → `skip-diagrams`；否则对每种：`draft-diagram-spec` → 等人确认 → `confirm-diagram-spec` → `skill("diagram-design")` 画 HTML → `attach-diagram`；全部 drawn 或剩余不要 → `emit-diagrams` 或 `skip-diagrams` → `polish-deliver`。禁止未确认 attach。禁止 bash。

`diagram-design`：从 https://github.com/cathrynlavery/diagram-design 拉 MIT 子集（`curl` raw）：
- `skills/diagram-design/references/style-guide.md`
- `references/type-architecture.md`
- `references/type-flowchart.md`
- `references/type-gantt.md`（若 404，则自写一页甘特约束：时间轴、任务条、4px 网格、一色强调，并在 NOTICE 说明为本地摘要）

本地 `SKILL.md` 只路由三种类型：读 `style-guide.md` + 对应 type 参考；按已确认 `spec_text` 画**一个**自包含 HTML（内联 SVG、无外链 script、无阴影）；交给 `attach-diagram`。禁止四层信息化套话。禁止 skip-qa。

`NOTICE`：

```
Diagram style adapted from https://github.com/cathrynlavery/diagram-design (MIT).
```

`proposal.md` 第 4 步改为与 emit-diagrams 相同的确认后再画；`feasibility.md` 同步。

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_skill_docs.py tests/test_skill_tools.py::test_skip_qa_is_not_a_tool -q
```

Expected: PASS

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add dsh-profile backend/tests/test_skill_docs.py
git commit -m "docs: emit-diagrams confirm gate and diagram-design subset"
```

---

### Task 8: Word 插入 PNG + 全量回归

**Files:**
- Test: `backend/tests/test_prose.py` 或 `backend/tests/test_diagrams.py`
- Modify: 仅当 `export_docx` 已有 PNG 分支时补测试（`document.py` 已按 `{chapter_id}.png` 插图）

- [ ] **Step 1: Write the failing test**

```python
def test_export_docx_embeds_png(tmp_path, monkeypatch) -> None:
    from docx import Document
    from solution_gen.domain import Chapter, DocType, Job, JobStatus, Profile
    from solution_gen.skills.document import export_docx
    from solution_gen.store import output_dir

    job = Job(
        id="jpng",
        doc_type=DocType.SOLUTION,
        status=JobStatus.DELIVERED,
        profile=Profile(place="乐山市", industry="低空经济", project_name="乐山项目"),
        chapters=[Chapter(id="c4", title="项目建设方案", content="建设方案正文。乐山市建设内容。", diagram=True)],
    )
    png = output_dir(job.id) / "c4.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    out = tmp_path / "out.docx"
    export_docx(job, out)
    doc = Document(str(out))
    assert any(p._element.xpath(".//*[local-name()='drawing']") for p in doc.paragraphs)
```

若 `output_dir("jpng")` 不在 tmp，测试仍有效（写真实 data/outputs）。能的话 monkeypatch `output_dir` 到 `tmp_path`。

- [ ] **Step 2: Run test**

```bash
cd backend && .venv/bin/python -m pytest tests/test_diagrams.py::test_export_docx_embeds_png -v
```

Expected: 若 `export_docx` 已插图则 PASS；否则 FAIL 后再改 `document.py`（已有 `add_picture` 则本步只加测试）。

- [ ] **Step 3: Full regression**

```bash
cd backend && .venv/bin/python -m pytest tests -q
```

Expected: 全部 PASS。不得改 `machine.py`。`tests/test_machine.py::test_diagram_spec_then_qa` 仍过。

- [ ] **Step 4: 手测清单（不写代码）**

重启 8002 后：`./scripts/dsh-web.sh`，3080 选本仓库。写到出图门时：先问要哪些图 → 架构说明 → 回复确认 → 再出图 → Word 章内有 PNG。

- [ ] **Step 5: Commit**（无 `.git` 则跳过）

```bash
git add backend/tests
git commit -m "test: word embed png after confirmed diagram attach"
```

---

## Self-review

| Spec 条款 | 任务 |
|---|---|
| 先问要哪些图；默认只是建议 | Task 7 emit-diagrams SKILL |
| 说明 → 确认 → 再画；一张走完再下一张 | Task 4–5 |
| 8002 拒绝未确认出图 | Task 3 |
| diagram-design 子集 + NOTICE | Task 7 |
| 不改 TRANSITIONS；说明/attach 留在 DIAGRAM_ASK | Task 1、4、5；Task 8 回归 machine |
| skip 保留已画；不是 skip-qa | Task 5；skill-tools 已有 skip-qa 测 |
| HTML 内联 SVG、禁外链 script、cairosvg PNG、Word 插图 | Task 2、4、8 |
| plugin / agents 同步 | Task 7 |
| handle_chat「确认」不误伤终稿 | Task 6 |
| 不 fork harness | 无任务动 harness |
