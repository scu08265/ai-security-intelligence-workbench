"""The model fallback chain and which agent role uses a model.

The system is deliberately not built around a local model runtime, so the chain
has three levels rather than a long list of local models.  Each level is
reported with the reason it is or is not available, and the levels below the
top one are always reachable: no configuration change can make the system
unable to answer, it can only make it less fluent.
"""

from __future__ import annotations

import os
from typing import Any

from . import config

# Which roles in the orchestration call the model and which are plain code.
# ``model`` means the role consults the configured model when one is available;
# ``code`` means the role is deterministic and never depends on a model being
# present.  Getting this wrong in either direction is the easiest way to
# overstate what the system does.
ROLE_BINDINGS: tuple[dict[str, Any], ...] = (
    {"role": "planner", "label": "计划器", "binding": "model",
     "detail": "受限计划器只能在允许的动作列表里选择，看不到凭据，也无法编造来源参数。"},
    {"role": "collector", "label": "采集", "binding": "code",
     "detail": "按登记来源的定义抓取，不经过模型。"},
    {"role": "normalizer", "label": "归一化", "binding": "code",
     "detail": "字段映射、去重与版本区间解析全部确定性完成。"},
    {"role": "retriever", "label": "检索", "binding": "code",
     "detail": "关键词与同义词扩展检索，打分可复算——这正是它可被评测的前提。"},
    {"role": "auditor", "label": "审核", "binding": "code",
     "detail": "按证据完整性规则标注缺口，不由模型判断对错。"},
    {"role": "scheduler", "label": "调度", "binding": "code",
     "detail": "计划任务触发与自愈降级策略。"},
    {"role": "answer_writer", "label": "答案组织", "binding": "model_optional",
     "detail": "有模型时由模型转述，没有模型时按证据拼装；两种模式都必须带引用。"},
)


def _key_present() -> bool:
    return bool(os.getenv(config.model_api_key_env(), "").strip())


def chain() -> dict[str, Any]:
    key = _key_present()
    switched_on = config.model_enabled()
    model = config.model_config()
    active_level = 1 if (key and switched_on) else 3
    levels = [
        {
            "level": 1,
            "name": "远端模型协助",
            "available": bool(key and switched_on),
            "detail": (
                f"{model.get('model', config.DEFAULT_MODEL_NAME)} @ "
                f"{model.get('base_url', config.DEFAULT_MODEL_BASE_URL)}"
            ),
            "skip_reason": None if (key and switched_on) else (
                "未配置 API Key，整条链路不发起外部请求" if not key else "已被 INTEL_USE_MODEL 关闭"
            ),
        },
        {
            "level": 2,
            "name": "模型计划 + 本地证据拼装",
            "available": bool(key and switched_on),
            "detail": "计划器仍可用模型选证据，但答案由本地拼装，避免模型写没有引用的话。",
            "skip_reason": None if (key and switched_on) else "模型不可用，直接进入本地抽取",
        },
        {
            "level": 3,
            "name": "本地确定性证据抽取与拼装",
            "available": True,
            "detail": "检索、富化、研判、拒答全部本地完成；这是兜底档，也是评测所用的档位。",
            "skip_reason": None,
        },
    ]
    for level in levels:
        level["active"] = level["level"] == active_level
    return {
        "active_level": active_level,
        "mode": config.mode_label(),
        "model_configured": key,
        "levels": levels,
        "role_bindings": [dict(item) for item in ROLE_BINDINGS],
        "policy": (
            "任何一层不可用都只降低表述能力，不降低证据要求：低层仍必须给出引用，"
            "证据不足时同样拒答。"
        ),
        "note": (
            "本系统没有本地模型层（如 Ollama / 本地权重），因此链路是三级而不是四级；"
            "如需本地层，需要额外部署运行时，属于部署决策而不是配置开关。"
        ),
    }
