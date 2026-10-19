---
name: emit-diagrams
description: 正文齐后先问要哪些图。每张先出文字说明并等人确认，再按 diagram-design 画 HTML。都不要走 skip-diagrams，不是 skip-qa。
---

# emit-diagrams

正文写完、任务在「询问配图」时加载本说明书。先用官方 `skill` 加载，再 `solution_skill`。属地与章节由工具写入，不要手改素材库，不要 bash 写 HTML 绕过硬门。**没有 skip-qa。**

文类默认只是口头建议：总体框架图（建设方案后）+ 甘特图（实施计划后）；流程图按需。以本次工具返回的 `genre.default_diagrams` 为准，不要自动出图。

## 先问要哪些图

向操作者问：要插入哪些图？可提示「建议总体框架图和甘特图，流程图按需」。等对方点名，或说「都不要」。

## 都不要

一张都不要：

```
solution_skill
  action: skip-diagrams
  job_id: 必填
```

随后必须进入 `polish-deliver`。这只跳过出图，**不是跳过质检**。

## 要图：一张走完再下一张

操作者点名一种或多种后，按架构 → 流程 → 甘特的顺序，**做完一张再开始下一张**。

### 1. 出文字说明

```
solution_skill
  action: draft-diagram-spec
  job_id: 必填
  kind: architecture | flowchart | gantt
  text: 可选；操作者改说明或改挂载章时带上原话
```

把返回的说明念给操作者。对方要改：再次 `draft-diagram-spec`（带 `text`）。

### 2. 等人确认

操作者回复「确认」之后才能画。此时的「确认」只对**当前这张图的文字说明**有效，不是目录确认或终稿确认。

```
solution_skill
  action: confirm-diagram-spec
  job_id: 必填
  kind: 当前这张
```

未确认禁止 `attach-diagram`，禁止开始画 HTML。

### 3. 按说明书画，再交给工具

```
skill("diagram-design")
```

按已确认说明画一张自包含 HTML（临摹 `diagram-design/assets/template.html` 与对应 `example-architecture|flowchart|gantt.html` 的几何，内容换成说明），然后：

```
solution_skill
  action: attach-diagram
  job_id: 必填
  kind: 当前这张
  html: 自包含 HTML（内联 SVG）
```

禁止未确认就 attach。禁止用 bash 把 HTML 写进磁盘来绕过确认门。

### 4. 收口

要的图都已画出，或操作者对剩余说「都不要」：

- 至少一张已出图：

```
solution_skill
  action: emit-diagrams
  job_id: 必填
```

- 一张都没有：只能 `skip-diagrams`。

然后进入 `polish-deliver`。

## 硬门

- 正文未齐：出图失败。
- 没有确认不能画、不能 attach。
- 不要把「都不要」理解成跳过质检。
- **不要 skip-qa**（该工具不存在）。
