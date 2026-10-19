# dsh profile（out-of-tree）

不 fork `deepseek-ai/deepseek-harness`。本目录是 web profile 的 patch：关无约束 shell、注册 `solution_skill`、host persona 只用主 agent 说明书。子 agent 说明书由官方 subagent 的 prompt 带入；skill 由官方 `skill` 工具按需加载。

钉死版本见 `VERSIONS`：`@deepseek-ai/dsh@0.1.0-rc.6` 与 `deepseek-harness-sdk==0.1.0rc6`。Harness 是 developer preview，升级前要重测。

```bash
./scripts/dsh-web.sh
```

打开 http://127.0.0.1:3080 ，workspace 选本仓库根目录。人在 web 里说话；8002 只给工具调。这是唯一前端，交付 Word 路径在对话里交回。skill 正文在 `skills/`；仓库根 `.dsh/skills` 是指向这里的符号链接，不是第二套文件。

`cordis.patch.yml` 由启动脚本按本机绝对路径生成，不要把含本机路径的副本当源文件。源是 `cordis.patch.yml.tmpl`。
