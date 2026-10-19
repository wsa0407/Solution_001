import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'solution-gen-tools'
export const inject = ['tools']

const backend = process.env.SOLUTION_BACKEND_URL || 'http://127.0.0.1:8002'

const ACTIONS =
  'create-job, status, collect-brief, draft-outline, edit-outline, write-chapters, request-diagram, skip-diagrams, emit-diagrams, polish-deliver, rewrite-chapter, swap-material, revise, deliver, draft-diagram-spec, confirm-diagram-spec, attach-diagram'

async function callBackend(action: string, payload: Record<string, unknown>, signal?: AbortSignal): Promise<string> {
  const key = String(action || '').replace(/_/g, '-').toLowerCase()
  if (key === 'skip-qa' || key === 'skipqa') {
    return JSON.stringify({ ok: false, error: '没有 skip-qa 工具。质检失败只能 rewrite 或 swap-material。' })
  }
  const res = await fetch(`${backend}/api/skills/${encodeURIComponent(action)}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  const text = await res.text()
  if (!res.ok) {
    return JSON.stringify({ ok: false, error: `backend ${res.status}: ${text.slice(0, 800)}` })
  }
  return text
}

export function apply(ctx: { tools: { register: (tool: unknown) => void } }) {
  ctx.tools.register(
    defineTool({
      name: 'solution_skill',
      description:
        '方案生产硬门工具。action 为 collect-brief / draft-outline / write-chapters / emit-diagrams / polish-deliver 等。没有 skip-qa。字段未齐不能出目录，未确认目录不能写正文。主 agent 只许 action=status；写作由子 agent 调用。',
      parameters: {
        action: {
          type: 'string',
          required: true,
          description: `工具名：${ACTIONS}。禁止 skip-qa。`,
        },
        job_id: { type: 'string', description: '任务 id；collect-brief 新建时可省略' },
        text: { type: 'string', description: '操作者原话或改目录指令' },
        doc_type: { type: 'string', description: 'solution | feasibility | initiation' },
        project_name: { type: 'string' },
        place: { type: 'string' },
        construction_unit: { type: 'string' },
        compilation_unit: { type: 'string' },
        funding_source: { type: 'string' },
        budget: { type: 'number', description: '总投资万元' },
        construction_period: { type: 'number', description: '建设周期月' },
        industry: { type: 'string' },
        need: { type: 'string' },
        modules: { type: 'array', items: { type: 'string' }, description: '已选建设模块 id' },
        kind: { type: 'string', description: 'architecture | flowchart | gantt' },
        html: { type: 'string', description: 'attach-diagram 的自包含 HTML' },
        placement: { type: 'string' },
        reference: { type: 'string' },
        chapter_id: { type: 'string' },
        instruction: { type: 'string' },
        material_title: { type: 'string' },
        op: { type: 'string', description: 'polish-deliver 子操作：run-qa | rewrite | swap | revise | deliver' },
        owner: { type: 'string' },
      },
      output: {
        schema: { type: 'string' },
        render: (_args, value) => [{ type: 'text', text: value }],
      },
      async execute(args, exec) {
        const { action, ...rest } = args
        const payload: Record<string, unknown> = {}
        for (const [k, v] of Object.entries(rest)) {
          if (v !== undefined && v !== null && v !== '') payload[k] = v
        }
        return callBackend(String(action), payload, exec.signal)
      },
    }),
  )
}
