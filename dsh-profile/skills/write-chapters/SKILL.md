---
name: write-chapters
description: 目录确认后按文类写法槽写正文。生成中禁止改目录。
---

# write-chapters

操作者确认目录之后调用。先用官方 `skill` 加载本说明书，再 `solution_skill`。写手是本仓 Python / DeepSeek 章节写手，不是你自己长文生成。

各章按工具写入的 `writing` 槽写，例如：概述含编制依据三清单与建设内容收口；建设方案按模块类型（设施 / 系统 / 土建 / 规划），不要用四层架构代替模块；建议书投资章是框算，可研经济评价才写 IRR/NPV。

## 调用

```
solution_skill
  action: write-chapters
  job_id: 必填
```

## 硬门

- 任务不在「请确认目录」：工具失败。回到 `draft-outline`。
- 生成中不要 `edit-outline`，不要重复 `write-chapters`。
- 不要用 bash 改章节文件来绕过状态机。
- 写完后进入出图 skill，不要直接交付。
- 各章正文编号必须与确认目录的序号一致（第N章用 N.1 / N.2）。不要让写手自编「第一章」或跳号。
- 地方政策由 8002 按属地检索，不要自己搜网写正文。
