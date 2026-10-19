# 方案生产 · skill 后端

FastAPI 只做硬门：`POST /api/skills/{action}`、Job 读写、QA、assemble。唯一前端是 dsh web（http://127.0.0.1:3080）。

```bash
cd backend
.venv/bin/python -m uvicorn solution_gen.gateway.app:app --host 127.0.0.1 --port 8002
```

`/api/health` 标明 `ui: dsh-web`。没有 `/api/agent/*`。`POST /api/skills/{action}` 与 `python -m solution_gen.tools` 是同一套硬门。

## 写章优先级

1. `DEEPSEEK_API_KEY`（可选 `DEEPSEEK_BASE_URL`）→ DeepSeek **chat/completions 章节写手**，不当调度
2. `SOLUTION_LLM_API_KEY` 或 `MINIMAX_API_KEY` → OpenAI 兼容接口
3. 都没有 → 三库接地短文，仍出 Word

```bash
pip install "deepseek-harness-sdk==0.1.0rc6"
```

不要把密钥提交进 git。可选 `DSH_TIMEOUT`（秒，默认 90）。

## 硬门

- 字段未齐不能出目录
- 未确认目录不能写正文；生成中不能改目录
- 没有 skip-qa；质检失败只能 rewrite / swap-material
- 地方库按属地过滤
- 出图：未确认说明不能 attach；SVG→PNG 先试 cairosvg，失败则用 PyMuPDF（不依赖系统 cairo）

## 目录

`tools` skill CLI · `pipeline` 状态机 · `chat` 对话门（测试/技能共用） · `qa` 规则引擎 · `rag` 三库 · `workers` 写章 · `store` SQLite
