# 知识库双通道召回 + 写前政策确认 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 历史文档按文类/属地/方向过滤后进入写章提示词；地区政策仍只许同属地历史 + 地方库 + 已确认的 DeepSeek 检索。未确认方向不能 `write-chapters`。

**Architecture:** 不改 `machine.py` 的 `TRANSITIONS`。RAGFlow 只当可选 HTTP 检索；测试用 `set_history_provider`，无 Key 时历史库为空、JSON 三库照旧。写章提示词按章过滤 `citations`（通道 A / B）。政策确认停在 `OUTLINE_CONFIRM`：`draft-locale-brief` → 人改/重搜 → `confirm-locale-brief` → `write-chapters`。

**Tech Stack:** 现有 FastAPI 8002、httpx、pytest。不新增向量库依赖。仓库若无 `.git`，所有 Commit 步跳过。

**Spec:** [docs/superpowers/specs/2026-08-17-knowledge-base-design.md](../specs/2026-08-17-knowledge-base-design.md)

本计划两部分可顺序交付：Part A 召回硬门（无 RAGFlow 也能测）；Part B 写前确认。不要先做全量 10G 入库脚本。

---

## File map

| 文件 | 职责 |
|---|---|
| `backend/solution_gen/domain.py` | `Citation.place` / `chunk_role`；`Job.locale_brief` / `locale_brief_status` |
| `backend/solution_gen/knowledge.py` | 方向、阶段资格、chunk_role、双通道过滤（纯函数） |
| `backend/solution_gen/ragflow.py` | 可选 HTTP 客户端；解析 chunk → `HistoryChunk` |
| `backend/solution_gen/rag.py` | JSON 三库不变；`fill_history` 合并历史库 citations |
| `backend/solution_gen/config.py` | `RAGFLOW_BASE_URL` / `RAGFLOW_API_KEY` / `RAGFLOW_DATASET_IDS` |
| `backend/solution_gen/workers/chapter.py` | `citations_for_chapter`；写章前 `fill_history` |
| `backend/solution_gen/locale_search.py` | `force` 重搜；`locale_brief_text` 综述模板 |
| `backend/solution_gen/qa/engine.py` | `KB-01` / `KB-02` |
| `backend/solution_gen/tools/locale.py` | `draft-locale-brief` / `confirm-locale-brief` |
| `backend/solution_gen/tools/chapter.py` | 未确认则拒绝写正文 |
| `backend/solution_gen/tools/dispatch.py` | 注册两个 action |
| `backend/solution_gen/tools/result.py` | snapshot 带 `locale_brief` |
| `dsh-profile/src/plugin.ts` | action 列表 |
| `dsh-profile/skills/write-chapters/SKILL.md` | 先综述确认再写 |
| `dsh-profile/agents/proposal.md` + `feasibility.md` | 同上 |
| `backend/tests/conftest.py` | autouse 空历史提供方 |
| `backend/tests/test_knowledge.py` | 双通道过滤 |
| `backend/tests/test_locale_brief.py` | 写前确认硬门 |
| `backend/tests/test_qa_gates.py` | KB-01/KB-02 |
| `backend/tests/test_skill_docs.py` | skill 含新 action |

不改：`backend/solution_gen/pipeline/machine.py`。

---

## Part A — 历史库召回

### Task 1: Citation 字段与纯过滤

**Files:**
- Modify: `backend/solution_gen/domain.py`
- Create: `backend/solution_gen/knowledge.py`
- Test: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_knowledge.py`：

```python
from solution_gen.domain import Citation, DocType, Profile
from solution_gen.knowledge import (
    HistoryChunk,
    filter_history,
    infer_chunk_role,
    profile_direction,
)


def test_direction_public_security() -> None:
    assert profile_direction("低空公安警务") == "low_altitude_public_security"
    assert profile_direction("低空经济") == "low_altitude_economy"


def test_infer_locale_role() -> None:
    assert infer_chunk_role("建设背景", "依据本市发展规划") == "locale"
    assert infer_chunk_role("建设方案", "起降点与通信网络") == "scheme"


