---
name: diagram-design
description: 按已确认文字说明画一张架构 / 流程 / 甘特自包含 HTML。画法对齐 cathrynlavery/diagram-design 总册。画完交给 attach-diagram。
---

# diagram-design

只画**一张**图。说明必须已经 `confirm-diagram-spec`。节点、关系、步骤、工期只来自已确认 `spec_text`，禁止改成「业务 / 应用 / 数据 / 技术」四层信息化套话。

本说明书是画法册（MIT 子集，出自 [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design)）。先读参考与 `assets/` 范例，再出 HTML，再交给 `solution_skill`。不要 bash 写文件绕过硬门。**不要 skip-qa**（没有 skip-qa 工具）。

不要 onboarding、品牌档案、另外二十几种图、draw.io / Mermaid 导入、动效、手绘风、暗色/terminal 变体。本产品只用 **Minimal light**。

## 只路由三种

| kind | 读这些 | 临摹范例 |
|---|---|---|
| `architecture`（总体框架图） | `references/style-guide.md` + `references/type-architecture.md` | `assets/example-architecture.html` |
| `flowchart`（流程图） | `references/style-guide.md` + `references/type-flowchart.md` | `assets/example-flowchart.html` |
| `gantt`（甘特图） | `references/style-guide.md` + `references/type-gantt.md` | `assets/example-gantt.html` |

**Always load the matching `references/type-*.md` before drawing.** Copy `assets/template.html` as the page shell, then replace the SVG body using the type example as the geometric grammar. Content (node names, edges, tasks) comes from `spec_text`, not from the example's sample labels.

## 1. Philosophy

**The highest-quality move is usually deletion.**

- Every node represents a distinct idea. Two nodes that always travel together are one node.
- Every connection carries information. If the relationship is obvious from layout, remove the line.
- Coral is **editorial, not a flag.** 1–2 focal nodes per diagram. Using it on 5 nodes erases the signal.
- The schematic isn't done when everything is added. It's done when nothing can be removed.

**Target density: 4/10.** Enough to be technically complete. Not so dense it needs a guide. Above 9 nodes, it's probably two diagrams.

## 4. Universal Anti-patterns

| Anti-pattern | Why it fails |
|---|---|
| Dark mode + cyan/purple glow | Looks "technical" without design decisions |
| JetBrains Mono as blanket "dev" font | Mono is for *technical* content — ports, commands, URLs. Names go in Geist sans. |
| Identical boxes for every node | Erases hierarchy |
| Legend floating inside the diagram area | Collides with nodes |
| Arrow labels with no masking rect | Bleeds through the line |
| Vertical `writing-mode` text on arrows | Unreadable |
| 3 equal-width summary cards as default | Generic grid — vary widths |
| Shadow on any element | Shadows are out. Borders are in. |
| `rounded-2xl` on boxes | Max radius 6–10px or none |
| Coral on every "important" node | Coral is 1–2 editorial accents, not a signaling system |
| Reproducing Mermaid's renderer layout | Imports automatic spacing and routing instead of making an editorial layout |
| Diagonal / slanted connectors between off-axis nodes | Rounded right-angle (orthogonal) elbows are mandatory — see §6 |
| Arrow label sitting on or touching its connector | Label must have a 6–10px gap above the line |
| Arrow label mask overlapping a node box | Nodes paint after labels — the fill clips the text |
| Two connectors overlapping or running on the same path | Bridge crossings, offset parallels |
| Two connectors sharing a single attach point on a box | Fan attach points along the edge (≥12px apart) |

Type-specific anti-patterns live in each `references/type-*.md`.

## 5. Design System

All colors, typography, and tokens live in [`references/style-guide.md`](references/style-guide.md). Look up current hex values there. Do not run onboarding or rewrite the style guide.

| Role | Purpose |
|---|---|
| `paper`, `paper-2` | Page bg and container bg |
| `ink` | Primary text / stroke |
| `muted`, `soft` | Secondary text, default arrows, sublabels |
| `rule`, `rule-solid` | Hairline borders |
| `accent`, `accent-tint` | 1–2 focal elements per diagram |
| `link` | HTTP/API calls, external arrows |

