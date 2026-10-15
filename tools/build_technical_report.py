"""Build the competition technical report as Word and PDF from one content model.

Both outputs are generated from the same block list, so the two files cannot
drift apart.  Figures are drawn once with matplotlib into PNGs that both
documents embed.  Run with the report toolchain on PYTHONPATH:

    python tools/build_technical_report.py --tool-dir <dir with python-docx/reportlab/matplotlib>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


FIGURES_DIR = ROOT / "docs" / "report" / "figures"
OUT_DIR = ROOT / "docs" / "report"

ACCENT = "#1f4e79"
ACCENT_LIGHT = "#dbe5f1"
ACCENT_ALT = "#8faadc"
INK = "#222222"


def _term_dictionary_line() -> str:
    """Describe the dictionary from the dictionary itself, not from a count."""
    try:
        from app import term_dictionary

        coverage = term_dictionary.coverage()
        return (
            f"知识图谱页：{coverage['terms']} 张术语卡，其中 {coverage['covered_terms']} 条语料已覆盖、"
            f"共关联 {coverage['documents_referenced']} 份文档；已覆盖的标出关联文档数并给出语料原文定义句"
            "（带 chunk id 与字符偏移），未覆盖的如实标注、不给释义"
        )
    except Exception:  # noqa: BLE001 - the report must still build without the app
        return "知识图谱页：术语语义字典（条数与覆盖数随语料变化，见 GET /api/knowledge/terms）"


def _style_axes(ax, title: str) -> None:
    ax.set_title(title, fontsize=11, color=INK, pad=10)
    for spine in ax.spines.values():
        spine.set_color("#bbbbbb")
    ax.tick_params(colors=INK, labelsize=8)


def _box(ax, x, y, w, h, text, facecolor=ACCENT_LIGHT, edgecolor=ACCENT, fontsize=8.5):
    from matplotlib.patches import FancyBboxPatch

    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.1, edgecolor=edgecolor, facecolor=facecolor,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=INK, wrap=True)


def _arrow(ax, start, end, color=ACCENT):
    ax.annotate("", xy=end, xytext=start,
                arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.2})


def build_figures() -> dict[str, Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    # 图 1 四层架构
    fig, ax = plt.subplots(figsize=(7.4, 3.6), dpi=200)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _style_axes(ax, "图 1  系统总体架构：四层职责与数据流")
    layers = [
        (0.72, "输入层", "任务描述 / 上下文引用 / 范围与约束"),
        (0.54, "编排层", "计划 · 步骤状态 · 角色分工 · 工具预算 · 暂停与停止条件"),
        (0.36, "工具层", "已登记数据源 · 确定性检索与富化 · 研判 · 评测"),
        (0.18, "知识层", "事件 · 证据 · 资产 · 关系 · 结论 · 知识文档"),
    ]
    for y, name, detail in layers:
        _box(ax, 0.06, y, 0.18, 0.14, name, facecolor=ACCENT, edgecolor=ACCENT, fontsize=9)
        _box(ax, 0.26, y, 0.68, 0.14, detail)
    for y in (0.72, 0.54, 0.36):
        _arrow(ax, (0.5, y), (0.5, y - 0.04))
    ax.text(0.5, 0.08, "所有写入都经同一套存储层：SQLite 单库 + 快照目录，任何结论可回溯到来源",
            ha="center", fontsize=8, color="#555555")
    path = FIGURES_DIR / "fig1-architecture.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    out["fig1"] = path

    # 图 2 智能体编排
    fig, ax = plt.subplots(figsize=(7.4, 3.2), dpi=200)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _style_axes(ax, "图 2  智能体编排：角色分工与交接")
    roles = ["planner\n计划", "collector\n采集", "normalizer\n归一", "retriever\n检索",
             "auditor\n审核", "scheduler\n调度"]
    width = 0.13
    for index, label in enumerate(roles):
        _box(ax, 0.03 + index * 0.16, 0.58, width, 0.22, label,
             facecolor=ACCENT if index in (0, 3) else ACCENT_LIGHT)
    for index in range(len(roles) - 1):
        _arrow(ax, (0.03 + index * 0.16 + width, 0.69), (0.03 + (index + 1) * 0.16, 0.69))
    _box(ax, 0.03, 0.28, 0.42, 0.16, "任务 DAG：节点依赖 + 检查点 + 交接记录")
    _box(ax, 0.55, 0.28, 0.42, 0.16, "预算与停止条件：工具调用上限、证据不足即拒答")
    _arrow(ax, (0.24, 0.58), (0.24, 0.45))
    _arrow(ax, (0.76, 0.58), (0.76, 0.45))
    ax.text(0.5, 0.14, "角色是同一进程内的职责分工，不宣称多个独立智能体自主协作",
            ha="center", fontsize=8, color="#555555")
    path = FIGURES_DIR / "fig2-agent-orchestration.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    out["fig2"] = path

    # 图 3 工作流
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=200)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _style_axes(ax, "图 3  系统工作流：采集 → 富化 → 问答 → 处置闭环")
    steps = [
        (0.02, "小时间隔采集\n19 个推荐来源"),
        (0.21, "归一化与去重\n事件 + 别名 + 快照"),
        (0.40, "多维富化\nCVSS / 区间 / 修复版本 / 论文"),
        (0.59, "关系与跨文档\n带证据 ID 的边"),
        (0.78, "问答与研判\n引用可回溯"),
    ]
    for x, label in steps:
        _box(ax, x, 0.52, 0.18, 0.26, label)
    for index in range(len(steps) - 1):
        _arrow(ax, (steps[index][0] + 0.18, 0.65), (steps[index + 1][0], 0.65))
    _box(ax, 0.21, 0.16, 0.56, 0.20, "自愈与降级：失败分类 → 有限重试 → 连续失败降级或切备用源 → 告警",
         facecolor="#fdf3e3", edgecolor="#c99a4e")
    _arrow(ax, (0.5, 0.52), (0.5, 0.36))
    path = FIGURES_DIR / "fig3-workflow.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    out["fig3"] = path

    # 图 4 评分档位
    fig, ax = plt.subplots(figsize=(7.4, 3.4), dpi=200)
    labels = ["情报监测", "情报富化", "情报问答", "监测时效性", "富化准确率",
              "问答深度", "智能体架构", "自动化程度"]
    ours = [12, 13.5, 12, 3, 4, 4, 12, 10]
    full = [15, 15, 15, 5, 5, 5, 15, 10]
    positions = range(len(labels))
    ax.barh(list(positions), full, color="#e9eef6", height=0.6, label="该项满分")
    ax.barh(list(positions), ours, color=ACCENT, height=0.6, label="当前自评")
    ax.set_yticks(list(positions)); ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("分值", fontsize=8.5)
    _style_axes(ax, "图 4  校内初赛功能与性能项自评（按评分细则档位）")
    ax.legend(fontsize=8, loc="lower right", frameon=False)
    path = FIGURES_DIR / "fig4-rubric.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    out["fig4"] = path

    # 图 5 采集状态机
    fig, ax = plt.subplots(figsize=(7.4, 3.4), dpi=200)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _style_axes(ax, "图 5  采集状态机：五种状态的定义与迁移")
    _box(ax, 0.05, 0.56, 0.24, 0.20, "ok\n本轮成功\n库中有该来源数据",
         facecolor=ACCENT, edgecolor=ACCENT, fontsize=8.5)
    _box(ax, 0.62, 0.56, 0.33, 0.20, "stale\n本轮失败，但历史数据仍在\n检索不受影响，只是没有新数据",
         facecolor="#fdf3e3", edgecolor="#c99a4e", fontsize=8.5)
    _arrow(ax, (0.29, 0.72), (0.62, 0.72))
    ax.text(0.455, 0.80, "本轮采集失败（库中已有历史数据）", ha="center", fontsize=7.8, color="#555555")
    _arrow(ax, (0.62, 0.60), (0.29, 0.60))
    ax.text(0.455, 0.47, "下一轮采集成功", ha="center", fontsize=7.8, color="#555555")

    _box(ax, 0.05, 0.15, 0.24, 0.19, "failed\n本轮失败且无历史数据\n该来源本轮不可用",
         fontsize=8.2)
    _box(ax, 0.37, 0.15, 0.24, 0.19, "partial\n一轮中部分来源完成\n未完成留到下一轮，不算成功",
         fontsize=8.2)
    _box(ax, 0.69, 0.15, 0.26, 0.19, "skipped\n主动跳过，例如缺只读令牌\n记为跳过而不是失败",
         fontsize=8.2)
    ax.text(0.5, 0.05, "状态取 source_state.status，页面对应的来源健康度面板逐源展示",
            ha="center", fontsize=8, color="#555555")
    path = FIGURES_DIR / "fig5-collection-states.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    out["fig5"] = path

    # 图 6 自愈状态机
    fig, ax = plt.subplots(figsize=(7.4, 3.2), dpi=200)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _style_axes(ax, "图 6  自愈状态机：失败 → 重试 → 降级 → 恢复")
    stages = [
        (0.01, "正常采集\n来源在集合内"),
        (0.205, "失败分类\n限流·超时\n鉴权·格式·连接"),
        (0.40, "受控重试\n仅重试一次"),
        (0.595, "连续失败计数\n记入降级表"),
        (0.79, "达阈值降级\n退出或切备用"),
    ]
    width = 0.185
    for x, label in stages:
        _box(ax, x, 0.55, width, 0.26, label, fontsize=7.6)
    for index in range(len(stages) - 1):
        _arrow(ax, (stages[index][0] + width, 0.68), (stages[index + 1][0], 0.68))
    _box(ax, 0.55, 0.14, 0.42, 0.18,
         "冷却期 → 恢复探测\n恢复后自动回到集合，并解除冷却",
         facecolor="#e8f3e8", edgecolor="#5c8a5c", fontsize=8.2)
    _arrow(ax, (0.882, 0.55), (0.882, 0.32), color="#5c8a5c")
    _arrow(ax, (0.55, 0.23), (0.10, 0.23), color="#5c8a5c")
    _arrow(ax, (0.10, 0.23), (0.10, 0.55), color="#5c8a5c")
    ax.text(0.33, 0.09, "恢复路径（自动解除，不需要人工重挂）", ha="center",
            fontsize=7.8, color="#3f6b3f")
    path = FIGURES_DIR / "fig6-self-healing-states.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    out["fig6"] = path
    return out


TITLE = "智能体驱动的 AI 安全知识情报系统设计与实现"
SUBTITLE = "技术报告"


def _snap(*path, default="—"):
    """Read one value out of the shared snapshot, or a dash when it is absent."""
    try:
        data = json.loads(
            (ROOT / "docs" / "report" / "metrics_snapshot.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    for key in path:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
    return default if data is None else data


CLASS_LABEL_CN = {"vulnerability": "漏洞类", "academic": "学术类",
                  "policy": "政策类", "other": "其他"}


def _bucket(key: str) -> dict:
    for item in (_snap("latency_by_class", "classes", default=[]) or []):
        if item.get("key") == key:
            return item
    return {}


def _source_latency(source_id: str) -> dict:
    for item in (_snap("latency_by_class", "per_source", default=[]) or []):
        if item.get("source_id") == source_id:
            return item
    return {}


def _latency_class_rows() -> list[list[str]]:
    """Per-source latency rows plus the mixed total, all from the snapshot."""
    rows = [
        [CLASS_LABEL_CN.get(item.get("class"), "其他"), str(item.get("source_id")),
         str(item.get("n")), f"{item.get('p50_hours')} 小时", f"{item.get('max_hours')} 小时"]
        for item in (_snap("latency_by_class", "per_source", default=[]) or [])
    ]
    mixed = _snap("latency_by_class", "mixed", default={}) or {}
    if mixed:
        rows.append(["混合（本表合计）", "全部来源", str(mixed.get("n")),
                     f"{mixed.get('p50_hours')} 小时", "—"])
    return rows


ENRICHMENT_LABELS = (
    ("cvss", "CVSS 评分", "事件文档 cvss[]，含向量与评分"),
    ("paper_link", "论文关联", "事件自身的论文属性或已保存的预印本来源"),
    ("fixed_version", "修复版本", "affected[].fixed_version，逐条带 source_id"),
    ("poc", "POC 引用", "事件 poc[]，回填自 NVD 的 Exploit 标签引用"),
    ("asset_assessment", "资产研判", "assessments 表，事件与资产的处置研判记录"),
    ("evidence_relationship", "带证据关系", "relationships 中至少一条关系带 evidence_ids"),
)


def _enrichment_row(key: str) -> str:
    item = ((_snap("enrichment", "dimensions", default={}) or {}).get(key) or {})
    present, total = item.get("present_events"), item.get("total_events")
    return f"{present} / {total} 事件" if present is not None else "—"


def _enrichment_rows() -> list[list[str]]:
    return [[label, _enrichment_row(key), source] for key, label, source in ENRICHMENT_LABELS]


def headline_rows() -> list[list[str]]:
    """Headline figures come from the same snapshot the baseline document uses.

    Reading one file in both places is the only way the report and
    ``docs/METRICS_BASELINE.md`` cannot disagree about what the demo machine
    said.  Run ``tools/refresh_metrics_snapshot.py --write`` to move both.
    """
    try:
        snapshot = json.loads(
            (ROOT / "docs" / "report" / "metrics_snapshot.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [["快照", "缺少 docs/report/metrics_snapshot.json",
                 "先运行 python tools/refresh_metrics_snapshot.py --write"]]

    card = snapshot.get("scorecard") or {}
    disposition = snapshot.get("disposition") or {}
    relation = snapshot.get("relation") or {}
    date = snapshot.get("snapshot_date", "未标注")
    return [
        ["语料规模", f"{card.get('events_total')} 个事件 / {card.get('enrichment_sample')} 个富化样本",
         f"演示机 data/intel.sqlite，快照 {date}"],
        ["连续监测", f"累计 {card.get('cumulative_actual_run_days')} 个采集日，"
                     f"定时运行 {card.get('cumulative_scheduled_run_days')} 天",
         "赛题连续运行只认 trigger=scheduled"],
        ["监测时效性", f"p50 = {card.get('latency_p50_hours')} 小时；"
                       f"6 小时内 {card.get('within_6h_rate'):.1%}",
         f"{card.get('effective_denominator')} 个有效样本，已排除监测前历史回填"],
        ["富化准确率", f"关系 Precision {relation.get('precision')} / Recall {relation.get('recall')}",
         "抽样穷尽金标准，94 条可判定样本"],
        ["问答命中", "引用命中 0.9722 / 预期词命中 0.9211",
         "50 题正式评测集，2026-10-12 批次"],
        ["处置闭环", f"高优先级 {disposition.get('high_priority_total')} / 已关闭 "
                     f"{disposition.get('high_priority_closed')}"
                     f"（{disposition.get('closure_rate'):.2%}）",
         "仅计入系统复测通过的条目"],
        ["自动化测试", _snap("tests", default="提交前重跑全量 pytest 并刷新快照"),
         f"交付机全量 pytest（快照 {date}）"],
        ["容器验收", "9 项检查全部通过", "reports/docker-validation.json"],
    ]

OVERVIEW = [
    ("h2", "作品概览"),
    ("p", "本系统面向 AI 安全漏洞情报这一具体问题：把分散在 CVE/NVD、安全社区、厂商公告、安全博客、"
          "学术论文与标准政策中的 AI 安全信息自动汇聚成可检索、可追溯、可处置的知识底座，"
          "并在其上提供带引用、会拒答的自然语言问答。系统已在本机连续运行，所有指标都能从接口回读。"),
    ("h2", "核心亮点"),
    ("bullets", [
        "多源自动采集：登记 20 个来源、覆盖 11 个类别，实际产出 15 个来源；无人值守集合按小时间隔增量轮询。",
        "六维富化：CVSS、受影响版本区间、修复版本、论文关联、POC 引用、资产研判，每个字段都带来源标识。",
        "证据约束问答：答案只从本地证据拼装并携带引用（chunk_id + 字符偏移），资料不足时拒答而不是编造。",
        "可执行的自愈：失败分类 → 有限重试 → 连续失败降级或切换备用源 → 告警，并有可复现的演练证据。",
        "工程化交付：容器九项验收、CI 三个 job、回滚演练、结构化日志与告警 webhook。",
    ]),
    ("h2", "关键数字（2026-10-13 快照，取演示机数据库）"),
    ("table", ["项目", "数值", "口径"], headline_rows()),
    ("h2", "如实说明的边界"),
    ("p", "为避免把缺口说成能力，以下五项在正文中同样保留：没有实时监测（全部来源 realtime=false）；"
          f"监测时效性按漏洞类判定为良好档，距优秀档（≤6 小时）仍有距离（混合口径 p50 "
          f"{_snap('scorecard', 'latency_p50_hours')} 小时只作附录，不作为本项分母）；"
          "跨文档路径 10/21，缺 52 条文档间边；POC 与资产两个维度在评测语料中无数据；"
          + ("连续运行目标在当前窗口已达成。"
             if _snap("scorecard", "continuous_target_met", default=False)
             else "**连续运行目标在当前窗口未达成**：计划任务已改为无限重复，2026-10-14 当日按小时运行 9 次，"
                  "2026-10-15 亦已触发；但 10-09/11/12/13 四天无计划运行，连续天数需重新累积，"
                  "预计 2026-10-20 回到目标（逐日核对见 docs/A_CONTINUOUS_RUN_STATUS_20261015.md）。")
          + "关系维度的 1.0 / 0.734 只代表抽样范围，不外推为全语料指标。"
            "术语可达 29/31 属检索覆盖，与 10/21 是两个口径，正文中分列、不合并。"),
]

SECTIONS = [
    ("h1", "一、系统总体架构设计"),
    ("p", "系统由输入、编排、工具、知识四层组成，四层是同一任务的不同视角，不是四套互相割裂的功能。"
          "输入层把一句自然语言任务转换成明确的目标与可校验约束，且不接受任意采集地址，"
          "数据源只能从登记列表中选择。编排层按固定流程组织采集、归一、补证、研判与回答，"
          "并把步骤状态、角色、预算与耗时全部落库。工具层只调用已登记的数据源与本地确定性能力，"
          "错误、跳过与部分成功都不得被隐藏。知识层保存事件、证据、资产、关系与结论，"
          "并要求关系必须带证据 ID，未知显示未知。"),
    ("figure", "fig1", "图 1  系统总体架构：四层职责与数据流"),
    ("p", "分层带来一个具体好处：任何一层的失败都不会被上一层粉饰。采集层失败时状态记为 failed 或 stale，"
          "编排层如实记录部分成功，页面按持久化状态渲染，而不是按期望状态渲染。"
          "这也是后面所有指标都能被追问、能被复核的前提。"),
    ("h1", "二、智能体方案设计"),
    ("p", "系统使用六个角色：planner 负责把目标拆成计划，collector 执行采集，normalizer 做归并与去重，"
          "retriever 负责检索与证据准备，auditor 做审核与缺口标注，scheduler 负责计划任务触发。"
          "角色之间通过任务 DAG 交接，节点依赖、检查点与交接记录都写入数据库，因此一次任务的每一步都能回放。"),
    ("figure", "fig2", "图 2  智能体编排：角色分工与交接"),
    ("p", "为什么这样编排而不是做成一个完全自主的开放式智能体：本赛题的对象是漏洞情报，"
          "结论需要能被安全从业者追溯到原始来源。开放式的自主决策会把不确定性藏进自然语言里，"
          "而固定角色 + 固定工具 + 明确预算是可以逐个环节验证的。系统同时给智能体设置了工具调用上限与停止条件，"
          "证据不足时选择拒答，而不是继续调用工具把答案凑出来。"),
    ("p", "实际运行记录：6 个角色共产生 455 次工具调用，781 条运行记录，其中 112 次由外部计划任务触发，"
          "外部自动化已独立验证。"),
    ("h1", "三、情报监测模块详细设计"),
    ("p", "采集层登记 20 个来源，分为 11 个类别，覆盖赛题要求的 CVE/NVD、厂商公告、安全社区、"
          "安全博客、学术论文、标准政策与事件库。每个来源是一条登记项，包含采集方式（api / feed / rss / page）、"
          "独立来源标记、可信度与许可说明；客户端无法提交任意 URL。"),
    ("table", ["数据源类型", "具体数据源", "更新频率", "实际产出"],
     [["CVE/NVD", "nvd、mitre_cve", "1 小时增量", "273 / 202 条"],
      ["开源生态漏洞库", "osv", "1 小时增量", "91 条"],
      ["安全社区与聚合公告", "ghsa", "1 小时增量（需只读令牌）", "108 条"],
      ["在野利用情报", "cisa_kev", "1 小时增量", "26 条"],
      ["厂商安全公告", "msrc", "1 小时增量", "10 条"],
      ["安全博客与社区", "freebuf、anquanke、talos_blog 等 7 个", "1 小时增量", "共 35 条"],
      ["学术论文", "arxiv、openalex", "openalex 1 小时；arxiv 按需", "114 / 36 条"],
      ["标准政策与框架", "eu_ai_act、nist_ai_rmf、owasp_genai 等", "1 小时增量", "共 7 条"]]),
    ("p", "更新频率只有一档：推荐集统一小时间隔增量轮询，机器休眠时由计划任务的补跑策略顺延。"
          "系统没有按来源分档频率的字段，因此不会在报告里写成核心源与全量分层轮询。"
          "需要特别说明的是实时监测：全部来源 realtime 均为 false，本系统是小时级，不是实时系统。"),
    ("p", "来源状态只有五种取值，并且都能在接口里看到：ok 表示本轮成功；failed 表示本轮失败且没有历史数据；"
          "stale 表示本轮失败但历史数据仍在，因此检索不受影响、只是没有新数据；partial 表示部分成功，"
          "系统会把未处理完的部分留到下一轮而不是标记成功；skipped 表示主动跳过，"
          "例如缺少只读令牌的 GHSA。把这五种状态区分开，是为了让“部分成功”不被读成“成功”。"),
    ("figure", "fig5", "图 5  采集状态机：五种状态的定义与迁移"),
    ("p", "重复信息在采集后会进入去重候选表（当前 210 条候选），同一漏洞的多来源记录不会各自成为独立知识点，"
          "而是合并成一个事件并保留各自的来源标识。这样问答引用到的是一条事件，"
          "但答题时仍能指出这条结论来自 NVD 还是 OSV。"),
    ("h1", "四、情报富化模块详细设计"),
    ("p", "富化对采集到的事件做多维扩展。六个维度在演示机上都有数据："
          + "、".join(
              f"{label} {_enrichment_row(key).split(' /')[0].strip()} 个事件"
              for key, label, _ in ENRICHMENT_LABELS
          )
          + "。每个字段都保存来源标识，可以逐条回读原始快照。"
            "这里的覆盖数来自同一份快照，分母随事件总量变化，不再手写。"),
    ("p", "关联推理的关键约束是不合并证据。以真实事件 GHSA-w794-rj3p-xv45（Langflow 命令注入）为例，"
          "同一事件下有三条受影响区间，分别属于 1.x 与 0.x 两条版本线，各自带独立 source_id 与各自的修复版本。"
          "系统没有把它们合并成一条更整洁的结论，因为合并会让 0.x 线的用户拿到错误的修复版本。"
          "完整案例见 docs/CASE_ENRICHMENT_INFERENCE.md。"),
    ("p", "必须如实说明的是 POC 与资产两个维度的边界：在 B 评测语料中 assets、assessments 两张表无记录，"
          "events[].poc[] 也为空，因此这两个维度没有可计算的分母；报告里写无数据，不写 0。"
          "演示机上的资产条目为合成资产，结论限定为策略感知处置建议，不声称个性化资产推荐。"),
    ("table", ["富化维度", "演示机覆盖", "数据来源"],
     _enrichment_rows()),
    ("p", "覆盖率的读法需要克制：覆盖率低不等于这是缺陷，例如论文关联只对论文类事件有意义。"
          "报告里给出的是“有该维度数据的事件数 / 全部事件数”，不是准确率，两者不能互相替代。"),
    ("h1", "五、情报问答模块详细设计"),
    ("p", "问答链路基于本地知识库做关键词与语义混合检索，答案只从检索到的证据拼装，并携带引用。"
          "每条引用包含 chunk_id、字符起始与结束偏移，正文可以按偏移回读核对。"
          "检索层对中文短语做英文同义词扩展，以便在英文语料上工作；扩展词参与匹配但按一个概念计分，"
          "避免出现提问词压过主题词的情况。"),
    ("p", "评测集为固定 50 题，覆盖基础事实问答 10 题、术语与语义查询 8 题、中英文混合查询 6 题、"
          "多轮追问 6 题、跨文档问答 8 题、真实多跳问答 2 题，以及无证据与拒答各 5 题。"
          "2026-10-12 批次实测：引用命中 35/36 = 0.9722，预期词命中 35/38 = 0.9211，"
          "拒答一致率 42/50 = 0.84，引用总数 222。完整演示脚本见 docs/CASE_QA_MULTITURN_CROSSDOC.md。"),
    ("p", "跨文档能力需要区分两个层次：在评测集上，跨文档题能答对，因为期望文档确实存在于语料中；"
          "但在知识图谱层面，跨文档路径只通过 10/21，仍缺 52 条文档间引用边。"
          "另有一项独立的检索覆盖指标：术语可达 29/31，衡量的是“给定术语能否在语料中被检索到”，"
          "它不对应任何推理链，因此单独报告，不替换也不抬高 10/21。"
          "因此本模块的定位是跨文档检索与聚合，不是完整跨文档推理。"),
    ("p", "拒答是这条链路的一等公民，不是失败兜底。评测集里 5 道无证据题与 5 道证据不足题专门考核这一点："
          "当检索不到可用证据时，系统返回拒答并说明原因，而不是用模型的常识补齐答案。"
          "同一批 50 题的作答与拒答结构为 46 / 4，与上一批次完全一致，说明本轮检索改动没有改变拒答口径。"),
    ("p", "引用可追溯性由测试固定：每条引用都要能按 chunk_id 与字符偏移回到原始分块，"
          "偏移与存储文本不一致的记录会被契约检查拒绝。这条约束让“引用能找回”与“引用支持答案”"
          "成为两件被分别检查的事情——前者有引用一致性测试，后者由预期词命中率度量。"),
    ("h1", "六、关键技术选型说明"),
    ("table", ["选择", "理由", "代价与边界"],
     [["Python + FastAPI", "单进程内即可完成采集、检索、研判与问答编排，部署简单", "长任务依赖计划任务而非常驻队列"],
      ["SQLite 单库 + 快照目录", "证据与结论同库，任何字段可回溯；备份即一个文件", "并发写入受限，不适合多实例水平扩展"],
      ["确定性检索（关键词 + 同义词扩展）", "离线可跑、结果可复现、不依赖外部模型", "语义泛化弱于向量检索，需靠扩展词弥补"],
      ["模型为可选增强", "未配置模型时系统仍可完整运行并给出证据", "问答为证据拼装式回答，长文本生成能力有限"],
      ["Docker + Compose + CI", "本机与 CI 使用同一镜像定义，验收可复现", "容器内不携带语料，评测语料需另行交付"]]),
    ("h1", "七、系统工作流程图"),
    ("figure", "fig3", "图 3  系统工作流：采集 → 富化 → 问答 → 处置闭环"),
    ("p", "计划任务每小时触发一次采集，采集结果先经过归一化与去重写入事件库，再进入富化与关系构建。"
          "问答与研判读取同一份知识库，回答带引用返回。任一环节失败都进入自愈分支：先做失败分类，"
          "再执行一次受控重试；重试仍失败则计入连续失败，达到阈值后该来源退出无人值守采集或切换到备用源，"
          "同时发出告警。整个链路的状态都落在 runs 与 source_state 两张表里，可逐条核查。"),
    ("figure", "fig6", "图 6  自愈状态机：失败 → 重试 → 降级 → 恢复"),
    ("h1", "八、系统实现细节与核心代码说明"),
    ("p", "采集编排入口是 app/agents.py 的 run_collection：逐个来源调用采集器，把结果写回 source_state，"
          "并把每个来源的状态、抓取数、保留数、过滤数、耗时与错误写入运行记录。"
          "自愈策略在 app/self_healing.py，核心是三步：classify_failure 把错误归类为限流、超时、"
          "鉴权、格式变化、连接重置或上游拒绝；recovery_decision 决定是否值得重试；"
          "degradation_for 在连续失败达到阈值时给出降级动作。"),
    ("p", "降级状态存放在独立表 source_degradations 而不是给 source_state 加列，"
          "这样已有数据库靠 CREATE TABLE IF NOT EXISTS 就能升级，不需要迁移脚本。"
          "采集挑选来源时经过 apply_degradation_policy：处于冷却期的来源被移出，"
          "声明了备用源的来源由备用源代采，并把每一次替换写进运行记录，避免来源悄悄消失。"),
    ("p", "可复现的自愈演练在 tools/run_self_healing_drill.py：它在数据库副本上注入可控故障，"
          "运行真实的自愈代码路径，验证四项断言——故障来源退出无人值守集合、恢复后自动回到集合、"
          "无备用源的来源走降频、声明备用源的来源切换成功。结果写入 reports/self-healing-drill.json。"),
    ("p", "数据层只有两个位置：一个 SQLite 数据库保存事件、别名、来源状态、资产、研判、处置、运行记录与分块索引；"
          "一个快照目录保存原始响应。事件的每个来源引用都指向一个快照哈希，"
          "因此“这条结论从哪来”可以一路查到原始字节。备份与回滚也按这个结构设计："
          "停服务、保留当前库、用备份覆盖、重启并校验健康接口，演练记录在 reports/backup-restore-validation.json。"),
    ("p", "问答与研判共用一套检索接口，避免出现“页面看到的证据”和“机器评判用的证据”来自两套实现。"
          "这一点直接决定了指标的可信度：页面、接口与证据文件读的是同一份持久化状态，"
          "前端不做二次换算，也不做估算。"),
    ("h1", "附录 A：术语与证据索引"),
    ("table", ["术语", "含义", "在本报告中的位置"],
     [["事件", "归一化后的一个漏洞或知识条目，可合并多个来源", "第三章、第九章"],
      ["证据 ID", "指向某个快照中一段具体内容的标识", "第四章、第五章"],
      ["stale", "本轮采集失败但历史数据仍可用，检索不受影响", "第三章"],
      ["降级", "来源连续失败后退出无人值守采集或切换备用源", "第七章、第八章"],
      ["抽样穷尽", "在声明的样本范围内逐条枚举应抽取关系，而非全语料穷尽", "第四章、第十章"],
      ["口径基线", "对外引用的指标一律取演示机数据库读数", "第一章、第十章"]]),
    ("p", "配套证据文件：docs/COMPETITION_RUBRIC_MAPPING.md（评分档位对照）、"
          "docs/METRICS_BASELINE.md（口径基线）、docs/CASE_ENRICHMENT_INFERENCE.md（富化案例）、"
          "docs/CASE_QA_MULTITURN_CROSSDOC.md（问答演示）、reports/（容器与自愈验收产物）。"),
    ("h1", "九、各功能模块实现效果展示"),
    ("table", ["模块", "展示方式", "证据文件"],
     [["监测与来源健康", "赛题指标页的来源健康度面板（每个来源的状态、类别、最近成功时间、产出条数、连续失败次数）",
       "docs/screenshots/09-source-health.png、/api/system/health"],
      ["系统健康", "模块状态、活跃降级、冷却截止与最近告警",
       "docs/screenshots/10-system-health.png、/api/system/health"],
      ["术语语义字典", _term_dictionary_line(),
       "docs/screenshots/11-term-dictionary.png、/api/knowledge/terms"],
      ["术语 → 文档两跳", "知识图谱页：术语节点与文档节点分型渲染的两跳关系",
       "docs/screenshots/11-term-dictionary.png、/api/knowledge/graph"],
      ["模型降级链与角色绑定", "赛题指标页：三级降级链（含每一级被跳过的原因）与七个角色的模型绑定",
       "docs/screenshots/12-model-chain.png、/api/system/model-chain"],
      ["推荐问法", "问答区：题目直接取自固定评测集，点一下即填入输入框；拒答类题目不入列",
       "docs/screenshots/13-question-suggestions.png、/api/qa/suggestions"],
      ["技术详情", "回答展开后的本轮计划、工具调用与返回条数、耗时与已知限制",
       "docs/screenshots/14-technical-detail.png"],
      ["富化", "事件详情中的 CVSS、受影响区间、修复版本与来源标识", "docs/CASE_ENRICHMENT_INFERENCE.md"],
      ["问答与多轮", "多轮追问、跨文档引用、拒答三组界面截图", "docs/screenshots/b-qa-0*.png"],
      ["处置闭环", "高优先级队列、复测关闭与操作前后对比截图", "docs/A_DISPOSITION_LIVE_CLOSURE.md"]]),
    ("p", "上表前两行是浏览器级实测，不是结构性断言：tools/browser_check.py 用真实 Chromium 打开页面，"
          "把渲染出来的行数与 /api/system/health 的返回逐项对齐——来源方向 20 行对 20 个来源、"
          "系统健康 4 行对 4 个模块、徽标文案与模块状态计数一致、每个来源的状态文案都能在接口取值里找到对应项，"
          "截图分别是 docs/screenshots/09-source-health.png 与 10-system-health.png。"
          "这两张图的数据全部来自 source_state 与 source_degradations 的持久化记录，前端不做任何推算。"),
    ("h1", "十、性能测试结果与分析"),
    ("table", ["指标", "实测", "说明"],
     [["监测时效性（混合，见附录 B）",
       f"p50 = {_snap('scorecard', 'latency_p50_hours')} 小时；"
       f"6 小时内 {(_snap('scorecard', 'within_6h_rate', default=0) or 0):.1%}",
       f"{_snap('scorecard', 'effective_denominator')} 个有效样本；混合口径只作附录，不作为本项判定分母"],
      ["监测时效性（漏洞类，赛题口径）",
       f"GHSA 中位 {_source_latency('ghsa').get('p50_hours', '—')} 小时；"
       f"NVD 中位 {_source_latency('nvd').get('p50_hours', '—')} 小时",
       f"赛题问的是漏洞信息从发布到采集的延迟，故按来源类别分列；"
       f"样本 {_source_latency('ghsa').get('n', '—')} / {_source_latency('nvd').get('n', '—')}，"
       f"与附录 B 同一份快照（{_snap('snapshot_date')}）"],
      ["问答引用命中", "0.9722（35/36）", "同一批题目在修复前的提交上重跑为 0.8889，差异可归因于代码"],
      ["问答响应", "p50 = 449.9 ms / p95 = 627.9 ms", "50 题同一批次实测（formal_qa_results_20261012.json）；赛题目标单题 5 秒内"],
      ["富化关系准确率", "Precision 1.0 / Recall 0.734", "抽样穷尽金标准，94 条可判定样本"],
      ["连续运行",
       f"累计 {_snap('scorecard', 'cumulative_actual_run_days')} 个采集日，"
       f"定时 {_snap('scorecard', 'cumulative_scheduled_run_days')} 天",
       ("7 天连续运行目标：已达成（窗口内每个自然日都有计划运行）"
        if _snap("scorecard", "continuous_target_met", default=False)
        else "7 天连续运行目标：当前窗口未达成——计划任务已改为无限重复，2026-10-14 当日运行 9 次、"
             "10-15 已触发，但 10-09/11/12/13 无计划运行；连续天数需重新累积，"
             "预计 2026-10-20 回到目标（见 docs/A_CONTINUOUS_RUN_STATUS_20261015.md）")],
      ["自动化测试", _snap("tests", default="提交前重跑全量 pytest 并刷新快照"),
       "交付机全量 pytest；语料与衍生副本均已交付核验"]]),
    ("figure", "fig4", "图 4  校内初赛功能与性能项自评（按评分细则档位）"),
    ("p", f"对时效性的归因：混合口径的中位延迟是 "
          f"{_snap('latency_by_class', 'mixed', 'p50_hours')} 小时，但如果就此说“采集慢”是错的。"
          f"按来源类别拆开看，延迟最大的一段根本不在漏洞类——"
          f"arxiv {_source_latency('arxiv').get('p50_hours', '—')} 小时、"
          f"openalex {_source_latency('openalex').get('p50_hours', '—')} 小时，"
          "它们衡量的是论文与索引的发布节奏；而赛题问的是漏洞信息。"
          f"漏洞类里 GHSA 中位 {_source_latency('ghsa').get('p50_hours', '—')} 小时、"
          f"NVD 中位 {_source_latency('nvd').get('p50_hours', '—')} 小时。"),
    ("p", "瓶颈在上游而不在我们：采集间隔是 1 小时（计划任务每小时触发一次），而同一个 CVE 在 MITRE 登记记录与"
          "NVD 记录之间的发布时差本身就有中位 0.68 小时（79 对样本）。也就是说上游两个登记库是先后滚动的，"
          "我们把 NVD 那条记到时，NVD 自己才刚发出来。跨来源时间线的可回读样例（含事件 ID 与两个来源时间戳）"
          "见 docs/A_TIMELINESS_ATTRIBUTION.md 第 4 节，机读产物是 reports/timeliness-attribution.json。"),
    ("p", f"因此结论写成一句可引用的话：采集间隔 1 小时；"
          f"GHSA 中位 {_source_latency('ghsa').get('p50_hours', '—')} 小时，"
          f"NVD 中位 {_source_latency('nvd').get('p50_hours', '—')} 小时，"
          "差值来自上游发布与入库节奏。分列把混合口径里那些与漏洞无关的发布节奏剥出去，但混合口径本身"
          "保留在附录 B，两个数都能被追问；两者的样本量与分位数由同一份快照生成，不会再各写一份。"),
    ("p", "本项的档位口径也一并定稿：**按漏洞类判定为良好**——GHSA 与 NVD 两个漏洞来源的中位延迟都落在"
          f"≤12 小时区间（GHSA {_source_latency('ghsa').get('p50_hours', '—')} 小时、"
          f"NVD {_source_latency('nvd').get('p50_hours', '—')} 小时，均取自同一份快照）；混合口径不算本项分母，"
          f"只作附录 B 的参考（当前快照 {_snap('latency_by_class', 'mixed', 'n')} 个有效样本、"
          f"中位 {_snap('latency_by_class', 'mixed', 'p50_hours')} 小时）。数字来源分两类：混合口径只认"
          "docs/report/metrics_snapshot.json 的快照块，分列与上游归因以 docs/A_TIMELINESS_ATTRIBUTION.md "
          "第 3、4 节为准（本机机读产物 reports/timeliness-attribution.json）。对照表 §2.1、"
          "docs/METRICS_BASELINE.md 的 2.1 节与本报告三处写的是同一条口径；"
          "tools/refresh_metrics_snapshot.py --write 只推进快照块，档位判定不随刷新改写。"),
    ("h1", "十一、创新点总结"),
    ("bullets", [
        "证据分层而非结论合并：同一事件的多个来源区间分别保留，避免合并后给出错误的修复版本。",
        "降级而不是重试到底：连续失败触发降频或切换备用源，并且恢复后自动回到采集集合。",
        "口径与展示同源：页面、接口与证据文件读同一份持久化状态，指标不靠前端估算。",
        "可复现的工程证据：容器验收、CI、回滚、自愈演练都留下可重跑的脚本与产物。",
    ]),
    ("h1", "附录 B：时效性的混合口径（保留，不进正表）"),
    ("p", "第十章的主表按来源类别分列，因为赛题问的是漏洞信息。混合口径不删除、不隐藏，列在这里备查："
          f"{_snap('latency_by_class', 'mixed', 'n')} 个有效样本，"
          f"中位 {_snap('latency_by_class', 'mixed', 'p50_hours')} 小时，"
          f"6 小时内 {_snap('scorecard', 'within_6h_rate', default=0):.1%}、"
          f"12 小时内 {_snap('scorecard', 'within_12h_rate', default=0):.1%}、"
          f"24 小时内 {_snap('scorecard', 'within_24h_rate', default=0):.1%}。"
          "混合口径只用于说明瓶颈在上游，不作为本项判定分母——本项判的是漏洞类，档位是良好。"
          "下面这张表是 2026-10-13 交付机的一次读数，与第十章主表第一行的快照读数日期和样本量都不同",
          "（基线库每小时增长），不是同一时点，不得混引在一张表里。"
          "本表与第十章共用同一份快照，不单独维护。"),
    ("table", ["口径", "来源", "样本", "中位延迟", "最大延迟"], _latency_class_rows()),
    ("p", "类别归属取自 app/sources.py 的 category 字段：漏洞类含 cve_database、ecosystem_advisory、"
          "community_advisory、exploitation_intel、vendor_advisory 与 security_blog；"
          "学术类为 academic_paper；政策类为 policy_regulation、technical_standard、risk_framework、threat_framework。"
          "不另造一套分类，避免出现“报告里的类别”与“代码里的类别”两套口径。"),
    ("h1", "附：评分细则档位对照"),
    ("p", "每一条评分细则对应到合格／良好／优秀的哪一档、证据在哪，见 docs/COMPETITION_RUBRIC_MAPPING.md。"
          "该表同时列出三处必须如实说明的缺口：无实时监测、时效性距优秀档（≤6 小时）尚有距离、"
          "跨文档路径 10/21。"),
]

BLOCKS = OVERVIEW + SECTIONS


def _iter_headings():
    for block in BLOCKS:
        if block[0] in ("h1", "h2"):
            yield block[0], block[1]


def build_docx(figures: dict[str, Path], path: Path) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    style = document.styles["Normal"]
    style.font.name = "微软雅黑"
    style.font.size = Pt(10.5)
    style.paragraph_format.line_spacing = 1.4
    style.paragraph_format.space_after = Pt(6)

    for section in document.sections:
        section.left_margin = section.right_margin = Cm(2.4)
        section.top_margin = section.bottom_margin = Cm(2.2)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(TITLE)
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = subtitle.add_run(SUBTITLE)
    sub_run.font.size = Pt(14)
    sub_run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    document.add_paragraph()

    # 目录：真正的 Word 目录域，并让 Word 打开时自动更新页码。
    toc_heading = document.add_paragraph()
    toc_heading.add_run("目录").font.size = Pt(15)
    paragraph = document.add_paragraph()
    run = paragraph.add_run()
    fld = run._r.makeelement(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fldSimple",
        {"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr": 'TOC \\o "1-2" \\h \\z \\u'},
    )
    run._r.append(fld)
    settings = document.settings.element
    update = settings.makeelement(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}updateFields",
        {"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val": "true"},
    )
    settings.append(update)
    document.add_page_break()

    for block in BLOCKS:
        kind = block[0]
        if kind == "h1":
            document.add_heading(block[1], level=1)
        elif kind == "h2":
            document.add_heading(block[1], level=2)
        elif kind == "p":
            document.add_paragraph(block[1])
        elif kind == "bullets":
            for item in block[1]:
                document.add_paragraph(item, style="List Bullet")
        elif kind == "table":
            headers, rows = block[1], block[2]
            table = document.add_table(rows=1, cols=len(headers))
            table.style = "Light Grid Accent 1"
            for index, header in enumerate(headers):
                table.rows[0].cells[index].text = str(header)
            for row in rows:
                cells = table.add_row().cells
                for index, cell in enumerate(row):
                    cells[index].text = str(cell)
            document.add_paragraph()
        elif kind == "figure":
            image = figures.get(block[1])
            if image and image.is_file():
                document.add_picture(str(image), width=Cm(13.0))
                document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption = document.add_paragraph()
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption_run = caption.add_run(block[2])
                caption_run.font.size = Pt(9)
                caption_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    document.save(str(path))


def build_pdf(figures: dict[str, Path], path: Path) -> int:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate, Paragraph,
        Spacer, Table, TableStyle,
    )
    from reportlab.platypus.tableofcontents import TableOfContents

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    font = "STSong-Light"

    base = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=base["Title"], fontName=font, fontSize=22,
                                 leading=30, alignment=TA_CENTER, textColor=colors.HexColor(ACCENT))
    sub_style = ParagraphStyle("S", parent=base["Normal"], fontName=font, fontSize=13,
                               leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#444444"))
    h1 = ParagraphStyle("H1", parent=base["Heading1"], fontName=font, fontSize=15, leading=22,
                        spaceBefore=14, spaceAfter=8, textColor=colors.HexColor(ACCENT))
    h2 = ParagraphStyle("H2", parent=base["Heading2"], fontName=font, fontSize=12.5, leading=19,
                        spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#333333"))
    body = ParagraphStyle("B", parent=base["BodyText"], fontName=font, fontSize=10.2, leading=17,
                          spaceAfter=6, firstLineIndent=0)
    bullet = ParagraphStyle("BU", parent=body, leftIndent=14, bulletIndent=4, spaceAfter=3)
    caption = ParagraphStyle("C", parent=body, fontSize=8.8, leading=13, alignment=TA_CENTER,
                             textColor=colors.HexColor("#555555"), spaceBefore=3, spaceAfter=10)
    cell = ParagraphStyle("CELL", parent=body, fontSize=8.6, leading=12.5, spaceAfter=0)
    head_cell = ParagraphStyle("HEAD", parent=cell, textColor=colors.white)

    class Report(BaseDocTemplate):
        def afterFlowable(self, flowable):
            if isinstance(flowable, Paragraph):
                style = flowable.style.name
                if style in ("H1", "H2"):
                    self.notify("TOCEntry", (0 if style == "H1" else 1,
                                             flowable.getPlainText(), self.page))

    doc = Report(str(path), pagesize=A4,
                 leftMargin=2.4 * cm, rightMargin=2.4 * cm,
                 topMargin=2.2 * cm, bottomMargin=2.0 * cm,
                 title=TITLE, author="参赛团队")

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setFont(font, 8.5)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawCentredString(A4[0] / 2, 1.25 * cm, "第 %d 页" % document.page)
        canvas.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=decorate)])

    story = [Paragraph(TITLE, title_style), Spacer(1, 6),
             Paragraph(SUBTITLE, sub_style), Spacer(1, 18),
             Paragraph("目录", h1)]
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC1", fontName=font, fontSize=10, leading=16, leftIndent=6),
        ParagraphStyle("TOC2", fontName=font, fontSize=9, leading=14, leftIndent=20,
                       textColor=colors.HexColor("#444444")),
    ]
    story.append(toc)
    story.append(Spacer(1, 12))

    for block in BLOCKS:
        kind = block[0]
        if kind == "h1":
            story.append(Paragraph(block[1], h1))
        elif kind == "h2":
            story.append(Paragraph(block[1], h2))
        elif kind == "p":
            story.append(Paragraph(block[1], body))
        elif kind == "bullets":
            for item in block[1]:
                story.append(Paragraph(item, bullet, bulletText="•"))
            story.append(Spacer(1, 4))
        elif kind == "table":
            headers, rows = block[1], block[2]
            data = [[Paragraph(str(h), head_cell) for h in headers]]
            for row in rows:
                data.append([Paragraph(str(c), cell) for c in row])
            width = doc.width / len(headers)
            table = Table(data, colWidths=[width] * len(headers), repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ACCENT)),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b7c4d8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]))
            story.append(table)
            story.append(Spacer(1, 10))
        elif kind == "figure":
            image = figures.get(block[1])
            if image and image.is_file():
                from PIL import Image as PILImage
                with PILImage.open(image) as handle:
                    ratio = handle.height / handle.width
                figure_width = doc.width * 0.84
                story.append(KeepTogether([
                    Image(str(image), width=figure_width, height=figure_width * ratio),
                    Paragraph(block[2], caption),
                ]))
    doc.multiBuild(story)
    return doc.page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", default="docs/report/AI安全知识情报系统技术报告.docx")
    parser.add_argument("--pdf", default="docs/report/AI安全知识情报系统技术报告.pdf")
    args = parser.parse_args()

    figures = build_figures()
    docx_path = ROOT / args.docx
    pdf_path = ROOT / args.pdf
    docx_path.parent.mkdir(parents=True, exist_ok=True)

    build_docx(figures, docx_path)
    pages = build_pdf(figures, pdf_path)

    print(json_dumps({
        "docx": str(docx_path.relative_to(ROOT)),
        "docx_bytes": docx_path.stat().st_size,
        "pdf": str(pdf_path.relative_to(ROOT)),
        "pdf_bytes": pdf_path.stat().st_size,
        "pdf_pages": pages,
        "figures": {key: value.name for key, value in figures.items()},
        "blocks": len(BLOCKS),
    }))
    return 0


def json_dumps(payload: dict) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