def test_qingdao_proposal_drops_dengfeng_locale_keeps_scheme() -> None:
    profile = Profile(place="青岛市", industry="低空经济")
    chunks = [
        HistoryChunk(
            title="登封市低空经济发展规划摘录",
            excerpt="登封市建设起降点。",
            place="登封市",
            doc_type="solution",
            direction="low_altitude_economy",
            stage="proposal",
            chunk_role="locale",
        ),
        HistoryChunk(
            title="登封建议书建设方案模块写法",
            excerpt="通信网络与起降点分列。",
            place="登封市",
            doc_type="solution",
            direction="low_altitude_economy",
            stage="proposal",
            chunk_role="scheme",
        ),
        HistoryChunk(
            title="登封市可研经济评价",
            excerpt="IRR 12%。",
            place="登封市",
            doc_type="feasibility",
            direction="low_altitude_economy",
            stage="feasibility",
            chunk_role="investment",
        ),
        HistoryChunk(
            title="初设总图说明",
            excerpt="初设图纸。",
            place="青岛市",
            doc_type="solution",
            direction="low_altitude_economy",
            stage="preliminary_design",
            chunk_role="scheme",
        ),
    ]
    locale = filter_history(chunks, profile, DocType.SOLUTION, channel="locale")
    scheme = filter_history(chunks, profile, DocType.SOLUTION, channel="scheme")
    assert locale == []
    assert [c.title for c in scheme] == ["登封建议书建设方案模块写法"]
    assert all(isinstance(c, Citation) and c.library == "历史库" for c in scheme)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge.py -v
```

Expected: FAIL（`solution_gen.knowledge` 不存在）

- [ ] **Step 3: Write minimal implementation**

`Citation` 增加默认字段（旧任务 JSON 仍能加载）：

```python
class Citation(BaseModel):
    library: str
    title: str
    why: str
    excerpt: str = ""
    url: str = ""
    place: str = ""
    chunk_role: str = ""
```

新建 `backend/solution_gen/knowledge.py`：

```python
from __future__ import annotations

from dataclasses import dataclass

from solution_gen.domain import Citation, DocType, Profile
from solution_gen.rag import place_key

WRITABLE_STAGES = frozenset({"initiation", "proposal", "feasibility"})
LOCALE_HINTS = ("政策", "规划", "编制依据", "市情", "区位", "概述", "背景", "立项依据")
INVEST_HINTS = ("投资", "估算", "经济评价", "IRR", "NPV")
SCHEME_HINTS = ("建设方案", "建设内容", "模块", "设施", "系统")


@dataclass(frozen=True)
class HistoryChunk:
    title: str
    excerpt: str = ""
    place: str = ""
    doc_type: str = ""
    direction: str = ""
    stage: str = ""
    chunk_role: str = ""
    url: str = ""


def profile_direction(industry: str) -> str:
    text = industry or ""
    if any(k in text for k in ("公安", "警务", "巡检")):
        return "low_altitude_public_security"
    return "low_altitude_economy"


def infer_chunk_role(title: str, text: str) -> str:
    blob = f"{title} {text}"
    if any(k in blob for k in LOCALE_HINTS):
        return "locale"
    if any(k in blob for k in INVEST_HINTS):
        return "investment"
    if any(k in blob for k in SCHEME_HINTS):
        return "scheme"
    return "other"


def _same_place(hit_place: str, profile_place: str) -> bool:
    if not hit_place or not profile_place:
        return False
    if profile_place in hit_place or hit_place in profile_place:
        return True
    pk = place_key(profile_place)
    return bool(pk) and pk in hit_place


def _eligible(chunk: HistoryChunk, profile: Profile, doc_type: DocType) -> bool:
    if chunk.stage not in WRITABLE_STAGES:
        return False
    if (chunk.doc_type or "") != doc_type.value:
        return False
    if not chunk.place:
        return False
    want = profile_direction(profile.industry)
    if (chunk.direction or "unknown") != want:
        return False
    return True


def filter_history(
    chunks: list[HistoryChunk],
    profile: Profile,
    doc_type: DocType,
    *,
    channel: str,
) -> list[Citation]:
    out: list[Citation] = []
    seen: set[str] = set()
    for chunk in chunks:
        if not _eligible(chunk, profile, doc_type):
            continue
        role = chunk.chunk_role or infer_chunk_role(chunk.title, chunk.excerpt)
        if channel == "locale":
            if role != "locale" or not _same_place(chunk.place, profile.place):
                continue
        elif channel == "scheme":
            if role == "locale":
                continue
        else:
            continue
        if chunk.title in seen:
            continue
        seen.add(chunk.title)
        out.append(
            Citation(
                library="历史库",
                title=chunk.title,
                why=channel,
                excerpt=(chunk.excerpt or "")[:240],
                url=chunk.url,
                place=chunk.place,
                chunk_role=role,
            )
        )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

仓库无 `.git` 或用户未要求提交则跳过。

---

### Task 2: 按章挑选 citations

**Files:**
- Modify: `backend/solution_gen/workers/chapter.py`
- Modify: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write the failing test**

追加到 `tests/test_knowledge.py`：

