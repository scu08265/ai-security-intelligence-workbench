"""B 任务四：策略感知的资产处置建议（独立模块，一页内可审计）。

本模块**不修改** `app/` 的共享链路，也不改数据库 schema：

* 事实层复用既有 `app.intelligence.assess_asset`（版本区间/条件判定 + 证据 ID）
  与 `app.intelligence.enrich_event`（证据维度、缺口、POC 与在野利用状态）。
* 事件与资产默认从数据库**只读**读取；数据库里 assets 表当前为 0 条，
  因此也支持从外部 JSON 读入资产（示例 / 合成数据必须显式标记 `"synthetic": true`）。
* 新增的只有：策略输入与校验、动作目录、优先级排序、运维约束检查、建议输出、演示运行。

分层约定（输出里逐条标注）：

* `confirmed`：由版本区间/条件等**已有证据**确认；
* `inferred`：系统推断（如仅凭组件同名），只能作为待核实；
* `missing`：信息缺失。

用法::

    # 示例/演示（合成资产，明确标记）
    python tools/asset_disposal_advisor.py --demo \
        --out artifacts/b_eval/asset_disposal_demo.json

    # 真实资产文件或数据库资产 + 策略文件
    python tools/asset_disposal_advisor.py \
        --assets config/assets.example.json \
        --policies config/asset_policies.example.json \
        --events CVE-2025-9959,CVE-2026-41106 \
        --out artifacts/b_eval/asset_disposal.json
"""

from __future__ import annotations

import argparse
import copy
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, intelligence  # noqa: E402

SOURCE_DATA_DIR = Path(r"D:\ICT\intel-data-b")
DEFAULT_POLICY_PATH = ROOT / "config" / "asset_policies.example.json"
EXAMPLE_ASSETS_PATH = ROOT / "config" / "assets.example.json"

# --------------------------------------------------------------------------
# 动作目录：任何影响生产的动作都必须在这里登记（估算值 = 配置，不是实测）
# --------------------------------------------------------------------------
DEFAULT_ACTION_CATALOG = {
    "verify_version": {
        "label": "核对资产实际版本与配置",
        "disruptive": False,
        "estimated_downtime_minutes": 0,
        "basis": "只读核查，不改变运行状态",
    },
    "apply_patch": {
        "label": "升级/打补丁到修复版本",
        "disruptive": True,
        "estimated_downtime_minutes": 15,
        "basis": "动作目录配置的停机估算（需按实际发布流程调整）",
    },
    "restart_service": {
        "label": "重启相关服务使缓解配置生效",
        "disruptive": True,
        "estimated_downtime_minutes": 5,
        "basis": "动作目录配置的停机估算",
    },
    "limit_exposure": {
        "label": "评估并降低对外暴露面（限流/白名单/关闭入口）",
        "disruptive": True,
        "estimated_downtime_minutes": 10,
        "basis": "可能影响可用性，必须经负责人批准",
    },
    "enhanced_monitoring": {
        "label": "加强监测与告警（针对该漏洞特征）",
        "disruptive": False,
        "estimated_downtime_minutes": 0,
        "basis": "只增加观测，不改变运行状态",
    },
    "further_verification": {
        "label": "进一步核实（补充版本/配置/影响证据）",
        "disruptive": False,
        "estimated_downtime_minutes": 0,
        "basis": "信息补全动作，不改变运行状态",
    },
}

BUSINESS_IMPORTANCE = ("low", "medium", "high", "critical")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# 优先级权重（可解释、可调整；缺失数据一律记 0 分并写入缺口，不猜）
PRIORITY_WEIGHTS = {
    "severity": {"critical": 40, "high": 30, "medium": 15, "low": 5, "unknown": 0},
    "exploitation": {"known_exploited": 25, "poc_recorded": 15, "none_recorded": 0},
    "business_importance": {"critical": 20, "high": 15, "medium": 8, "low": 3,
                            "unknown": 0},
    "exposure": {"public": 10, "internal": 5, "unknown": 0},
    "link_confidence": {"affected": 5, "needs_confirmation": 0},
}


class PolicyError(ValueError):
    """策略文件不合法。"""


