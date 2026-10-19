---
name: collect-brief
description: 收集文类槽位。字段未齐禁止出目录。用于项目建议书、可研、立项。
---

# collect-brief

向操作者问齐**文类槽位**，再调用 `solution_skill`。先用官方 `skill` 加载本说明书。不要自己编属地；属地不能默成「XX市」。建设模块的选项以工具返回的 `genre.module_options` 为准，不要按某个行业默写目录。

## 必问槽位（各行业相同）

- 文档类型：项目建议书 / 可研 / 立项（若主 agent 已定类型，不要改）
- 项目全称 `project_name`
- 属地 `place`（市或县）
- 建设单位 `construction_unit`
- 总投资万元 `budget`
- 建设周期月 `construction_period`

## 建议问（有则写入画像）

- 编制单位 `compilation_unit`
- 资金来源 `funding_source`（自有资金 / 专项债 / 财政等）
- 建设模块 `modules`：勾选 `module_options`；对方不选时工具会用行业包默认模块，摘要里会写明

行业包由工具解析。若当前只登记了一个行业包，摘要会点名，不要把属地或项目名一并默认。


## 调用

```
solution_skill
  action: collect-brief
  job_id: 已有任务则必填；没有则省略以新建
  text: 操作者原话
  以及已解析出的 project_name / place / construction_unit / budget / construction_period
  可选 compilation_unit / funding_source / modules / industry
```

## 硬门（工具会拒绝，不要绕）

- 缺字段时 `draft-outline` 会失败。继续问 `missing` 里的项。
- 工具返回 `next=wait_confirm_then_draft_outline` 时：把 `replies` 里的摘要念给操作者（含文类名、行业包、拟建模块），等对方确认后才进入 `draft-outline`。
- 不要调用 bash、不要改数据库、不要 skip-qa（该工具不存在）。