```python
from solution_gen.domain import Chapter, Job
from solution_gen.locale_search import needs_locale_policy
from solution_gen.workers.chapter import citations_for_chapter


def test_scheme_chapter_hides_foreign_locale_history() -> None:
    job = Job(
        id="k1",
        doc_type=DocType.SOLUTION,
        profile=Profile(place="青岛市", industry="低空经济"),
        chapters=[
            Chapter(id="c2", title="项目建设背景及必要性", writing="background"),
            Chapter(id="c4", title="项目建设方案", writing="scheme"),
        ],
        citations=[
            Citation(library="产品库", title="白皮书", why="x", excerpt="参数"),
            Citation(
                library="历史库",
                title="登封市低空经济发展规划摘录",
                why="locale",
                excerpt="登封",
                place="登封市",
                chunk_role="locale",
            ),
            Citation(
                library="历史库",
                title="登封建议书建设方案模块写法",
                why="scheme",
                excerpt="模块",
                place="登封市",
                chunk_role="scheme",
            ),
        ],
    )
    bg = citations_for_chapter(job, job.chapters[0])
    sch = citations_for_chapter(job, job.chapters[1])
    assert needs_locale_policy(job.chapters[0])
    assert "登封市低空经济发展规划摘录" not in [c.title for c in bg]
    assert "登封建议书建设方案模块写法" in [c.title for c in sch]
    assert "登封市低空经济发展规划摘录" not in [c.title for c in sch]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge.py::test_scheme_chapter_hides_foreign_locale_history -v
```

Expected: FAIL（`citations_for_chapter` 未定义）

- [ ] **Step 3: Write minimal implementation**

在 `workers/chapter.py` 增加并改 `build_chapter_prompt` 的摘录行：

```python
from solution_gen.locale_search import fill_locale_search, locale_prompt_block, needs_locale_policy


def citations_for_chapter(job: Job, chapter: Chapter) -> list[Citation]:
    selected: list[Citation] = []
    locale_ch = needs_locale_policy(chapter)
    for c in job.citations:
        if c.library == "历史库" and c.chunk_role == "locale":
            if locale_ch and c.place and job.profile and (
                job.profile.place in c.place or c.place in job.profile.place
            ):
                selected.append(c)
            continue
        if c.library == "历史库" and c.chunk_role != "locale":
            if not locale_ch:
                selected.append(c)
            continue
        if c.library == "检索":
            if locale_ch:
                selected.append(c)
            continue
        selected.append(c)
    return selected
```

`build_chapter_prompt` 里把 `job.citations[:8]` 换成 `citations_for_chapter(job, chapter)[:8]`。

`locale_prompt_block`（`locale_search.py`）在地方库/检索之外追加：

```python
hist = [
    c for c in job.citations
    if c.library == "历史库" and c.chunk_role == "locale"
]
```

并入 `lib + web + hist` 列表（仍最多 8 条）。外地 locale 历史不应出现在 `job.citations`（Task 3 过滤）；此处再挡一层。

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge.py tests/test_locale_search.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 3: 可 mock 的历史提供方 + fill_history

**Files:**
- Modify: `backend/solution_gen/rag.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write the failing test**

```python
from solution_gen.rag import fill_history, set_history_provider


def test_fill_history_appends_filtered_chunks() -> None:
    set_history_provider(
        lambda _profile, _doc_type: [
            HistoryChunk(
                title="青岛市低空经济实施方案摘录",
                excerpt="青岛市加快低空基建。",
                place="青岛市",
                doc_type="solution",
                direction="low_altitude_economy",
                stage="proposal",
                chunk_role="locale",
            )
        ]
    )
    job = Job(
        id="k2",
        doc_type=DocType.SOLUTION,
        profile=Profile(place="青岛市", industry="低空经济"),
        chapters=[Chapter(id="c2", title="项目建设背景及必要性", writing="background")],
    )
    hits = fill_history(job)
    assert any(c.title == "青岛市低空经济实施方案摘录" and c.library == "历史库" for c in hits)
    assert any(c.library == "历史库" for c in job.citations)
```

另加：`test_missing_metadata_not_recalled`（无 `place` 或 `stage=tender` 的 chunk 不进 `job.citations`）。

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL（`fill_history` 未定义）

- [ ] **Step 3: Write minimal implementation**

`rag.py` 增加：

```python
from collections.abc import Callable
from solution_gen.domain import Job
from solution_gen.knowledge import HistoryChunk, filter_history

HistoryFn = Callable[[Profile, str], list[HistoryChunk]]
_history_provider: HistoryFn | None = None


def set_history_provider(fn: HistoryFn | None) -> None:
    global _history_provider
    _history_provider = fn


