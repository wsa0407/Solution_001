# 方案生产台

人在 **dsh web**（http://127.0.0.1:3080）里说话。这是唯一前端。主 agent 只路由文档类型，子 agent 用官方 `skill` 加载说明书，再调 `solution_skill`。硬门在 Python（质检不能跳、属地库必过滤、写正文不能改目录）。交付物是 Word 路径，由子 agent 在对话里交回。

## 启动

```bash
./scripts/dsh-web.sh
```

打开 **http://127.0.0.1:3080** ，workspace 选本仓库根目录。

也可单独起 skill 后端（工具用，不是页面）：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dsh]"
.venv/bin/python -m uvicorn solution_gen.gateway.app:app --host 127.0.0.1 --port 8002
```

手测：在 3080 说「帮我写一份青岛项目建议书」→ 主 agent 委派 → 子 agent `skill` 后 `collect-brief` 打到 8002 → 确认摘要 → 目录再确认 → 写章 → 问要哪些图 → 每张先出文字说明、回复「确认」后再画 → `emit-diagrams` 或 `skip-diagrams` → `polish-deliver` 出 Word。终稿路径在对话里。

## 结构

```
操作者
  → dsh web :3080（唯一前端：官方 subagent + skill + solution_skill）
      → FastAPI :8002 POST /api/skills/{action}
          → Python 硬门（状态机 / 文类合同 / 行业包 / 质检 / Word）
```

说明书在 `dsh-profile/`。没有 skip-qa。
