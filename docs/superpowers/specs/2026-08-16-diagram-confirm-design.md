# 出图：先确认文字说明，再按 diagram-design 画图

日期：2026-08-16  
状态：已实现  
范围：`DIAGRAM_ASK` 交互、`emit-diagrams` skill、8002 出图硬门、Word 附图。  
不在范围：改 `TRANSITIONS`、27 种图、品牌 onboarding、draw.io/Mermaid 导入、fork harness、把 8002 融进 harness。

## 1. 一句话

正文齐了之后先问要哪些图（架构 / 流程 / 甘特，或都不要）。每一张都先出**文字说明**，操作者确认或改说明之后，再用 [diagram-design](https://github.com/cathrynlavery/diagram-design) 的画法生成图，最后进 Word。没有确认不能画。

## 2. 决策日志

| 决策 | 选择 | 不选 |
|---|---|---|
| 问哪些图 | 正文齐后先问；文类 `default_diagrams`（建议书/可研/立项均为 architecture + gantt）只是口头建议 | 按默认自动出图；大纲里预勾 |
| 类型 | 仍只允许 `architecture` / `flowchart` / `gantt` | 27 种编辑图、雷达、维恩等 |
| 每张图顺序 | 文字说明 → 确认或改说明 → 再画；一张走完再下一张 | 登记 kind 后立刻 SVG；先把三张说明出齐再一起画 |
| 确认硬门 | 8002 拒绝未确认的出图 | 只靠 skill 说明书约束 |
| 画图技术 | 确认后由子 agent 按 diagram-design 出自包含 HTML（内联 SVG）；8002 收文件、抽 SVG、栅格成 PNG 供 Word | 继续用 `charts.py` 色块 SVG；Playwright 作为必依赖 |
| diagram-design 进仓 | 摘 MIT 子集进 `dsh-profile/skills/diagram-design/`（说明书 + 三种 type 参考 + style-guide），注明出处 | 整仓 clone 到仓库根；运行时 npx 拉远程 |
| 状态机 | 不改 `machine.py` 的 `TRANSITIONS`。说明/确认/单张出图都发生在 `DIAGRAM_ASK`。全部要的图都已画出，或剩余不要，才 `DIAGRAM_SPEC_DONE` 或 `SKIP_DIAGRAMS` | 每画一张就进 `DIAGRAM_RUNNING`（会提前进质检） |
| 都不要 | `skip-diagrams`；已画出的图保留；随后必须 `polish-deliver` | 把「都不要」当成 skip-qa |
| 落盘 | 只经 `solution_skill` | bash 写 HTML 绕过硬门 |

沿用且不可改：合法边只在 `TRANSITIONS`；没有 skip-qa；生成中不能改目录；属地库按属地过滤；交付物是 Word。

## 3. 使用流程

任务状态为 `diagram_ask`（文案：询问配图）。

1. 子 agent 加载 `emit-diagrams`，问要插入哪些图。可提示「建议总体框架图（建设方案后）和甘特图（实施计划后），流程图按需」。
2. 操作者说「都不要」→ `skip-diagrams` → `QA_RUNNING` → `polish-deliver`。
3. 操作者点名一种或多种。每种按下面循环，**做完一张再开始下一张**（先架构再流程再甘特，若都要了）：
   1. `draft-diagram-spec`：8002 根据该章正文 + 画像生成中文文字说明，并带上默认挂载章（架构→建设方案，流程→需求分析或建设方案，甘特→实施计划）。
   2. 把说明念给操作者。操作者改内容或改挂载章：再次 `draft-diagram-spec`（可带 `text` 修正）。
   3. 操作者回复「确认」→ `confirm-diagram-spec`。未确认禁止出图。
   4. 子 agent 加载 `diagram-design`（只读对应 type 参考），按已确认说明画一张自包含 HTML，经 `attach-diagram` 交给 8002。
   5. 8002 校验、抽 SVG、写出 `{chapter_id}.png`，章内留「【图 …】」占位。任务仍停在 `DIAGRAM_ASK`。
4. 要的图都已 attach，或操作者对剩余说「都不要」：
   - 至少有一张已出图：`emit-diagrams`（收口：已有附图则直接 `DIAGRAM_SPEC_DONE` → `DIAGRAMS_DONE` → 质检）。
   - 一张都没有：只能 `skip-diagrams`。
5. `polish-deliver`。Word 在对应章落后插入 PNG。

「确认」只对当前这张图的说明有效，不能误触目录确认或终稿确认（此时 `pending_confirm` 不是 brief/outline/final）。

## 4. 出图单

`DiagramRequest` 增加：

| 字段 | 含义 |
|---|---|
| `kind` | architecture / flowchart / gantt |
| `chapter_id` / `placement` | 挂在哪一章后面 |
| `spec_text` | 待确认/已确认的中文说明（节点、关系、步骤、工期） |
| `status` | `selected` → `spec_pending` → `confirmed` → `drawn` |

`reference` 不再当「直接开画」的口。旧调用若只传 kind 而无说明，停在 `selected`，必须先 `draft-diagram-spec`。

硬门：

- 非 `DIAGRAM_ASK`：选图、出说明、确认、attach 全部失败。
- `kind` 非法：失败。
- `confirm-diagram-spec`：该 kind 必须已有非空 `spec_text`。
- `attach-diagram`：该 kind 必须 `confirmed`；HTML 必须是单文件、含 `<svg>`；禁止外链脚本。失败则该张保持 `confirmed`，任务仍 `DIAGRAM_ASK`，让操作者改说明或重画。
- `emit-diagrams`：至少一张 `drawn`；不得把未确认的 kind 带进 `DIAGRAM_RUNNING`。
- `skip-diagrams`：进入质检；已 `drawn` 的附图保留；未画出的请求丢弃。不是 skip-qa。

## 5. 8002 动作

在现有 `request-diagram` / `skip-diagrams` / `emit-diagrams` 上增加，不改 `TRANSITIONS`：

| action | 作用 |
|---|---|
| `request-diagram` | 只登记 kind（及可选 placement）。`status=selected`。可省略：`draft-diagram-spec` 带 `kind` 时一并登记。 |
| `draft-diagram-spec` | 生成或按 `text` 修订 `spec_text`，`status=spec_pending`。用章节正文，不编属地。 |
| `confirm-diagram-spec` | `spec_pending` → `confirmed`。 |
| `attach-diagram` | 接收 `html` 字符串。抽 SVG → PNG，并把 HTML 写入该 job 的 `outputs/`。`confirmed` → `drawn`。不接受任意仓库相对路径。 |
| `emit-diagrams` | 收口已 drawn 的图，触发 `DIAGRAM_SPEC_DONE`。 |
| `skip-diagrams` | 不再要图，`SKIP_DIAGRAMS`。 |

主 agent 仍只许 `status`。出图由子 agent 调。

## 6. diagram-design 子集

目录：`dsh-profile/skills/diagram-design/`。

保留：`SKILL.md`（只路由三种类型，并收录上游总册的画法章节）、`references/style-guide.md`、architecture / flowchart / gantt 各一份 type 参考，以及 Minimal light 范例 `assets/template.html` 与 `example-{architecture,flowchart,gantt}.html`。

删去本产品不用的：onboarding、profiles、27 种其余 type、draw.io/Mermaid import、motion、sketchy、暗色/terminal 变体。

画法约束（写入该 SKILL，渲染时遵守）：一色强调、细线、无阴影、坐标/间距为 4 的倍数、单文件 HTML（内联 SVG；允许 Google Fonts 链接，与上游一致；无网时系统字体回退）。Word 插的是栅格 PNG，不依赖网页字体。节点来自已确认 `spec_text`，禁止改成「业务/应用/数据/技术」四层套话顶替建设模块。

许可证：MIT，在该目录留 `NOTICE` 指向 https://github.com/cathrynlavery/diagram-design 。

`.dsh/skills` 已指向 `dsh-profile/skills`，选仓库根为工作区即可 `skill("diagram-design")`。

## 7. Word 与失败

`export_docx`：章有 `diagram` 且 `{chapter_id}.png` 存在则插入图片（现有逻辑）。HTML 与 SVG 源文件留在 `backend/data/outputs/{job_id}/` 备查，不把 HTML 当正文。

栅格：用 Python 从 HTML 取出内联 SVG，转 PNG。先试 `cairosvg`；系统 cairo 架构对不上或导入失败时改用 PyMuPDF。不把 Playwright 当必装。转换失败 → `attach-diagram` 失败，状态仍 `DIAGRAM_ASK`。

`charts.py` 色块 SVG 不再作为确认后的出图路径；无确认、无 HTML 时禁止用它顶替。

## 8. 测试

- 未确认 `attach-diagram` / 旧 `emit-diagrams` 一键出图 → 失败。
- 确认后 attach 合法 HTML → `drawn`，任务仍 `diagram_ask`。
- 两张图：第一张 drawn 之后第二张仍要说明+确认；不能直接画第二张。
- `skip-diagrams` 后 `polish-deliver` 的 skip-qa 仍 400。
- `TRANSITIONS` 表与现文件一致（测试锁哈希或逐边断言）。
- Word：有 PNG 的章含图片；说明提纲不得当正文。

## 9. 非目标

- 不改 `TRANSITIONS`。
- 不在 3080 预览分页编辑器。
- 不把出图改成无约束 shell。
- 本期不融合 deepseek-harness 源码（对话层融合另案）。