def fill_history(job: Job) -> list[Citation]:
    if not job.profile:
        return []
    chunks: list[HistoryChunk] = []
    if _history_provider is not None:
        chunks = list(_history_provider(job.profile, job.doc_type.value))
    else:
        chunks = []  # Task 4 再接 RAGFlow；无 mock 时历史库为空，JSON 三库不受影响
    locale = filter_history(chunks, job.profile, job.doc_type, channel="locale")
    scheme = filter_history(chunks, job.profile, job.doc_type, channel="scheme")
    merged = locale + scheme
    existing = {c.title for c in job.citations}
    added: list[Citation] = []
    for hit in merged:
        if hit.title in existing:
            continue
        job.citations.append(hit)
        existing.add(hit.title)
        added.append(hit)
    return added
```

`conftest.py` autouse 同时静音网页检索和历史库：

```python
from solution_gen.locale_search import set_search_provider
from solution_gen.rag import set_history_provider


@pytest.fixture(autouse=True)
def _silence_external_recall():
    set_search_provider(lambda _query: [])
    set_history_provider(lambda _profile, _doc_type: [])
    yield
    set_search_provider(None)
    set_history_provider(None)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge.py tests/test_locale_search.py tests/test_qa_gates.py -q
```

Expected: PASS（成都地方库过滤用例仍只看 JSON）

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 4: RAGFlow 客户端（无网可测）

**Files:**
- Create: `backend/solution_gen/ragflow.py`
- Modify: `backend/solution_gen/config.py`
- Modify: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write the failing test**

```python
from solution_gen.ragflow import fetch_history_chunks, hits_from_ragflow_response


def test_parse_ragflow_chunks() -> None:
    data = {
        "code": 0,
        "data": {
            "chunks": [
                {
                    "content": "青岛市加快低空基建。",
                    "document_keyword": "青岛市低空经济实施方案",
                    "metadata": {
                        "place": "青岛市",
                        "doc_type": "solution",
                        "direction": "low_altitude_economy",
                        "stage": "proposal",
                        "chunk_role": "locale",
                    },
                }
            ]
        },
    }
    hits = hits_from_ragflow_response(data)
    assert hits[0].title == "青岛市低空经济实施方案"
    assert hits[0].place == "青岛市"


def test_no_ragflow_key_returns_empty(monkeypatch) -> None:
    from solution_gen.config import settings
    from solution_gen.rag import set_history_provider

    set_history_provider(None)
    monkeypatch.setattr(settings, "ragflow_api_key", "")
    monkeypatch.setattr(settings, "ragflow_base_url", "")
    assert fetch_history_chunks(Profile(place="青岛市", industry="低空经济"), "solution") == []
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`config.py` 的 `Settings` 增加：

```python
ragflow_base_url: str = Field(default_factory=lambda: os.environ.get("RAGFLOW_BASE_URL", ""))
ragflow_api_key: str = Field(default_factory=lambda: os.environ.get("RAGFLOW_API_KEY", ""))
ragflow_dataset_ids: str = Field(default_factory=lambda: os.environ.get("RAGFLOW_DATASET_IDS", ""))
```

`ragflow.py`：

```python
from __future__ import annotations

import os
from typing import Any

import httpx

from solution_gen.config import settings
from solution_gen.domain import Profile
from solution_gen.knowledge import HistoryChunk, infer_chunk_role, profile_direction


def hits_from_ragflow_response(data: dict[str, Any]) -> list[HistoryChunk]:
    rows = (data.get("data") or {}).get("chunks") or data.get("chunks") or []
    hits: list[HistoryChunk] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        title = str(meta.get("title") or row.get("document_keyword") or row.get("docnm_kwd") or "").strip()
        excerpt = str(row.get("content") or "")[:240]
        if not title:
            continue
        role = str(meta.get("chunk_role") or "") or infer_chunk_role(title, excerpt)
        hits.append(
            HistoryChunk(
                title=title,
                excerpt=excerpt,
                place=str(meta.get("place") or ""),
                doc_type=str(meta.get("doc_type") or ""),
                direction=str(meta.get("direction") or ""),
                stage=str(meta.get("stage") or ""),
                chunk_role=role,
                url=str(row.get("url") or meta.get("url") or ""),
            )
        )
    return hits


def fetch_history_chunks(profile: Profile, doc_type: str) -> list[HistoryChunk]:
    key = (settings.ragflow_api_key or "").strip()
    base = (settings.ragflow_base_url or os.environ.get("RAGFLOW_BASE_URL") or "").rstrip("/")
    if not key or not base:
        return []
    dataset_ids = [x.strip() for x in (settings.ragflow_dataset_ids or "").split(",") if x.strip()]
    payload: dict[str, Any] = {
        "question": f"{profile.place} {profile.industry} {profile.need or ''} {doc_type}",
        "page": 1,
        "size": 12,
        "similarity_threshold": 0.1,
    }
    if dataset_ids:
        payload["dataset_ids"] = dataset_ids
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(base + "/api/v1/retrieval", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
    except Exception:
        return []
    return hits_from_ragflow_response(data if isinstance(data, dict) else {})
```

