# 对话控制台 + 目录确认 + 正文编辑器

> **已废止作为现行方案。** 2026-08-15 后业务页改为 dsh web + 主 agent / 子 agent / skill。现行入口见仓库根目录 [README.md](../../../README.md)。本文只保留当时的交互决策（确认门、质检不能跳、属地过滤）。**不要按第 1 节及以后的界面描述实施**（canvas-editor、8002 对话页、dsh 只写章均已作废）。

日期：2026-08-15  
状态：已废止（被主 Agent + Skill 架构取代）

## 1. 一句话

人在聊天里说需求；助理按 PRD 问齐关键字段并请人确认；确认后先出目录再出正文。正文出齐后，右侧用 [canvas-editor](https://github.com/Hufe921/canvas-editor) 展示可翻页文稿，再问要不要架构图 / 流程图 / 甘特图。全部完成后聊天回「确认」交付。不做视频数字人，不做语音。代码管流转，dsh + DeepSeek 只写章、出图。

## 2. 决策日志

| 决策 | 选择 | 不选 |
|---|---|---|
| 开场 | 人先说一句话需求，助理追问并复述确认 | 先填短表再聊；预填乐山演示 |
| 内容确认问什么 | 对齐 PRD 必填：文档类型、项目名称、属地、建设单位、总投资、建设周期；可选场景、编制单位、补充要点 | 只问属地/行业/字数 |
| 目录 | 先出目录，聊天确认后才写正文；改目录也用说的 | 章节树编辑器；目录和正文一起出 |
| 正文展示 | 3.2 完成后打开 canvas-editor 展示全文（可改、可分页） | 聊天里截 280 字；五段驾驶舱 |
| 出图时机 | 正文齐了再问要不要图；要则逐张问位置和参考 | 大纲里预先勾「出图」；生成中插图 |
| 点头 | 聊天回「确认」（仅当前门有效） | 必须点按钮 |
| 数字人/语音 | 不做 | 形象、麦克风 |
| dsh | 写章 / 出图运行时，模型 DeepSeek | Ralph 当总调度；dsh Web 当业务页 |

沿用且不可改：

- 合法边只在状态机里，AI 不能改图。
- `SKIP_QA` 永远非法。
- 写正文过程中不能改目录。
- 地方库强制按属地过滤。
- 文档类型一期：项目建议书（对应现有 solution）、可研、立项。PRD 里的初设 / 投标仍标二期。

## 3. 使用流程

### 1）人说需求

例：「帮我写一份项目建议书」。系统建任务，进入收集，不写目录。

### 2）助理做必要确认（对齐 PRD）

缺什么问什么，已从原话抽出的先复述请人改。必齐：

| 字段 | PRD | 说明 |
|---|---|---|
| 文档类型 | doc_type | 建议书 / 可研 / 立项；从「项目建议书」等话术推断，不确定就问 |
| 项目名称 | project_name | |
| 属地 | project_location | 市/县，禁止默认「XX市」 |
| 建设单位 | construction_unit | |
| 总投资（万元） | budget | |
| 建设周期（月） | construction_period | |
| 应用场景 | scenes | 可选；不选则按模板全场景 |
| 补充要点 | requirements | 可选 |

齐了之后助理用一段话复述全部字段，请人回「确认」开始做目录。此时 `pending_confirm=brief`。未齐不进入目录。投资、工期等可按 PRD 规则推断衍生量，但必填六项不能空。

### 3）确认后撰写

**3.1 目录**  
出章名、每章要写什么、目标字数。助理请人回「确认」或说怎么改（拆章、并章、改名）。`pending_confirm=outline`。改完仍停在目录门，再请一次确认。

**3.2 写各章正文**  
目录确认后按依赖波次写。助理按章报进度。人不能改目录。全部章 `done` 后：

- 前端打开 canvas-editor，载入全文（标题、各章、分页）。
- 之后出图、修订都写进同一份编辑器，不再用聊天长文代替正文。

**3.3 问图**  
助理问：是否需要架构图、流程图、甘特图（可多选）。人说「都不要」则跳到质检。  
若要某类图，逐张问：

- 放在哪一章 / 哪一节后面
- 参考什么（已有素材、一句话结构、或「按正文生成」）

**3.4 出图**  
按需求逐张生成，插入指定位置，编辑器刷新。失败则说明，允许再说一次参考或放弃该图。

**3.5 质检与终稿确认**  
出图结束（或不要图）后跑规则质检。通过：组装 Word，助理请人看编辑器并回「确认」交付。失败：聊天列出问题，人说改哪章或换素材，不能跳过；改完重跑质检。  
`pending_confirm=final`。无 Word 时「确认」无效。

「新开一份」回到步骤 1。已交付只读。

## 4. 「确认」生效规则

网关解析，不是模型 tool。仅当助理刚发出对应邀请（`pending_confirm` 已置位）且状态匹配：

| pending_confirm | 状态 | 事件 |
|---|---|---|
| brief | 收集齐字段后 | `SUBMIT_PROFILE` → 出目录 |
| outline | `outline_confirm` | `CONFIRM_OUTLINE` → 写正文 |
| final | `final_confirm` 且已有 Word | `DELIVER` |

写目录、写正文、出图、质检中的「确认」忽略。  
「都不要」（问图时）不是确认门，是跳过出图。  
歧义当修改，再单独请「确认」。

## 5. 对话意图

| 人说的大致意思 | 行为 | 允许的状态 |
|---|---|---|
| 帮我写… | 建任务，开始问字段 | 无任务 / 已交付后新开 |
| 字段补全、纠正 | 写入画像，未齐继续问 | 收集中 |
| 确认 | 第 4 节 | brief / outline / final |
| 改目录 | 改树，仍在目录门 | `outline_confirm` |
| 要架构图 / 流程图 / 甘特图 + 位置 + 参考 | 记录出图单 | 正文已齐、问图或出图中 |
| 都不要图 | 进入质检 | 问图 |
| 改第 N 章 / 换素材 | 质检通道 | `qa_blocked` |
| 编辑器里改完了 / 按正文修订 | 保存并增量质检 | 正文已齐之后 |
| 跳过质检 | 拒绝 | 任何 |
| 新开一份 | 新任务 | 任何（写稿中提示旧稿保留） |

## 6. 界面

左：对话。右：仅在 3.2 完成后出现 canvas-editor（[仓库](https://github.com/Hufe921/canvas-editor)，包 `@hufe921/canvas-editor`）。未出正文时编辑器不出现，对话全宽。

顶栏：项目名 · 文档类型 · 阶段中文（收集确认 / 等目录 / 写正文 / 出图 / 请确认终稿）。不要阶段条导航、三库侧栏、Token、UUID 当标题。

编辑器：

- 用官方 JSON 结构渲染（`main` 元素数组），章标题用 heading，正文用段落，图用 image。
- 分页、页边距按公文稿（接近 Word）。
- 人可在编辑器改字；保存走现有章节更新 + 质检。保存不是交付。
- 出图后插入对应位置并滚动到该处。
- 窄屏：对话在上、编辑器在下，可折叠对话。

前端不再用单文件 HTML 硬塞该库，改为小的 Vite 页（或等价打包），仍由 8002 同源提供。

## 7. 状态机增量

在现有边上增加问图 / 出图，不删原有门：

```
收集字段 --SUBMIT_PROFILE--> 出目录 --OUTLINE_READY--> outline_confirm
outline_confirm --CONFIRM_OUTLINE--> generating
generating --CHAPTERS_DONE--> diagram_ask
diagram_ask --SKIP_DIAGRAMS--> qa_running
diagram_ask --DIAGRAM_SPEC_DONE--> diagram_running
diagram_running --DIAGRAMS_DONE--> qa_running
qa_running --QA_PASS--> assembling --ASSEMBLED--> final_confirm
qa_running --QA_FAIL--> qa_blocked
qa_blocked --REWRITE/SWAP--> generating（只重跑问题章）或 diagram_running（只重跑图）
final_confirm --REVISE--> revising --REVISED--> qa_running
final_confirm --DELIVER--> delivered
```

`SKIP_QA` 仍禁止。`SKIP_DIAGRAMS` 合法。

## 8. 后台与 API

结构不变：对话页 → `/chat` → 状态机 → dsh 写章/出图；三库与质检仍是代码。

模型工具：`retrieve_library`、`write_chapter`、`emit_diagram`。仅 `generating` / `revising` / `diagram_running` 可出图或写章。

`POST /api/jobs/{id}/chat` 返回增加：

- `pending_confirm`: `brief` \| `outline` \| `final` \| null
- `editor`: canvas-editor 文档 JSON（3.2 之后有）
- `diagram_prompt`: 当前在问哪类图、还缺位置还是参考

`PUT /api/jobs/{id}/editor`：编辑器保存，拆回各章 content，走增量质检。

## 9. 一期范围

做：对话收集（PRD 字段）、目录确认、分章、canvas-editor 展示与保存、问图与出图、质检不可跳过、聊天确认交付、dsh/DeepSeek 写章适配。

不做：视频数字人、语音、dsh Web 业务页、Ralph 总调度、初设/投标、大纲树 UI。

实现顺序：

1. 对话收集 + 目录确认 + `/chat`（写章仍走现网）
2. 分章完成后挂 canvas-editor
3. 问图 / 出图写入编辑器
4. writer 换 dsh + DeepSeek
5. pipeline 插件化（对外契约不变）

## 10. 验收

- 只说「帮我写一份项目建议书」、不给属地，不能出目录。
- 字段未齐时回「确认」不出目录。
- 目录未确认不写正文，编辑器不出现。
- 正文未齐不问图、不打开编辑器。
- 问图时说「都不要」进入质检，不生成图。
- 要架构图但不给位置，不出图，继续问位置。
- 仅 `pending_confirm` 匹配时「确认」才过门。
- 质检失败「跳过」无效。
- 编辑器展示各章全文；保存不自动交付。
- 无视频、无麦克风。

## 11. 风险

- canvas-editor 是自有 JSON，不是 HTML。必须做「章节 ↔ editor JSON」双向转换，测往返不丢标题和段落。
- 8–20 万字分页性能：按章懒加载或先载当前章 + 目录跳转。
- 聊天「确认」误触：`pending_confirm` 收窄。
- dsh preview：pin 版本，只关在 writer。
