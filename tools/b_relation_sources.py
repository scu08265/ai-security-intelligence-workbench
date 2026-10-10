"""库外源头的关系枚举：把快照里**明确写明**的受影响区间 / 修复版本翻成 gold 可枚举的关系。

为什么单独一个模块：``build_b_relation_gold.py`` 的职责是"从源头枚举应抽取关系"，
而源头不止事件字段一种。10-06 批次的 gold 在 ``completeness.sources_not_covered``
里如实写着"OSV 快照结构未解析成功"；本模块把这一类缺口补上：

* OSV：``affected[].ranges[].events[]`` 的 ``introduced`` / ``fixed`` / ``last_affected``；
* NVD：``configurations[].nodes[].cpeMatch[]`` 的版本边界；
* MITRE CVE：``containers.cna.affected[].versions[]`` 的 ``lessThan`` / ``lessThanOrEqual``。

三条铁律：

1. **不推断**：只翻译快照原文里写着的字段。``unknown`` 区间、GIT 区间、``limit``
   事件都不是可比版本，只记进 ``coverage``，不产出关系。
2. **不合并**：本模块不认识候选集，只输出
   ``(dimension, subject, relation, object)`` 与证据定位；哪些算命中、哪些算漏检，
   由 gold 工具比对候选集后决定。
3. **可回读**：每条关系都带 ``source_path`` + ``source_locator``，复核时能回到原文那一行。

每个函数统一返回 ``{"relations": [...], "coverage": {...}}``。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

UNKNOWN_RANGE = "unknown"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _relation(*, dimension: str, subject: str, relation: str, obj: str,
              source: str, source_path: str, source_locator: str,
              detail: dict) -> dict:
    return {
        "dimension": dimension,
        "subject": subject,
        "relation": relation,
        "object": obj,
        "source": source,
        "source_path": source_path,
        "source_locator": source_locator,
        "detail": detail,
    }


def snapshot_rel_path(snapshot_dir: Path, path: Path) -> str:
    """快照在**副本库**里的相对定位（``snapshots/<source>/<file>``），便于人工回读。"""
    return f"snapshots/{Path(snapshot_dir).name}/{path.name}"


# ---------------------------------------------------------------------------
# OSV
# ---------------------------------------------------------------------------

def _osv_range_spec(introduced: Any, upper_kind: str, upper_value: Any) -> str:
    """把 ``introduced`` + ``fixed``/``last_affected`` 翻成区间字符串。

    与 ``app.normalize.osv_ranges_to_specifiers`` 保持同一语义：下界为 ``0`` 或空
    视为"从最早版本开始"，因此不写 ``>= 0``；``last_affected`` 是闭区间上界。
    """
    lower = [] if introduced in (None, "", "0") else [f">= {introduced}"]
    operator = "<=" if upper_kind == "last_affected" else "<"
    return ", ".join([*lower, f"{operator} {upper_value}"])


def _osv_record_relations(record: dict, rel_path: str, coverage: dict) -> list[dict]:
    relations: list[dict] = []
    subject = _text(record.get("id"))
    for a_index, affected in enumerate(record.get("affected") or []):
        if not isinstance(affected, dict):
            continue
        package = _text((affected.get("package") or {}).get("name"))
        ecosystem = _text((affected.get("package") or {}).get("ecosystem"))
        if not package:
            coverage["ranges_skipped"].append(
                {"path": rel_path, "reason": "affected 缺少 package.name，无法构成关系主体"})
            continue
        ranges = affected.get("ranges") or []
        if not ranges and (affected.get("versions") or []):
            coverage["ranges_skipped"].append(
                {"path": rel_path,
                 "reason": "该 affected 只声明了枚举版本（versions），没有 ranges，"
                           "不构成本批次枚举的区间/修复版本关系"})
        for r_index, rng in enumerate(ranges):
            if not isinstance(rng, dict):
                continue
            if _text(rng.get("type")).upper() == "GIT":
                coverage["ranges_skipped"].append(
                    {"path": rel_path,
                     "reason": f"affected[{a_index}].ranges[{r_index}] 是 GIT 区间（提交哈希），"
                               "不是可比版本"})
                continue
            introduced: Any = None
            for e_index, event in enumerate(rng.get("events") or []):
                if not isinstance(event, dict) or len(event) != 1:
                    coverage["ranges_skipped"].append(
                        {"path": rel_path,
                         "reason": f"affected[{a_index}].ranges[{r_index}].events[{e_index}] "
                                   "不是单键结构"})
                    continue
                (kind, value), = event.items()
                locator = f"affected[{a_index}].ranges[{r_index}].events[{e_index}]"
                if kind == "introduced":
                    introduced = value
                    continue
                if kind in {"fixed", "last_affected"}:
                    if introduced is None:
                        coverage["ranges_skipped"].append(
                            {"path": rel_path, "locator": locator,
                             "reason": f"{kind} 之前没有 introduced，无法确定区间下界"})
                        continue
                    spec = _osv_range_spec(introduced, kind, value)
                    relations.append(_relation(
                        dimension="version_range", subject=subject, relation="affects",
                        obj=f"{package}@{spec}", source="osv_snapshot",
                        source_path=rel_path, source_locator=locator,
                        detail={"package": package, "ecosystem": ecosystem, "range": spec,
                                "introduced": introduced, "upper": {kind: value}}))
                    if kind == "fixed":
                        relations.append(_relation(
                            dimension="fixed_version", subject=subject, relation="fixed_by",
                            obj=f"{package}@{value}", source="osv_snapshot",
                            source_path=rel_path, source_locator=locator,
                            detail={"package": package, "ecosystem": ecosystem,
                                    "fixed_version": value, "introduced": introduced}))
                    introduced = None
                    continue
                if kind == "limit":
                    coverage["ranges_skipped"].append(
                        {"path": rel_path, "locator": locator,
                         "reason": "limit 是提交上界，没有版本等价物"})
                    continue
            if introduced not in (None, "", "0"):
                spec = f">= {introduced}"
                relations.append(_relation(
                    dimension="version_range", subject=subject, relation="affects",
                    obj=f"{package}@{spec}", source="osv_snapshot",
                    source_path=rel_path,
                    source_locator=f"affected[{a_index}].ranges[{r_index}].events[open]",
                    detail={"package": package, "ecosystem": ecosystem, "range": spec,
                            "introduced": introduced, "upper": None}))
    return relations


def osv_snapshot_relations(snapshot_dir: Path, event_ids: set[str]) -> dict:
    """解析 ``snapshots/osv/*.json``。

    目录里有两类文件：单条记录（顶层 ``id``）与批量查询响应
    （``{"results": [{"vulns": [...]}]}``）。**批量响应里只有 ``id`` / ``modified``，
    没有 ``affected``**，因此离线枚举不出区间——这不是"解析失败"，而是数据本身
    只有发现清单。这一点必须在 ``coverage`` 里如实反映，不能伪装成已覆盖。
    """
    relations: list[dict] = []
    coverage: dict[str, Any] = {
        "snapshot_files": 0,
        "detail_records": 0,
        "records_in_scope": 0,
        "records_out_of_scope": [],
        "batch_response_files": 0,
        "batch_advisory_ids": 0,
        "batch_records_with_body": 0,
        "ranges_skipped": [],
    }
    for path in sorted(Path(snapshot_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rel_path = snapshot_rel_path(snapshot_dir, path)
        coverage["snapshot_files"] += 1
        records: list[dict] = []
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            coverage["batch_response_files"] += 1
            for group in payload["results"]:
                for vuln in (group or {}).get("vulns") or []:
                    if not isinstance(vuln, dict):
                        continue
                    coverage["batch_advisory_ids"] += 1
                    if vuln.get("affected"):
                        coverage["batch_records_with_body"] += 1
                        records.append(vuln)
        elif isinstance(payload, dict) and payload.get("id"):
            coverage["detail_records"] += 1
            records.append(payload)
        for record in records:
            record_id = _text(record.get("id"))
            if record_id not in event_ids:
                coverage["records_out_of_scope"].append(
                    {"id": record_id, "path": rel_path})
                continue
            coverage["records_in_scope"] += 1
            relations.extend(_osv_record_relations(record, rel_path, coverage))
    coverage["relations"] = len(relations)
    coverage["relations_deduped_by_source"] = len(
        {(r["subject"], r["dimension"], r["object"]) for r in relations})
    return {"relations": relations, "coverage": coverage}


# ---------------------------------------------------------------------------
# NVD
# ---------------------------------------------------------------------------

def _cpe_product(criteria: str) -> str:
    """``cpe:2.3:a:vendor:product:...`` → ``product``。"""
    parts = _text(criteria).split(":")
    return parts[4] if len(parts) > 4 else ""


NVD_METRIC_KEYS = ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2")


def _nvd_metric_relations(cve_id: str, cve: dict, rel_path: str) -> list[dict]:
    """NVD ``metrics`` 里的 CVSS 向量（与 10-06 批次回填链路读的是同一批字段）。"""
    relations: list[dict] = []
    metrics = cve.get("metrics") or {}
    for key in NVD_METRIC_KEYS:
        for index, item in enumerate(metrics.get(key) or []):
            data = (item or {}).get("cvssData") or {}
            vector = _text(data.get("vectorString"))
            if not vector:
                continue
            relations.append(_relation(
                dimension="cvss", subject=cve_id, relation="has_cvss", obj=vector,
                source="nvd_snapshot", source_path=rel_path,
                source_locator=f"metrics.{key}[{index}]",
                detail={"base_score": data.get("baseScore"),
                        "base_severity": data.get("baseSeverity"), "metric": key}))
    return relations


def _count_by_dimension(relations: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for relation in relations:
        counts[relation["dimension"]] = counts.get(relation["dimension"], 0) + 1
    return counts


def _nvd_configuration_relations(cve_id: str, cve: dict, rel_path: str,
                                 coverage: dict) -> list[dict]:
    relations: list[dict] = []
    for c_index, configuration in enumerate(cve.get("configurations") or []):
        for n_index, node in enumerate((configuration or {}).get("nodes") or []):
            if (node or {}).get("negate"):
                coverage["matches_skipped"].append(
                    {"cve": cve_id, "path": rel_path,
                     "reason": f"configurations[{c_index}].nodes[{n_index}] 是取反节点"})
                continue
            for m_index, match in enumerate((node or {}).get("cpeMatch") or []):
                if (match or {}).get("vulnerable") is False:
                    coverage["matches_skipped"].append(
                        {"cve": cve_id, "path": rel_path,
                         "reason": "cpeMatch 标记 vulnerable=false"})
                    continue
                product = _cpe_product(match.get("criteria"))
                if not product:
                    coverage["matches_skipped"].append(
                        {"cve": cve_id, "path": rel_path,
                         "reason": f"cpeMatch criteria 无法解析出 product：{match.get('criteria')}"})
                    continue
                start_in = _text(match.get("versionStartIncluding")) or None
                start_ex = _text(match.get("versionStartExcluding")) or None
                end_ex = _text(match.get("versionEndExcluding")) or None
                end_in = _text(match.get("versionEndIncluding")) or None
                locator = f"configurations[{c_index}].nodes[{n_index}].cpeMatch[{m_index}]"
                spec = None
                parts: list[str] = []
                if start_in:
                    parts.append(f">= {start_in}")
                elif start_ex:
                    parts.append(f"> {start_ex}")
                if end_ex:
                    parts.append(f"< {end_ex}")
                elif end_in:
                    parts.append(f"<= {end_in}")
                if parts:
                    spec = ", ".join(parts)
                    relations.append(_relation(
                        dimension="version_range", subject=cve_id, relation="affects",
                        obj=f"{product}@{spec}", source="nvd_configuration",
                        source_path=rel_path, source_locator=locator,
                        detail={"product": product, "range": spec,
                                "versionStartIncluding": start_in,
                                "versionStartExcluding": start_ex,
                                "versionEndExcluding": end_ex,
                                "versionEndIncluding": end_in}))
                if end_ex:
                    relations.append(_relation(
                        dimension="fixed_version", subject=cve_id, relation="fixed_by",
                        obj=f"{product}@{end_ex}", source="nvd_configuration",
                        source_path=rel_path, source_locator=locator,
                        detail={"product": product, "fixed_version": end_ex,
                                "bound": "versionEndExcluding"}))
    return relations


def nvd_snapshot_relations(snapshot_dir: Path, cve_ids: set[str]) -> dict:
    relations: list[dict] = []
    coverage: dict[str, Any] = {
        "snapshot_files": 0,
        "records_in_scope": 0,
        "in_scope_ids": [],
        "records_without_event": [],
        "matches_skipped": [],
    }
    for path in sorted(Path(snapshot_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rel_path = snapshot_rel_path(snapshot_dir, path)
        coverage["snapshot_files"] += 1
        for vulnerability in payload.get("vulnerabilities") or []:
            cve = (vulnerability or {}).get("cve") or {}
            cve_id = _text(cve.get("id"))
            if not cve_id:
                continue
            if cve_id not in cve_ids:
                coverage["records_without_event"].append(
                    {"cve": cve_id, "path": rel_path})
                continue
            coverage["records_in_scope"] += 1
            coverage["in_scope_ids"].append(cve_id)
            relations.extend(_nvd_metric_relations(cve_id, cve, rel_path))
            relations.extend(
                _nvd_configuration_relations(cve_id, cve, rel_path, coverage))
    coverage["relations"] = len(relations)
    coverage["relations_by_dimension"] = _count_by_dimension(relations)
    return {"relations": relations, "coverage": coverage}


# ---------------------------------------------------------------------------
# MITRE CVE Program record
# ---------------------------------------------------------------------------

def _mitre_range_spec(version_value: Any, less_than: Any,
                      less_than_or_equal: Any) -> str:
    """与 ``app.normalize.mitre_to_event`` 的区间语义一致。"""
    value = _text(version_value)
    if value and value[0] in "<>=^~":
        return value
    if less_than and value:
        return f">= {value}, < {_text(less_than)}"
    if less_than_or_equal and value:
        return f">= {value}, <= {_text(less_than_or_equal)}"
    if less_than:
        return f"< {_text(less_than)}"
    if less_than_or_equal:
        return f"<= {_text(less_than_or_equal)}"
    if value:
        return f"= {value}"
    return UNKNOWN_RANGE


def mitre_snapshot_relations(snapshot_dir: Path, cve_ids: set[str]) -> dict:
    """MITRE 记录里 ``lessThan`` 声明的上界即**首个修复版本**（``< X`` ⇒ 修复于 ``X``）。

    这不是猜测：CVE 5.x 的 ``versions[]`` 用 ``lessThan`` 表示受影响上界，修复版本
    就是该边界的下一个版本号。``lessThanOrEqual`` 只说明"到 X 为止仍受影响"，
    推不出修复版本，因此只产出区间、不产出 ``fixed_version``。
    """
    relations: list[dict] = []
    coverage: dict[str, Any] = {
        "snapshot_files": 0,
        "records_in_scope": 0,
        "in_scope_ids": [],
        "records_without_event": [],
        "versions_skipped": [],
    }
    for path in sorted(Path(snapshot_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rel_path = snapshot_rel_path(snapshot_dir, path)
        coverage["snapshot_files"] += 1
        cve_id = _text((payload.get("cveMetadata") or {}).get("cveId"))
        if not cve_id:
            continue
        if cve_id not in cve_ids:
            coverage["records_without_event"].append({"cve": cve_id, "path": rel_path})
            continue
        coverage["records_in_scope"] += 1
        coverage["in_scope_ids"].append(cve_id)
        cna = (payload.get("containers") or {}).get("cna") or {}
        for a_index, entry in enumerate(cna.get("affected") or []):
            if not isinstance(entry, dict):
                continue
            package = _text(entry.get("product")) or _text(entry.get("packageName"))
            if not package:
                coverage["versions_skipped"].append(
                    {"path": rel_path, "reason": "affected 缺少 product/packageName"})
                continue
            for v_index, version in enumerate(entry.get("versions") or []):
                if not isinstance(version, dict):
                    continue
                locator = f"containers.cna.affected[{a_index}].versions[{v_index}]"
                if _text(version.get("status")).casefold() == "unaffected":
                    coverage["versions_skipped"].append(
                        {"path": rel_path, "locator": locator,
                         "reason": "status=unaffected（修复后的版本，不是受影响关系）"})
                    continue
                less_than = version.get("lessThan")
                less_than_or_equal = version.get("lessThanOrEqual")
                spec = _mitre_range_spec(version.get("version"), less_than,
                                         less_than_or_equal)
                if spec == UNKNOWN_RANGE:
                    coverage["versions_skipped"].append(
                        {"path": rel_path, "locator": locator,
                         "reason": "versions 条目没有任何版本边界"})
                    continue
                relations.append(_relation(
                    dimension="version_range", subject=cve_id, relation="affects",
                    obj=f"{package}@{spec}", source="mitre_snapshot",
                    source_path=rel_path, source_locator=locator,
                    detail={"package": package, "range": spec,
                            "lessThan": _text(less_than) or None,
                            "lessThanOrEqual": _text(less_than_or_equal) or None}))
                if less_than:
                    fixed_version = _text(less_than)
                    relations.append(_relation(
                        dimension="fixed_version", subject=cve_id, relation="fixed_by",
                        obj=f"{package}@{fixed_version}", source="mitre_snapshot",
                        source_path=rel_path, source_locator=locator,
                        detail={"package": package, "fixed_version": fixed_version,
                                "bound": "lessThan"}))
    coverage["relations"] = len(relations)
    coverage["relations_by_dimension"] = _count_by_dimension(relations)
    return {"relations": relations, "coverage": coverage}