`rag.py` 的 `fill_history`：`_history_provider is None` 时改为调用 `fetch_history_chunks(job.profile, job.doc_type.value)`。测试 autouse 仍注入空 provider，不会打网。

测试禁止真实打 RAGFlow。

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 5: 写章时注入历史库

**Files:**
- Modify: `backend/solution_gen/workers/chapter.py`
- Modify: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio
from solution_gen.domain import JobStatus
from solution_gen.workers.chapter import generate_chapters


def test_generate_chapters_injects_scheme_history_not_foreign_locale() -> None:
    set_history_provider(
        lambda _p, _d: [
            HistoryChunk(
                title="登封市低空经济发展规划摘录",
                excerpt="登封市政策。",
                place="登封市",
                doc_type="solution",
                direction="low_altitude_economy",
                stage="proposal",
                chunk_role="locale",
            ),
            HistoryChunk(
                title="登封建议书建设方案模块写法",
                excerpt="模块分列。",
                place="登封市",
                doc_type="solution",
                direction="low_altitude_economy",
                stage="proposal",
                chunk_role="scheme",
            ),
        ]
    )
    seen: list[str] = []

    async def writer(prompt: str, ch):
        seen.append(prompt)
        return "青岛市项目建设方案如下。建设内容对应需求。" * 20

    ch = Chapter(id="c4", title="项目建设方案", writing="scheme", words=400, brief="模块")
    job = Job(
        id="k3",
        doc_type=DocType.SOLUTION,
        status=JobStatus.GENERATING,
        profile=Profile(place="青岛市", industry="低空经济", budget=1, construction_period=12),
        chapters=[ch],
    )
    asyncio.run(generate_chapters(job, writer))
    assert seen
    assert "登封建议书建设方案模块写法" in seen[0]
    assert "登封市低空经济发展规划摘录" not in seen[0]
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL（提示词无历史库标题）

- [ ] **Step 3: Write minimal implementation**

`generate_chapters` 在 `fill_locale_search(job)` 之后调用 `fill_history(job)`。

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge.py tests/test_locale_search.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 6: KB-01 / KB-02

**Files:**
- Modify: `backend/solution_gen/qa/engine.py`
- Modify: `backend/tests/test_qa_gates.py`

- [ ] **Step 1: Write the failing tests**

```python
from solution_gen.domain import Citation, DocType, Job, JobStatus, Chapter, Profile
from solution_gen.qa.engine import run_qa


def test_kb01_flags_foreign_history_title_in_locale_chapter() -> None:
    pad = "建设内容。" * 80
    job = Job(
        id="kb1",
        doc_type=DocType.SOLUTION,
        status=JobStatus.QA_RUNNING,
        profile=Profile(place="青岛市", industry="低空经济", budget=4000, construction_period=35),
        citations=[
            Citation(
                library="历史库",
                title="登封市低空经济发展规划摘录",
                why="locale",
                excerpt="登封",
                place="登封市",
                chunk_role="locale",
            )
        ],
        chapters=[
            Chapter(
                id="c2",
                title="项目建设背景及必要性",
                writing="background",
                content="依据登封市低空经济发展规划摘录推进青岛低空。" + pad,
            )
        ],
    )
    assert "KB-01" in {i.code for i in run_qa(job)}


def test_kb02_flags_irr_in_proposal() -> None:
    pad = "建设内容。" * 80
    job = Job(
        id="kb2",
        doc_type=DocType.SOLUTION,
        status=JobStatus.QA_RUNNING,
        profile=Profile(place="青岛市", industry="低空经济", budget=4000, construction_period=35),
        chapters=[
            Chapter(
                id="c8",
                title="项目投融资与财务方案",
                writing="investment",
                content="本项目 IRR 为 12%，NPV 为正。" + pad,
            )
        ],
    )
    assert "KB-02" in {i.code for i in run_qa(job)}
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL（无 KB-01/KB-02）

- [ ] **Step 3: Write minimal implementation**

`HARD_CHECKS` 追加 `"knowledge_bounds"`。`run_qa` 调用 `_knowledge_bounds`：

```python
_IRR = re.compile(r"\bIRR\b|内部收益率|NPV|净现值")