@dataclass
class Policy:
    """单个资产的运维策略（六个必需字段；缺失即视为缺失，不推断）。"""

    asset_id: str
    maintenance_window: dict | None = None
    business_importance: str = "unknown"
    prohibited_actions: list[str] = field(default_factory=list)
    owner: str | None = None
    acceptable_downtime_minutes: int | None = None
    explicit: bool = True          # False = 系统默认策略（该资产没有提供策略）
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "maintenance_window": self.maintenance_window,
            "business_importance": self.business_importance,
            "prohibited_actions": list(self.prohibited_actions),
            "owner": self.owner,
            "acceptable_downtime_minutes": self.acceptable_downtime_minutes,
            "explicit": self.explicit,
            "warnings": list(self.warnings),
        }


def default_policy(asset_id: str) -> Policy:
    """无策略资产的默认规则：不允许停机、不得执行破坏性操作、必须人工审核。"""
    return Policy(
        asset_id=asset_id,
        maintenance_window=None,
        business_importance="unknown",
        prohibited_actions=["apply_patch", "restart_service", "limit_exposure"],
        owner=None,
        acceptable_downtime_minutes=0,
        explicit=False,
        warnings=[
            "资产未提供策略：按默认规则处理（可接受停机=0 分钟，破坏性动作全部禁止）",
            "默认规则不表示资产真的不能停机，只表示系统不假设它可以停机",
        ],
    )


def _validate_window(raw) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PolicyError("maintenance_window 必须是对象或 null")
    weekday = str(raw.get("weekday") or "").strip()
    start = str(raw.get("start") or "").strip()
    end = str(raw.get("end") or "").strip()
    timezone = str(raw.get("timezone") or "").strip()
    if weekday not in WEEKDAYS:
        raise PolicyError(f"maintenance_window.weekday 非法：{weekday!r}（允许 {list(WEEKDAYS)}）")
    for label, value in (("start", start), ("end", end)):
        parts = value.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise PolicyError(f"maintenance_window.{label} 必须是 HH:MM，收到 {value!r}")
        if not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
            raise PolicyError(f"maintenance_window.{label} 超出范围：{value!r}")
    if start >= end:
        raise PolicyError(f"maintenance_window 的 start({start}) 必须早于 end({end})")
    if not timezone:
        raise PolicyError("maintenance_window.timezone 缺失（必须显式给出，避免跨时区误判）")
    return {"weekday": weekday, "start": start, "end": end, "timezone": timezone}


def parse_policy(asset_id: str, raw: dict) -> Policy:
    if not asset_id:
        raise PolicyError("策略条目缺少 asset_id")
    if not isinstance(raw, dict):
        raise PolicyError(f"资产 {asset_id} 的策略必须是对象")
    warnings: list[str] = []
    importance = str(raw.get("business_importance", "unknown")).strip().casefold() or "unknown"
    if importance not in BUSINESS_IMPORTANCE:
        raise PolicyError(
            f"资产 {asset_id} 的 business_importance 非法：{importance!r}"
            f"（允许 {list(BUSINESS_IMPORTANCE)}）")
    actions = raw.get("prohibited_actions") or []
    if not isinstance(actions, list) or any(not isinstance(a, str) for a in actions):
        raise PolicyError(f"资产 {asset_id} 的 prohibited_actions 必须是字符串数组")
    actions = [a.strip() for a in actions if a.strip()]
    unknown_actions = [a for a in actions if a not in DEFAULT_ACTION_CATALOG]
    if unknown_actions:
        warnings.append(f"prohibited_actions 含未登记动作 {unknown_actions}："
                        "已保留，但系统无法判断其影响，需要人工确认")
    downtime = raw.get("acceptable_downtime_minutes")
    if downtime is None:
        warnings.append("acceptable_downtime_minutes 缺失：按 0 分钟处理（不假设可停机）")
        downtime_value = 0
    elif isinstance(downtime, bool) or not isinstance(downtime, int) or downtime < 0:
        raise PolicyError(f"资产 {asset_id} 的 acceptable_downtime_minutes 必须是非负整数")
    else:
        downtime_value = downtime
    owner = raw.get("owner")
    if owner is not None and not isinstance(owner, str):
        raise PolicyError(f"资产 {asset_id} 的 owner 必须是字符串或 null")
    if not owner:
        warnings.append("owner 缺失：建议会标注为『负责人未知，需人工指派』")
        owner = None
    return Policy(
        asset_id=asset_id,
        maintenance_window=_validate_window(raw.get("maintenance_window")),
        business_importance=importance,
        prohibited_actions=actions,
        owner=owner,
        acceptable_downtime_minutes=downtime_value,
        explicit=True,
        warnings=warnings,
    )


