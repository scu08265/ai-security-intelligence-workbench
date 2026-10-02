"""CycloneDX asset inventory import and evidence-bound assessment.

Only fields asserted by the BOM are stored under ``sbom``.  Deployment facts
such as exposure, business criticality and runtime conditions remain unknown;
they are never synthesized from package metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from . import agents, intelligence, storage

MAX_COMPONENTS = 5000
SUPPORTED_SPEC_VERSIONS = {"1.3", "1.4", "1.5", "1.6", "1.7"}


class CycloneDXError(ValueError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _batch_id(bom: dict) -> str:
    canonical = json.dumps(bom, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "cdx-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _asset_id(batch_id: str, bom_ref: str) -> str:
    digest = hashlib.sha256(f"{batch_id}\0{bom_ref}".encode("utf-8")).hexdigest()[:20]
    return "asset-cdx-" + digest


def _ecosystem(purl: str) -> str:
    match = re.match(r"^pkg:([^/]+)/", purl, re.I)
    return match.group(1).casefold() if match else ""


def _tools(metadata: dict) -> list[dict]:
    value = metadata.get("tools") or []
    candidates = value if isinstance(value, list) else [
        *(value.get("components") or []), *(value.get("services") or [])
    ] if isinstance(value, dict) else []
    result = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        result.append({key: item.get(key) for key in ("vendor", "name", "version")
                       if item.get(key) is not None})
    return result


def parse(bom: dict) -> dict:
    if not isinstance(bom, dict):
        raise CycloneDXError("BOM 必须是 JSON 对象")
    if bom.get("bomFormat") != "CycloneDX":
        raise CycloneDXError("bomFormat 必须为 CycloneDX")
    spec_version = _text(bom.get("specVersion"))
    if spec_version not in SUPPORTED_SPEC_VERSIONS:
        raise CycloneDXError(f"不支持的 CycloneDX specVersion：{spec_version or 'missing'}")
    components = bom.get("components") or []
    if not isinstance(components, list):
        raise CycloneDXError("components 必须是数组")
    if len(components) > MAX_COMPONENTS:
        raise CycloneDXError(f"components 超过单批上限 {MAX_COMPONENTS}")

    errors: list[str] = []
    unique: dict[str, dict] = {}
    duplicate_count = 0
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            errors.append(f"components[{index}] 不是对象")
            continue
        bom_ref = _text(component.get("bom-ref"))
        name = _text(component.get("name"))
        component_type = _text(component.get("type"))
        if not bom_ref:
            errors.append(f"components[{index}] 缺少 bom-ref")
        if not name:
            errors.append(f"components[{index}] 缺少 name")
        if not component_type:
            errors.append(f"components[{index}] 缺少 type")
        if not (bom_ref and name and component_type):
            continue
        normalized = {
            "bom_ref": bom_ref, "name": name,
            "version": _text(component.get("version")) or None,
            "type": component_type, "group": _text(component.get("group")) or None,
            "purl": _text(component.get("purl")) or None,
            "cpe": _text(component.get("cpe")) or None,
        }
        if bom_ref in unique:
            duplicate_count += 1
            if unique[bom_ref] != normalized:
                errors.append(f"bom-ref {bom_ref} 重复且组件身份冲突")
            continue
        unique[bom_ref] = normalized
    if errors:
        raise CycloneDXError("；".join(errors[:20]))

    metadata = bom.get("metadata") if isinstance(bom.get("metadata"), dict) else {}
    batch_id = _batch_id(bom)
    source_component = metadata.get("component") if isinstance(metadata.get("component"), dict) else {}
    assets = []
    for component in unique.values():
        purl = component["purl"] or ""
        assets.append({
            "id": _asset_id(batch_id, component["bom_ref"]),
            "name": component["name"],
            "component": component["name"],
            "ecosystem": _ecosystem(purl),
            "version": component["version"],
            "authorized": None,
            "is_demo": None,
            "policy": None,
            "sbom": {
                **component,
                "batch_id": batch_id,
                "serial_number": bom.get("serialNumber"),
                "sbom_version": bom.get("version"),
                "spec_version": spec_version,
                "inventory_timestamp": metadata.get("timestamp"),
                "generation_tools": _tools(metadata),
                "source": {
                    "format": "CycloneDX JSON",
                    "root_bom_ref": source_component.get("bom-ref"),
                    "root_name": source_component.get("name"),
                },
            },
            "deployment_context": {
                "exposure": None, "business_criticality": None, "conditions": None,
                "status": "not_asserted_by_sbom",
            },
        })
    return {
        "batch_id": batch_id, "spec_version": spec_version,
        "serial_number": bom.get("serialNumber"),
        "inventory_timestamp": metadata.get("timestamp"),
        "generation_tools": _tools(metadata), "assets": assets,
        "input_component_count": len(components),
        "deduplicated_asset_count": len(assets), "duplicate_component_count": duplicate_count,
        "assumptions": [
            "每个唯一 bom-ref 代表该 SBOM 快照中的一个组件资产。",
            "目录或镜像盘点只能证明清单可见组件，不能证明组件正在运行。",
            "SBOM 未声明 exposure、business_criticality 或 runtime conditions；这些字段保持未知。",
            "导入授权范围必须由调用方显式确认，不从 SBOM 推断。",
        ],
    }


def preview(bom: dict) -> dict:
    parsed = parse(bom)
    return {**parsed, "assets": parsed["assets"], "dry_run": True, "mutated": False,
            "assessment_relationship_count": 0}


def import_bom(
    bom: dict, *, authorized: bool, is_demo: bool = True,
    policies: dict[str, dict[str, Any]] | None = None,
) -> dict:
    parsed = parse(bom)
    existing = {item.get("id") for item in storage.list_assets()}
    policies = policies or {}
    created = updated = 0
    policy_count = 0
    for candidate in parsed["assets"]:
        asset = dict(candidate)
        asset["authorized"] = authorized
        asset["is_demo"] = bool(is_demo)
        bom_ref = _text((asset.get("sbom") or {}).get("bom_ref"))
        policy = (
            policies.get(asset["id"])
            or policies.get(_text(asset.get("component")))
            or policies.get(bom_ref)
        )
        if policy is not None and not isinstance(policy, dict):
            raise CycloneDXError(f"资产 {asset['id']} 的 policy 必须是对象")
        asset["policy"] = dict(policy) if isinstance(policy, dict) else None
        if asset["policy"] is not None:
            policy_count += 1
        asset["authorization_assertion"] = {
            "value": authorized,
            "source": "cyclonedx import request",
            "note": "调用方声明是否允许本系统对该批次执行影响研判；不是 SBOM 字段。",
        }
        if asset["id"] in existing:
            updated += 1
        else:
            created += 1
        storage.upsert_asset(asset)
    return {
        **{key: value for key, value in parsed.items() if key != "assets"},
        "dry_run": False, "created": created, "updated": updated,
        "authorized": authorized, "is_demo": bool(is_demo),
        "policy_asset_count": policy_count,
        "assessment_relationship_count": 0,
        "idempotent": updated == parsed["deduplicated_asset_count"],
    }


def assess_batch(batch_id: str) -> dict:
    assets = [item for item in storage.list_assets()
              if (item.get("sbom") or {}).get("batch_id") == batch_id]
    if not assets:
        raise CycloneDXError("批次不存在或尚未导入")
    events, _ = storage.list_events(limit=500)
    counts: Counter[str] = Counter()
    relationships = []
    for event in events:
        for asset in assets:
            if not agents._component_matches(event, asset):
                continue
            assessment = intelligence.assess_asset(event, asset)
            version_outside = any(
                "不在已知受影响区间" in str(reason)
                for reason in assessment.get("reasons") or []
            )
            event_conditions = event.get("conditions") or []
            condition_factor = {
                "applicable": not version_outside,
                "status": (
                    "not_applicable_version_outside_range" if version_outside
                    else ("evaluated" if event_conditions else "no_conditions_declared")
                ),
                "declared_condition_count": len(event_conditions),
                "reason": (
                    "资产版本明确不在已知受影响区间，触发条件不参与结论。"
                    if version_outside else
                    "仅在版本命中受影响区间时，触发条件才会缩小适用范围。"
                ),
            }
            assessment["sbom_batch_id"] = batch_id
            assessment["decision_factors"] = {
                "component_match": {
                    "matched": True, "event_component": event.get("component"),
                    "asset_component": asset.get("component"), "basis": "normalized exact component/package match",
                },
                "inventory_identity": {
                    "bom_ref": (asset.get("sbom") or {}).get("bom_ref"),
                    "purl": (asset.get("sbom") or {}).get("purl"),
                    "version": asset.get("version"), "type": (asset.get("sbom") or {}).get("type"),
                    "source": "CycloneDX SBOM",
                },
                "deployment_context": asset.get("deployment_context"),
                "condition_evaluation": condition_factor,
                "authorization": asset.get("authorization_assertion"),
                "rule_result": {"status": assessment["status"],
                                "reasons": assessment["reasons"],
                                "evidence_ids": assessment["evidence_ids"]},
            }
            storage.save_assessment(assessment)
            counts[assessment["status"]] += 1
            relationships.append({
                "event_id": assessment["event_id"], "asset_id": assessment["asset_id"],
                "event_title": event.get("title"), "asset_name": asset.get("name"),
                "status": assessment["status"], "priority": assessment["priority"],
                "reasons": assessment["reasons"],
                "evidence_ids": assessment["evidence_ids"],
                "decision_factors": assessment["decision_factors"],
            })
    return {
        "batch_id": batch_id, "deduplicated_asset_count": len(assets),
        "assessment_relationship_count": len(relationships),
        "status_counts": dict(counts), "relationships": relationships,
        "note": "只为组件匹配的事件-资产对保存关系；未知部署上下文不会被补写。",
    }