def _knowledge_bounds(job: Job) -> list[QaIssue]:
    issues: list[QaIssue] = []
    place = (job.profile.place if job.profile else "") or ""
    for ch in job.chapters:
        text = ch.content or ""
        if not text.strip():
            continue
        if needs_locale_policy(ch):
            for c in job.citations:
                if c.library != "历史库" or not c.title:
                    continue
                if c.title not in text and c.title.replace("摘录", "") not in text:
                    continue
                foreign = c.chunk_role == "locale" and c.place and place and c.place not in place and place not in c.place
                if foreign:
                    issues.append(
                        QaIssue(
                            code="KB-01",
                            dimension="历史库属地隔离",
                            chapter_id=ch.id,
                            detail=f"章节「{ch.title}」引用外地历史「{c.title}」。",
                        )
                    )
        if job.doc_type.value == "solution" and _IRR.search(text):
            issues.append(
                QaIssue(
                    code="KB-02",
                    dimension="文类深度不串",
                    chapter_id=ch.id,
                    detail=f"建议书章节「{ch.title}」出现可研级 IRR/NPV。",
                )
            )
    return issues
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_qa_gates.py tests/test_knowledge.py -q
```

Expected: PASS。若 `test_qa_pass_when_content_grounded` 被 IRR 误伤，收窄为同时出现 `IRR`/`NPV`/`内部收益率` 且当前文类为建议书（上式已满足；grounded 用例正文无 IRR）。

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 7: Skill 禁止 3080 直连知识库

**Files:**
- Modify: `dsh-profile/skills/write-chapters/SKILL.md`（`.dsh/skills` 是符号链接，只改 profile）
- Modify: `backend/tests/test_skill_docs.py`

- [ ] **Step 1: Write the failing assertion**

在 `test_skill_docs.py` 的 write-chapters 断言后追加：

```python
    assert "历史库" in write
    assert "不要自己" in write and "RAGFlow" in write
```

- [ ] **Step 2: Run to verify fail**

Expected: FAIL

- [ ] **Step 3: Update SKILL.md 硬门**（Part B 还会再改流程；本步先加禁令）

增加一条：

```
- 历史项目材料由 8002 按文类和属地过滤后注入。不要自己连 RAGFlow 或搜网写正文。
```

- [ ] **Step 4: Run `pytest tests/test_skill_docs.py -q`**

Expected: PASS

- [ ] **Step 5: Commit**（无 git 则跳过）

---

## Part B — 写前政策确认

### Task 8: Job 字段与综述模板

**Files:**
- Modify: `backend/solution_gen/domain.py`
- Modify: `backend/solution_gen/locale_search.py`
- Test: `backend/tests/test_locale_brief.py`

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_locale_brief.py`：

```python
from solution_gen.domain import Citation, Job, Profile
from solution_gen.locale_search import locale_brief_text


def test_brief_lists_hits() -> None:
    job = Job(
        id="b1",
        profile=Profile(place="青岛市", industry="低空经济"),
        citations=[
            Citation(library="检索", title="青岛市低空经济发展行动方案", why="q", excerpt="加快基建"),
        ],
    )
    text = locale_brief_text(job)
    assert "青岛市低空经济发展行动方案" in text
    assert "青岛市" in text


def test_brief_empty_forbids_invention() -> None:
    job = Job(id="b2", profile=Profile(place="青岛市", industry="低空经济"))
    text = locale_brief_text(job)
    assert "未见" in text
    assert "不编" in text or "禁止编造" in text
```

- [ ] **Step 2: Run to verify fail**

Expected: FAIL

- [ ] **Step 3: Implement**

`Job` 增加：

```python
locale_brief: str = ""
locale_brief_status: str = ""  # "" | "drafted" | "confirmed"
```

`locale_search.py`：

```python
def locale_brief_text(job: Job) -> str:
    place = (job.profile.place if job.profile else "") or "属地"
    industry = (job.profile.industry if job.profile else "") or "产业"
    hits = [c for c in job.citations if c.library in {"检索", "地方库"}]
    lines = [f"属地政策方向（{place} / {industry}）。下列文件拟写入概述、背景、立项依据。"]
    for c in hits[:8]:
        lines.append(f"- [{c.library}] {c.title}：{(c.excerpt or '')[:80]}")
    if not hits:
        lines.append("未见该市公开专项规划，拟只引用国家/行业政策，不编地方文件名。")
    lines.append("请确认、改这段话、补文件名或要求重搜。确认后才写全部正文。")
    return "\n".join(lines)
```

`fill_locale_search` 增加 `force: bool = False`：`force` 时忽略 `locale_searched`，允许重搜（先丢掉旧 `library==检索` 再搜）。

- [ ] **Step 4: pytest tests/test_locale_brief.py -q**

Expected: PASS

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 9: draft / confirm 工具与 write-chapters 硬门