def load_policies(path: Path | None) -> tuple[dict[str, Policy], dict]:
    """读取策略文件；返回 ({asset_id: Policy}, 元信息)。文件不存在时返回空策略。"""
    if path is None or not Path(path).is_file():
        return {}, {"path": None, "count": 0,
                    "note": "未提供策略文件：所有资产使用默认保守规则"}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("policies") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise PolicyError("策略文件必须是数组，或带 policies 数组的对象")
    policies: dict[str, Policy] = {}
    for item in entries:
        asset_id = str((item or {}).get("asset_id") or "")
        if asset_id in policies:
            raise PolicyError(f"策略文件中 asset_id 重复：{asset_id}")
        policies[asset_id] = parse_policy(asset_id, item)
    return policies, {"path": str(Path(path)), "count": len(policies),
                      "synthetic": bool(payload.get("synthetic")) if isinstance(payload, dict) else False}


def _readonly_connection(db_path: Path) -> sqlite3.Connection:
    wal = Path(f"{db_path}-wal")
    options = "mode=ro" if (wal.is_file() and wal.stat().st_size > 0) else "mode=ro&immutable=1"
    return sqlite3.connect(f"file:{Path(db_path).as_posix()}?{options}", uri=True)


def load_assets_from_db(db_path: Path | None = None) -> list[dict]:
    db = Path(db_path or config.DB_PATH)
    if not db.is_file():
        return []
    connection = _readonly_connection(db)
    try:
        rows = list(connection.execute("select doc from assets"))
    finally:
        connection.close()
    assets = []
    for (doc,) in rows:
        try:
            record = json.loads(doc)
        except (TypeError, ValueError):
            continue
        record.setdefault("source", "db")
        assets.append(record)
    return assets


