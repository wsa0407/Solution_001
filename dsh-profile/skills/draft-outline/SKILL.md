---
name: draft-outline
description: 需求字段齐且操作者确认后，按文类合同生成目录。写正文前必须再确认目录。
---

# draft-outline

只在 `collect-brief` 返回字段已齐、操作者确认摘要之后调用。先用官方 `skill` 加载本说明书，再 `solution_skill`。目录由文类合同生成，建设方案的二级模块来自已选行业包模块，不要改成信息化方案十章。

## 调用

```
solution_skill
  action: draft-outline
  job_id: 必填
```

改目录（仍在确认门）：

```
solution_skill
  action: edit-outline
  job_id: 必填
  text: 例如「把实施计划拆成两章」
```

## 硬门

- 字段未齐或任务不在收集完成态：工具拒绝出目录。
- 正文生成中：`edit-outline` 会失败。不要改目录。
- 目录草案出来后，把章节标题念给操作者，等确认再 `write-chapters`。
- 文类必选章（概述、需求、建设方案、实施、投资、风险、结论等，以本次 `genre` 为准）尽量保留；建设方案不要改成「总体架构 / 核心建设内容」来代替已选模块。