**Files:**
- Create: `backend/solution_gen/tools/locale.py`
- Modify: `backend/solution_gen/tools/dispatch.py`
- Modify: `backend/solution_gen/tools/chapter.py`
- Modify: `backend/solution_gen/tools/result.py`
- Modify: `backend/tests/test_locale_brief.py`
- Modify: `backend/tests/test_skill_tools.py`（若 write-chapters 未确认应变失败，同步改现有用例）

- [ ] **Step 1: Write the failing tests**

```python
import asyncio
from solution_gen.domain import DocType, JobStatus, Profile
from solution_gen.service import JobService
from solution_gen.store import save_job
from solution_gen.tools.dispatch import dispatch


def _outline_job() -> str:
    svc = JobService()
    job = svc.create(DocType.SOLUTION)
    asyncio.run(svc.submit_profile(job.id, Profile(place="青岛市", industry="低空经济", budget=1, construction_period=12, need="示范")))
    return job.id


def test_write_chapters_without_locale_confirm_fails() -> None:
    jid = _outline_job()
    result = asyncio.run(dispatch("write-chapters", {"job_id": jid}))
    assert result["ok"] is False
    assert "确认" in (result.get("error") or "")


def test_draft_then_confirm_then_write_allowed(monkeypatch) -> None:
    from solution_gen.locale_search import SearchHit, set_search_provider

    set_search_provider(
        lambda _q: [SearchHit(title="青岛市低空经济发展行动方案", excerpt="青岛市加快基建", url="https://example.com/qd")]
    )
    jid = _outline_job()
    drafted = asyncio.run(dispatch("draft-locale-brief", {"job_id": jid}))
    assert drafted["ok"] is True
    assert drafted.get("locale_brief") and "青岛市低空经济发展行动方案" in drafted["locale_brief"]
    confirmed = asyncio.run(dispatch("confirm-locale-brief", {"job_id": jid}))
    assert confirmed["ok"] is True
    # 不真正跑 LLM 写章：只断言状态仍是 outline_confirm 且 locale_brief_status=confirmed
    from solution_gen.store import get_job
    job = get_job(jid)
    assert job.locale_brief_status == "confirmed"
    assert job.status is JobStatus.OUTLINE_CONFIRM
```

`test_write_chapters_before_outline_confirm_fails` 保持。`tests/test_skill_tools.py` 的 `test_write_chapters_before_outline_confirm_fails` 保持（任务还在 profile，错误仍是「不能写正文」）。不要改成政策确认文案。

- [ ] **Step 2: Run to verify fail**

Expected: FAIL（未知工具 `draft-locale-brief`）

- [ ] **Step 3: Implement tools**

`tools/locale.py`：

```python
from __future__ import annotations

from typing import Any

from solution_gen.domain import Citation, JobStatus
from solution_gen.locale_search import fill_locale_search, locale_brief_text, needs_locale_policy
from solution_gen.service import JobService
from solution_gen.tools.result import fail, snapshot

_svc = JobService()


def draft_locale_brief(job_id: str, text: str = "", requery: bool = False, titles: str = "") -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.OUTLINE_CONFIRM:
        return fail("未确认目录，不能检索地方政策。", job)
    pending = [c for c in job.chapters if needs_locale_policy(c)]
    if not pending:
        job.locale_brief = "本目录无概述/背景/立项依据章，无需确认地方政策。"
        job.locale_brief_status = "confirmed"
        _svc  # persist via save
        from solution_gen.store import save_job
        save_job(job)
        return snapshot(job, replies=[job.locale_brief], locale_brief=job.locale_brief, next="write_chapters")
    fill_locale_search(job, force=requery or not job.locale_searched)
    extra = [t.strip() for t in titles.replace("，", ",").split(",") if t.strip()]
    have = {c.title for c in job.citations}
    for title in extra:
        if title not in have:
            job.citations.append(
                Citation(library="检索", title=title, why="人工补录", excerpt="", place=job.profile.place if job.profile else "")
            )
            have.add(title)
    if text.strip() and not requery:
        job.locale_brief = text.strip()
    else:
        job.locale_brief = locale_brief_text(job)
    job.locale_brief_status = "drafted"
    from solution_gen.store import save_job
    save_job(job)
    return snapshot(
        job,
        replies=[job.locale_brief],
        locale_brief=job.locale_brief,
        next="wait_confirm_locale_then_write",
    )


def confirm_locale_brief(job_id: str) -> dict[str, Any]:
    job = _svc.get(job_id)
    if job.status is not JobStatus.OUTLINE_CONFIRM:
        return fail("未确认目录。", job)
    if not (job.locale_brief or "").strip():
        return fail("还没有政策方向综述。先 draft-locale-brief。", job)
    job.locale_brief_status = "confirmed"
    from solution_gen.store import save_job
    save_job(job)
    return snapshot(job, replies=["地方政策方向已确认，可以 write-chapters。"], locale_brief=job.locale_brief, next="write_chapters")
```