def load_assets_from_file(path: Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("assets") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise PolicyError("资产文件必须是数组，或带 assets 数组的对象")
    synthetic = bool(payload.get("synthetic")) if isinstance(payload, dict) else False
    assets = []
    for item in entries:
        if not isinstance(item, dict) or not item.get("id"):
            raise PolicyError("资产条目必须是对象且包含 id")
        record = copy.deepcopy(item)
        record.setdefault("synthetic", synthetic or bool(item.get("is_demo")))
        record.setdefault("source", "file")
        assets.append(record)
    return assets


def load_events(event_ids: list[str] | None, db_path: Path | None = None) -> dict[str, dict]:
    db = Path(db_path or config.DB_PATH)
    if not db.is_file():
        return {}
    connection = _readonly_connection(db)
    try:
        if event_ids:
            marks = ",".join("?" for _ in event_ids)
            rows = list(connection.execute(
                f"select id, doc from events where id in ({marks})", event_ids))
        else:
            rows = list(connection.execute("select id, doc from events"))
    finally:
        connection.close()
    events = {}
    for event_id, doc in rows:
        try:
            record = json.loads(doc)
        except (TypeError, ValueError):
            continue
        record.setdefault("id", event_id)
        events[str(event_id)] = record
    return events


def _severity_of(event: dict) -> str:
    severity = str(event.get("severity") or "").casefold()
    if severity in PRIORITY_WEIGHTS["severity"]:
        return severity
    scores = [float(x.get("score")) for x in event.get("cvss") or []
              if str(x.get("score") or "").replace(".", "", 1).isdigit()]
    if not scores:
        return "unknown"
    top = max(scores)
    if top >= 9:
        return "critical"
    if top >= 7:
        return "high"
    if top >= 4:
        return "medium"
    return "low"


def _exploitation_of(event: dict) -> tuple[str, list[str]]:
    evidence: list[str] = []
    for rel in event.get("relationships") or []:
        if rel.get("predicate") == "known_exploited":
            evidence.extend(str(i) for i in rel.get("evidence_ids") or [])
            return "known_exploited", evidence
    pocs = event.get("poc") or []
    evidence.extend(str(p.get("source_id")) for p in pocs if p.get("source_id"))
    return ("poc_recorded" if pocs else "none_recorded"), evidence


def _fixed_versions(event: dict, asset: dict) -> list[str]:
    fixes = []
    asset_name = str(asset.get("component") or "").casefold()
    for item in event.get("affected") or []:
        package = str(item.get("package") or "").casefold()
        if package and package != asset_name:
            continue
        fixed = item.get("fixed_version")
        if fixed:
            fixes.append(str(fixed))
    return sorted(set(fixes))


def _action_plan(assessment: dict, event: dict, asset: dict, enrichment: dict) -> list[dict]:
    """按事实状态生成候选动作；不允许出现无证据依据的动作。"""
    status = assessment["status"]
    fixes = _fixed_versions(event, asset)
    gaps = (enrichment.get("gaps") or [])
    evidence = list(assessment["evidence_ids"])
    plan: list[dict] = []
    if status == "affected":
        plan.append({"action": "verify_version",
                     "rationale": "确认线上实例与受影响版本一致（版本来自资产登记）",
                     "evidence_ids": evidence})
        if fixes:
            plan.append({"action": "apply_patch",
                         "target_version": fixes[-1],
                         "rationale": f"事件给出修复版本 {fixes[-1]}，且资产命中受影响区间",
                         "evidence_ids": evidence})
        else:
            plan.append({"action": "enhanced_monitoring",
                         "rationale": "命中受影响区间但事件未给出修复版本，先加强监测",
                         "evidence_ids": evidence})
            plan.append({"action": "further_verification",
                         "rationale": "缺失修复版本信息，需要人工核实厂商公告",
                         "evidence_ids": evidence})
    elif status == "needs_confirmation":
        plan.append({"action": "further_verification",
                     "rationale": "影响判定尚未确认：" + "；".join(assessment["reasons"]),
                     "evidence_ids": evidence})
        if any("POC" in g or "在野利用" in g for g in gaps):
            plan.append({"action": "enhanced_monitoring",
                         "rationale": "在影响未确认前，先加强与该漏洞特征相关的监测",
                         "evidence_ids": evidence})
    else:  # not_affected / not_applicable
        plan.append({"action": "enhanced_monitoring",
                     "rationale": "当前证据不支持该资产受影响，保留监测不做事后动作",
                     "evidence_ids": evidence})
    return plan


def _constraints(policy: Policy, actions: list[dict],
                 catalog: dict) -> tuple[list[dict], list[dict], dict, list[dict]]:
    """运维约束检查：禁止动作、维护窗口、可接受停机、冲突说明。"""
    allowed, blocked, conflicts = [], [], []
    for action in actions:
        spec = catalog.get(action["action"], {})
        entry = {**action, **spec,
                 "estimated_downtime_minutes": spec.get("estimated_downtime_minutes"),
                 "disruptive": bool(spec.get("disruptive"))}
        if action["action"] in policy.prohibited_actions:
            blocked.append({**entry,
                            "blocked_reason": "该动作在资产策略的 prohibited_actions 中"})
            conflicts.append(
                f"动作 {action['action']} 被策略禁止，但事实层建议它——需要人工选择替代方案")
            continue
        downtime = entry.get("estimated_downtime_minutes") or 0
        limit = policy.acceptable_downtime_minutes
        if entry["disruptive"] and limit is not None and downtime > limit:
            entry["constraint_warning"] = (
                f"预计停机 {downtime} 分钟 > 可接受停机 {limit} 分钟，"
                "不得作为无条件推荐")
            conflicts.append(entry["constraint_warning"])
        if entry["disruptive"] and policy.maintenance_window is None:
            entry["scheduling"] = {"status": "needs_window",
                                   "detail": "策略未提供维护窗口，需人工安排",
                                   "basis": "maintenance_window 缺失"}
        elif entry["disruptive"]:
            window = policy.maintenance_window
            entry["scheduling"] = {
                "status": "inside_declared_window_only",
                "allowed_from": f"{window['weekday']} {window['start']}",
                "allowed_until": f"{window['weekday']} {window['end']}",
                "timezone": window["timezone"],
                "basis": "资产策略声明的维护窗口（系统不判断当前时刻）",
            }
        else:
            entry["scheduling"] = {"status": "not_required",
                                   "detail": "非破坏性动作，无需维护窗口"}
        if entry["disruptive"] and not policy.explicit:
            entry["requires_approval"] = True
            entry["approval_reason"] = "资产未提供策略，默认禁止破坏性操作"
        else:
            entry["requires_approval"] = bool(entry["disruptive"])
            if entry["disruptive"]:
                entry["approval_reason"] = "涉及生产影响，需负责人批准后执行"
        allowed.append(entry)
    scheduling = {
        "maintenance_window": policy.maintenance_window,
        "acceptable_downtime_minutes": policy.acceptable_downtime_minutes,
        "window_source": "policy" if policy.explicit else "default(no policy)",
    }
    return allowed, blocked, scheduling, conflicts


def _priority(event: dict, asset: dict, policy: Policy, assessment: dict) -> dict:
    severity = _severity_of(event)
    exploitation, exploitation_evidence = _exploitation_of(event)
    importance = policy.business_importance
    exposure = str(asset.get("exposure") or "unknown").casefold()
    if exposure not in PRIORITY_WEIGHTS["exposure"]:
        exposure = "unknown"
    components = {
        "severity": PRIORITY_WEIGHTS["severity"].get(severity, 0),
        "exploitation": PRIORITY_WEIGHTS["exploitation"].get(exploitation, 0),
        "business_importance": PRIORITY_WEIGHTS["business_importance"].get(importance, 0),
        "exposure": PRIORITY_WEIGHTS["exposure"].get(exposure, 0),
        "link_confidence": PRIORITY_WEIGHTS["link_confidence"].get(assessment["status"], 0),
    }
    gaps = []
    if severity == "unknown":
        gaps.append("缺少严重性/CVSS：severity 分量记 0 分，不推断")
    if exploitation == "none_recorded":
        gaps.append("未收录 POC/在野利用：exploitation 分量记 0 分（不等于不存在）")
    if importance == "unknown":
        gaps.append("业务重要性未知：business_importance 分量记 0 分")
    if exposure == "unknown":
        gaps.append("暴露面未知：exposure 分量记 0 分")
    provisional = assessment["status"] != "affected"
    score = None if provisional else sum(components.values())
    if provisional:
        level = "待核实"
    elif score >= 70:
        level = "critical"
    elif score >= 50:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "score": score,
        "score_is_provisional": provisional,
        "components": components,
        "weights": PRIORITY_WEIGHTS,
        "inputs": {"severity": severity, "exploitation": exploitation,
                   "business_importance": importance, "exposure": exposure,
                   "link_status": assessment["status"]},
        "gaps": gaps,
        "exploitation_evidence_ids": exploitation_evidence,
        "note": "分值=分量之和（0–100）；状态非 affected 时不给出精确分值，仅输出"
                "『待核实』与参考分量，避免用推断风险冒充确定风险",
    }


