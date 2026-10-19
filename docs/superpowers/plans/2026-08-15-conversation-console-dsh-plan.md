# 实现计划：对话控制台 + 目录确认 + canvas-editor

> **已废止。** 现行实现是 `dsh-profile/` + `solution_gen.tools`，业务页是 dsh web。见仓库根目录 [README.md](../../../README.md)。本文任务（含 canvas-editor）不要再执行。

依据：[2026-08-15-conversation-console-dsh-design.md](../specs/2026-08-15-conversation-console-dsh-design.md)

原则：先把对话门和编辑器跑通（写章仍走现网），再换 dsh/DeepSeek。每步可单独验收。不在本计划里做视频数字人、语音、Ralph、初设/投标。

---

## 阶段 0 · 领域模型

### 任务 0.1 扩展 Profile 与 Job

文件：`backend/solution_gen/domain.py`

- `Profile` 增加 PRD 字段：`project_name`、`construction_unit`、`budget`（万元）、`construction_period`（月）、`scenes: list[str]`、`compilation_unit`。保留 `place`、`industry`、`words`、`need`。新字段均可空，收集齐再提交。
- `Job` 增加：`pending_confirm: str | None`（`brief` / `outline` / `final`）、`chat_log: list[ChatMessage]`、`diagram_requests: list[DiagramRequest]`、`brief_complete: bool`。
- 新类型：`ChatMessage(role, text, at)`；`DiagramRequest(kind: architecture|flowchart|gantt, chapter_id, placement, reference, status)`。

完成：模型能 round-trip 进 SQLite（`store._load` 不丢新字段）。旧任务缺字段用默认值，不崩。

### 任务 0.2 状态机加问图边

文件：`backend/solution_gen/pipeline/machine.py`、`backend/tests/test_machine.py`

新状态：`DIAGRAM_ASK`、`DIAGRAM_RUNNING`。  
新事件：`CHAPTERS_DONE` 仍从 `GENERATING` 出发，目标改为 `DIAGRAM_ASK`（不再直接 `QA_RUNNING`）。  
`SKIP_DIAGRAMS`: `DIAGRAM_ASK` → `QA_RUNNING`。  
`DIAGRAM_SPEC_DONE`: `DIAGRAM_ASK` → `DIAGRAM_RUNNING`。  
`DIAGRAMS_DONE`: `DIAGRAM_RUNNING` → `QA_RUNNING`。  
`SKIP_QA` 仍 409。

完成：单测覆盖新边；旧「章写完直接质检」的测试改期望。

---

## 阶段 1 · 对话收集与目录门

### 任务 1.1 字段抽取与追问

新文件：`backend/solution_gen/chat/brief.py`

- 输入：用户原话 + 当前 Profile。
- 规则优先：识别「项目建议书/可研/立项」、地名（市/县）、数字+万/月。
- 缺项返回下一问（一次只问缺的一项或一组）。
- 六项必填齐：返回复述文本，调用方置 `pending_confirm=brief`。
- 禁止把空属地写成 XX市。

完成：`backend/tests/test_brief.py`：只说「帮我写一份项目建议书」→ 未齐、不出目录；补齐后复述含属地和投资。

### 任务 1.2 `/chat` 意图与门控

新文件：`backend/solution_gen/chat/intent.py`、`backend/solution_gen/chat/service.py`  
改：`gateway/app.py`、`service.py`

`POST /api/jobs`：无类型也可建（默认 solution，对话里再改）。  
`POST /api/jobs/{id}/chat` body `{text}`：

1. 追加 user 消息。
2. 按状态分流：收集 → brief；`outline_confirm` → 改目录或确认；`diagram_ask` → 要图/都不要；`qa_blocked` → 改写/换素材；`final_confirm` → 修订或确认；生成中 → 只回进度话术。
3. 「确认」仅当 `pending_confirm` 匹配才触发事件（见设计第 4 节）。
4. 返回 `{job, replies, pending_confirm, editor, diagram_prompt}`。

完成：`test_chat_gates.py`：未齐确认无效；outline 确认才 `CONFIRM_OUTLINE`；生成中确认状态不变；跳过质检无效。

### 任务 1.3 目录改写走聊天

改：`service.update_outline`、`workers/outline.py`

- 人在 `outline_confirm` 说「把实施计划拆成两章」：用现有 LLM/stub 改 `chapters`，不离门，清掉再置 `pending_confirm=outline`。
- 目录确认后现有 `run_generation` 照旧。

完成：测试「拆章」后仍为 `outline_confirm`，章数变化。

---

## 阶段 2 · 正文后编辑器

### 任务 2.1 章节 ↔ canvas-editor JSON

