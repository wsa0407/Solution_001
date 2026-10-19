from __future__ import annotations

from solution_gen.domain import Profile
from solution_gen.genre.models import IndustryPack, PackModule, WorkPackage

LOW_ALTITUDE = IndustryPack(
    id="low_altitude",
    name="低空经济",
    aliases=["低空", "低空经济", "低空经济产业", "智联网"],
    work_packages=[
        WorkPackage(id="ops", title="运营服务保障体系", unit="套"),
        WorkPackage(id="infra", title="新型基础设施", unit="批"),
        WorkPackage(id="scenes", title="场景应用", unit="系列"),
    ],
    modules=[
        PackModule(
            id="intelligent_network",
            title="低空智联网设施",
            kind="facility",
            package="infra",
            brief="通信、导航、监视、气象、反制等设施：设备、指标表、布设原则。",
        ),
        PackModule(
            id="vertiport",
            title="无人机及起降场设备",
            kind="facility",
            package="infra",
            brief="枢纽站、起降点、物流与治理无人机及配套设备。",
        ),
        PackModule(
            id="data_center",
            title="低空数据中心",
            kind="civil",
            package="infra",
            implies_civil=True,
            default=False,
            brief="数据中心建设内容与规模。",
        ),
        PackModule(
            id="ops_center",
            title="运营服务保障中心",
            kind="civil",
            package="ops",
            implies_civil=True,
            brief="保障中心土建与大屏、会议、网络、机房配套。",
        ),
        PackModule(
            id="training",
            title="低空考培基地",
            kind="civil",
            package="scenes",
            implies_civil=True,
            default=False,
            brief="培训、实践、考试区域。",
        ),
        PackModule(
            id="academy",
            title="低空研学基地",
            kind="civil",
            package="scenes",
            implies_civil=True,
            default=False,
            brief="研学场地与配套设施。",
        ),
        PackModule(
            id="planning",
            title="低空规划设计",
            kind="planning",
            package="ops",
            brief="空域、航线、基础设施规划与申请。",
        ),
        PackModule(
            id="flight_platform",
            title="低空飞行综合运营服务平台",
            kind="system",
            package="ops",
            brief="数字孪生、中台、规划/物联/反无/气象/飞行服务等平台，按概述+功能模块写。",
        ),
        PackModule(
            id="scene_platform",
            title="低空场景运营平台",
            kind="system",
            package="scenes",
            brief="已选场景对应的运营平台；未点名的场景不要展开到七级菜单。",
        ),
        PackModule(
            id="xinchuang",
            title="信创方案",
            kind="system",
            package="ops",
            default=False,
            brief="信创替代范围与实施安排。",
        ),
    ],
    scenes=["城市物流", "应急救援", "医疗转运", "教育培训", "政务巡检", "低空文旅", "编队表演"],
    terms=["低空智联网", "通感一体", "起降场", "运营服务保障中心"],
    term_aliases={"低空感知网": "低空智联网"},
)

PACKS: tuple[IndustryPack, ...] = (LOW_ALTITUDE,)


def _haystack(profile: Profile) -> str:
    return " ".join(
        part
        for part in (profile.industry, profile.project_name, profile.need, " ".join(profile.scenes))
        if part
    )


def resolve_pack(profile: Profile | None) -> IndustryPack | None:
    if profile is None:
        return None
    text = _haystack(profile)
    for pack in PACKS:
        names = (pack.name, pack.id, *pack.aliases)
        if profile.industry and any(n and n in profile.industry for n in names):
            return pack
        if any(alias and alias in text for alias in names):
            return pack
    if profile.industry.strip():
        return None
    return None


def apply_pack(profile: Profile) -> Profile:
    pack = resolve_pack(profile)
    if pack is None and not profile.industry.strip() and len(PACKS) == 1:
        pack = PACKS[0]
    if pack is None:
        return profile
    if not profile.industry.strip():
        profile.industry = pack.name
    if not profile.modules:
        profile.modules = [m.id for m in pack.modules if m.default]
    return profile


def selected_modules(profile: Profile | None) -> list[PackModule]:
    pack = resolve_pack(profile)
    if pack is None or profile is None:
        return []
    wanted = set(profile.modules)
    if not wanted:
        return [m for m in pack.modules if m.default]
    found = [m for m in pack.modules if m.id in wanted or m.title in wanted]
    return found or [m for m in pack.modules if m.default]


def has_civil(profile: Profile | None) -> bool:
    return any(m.implies_civil or m.kind == "civil" for m in selected_modules(profile))


def closer_sentence(profile: Profile | None) -> str:
    pack = resolve_pack(profile)
    mods = selected_modules(profile)
    if pack is None or not mods:
        need = (profile.need if profile else "") or "按需求要点展开。"
        return need.strip().split("\n")[0][:80]
    used = {m.package for m in mods}
    parts: list[str] = []
    for pkg in pack.work_packages:
        if pkg.id in used:
            parts.append(f"1{pkg.unit}{pkg.title}")
    scenes = [s for s in (profile.scenes if profile else []) if s]
    if scenes and any(m.package == "scenes" for m in mods):
        return "、".join(parts) + f"（{'、'.join(scenes)}）"
    return "、".join(parts) or (profile.need if profile else "")


def kind_label(kind: str) -> str:
    return {
        "facility": "设施类：设备 + 指标表 + 布设原则",
        "system": "系统类：概述 + 功能模块",
        "civil": "土建类：选址/规模 + 工程内容",
        "planning": "规划类：对象 + 编制成果",
        "service": "服务类：组织 + 服务内容",
    }.get(kind, kind)