def advise(asset: dict, policy: Policy, events: dict[str, dict],
           catalog: dict | None = None) -> dict:
    """对单个资产×全部事件生成处置建议（事实 → 排序 → 约束 → 建议）。"""
    catalog = catalog or DEFAULT_ACTION_CATALOG
    findings = []
    for event_id, event in events.items():
        assessment = intelligence.assess_asset(event, asset)
        if assessment["status"] == "not_applicable":
            continue          # 组件不匹配：不作为该资产的处置对象
        enrichment = intelligence.enrich_event(event)
        priority = _priority(event, asset, policy, assessment)
        plan = _action_plan(assessment, event, asset, enrichment)
        allowed, blocked, scheduling, conflicts = _constraints(policy, plan, catalog)
        evidence_pool = []
        for value in (assessment["evidence_ids"], priority["exploitation_evidence_ids"]):
            evidence_pool.extend(value)
        for item in event.get("sources") or []:
            if item.get("id"):
                evidence_pool.append(str(item["id"]))
        findings.append({
            "event_id": event_id,
            "event_title": event.get("title"),
            "asset_id": asset.get("id"),
            "link_status": assessment["status"],
            "link_reasons": assessment["reasons"],
            "priority": priority,
            "recommended_actions": allowed,
            "blocked_actions": blocked,
            "scheduling": scheduling,
            "conflicts": conflicts,
            "owner": policy.owner,
            "owner_known": policy.owner is not None,
            "policy_explicit": policy.explicit,
            "policy_warnings": policy.warnings,
            "evidence_ids": list(dict.fromkeys(evidence_pool)),
            "enrichment_gaps": enrichment.get("gaps") or [],
            "poc_status": (enrichment.get("poc_status") or {}).get("status"),
            "confidence": ("confirmed" if assessment["status"] == "affected" else
                           "inferred" if assessment["status"] == "needs_confirmation" else
                           "missing" if assessment["status"] == "not_affected" else "unknown"),
            "needs_human_review": bool(
                conflicts or blocked or assessment["status"] == "needs_confirmation"
                or not policy.explicit or policy.owner is None
                or (enrichment.get("gaps") or [])),
            "limitations": [
                "系统只输出建议，不执行任何扫描/隔离/升级/关机动作",
                "风险分值基于事件严重性、利用证据、业务重要性与暴露面；"
                "缺少的输入记 0 分并列入 gaps",
                "POC『未收录』不等于不存在；在野利用以已接入来源（CISA KEV）为准",
            ],
        })
    # 排序：状态为 affected 的优先，其次按分值（待核实无分值排在其后）
    def sort_key(item):
        priority = item["priority"]
        return (0 if item["link_status"] == "affected" else 1,
                -(priority["score"] or 0),
                item["event_id"])
    findings.sort(key=sort_key)
    for rank, item in enumerate(findings, start=1):
        item["rank"] = rank
    return {
        "asset": {k: asset.get(k) for k in
                  ("id", "name", "component", "ecosystem", "version", "exposure",
                   "business_criticality", "authorized", "synthetic", "source")},
        "policy": policy.as_dict(),
        "findings": findings,
        "summary": {
            "findings": len(findings),
            "affected": sum(1 for f in findings if f["link_status"] == "affected"),
            "needs_confirmation": sum(1 for f in findings
                                      if f["link_status"] == "needs_confirmation"),
            "needs_human_review": sum(1 for f in findings if f["needs_human_review"]),
            "blocked_actions": sum(len(f["blocked_actions"]) for f in findings),
        },
    }