把 `save_job` 收到文件顶部。`fill_locale_search(job, force=...)` 必须在 Task 8 已改签名。

`dispatch.py`：`ACTIONS` 加入 `draft-locale-brief`、`confirm-locale-brief`；分支调用上述两函数。`requery` 从 payload 读 `true`/`1`/`yes`。

`result.snapshot` 增加 `"locale_brief": job.locale_brief`、`"locale_brief_status": job.locale_brief_status`。

`write_chapters`：在 `OUTLINE_CONFIRM` 校验之后、`confirm_outline` 之前：

```python
    needs = [c for c in job.chapters if needs_locale_policy(c)]
    if needs and job.locale_brief_status != "confirmed":
        return fail("请先 draft-locale-brief，等人确认地方政策方向后再 write-chapters。", job, locale_brief=job.locale_brief)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_locale_brief.py tests/test_skill_tools.py -q
```

Expected: PASS。修正任何「直接 write-chapters」的旧测试。

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 10: plugin + skill 流程

**Files:**
- Modify: `dsh-profile/src/plugin.ts`
- Modify: `dsh-profile/skills/write-chapters/SKILL.md`
- Modify: `dsh-profile/agents/proposal.md`
- Modify: `dsh-profile/agents/feasibility.md`
- Modify: `backend/tests/test_skill_docs.py`

- [ ] **Step 1: Failing assertions**

```python
    plugin = PLUGIN.read_text(encoding="utf-8")
    assert "draft-locale-brief" in plugin
    assert "confirm-locale-brief" in plugin
    write = (SKILLS / "write-chapters" / "SKILL.md").read_text(encoding="utf-8")
    assert "draft-locale-brief" in write
    assert "confirm-locale-brief" in write
```

proposal / feasibility 须出现 `draft-locale-brief`。

- [ ] **Step 2: Run to fail**

- [ ] **Step 3: 改文件**

`plugin.ts` 的 `ACTIONS` 字符串追加 `draft-locale-brief, confirm-locale-brief`。parameters 可复用 `text`；增加可选说明：`text` 也可为改写的政策综述。

`write-chapters/SKILL.md` 改为：

```
操作者确认目录之后：
1. solution_skill action=draft-locale-brief
2. 把返回的 locale_brief 原样念给操作者
3. 改综述：再调 draft-locale-brief（text=改写）；重搜：text 说明查询并在对话里说明要重搜（工具 requery）；补文件名：titles
4. 操作者确认后 confirm-locale-brief
5. 再 write-chapters
未确认禁止 write-chapters。不要自己搜网或连 RAGFlow 写正文。
```

proposal 第 3 步拆成「政策综述确认 → write-chapters」。feasibility 同样。

plugin/persona 改完需重启 3080；SKILL.md 在 `skill()` 时重读。

- [ ] **Step 4: pytest tests/test_skill_docs.py -q**

Expected: PASS

- [ ] **Step 5: Commit**（无 git 则跳过）

---

### Task 11: 状态机回归与全量测试

**Files:**
- Test only: `backend/tests/test_machine.py`（不改 `machine.py`）

- [ ] **Step 1: Run**

```bash
cd backend && .venv/bin/python -m pytest tests -q
```

Expected: 全绿。`test_happy_path_to_delivered` 不经过 locale 工具（直接 `apply`），应仍通过。

- [ ] **Step 2: 若失败**只修本计划引入的断言/硬门，禁止改 `TRANSITIONS`。

- [ ] **Step 3: Commit**（无 git 则跳过）

---

## Spec coverage

| 规格章节 | 任务 |
|---|---|
| 文类不串、阶段不进写手 | Task 1 `WRITABLE_STAGES` + `doc_type` |
| 外地不进地区章 | Task 1 channel locale + Task 2/5 |
| 外地方案可进建设方案 | Task 1 channel scheme |
| 方向过滤 | Task 1 `profile_direction` |
| RAGFlow 可选、无 Key 为空 | Task 4 |
| JSON 三库仍可用 | Task 3 conftest + 既有 `test_locale_library_filtered` |
| 3080 不直连 | Task 7/10 |
| KB-01 / KB-02 | Task 6 |
| 写前确认、0 命中也确认、可改/重搜/补名 | Task 8–10 |
| 不改 TRANSITIONS | Task 11 |
| 10G 入库脚本 | 明确不做 |

## 非目标（计划内不要做）

- Docker 安装 RAGFlow、全量 10G 爬夹上传
- 改 `TRANSITIONS`、3080 知识库 UI
- 把 IRR 检测做成可研必填（只禁止建议书出现）
