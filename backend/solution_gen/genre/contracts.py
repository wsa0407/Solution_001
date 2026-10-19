from __future__ import annotations

from solution_gen.genre.models import BriefSlot, ChapterTemplate, GenreContract

_SLOTS = [
    BriefSlot(key="project_name", label="项目全称", required=True, question="项目全称是什么？"),
    BriefSlot(key="place", label="属地", required=True, question="项目在哪个市或县？"),
    BriefSlot(key="construction_unit", label="建设单位", required=True, question="建设单位是哪家？"),
    BriefSlot(key="budget", label="总投资", required=True, question="总投资大约多少万元？"),
    BriefSlot(key="construction_period", label="建设周期", required=True, question="建设周期多少个月？"),
    BriefSlot(key="compilation_unit", label="编制单位", required=False, question="编制单位是哪家？（没有可先空着）"),
    BriefSlot(key="funding_source", label="资金来源", required=False, question="资金来源是什么？例如自有资金、专项债、财政。"),
    BriefSlot(key="modules", label="建设模块", required=False, question="建设模块勾选哪些？选项以行业包 module_options 为准。"),
]

WRITING = {
    "overview": (
        "写概述，覆盖：项目名称、建设目标、建设地点、建设内容收口、建设周期、"
        "投资构成与资金来源、建设单位、编制依据（规范 / 政策 / 标准三清单）、主要结论预告。"
        "编制依据里的地方文件必须来自属地库或本次检索摘录，不要写「XX市相关规划」。"
        "建设内容用收口句（见写作要点里的数量化收口），不要改成四层架构总览。"
    ),
    "background": (
        "写建设背景与必要性：国家政策与地方政策分列，再写必要性与建设意义。"
        "地方政策必须能落到属地库条目或本次检索摘录。"
    ),
    "demand": (
        "写需求分析：业务、数据、性能、网络安全（或行业等价的非功能需求）。"
        "性能给指标，不要只用形容词。"
    ),
    "scheme": (
        "写建设方案。按已选模块展开，每个模块用其类型写法："
        "设施类＝设施设备 + 关键指标表 + 布设/选址原则；"
        "系统类＝平台概述 + 功能模块（深度以勾选为准，不要展开到七级菜单）；"
        "土建类＝选址/规模 + 主要工程内容；"
        "规划类＝规划对象 + 编制成果。"
        "禁止用「业务 / 应用 / 数据 / 技术」四层代替已选模块作为本章结构。"
        "文末与概述使用同一条建设内容收口句。"
    ),
    "reuse": "写资源共享与利旧：本单位既有资源、其他可利用资源、本项目可对外共享的资源。没有既有资产也要写清「新建为主、利旧范围」。",
    "ehs": "写环保、节能、职业安全卫生与消防。有土建或机房时必须结合建设内容，不要空套话。",
    "implementation": "写实施计划：分期、里程碑、组织。工期须与画像建设周期一致。出甘特则时间与正文一致。",
    "investment": (
        "写投融资与财务：编制依据、投资估算（建安 / 工程建设其他 / 预备费等构成）、资金来源。"
        "建议书深度为框算，不要写成可研级 IRR/NPV，除非文类是可研。"
        "总投资数字必须与画像一致。"
    ),
    "economy": "写经济评价：IRR、NPV、回收期等，口径与产品库/参数表同源。这是可研深度，不是建议书框算。",
    "compare": "写多方案比选：技术路线、建设规模或选址比选，给出推荐方案及理由。",
    "benefit": "写影响与效益：经济、社会、生态（及碳相关若建设内容涉及）。定性为主，数字须能在画像或产品库落地。",
    "risk": "写风险识别与对策：工程、管理、技术、安全、运营财务；含应急要点。",
    "conclusion": "写主要结论与建议。建设内容收口、投资、周期须与概述同一口径。列出需甲方决策事项。",
    "annex": "列附件、附图、附表清单（投资估算表、设备清单、总体框架图、甘特图等）。正文从简，不要再写一遍建设方案。",
    "initiation_basis": "写立项依据：政策、规划、上级要求，点名属地。地方文件必须来自属地库或本次检索摘录。",
    "scope": "写建设目标与范围：边界、不包含项、与需求要点对齐。",
    "overall": "写总体方案：与已选模块对齐的建设内容，不要四层套话代替模块。",
    "schedule_budget": "写进度与投资框算，数字与画像一致。",
    "safeguard": "写保障措施：组织、合规、风险。",
    "request": "写请示事项：需批准的事项清单。",
}