**Focal rule:** `accent` goes on 1–2 elements max. Everything else is `ink` / `muted` / `soft`.

| Type | Fill | Stroke |
|---|---|---|
| **Focal** (1–2 max) | `accent-tint` | `accent` |
| **Backend / API / Step** | white | `ink` |
| **Store / State** | `ink @ 0.05` | `muted` |
| **External / Cloud** | `ink @ 0.03` | `ink @ 0.30` |
| **Input / User** | `muted @ 0.10` | `soft` |
| **Optional / Async** | `ink @ 0.02` | `ink @ 0.20` dashed `4,3` |
| **Security / Boundary** | `accent @ 0.05` | `accent @ 0.50` dashed `4,4` |

- **Title** — Instrument Serif, 1.75rem, 400 — H1 only
- **Node name** — Geist (sans), 12px, 600
- **Sublabel** — Geist Mono, 9px
- **Eyebrow / tag** — Geist Mono, 7–8px, uppercase, tracked
- **Arrow label** — Geist Mono, 8px

Google Fonts 链接与上游一致；没有网时系统回退。PNG 栅格看 SVG 几何，不依赖网页字体。

```html
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

## 6. Core SVG Primitives

### Background

**Default: clean paper, no dot pattern.** Single `<rect>` filled with `paper`. Don't wrap the diagram in a secondary container background.

```svg
<rect width="100%" height="100%" fill="#f5f5f5"/>
```

### Arrow markers (define all three, always)

```svg
<marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
  <polygon points="0 0, 8 3, 0 6" fill="#4f5d75"/>
</marker>
<marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
  <polygon points="0 0, 8 3, 0 6" fill="#eb6c36"/>
</marker>
<marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
  <polygon points="0 0, 8 3, 0 6" fill="#2e5aa8"/>
</marker>
```

**Draw arrows before boxes** so z-order puts lines behind nodes.

### Mandatory connector rules

These six rules are **non-negotiable**.

1. **Rounded right-angle (orthogonal) connectors are mandatory.** Never use diagonal `<line>` between nodes that don't share an x or y axis. Every bend is a quarter-arc with `r=8` (or `r=6` minimum). Elbow formula is in `references/type-architecture.md`. Plain `<line>` only when endpoints share x or y.
2. **Label-to-connector margin: 6–10px gap, always.** A label must never sit on its arrow. Opaque mask rect, visible gap between mask edge and stroke.
3. **No overlapping connectors.** Crossings use the bridge / hop in `type-architecture.md`. Offset parallels by ≥12px.
4. **Shared edge → fan the attach points.** No two connectors share a single point on a box. ≥12px between adjacent points.
5. **A connector must not pass behind a box that isn't its source or destination**, except the unavoidable-intervening-box case (then dashed, label at visible end, marker only at true destination). When in doubt, reroute.
6. **A label mask must not overlap a node drawn after it.** Place labels on open canvas. (Do not run upstream `verify-geometry.py`; this repo does not ship that script.)

### Node box — full pattern

```svg
<rect x="X" y="Y" width="W" height="H" rx="6" fill="#f5f5f5"/>
<rect x="X" y="Y" width="W" height="H" rx="6" fill="FILL" stroke="STROKE" stroke-width="1"/>
<rect x="X+8" y="Y+6" width="28" height="12" rx="2" fill="transparent" stroke="STROKE@0.40" stroke-width="0.8"/>
<text x="X+22" y="Y+15" fill="STROKE@0.8" font-size="7" font-family="'Geist Mono', monospace"
      text-anchor="middle" letter-spacing="0.08em">API</text>
<text x="CX" y="CY+2" fill="#2d3142" font-size="12" font-weight="600"
      font-family="'Geist', sans-serif" text-anchor="middle">Node Name</text>
<text x="CX" y="CY+18" fill="#4f5d75" font-size="9"
      font-family="'Geist Mono', monospace" text-anchor="middle">tech:port</text>