新文件：`backend/solution_gen/editor/canvas_doc.py`、`backend/tests/test_canvas_doc.py`

- `chapters_to_editor(job) -> { header, main: [...] }`：封面题、各章 heading + 段落；图占位先空。
- `editor_to_chapters(doc, chapters) -> list[Chapter]`：按 heading 切回 `content`，不丢 id。
- 往返：标题和主要段落还在。

### 任务 2.2 保存编辑器

改：`app.py`、`service.py`

`PUT /api/jobs/{id}/editor`：拆章、`save_chapter` 批量、增量质检。不交付。  
`GET /api/jobs/{id}` 在章已齐时带 `editor` 字段（或 chat 返回里带）。

完成：测试保存后 content 更新、status 仍非 delivered。

### 任务 2.3 Vite 对话页 + canvas-editor

新目录：`frontend/`（Vite + TS）  
依赖：`@hufe921/canvas-editor`  
改：`app.py` 根路径改指向 `frontend/dist`（开发时可用静态挂载或 5173 代理 /api）。

页面：

- 左对话：消息列表、输入框。无阶段条、无三库侧栏。
- 仅当存在 `editor.main` 时右侧挂 `new Editor(el, editor)`。
- 轮询 job 或跟在 `/chat` 后刷新编辑器。
- 顶栏：项目名 · 类型 · 阶段中文。
- 编辑器失焦或「保存」调 `PUT /editor`。
- 无麦克风、无人脸。

完成：本地打开能聊到目录确认；确认后生成，正文齐了右侧出分页稿。旧 `prototype/解决方案生成控制台.html` 可留作备份，不再作为 `/`。

---

## 阶段 3 · 问图与出图

### 任务 3.1 问图对话

改：`chat/intent.py`、`service.py`、`machine.py`（已在 0.2）

- `CHAPTERS_DONE` → `diagram_ask`，助理问三类图。
- 「都不要」→ `SKIP_DIAGRAMS` → 质检。
- 「要架构图」→ 记 kind，追问位置、参考；三项齐才入 `diagram_requests`。
- 至少一张齐且人说「按这些出图」或最后一张参考说完 → `DIAGRAM_SPEC_DONE`。

完成：测试不要图直达 `qa_running`；只要图不给位置不进入 `diagram_running`。

### 任务 3.2 出图写入编辑器

改：`service.py`、`skills/charts.py`、`assemble.py`

- `diagram_running`：对每条 request 调现有出图，写入对应章 `diagram_json`，刷新 editor JSON（image 元素）。
- 完 → `DIAGRAMS_DONE` → 质检 → 组装 Word。
- 失败：该条 fail，聊天可重说参考。

完成：有架构图请求时 editor 出现 image；不要图时无 image。

---

## 阶段 4 · DeepSeek Harness 写章

### 任务 4.1 writer 适配层

新文件：`backend/solution_gen/workers/dsh_writer.py`  
改：`llm.py`、`config.py`、`workers/runtime.py`

- 优先 `DeepSeekHarness().run(prompt)`（`deepseek-harness-sdk`，pin 版本）。
- 环境：`DEEPSEEK_API_KEY`、可选 `DEEPSEEK_BASE_URL`。
- 失败再退现有 OpenAI 兼容 / stub。
- 超时、无密钥：stub，任务不卡死。

完成：无密钥测试仍出 stub 章；有密钥的手动烟测记在 README，不进 CI。

### 任务 4.2 出图同样走适配层

`emit_diagram` 的说明文案可由 dsh 生成结构化 JSON，渲染仍用本仓 `charts.py`（模型不改状态）。

---

## 阶段 5 · 收尾

### 任务 5.1 文案与列表

- 任务列表可读名：`{属地} · {类型} · {阶段中文}`。
- 对外零出现：HARNESS、Worker、热记忆、Token、UUID 当标题。
- `backend/README.md`：对话页地址、环境变量、与旧驾驶舱备份的关系。

### 任务 5.2 回归

跑：`test_machine`、`test_qa_gates`、新 brief/chat/canvas/diagram 测试。  
手测设计第 10 节清单。

---

## 建议开发顺序（勾选用）

1. 0.1 → 0.2  
2. 1.1 → 1.2 → 1.3  
3. 2.1 → 2.2 → 2.3  
4. 3.1 → 3.2  
5. 4.1 → 4.2 → 5.1 → 5.2  

阶段 4 可与 2.3 并行，但不阻塞编辑器。

## 不在本计划

视频数字人、语音、fork dsh 进本仓、把状态机改成模型 workflow、恢复五段驾驶舱为主界面。
