---
name: polish-deliver
description: 规则质检并组装 Word。失败只能改写或换素材，不能跳过质检。
---

# polish-deliver

出图结束（含 skip-diagrams）后核对正文。先用官方 `skill` 加载本说明书，再 `solution_skill`。质检失败是业务事故，不能跳过。

除术语、属地外，工具会卡**单章字数下限**（该章目标字数的约 15%，至少 200 字），不是全书必须写满 8 万。还会按文类合同检查：必选章是否还在、总投资是否在概述/投资/结论回写、已选模块是否出现在概述/建设方案/结论。不要按某个行业的专用指标去口头放行。

## 开始质检

```
solution_skill
  action: polish-deliver
  job_id: 必填
  op: run-qa
```

## 失败时只允许

```
solution_skill
  action: rewrite-chapter
  job_id: 必填
  chapter_id: 问题章
  instruction: 改法
```

或

```
solution_skill
  action: swap-material
  job_id: 必填
  chapter_id: 问题章
  material_title: 产品库条目标题
```

## 通过后

把 `export_path` 告诉操作者。对方确认终稿后：

```
solution_skill
  action: deliver
  job_id: 必填
```

若操作者要改一处再交付：`action: revise`（会再进质检）。

## 硬门

- **没有 skip-qa 工具。** 调用会被拒绝。
- 未到终稿确认门不能 `deliver`。
- 不要改 `TRANSITIONS`，不要用 shell 改 SQLite。