def build(assets: list[dict], policies: dict[str, Policy],
          events: dict[str, dict], catalog: dict | None = None) -> dict:
    results = []
    for asset in assets:
        policy = policies.get(str(asset.get("id"))) or default_policy(str(asset.get("id")))
        results.append(advise(asset, policy, events, catalog))
    return {
        "schema_version": "b-asset-disposal-1.0",
        "disclaimer": "本文件是处置建议，不是执行记录；系统不执行任何生产动作。"
                      "合成资产/策略一律标记 synthetic=true。",
        "action_catalog": catalog or DEFAULT_ACTION_CATALOG,
        "priority_weights": PRIORITY_WEIGHTS,
        "assets": results,
        "totals": {
            "assets": len(results),
            "assets_with_explicit_policy": sum(1 for r in results if r["policy"]["explicit"]),
            "findings": sum(len(r["findings"]) for r in results),
            "needs_human_review": sum(r["summary"]["needs_human_review"] for r in results),
        },
    }


def _demo_inputs() -> tuple[list[dict], dict[str, Policy], dict[str, dict]]:
    """演示用输入：合成资产（明确标记）+ 真实事件（来自只读数据库）。"""
    assets = [
        {"id": "asset-demo-smolagents-prod", "name": "Agent 工具链生产服务（合成）",
         "component": "smolagents", "ecosystem": "smolagents", "version": "1.20.0",
         "exposure": "public", "business_criticality": "critical",
         "authorized": True, "is_demo": True, "synthetic": True, "conditions": {}},
        {"id": "asset-demo-copilot-prod", "name": "Copilot 生产网关（合成）",
         "component": "Microsoft 365 Copilot", "ecosystem": "Microsoft",
         "version": "unknown", "exposure": "public",
         "business_criticality": "high", "authorized": True, "is_demo": True,
         "synthetic": True, "conditions": {}},
        {"id": "asset-demo-vllm-prod", "name": "推理服务生产集群（合成）",
         "component": "vllm", "ecosystem": "PyPI", "version": "0.29.0",
         "exposure": "internal", "business_criticality": "high",
         "authorized": True, "is_demo": True, "synthetic": True, "conditions": {}},
        {"id": "asset-demo-vllm-lab", "name": "推理服务实验环境（合成）",
         "component": "vllm", "ecosystem": "PyPI", "version": "0.29.0",
         "exposure": "internal", "business_criticality": "low",
         "authorized": True, "is_demo": True, "synthetic": True, "conditions": {}},
        {"id": "asset-demo-vllm-edge", "name": "推理服务对外边缘节点（合成）",
         "component": "vllm", "ecosystem": "PyPI", "version": "0.29.0",
         "exposure": "public", "business_criticality": "critical",
         "authorized": True, "is_demo": True, "synthetic": True, "conditions": {}},
        {"id": "asset-demo-openwebui", "name": "Open WebUI 内部面板（合成）",
         "component": "open-webui", "ecosystem": "PyPI", "version": "0.10.0",
         "exposure": "internal", "business_criticality": "medium",
         "authorized": True, "is_demo": True, "synthetic": True, "conditions": {}},
    ]
    policies_path = ROOT / "config" / "asset_policies.example.json"
    policies, _meta = load_policies(policies_path)
    events = load_events(["CVE-2025-9959", "CVE-2026-41106", "CVE-2026-50517",
                          "CVE-2026-50510",
                          "PYSEC-2026-4000", "GHSA-wvm9-9g5j-623f", "CVE-2025-9959"])
    return assets, policies, events