```

### Arrow labels — always mask, always with margin

```svg
<rect x="MID_X-18" y="ARROW_Y-20" width="36" height="12" rx="2" fill="#f5f5f5"/>
<text x="MID_X" y="ARROW_Y-11" fill="#7a8399" font-size="8"
      font-family="'Geist Mono', monospace" text-anchor="middle" letter-spacing="0.06em">WRITE</text>
```

≤14 characters, all-caps. Never `writing-mode` vertical. Vertical segments: label to the side with the same 6–10px gap.

### Legend — horizontal strip at the bottom

Never inside the diagram area. Hairline separator, then a horizontal row. Expand `viewBox` height by ~60px.

## 7. Layout & Spacing

**All values — font sizes, padding, node dimensions, gaps, x/y coords — divisible by 4.**

| Category | Allowed values |
|---|---|
| Font sizes | 8, 12, 16, 20, 24, 28, 32, 40 |
| Node width / height | 80, 96, 112, 120, 128, 140, 144, 160, 180, 200, 240, 320 |
| x / y coordinates | multiples of 4 |
| Gap between nodes | 20, 24, 32, 40, 48 |
| Padding inside boxes | 8, 12, 16 |
| Border radius | 4, 6, 8 |

Exempt: stroke widths (0.8, 1, 1.2), opacity values.

### Complexity budget (this product)

| Limit | Rule |
|---|---|
| Max nodes | 9 |
| Max arrows / transitions | 12 |
| Max coral elements | 2 |
| Max tasks (Gantt) | 12 |

If you exceed, split into two diagrams (overview + detail) — still one HTML per `attach-diagram` call; the next figure waits for its own spec confirm.

### Page layout

1. **Header** — eyebrow (Geist Mono), title (Instrument Serif), optional subtitle.
2. **Diagram** — clean, borderless SVG on page paper. **No `box-shadow`.**
3. **Footer** — optional colophon in Geist Mono. This product does not require summary cards.

## 9. Pre-Output Checklist (Taste Gate)

Run before producing any diagram.

- [ ] Right type among architecture / flowchart / gantt? Matching `type-*.md` loaded?
- [ ] Nodes and labels from confirmed `spec_text`, not 四层套话, not example-file sample names left in place?
- [ ] Can I remove any node / merge two / drop an obvious arrow?
- [ ] Coral on ≤2 elements? Within complexity budget?
- [ ] `<svg>` has `role="img"` and `aria-labelledby` to prefixed `<title>` / `<desc>`? Title is first child, before `<defs>`.
- [ ] Arrows drawn before boxes?
- [ ] Off-axis connectors use rounded right-angle elbows (`r=8`)? No diagonal slants?
- [ ] Every arrow label has a 6–10px gap and an opaque paper mask?
- [ ] No overlapping connectors; shared edges fan attach points ≥12px?
- [ ] No label mask overlapping a later-painted node?
- [ ] Legend is a bottom strip? `viewBox` includes it?
- [ ] Every font size, coord, width, height, gap divisible by 4?
- [ ] No external `<script src>`? No shadows? Single file (Google Fonts link allowed)?
- [ ] Names in Geist sans, technical sublabels in Geist Mono, page title in Instrument Serif? No JetBrains Mono?

## 10. Templates

本产品只用 Minimal light：

1. 以 `assets/template.html` 为壳。
2. 用对应 `assets/example-<type>.html` 的 SVG 几何当语法，**内容换成 `spec_text`**。
3. 跑 §9。
4. 不要 dark / full / motion / sketchy / terminal 变体。

## 交给 8002

不要自己落盘，不要按上游 `export.md` 另存 PNG。调用：

```
solution_skill
  action: attach-diagram
  job_id: 必填
  kind: architecture | flowchart | gantt
  html: 刚才画出的自包含 HTML
```

## 硬门

- 未确认禁止画、禁止 attach。
- 一次只画一张；下一张由 `emit-diagrams` 再走说明与确认。
- 禁止 bash / 手写 HTML 文件绕过 `attach-diagram`。
- **没有 skip-qa。禁止**把它当成可用工具。