PROPOSAL = GenreContract(
    doc_type="solution",
    name="固定资产投资项目建议书",
    slots=_SLOTS,
    default_diagrams=["architecture", "gantt"],
    chapters=[
        ChapterTemplate(key="overview", title="概述", words=5000, writing="overview"),
        ChapterTemplate(key="background", title="项目建设背景及必要性", words=9000, writing="background"),
        ChapterTemplate(key="demand", title="项目需求分析", words=10000, writing="demand"),
        ChapterTemplate(
            key="scheme",
            title="项目建设方案",
            words=22000,
            writing="scheme",
            diagram=True,
            nest_modules=True,
        ),
        ChapterTemplate(key="reuse", title="资源共享、利旧方案", words=4000, writing="reuse"),
        ChapterTemplate(
            key="ehs",
            title="环保、节能、职业安全卫生与消防",
            words=5000,
            writing="ehs",
            when="has_civil",
        ),
        ChapterTemplate(key="plan", title="项目实施计划", words=7000, writing="implementation", diagram=True),
        ChapterTemplate(key="finance", title="项目投融资与财务方案", words=7000, writing="investment"),
        ChapterTemplate(key="benefit", title="项目影响与效益分析", words=6000, writing="benefit"),
        ChapterTemplate(key="risk", title="项目风险管控方案", words=5000, writing="risk"),
        ChapterTemplate(key="conclusion", title="主要结论和建议", words=3000, writing="conclusion"),
        ChapterTemplate(key="annex", title="附件、附图、附表", words=1500, writing="annex"),
    ],
)

FEASIBILITY = GenreContract(
    doc_type="feasibility",
    name="固定资产投资可行性研究",
    slots=_SLOTS,
    default_diagrams=["architecture", "gantt"],
    chapters=[
        ChapterTemplate(key="overview", title="项目概述", words=6000, writing="overview"),
        ChapterTemplate(key="background", title="建设背景与必要性", words=8000, writing="background"),
        ChapterTemplate(key="demand", title="需求分析", words=10000, writing="demand"),
        ChapterTemplate(
            key="scheme",
            title="建设方案",
            words=14000,
            writing="scheme",
            diagram=True,
            nest_modules=True,
        ),
        ChapterTemplate(key="compare", title="多方案比选", words=8000, writing="compare"),
        ChapterTemplate(key="plan", title="实施计划", words=7000, writing="implementation", diagram=True),
        ChapterTemplate(key="finance", title="投资估算", words=7000, writing="investment"),
        ChapterTemplate(key="economy", title="经济评价", words=8000, writing="economy"),
        ChapterTemplate(key="risk", title="风险与社会稳定", words=6000, writing="risk"),
        ChapterTemplate(key="conclusion", title="结论与建议", words=4000, writing="conclusion"),
    ],
)

INITIATION = GenreContract(
    doc_type="initiation",
    name="项目立项报告",
    slots=_SLOTS,
    default_diagrams=["architecture", "gantt"],
    chapters=[
        ChapterTemplate(key="basis", title="立项依据", words=5000, writing="initiation_basis"),
        ChapterTemplate(key="scope", title="建设目标与范围", words=6000, writing="scope"),
        ChapterTemplate(key="overall", title="总体方案", words=8000, writing="overall", diagram=True, nest_modules=True),
        ChapterTemplate(key="schedule", title="进度与投资", words=6000, writing="schedule_budget", diagram=True),
        ChapterTemplate(key="safeguard", title="保障措施", words=4000, writing="safeguard"),
        ChapterTemplate(key="request", title="请示事项", words=3000, writing="request"),
    ],
)

CONTRACTS = {
    "solution": PROPOSAL,
    "feasibility": FEASIBILITY,
    "initiation": INITIATION,
}