def main() -> int:
    parser = argparse.ArgumentParser(description="B 任务四：策略感知资产处置建议")
    parser.add_argument("--assets", type=Path, default=None)
    parser.add_argument("--policies", type=Path, default=None)
    parser.add_argument("--events", default=None, help="逗号分隔的事件 ID；缺省为全部事件")
    parser.add_argument("--demo", action="store_true", help="运行三个演示案例")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    config.DATA_DIR = SOURCE_DATA_DIR
    config.DB_PATH = SOURCE_DATA_DIR / "intel.sqlite"
    config.SNAPSHOT_DIR = SOURCE_DATA_DIR / "snapshots"

    if args.demo:
        assets, policies, events = _demo_inputs()
        result = build(assets, policies, events)
        result["demo"] = _demo_cases(result, events)
    else:
        if args.assets:
            assets = load_assets_from_file(args.assets)
        else:
            assets = load_assets_from_db()
        if not assets:
            print("没有可用资产：数据库 assets 表为空，且未提供 --assets 文件")
            return 2
        policies_path = args.policies or DEFAULT_POLICY_PATH
        policies, _meta = load_policies(policies_path)
        event_ids = [e.strip() for e in args.events.split(",")] if args.events else None
        events = load_events(event_ids)
        result = build(assets, policies, events)

    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print("结果已写入:", args.out)
    totals = result["totals"]
    print("资产:", totals["assets"], "| 有显式策略:", totals["assets_with_explicit_policy"],
          "| 建议条目:", totals["findings"], "| 需人工复核:",
          totals["needs_human_review"])
    return 0


def _demo_cases(result: dict, events: dict) -> dict:
    """三个演示案例的可复核输出（A 高风险 / B 策略差异 / C 证据不足与冲突）。"""
    by_asset = {item["asset"]["id"]: item for item in result["assets"]}
    return {
        "case_A_high_priority": {
            "intent": "有现实证据支持的高风险处置建议",
            "asset_id": "asset-demo-smolagents-prod",
            "findings": by_asset["asset-demo-smolagents-prod"]["findings"],
        },
        "case_B_policy_difference": {
            "intent": "同一漏洞、同一版本，不同策略下的建议差异",
            "assets": ["asset-demo-vllm-prod", "asset-demo-vllm-lab", "asset-demo-vllm-edge"],
            "prod_summary": by_asset["asset-demo-vllm-prod"]["summary"],
            "lab_summary": by_asset["asset-demo-vllm-lab"]["summary"],
            "edge_summary": by_asset["asset-demo-vllm-edge"]["summary"],
            "prod_policy": by_asset["asset-demo-vllm-prod"]["policy"],
            "lab_policy": by_asset["asset-demo-vllm-lab"]["policy"],
            "edge_policy": by_asset["asset-demo-vllm-edge"]["policy"],
            "edge_findings": by_asset["asset-demo-vllm-edge"]["findings"],
        },
        "case_C_insufficient_evidence_or_conflict": {
            "intent": "信息缺失/策略冲突时的降级与待核实输出",
            "assets": ["asset-demo-copilot-prod", "asset-demo-openwebui"],
            "copilot_findings": by_asset["asset-demo-copilot-prod"]["findings"],
            "openwebui_findings": by_asset["asset-demo-openwebui"]["findings"],
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
