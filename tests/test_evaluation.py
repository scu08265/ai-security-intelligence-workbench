"""B 任务回归测试：评测用例构造必须使用每个事件自己的 probe 版本。

Bug B-01：`app/evaluation.py::_make_cases()` 内的 `out_of_scope` 与 `withdrawn`
两个闭包引用了循环变量 `inside`，却没有像 `missing_condition` 那样按迭代绑定，
因此它们在调用时取到的是循环结束后的最终值（最后一条案例的 `inside`）。

这两个用例的**最终判定状态**不受该缺陷影响：`assess_asset` 对「事件已撤回」
和「资产未授权」两种情形在版本比较之前就短路返回。所以只看 pass/fail 永远
发现不了它——必须核验实际传入 `assess_asset` 的版本参数。

参见 `docs/B_TASK_AUDIT.md` 第 4 节 Bug B-01。
"""

from __future__ import annotations

import json

from packaging.version import Version
from packaging.specifiers import SpecifierSet

from app import config, evaluation, intelligence, normalize

# 这三个用例都会把所属事件的 inside 版本传给 assess_asset
VERSION_SENSITIVE_SUFFIXES = ("::missing-condition", "::out-of-scope", "::withdrawn")


def _research_entries() -> list[tuple[str, str, str]]:
    """返回 [(事件 ID, inside 版本, 受影响区间)]，只保留可推导出版本的研究案例。"""
    payload = json.loads(
        (config.BASE_DIR / "research" / "cases.json").read_text(encoding="utf-8")
    )
    entries: list[tuple[str, str, str]] = []
    for case in payload.get("cases") or []:
        event = normalize.research_case_to_event(case)
        affected = (event.get("affected") or [None])[0]
        if not affected:
            continue
        inside, _ = evaluation._probe_versions(affected)
        if inside:
            entries.append((str(event.get("id")), inside, str(affected.get("range") or "")))
    return entries


def test_probe_versions_are_distinct_and_really_inside_the_range():
    """前提校验。

    如果所有研究案例的 inside 版本相同，下面的回归测试就失去了发现能力；
    同时确认 `_probe_versions` 给出的 inside 确实落在该事件自己的受影响区间内，
    避免把错误的期望值写进断言。
    """
    entries = _research_entries()
    assert len(entries) >= 2, "至少需要 2 条可推导版本的研究案例"
    assert len({version for _, version, _ in entries}) >= 2, (
        "research/cases.json 各事件的 inside 版本必须互不相同，"
        "否则无法用版本区分闭包是否串值"
    )
    for event_id, version, spec in entries:
        assert Version(version) in SpecifierSet(spec), (
            f"{event_id} 的 inside 版本 {version} 不在受影响区间 {spec!r} 内"
        )


def test_version_sensitive_cases_pass_their_own_probe_version(monkeypatch):
    """每条用例传给 assess_asset 的版本，必须等于它自己事件的 inside。

    该断言刻意绕过判定结果，直接检查传参，因为缺陷本身不影响判定结果。
    """
    seen: dict[str, list[str | None]] = {}
    original = intelligence.assess_asset

    def spy(event, asset):
        seen.setdefault(str(event.get("id")), []).append(asset.get("version"))
        return original(event, asset)

    monkeypatch.setattr(intelligence, "assess_asset", spy)

    executed = 0
    for case in evaluation._make_cases():
        if case.id.endswith(VERSION_SENSITIVE_SUFFIXES):
            case.check()
            executed += 1

    entries = _research_entries()
    expected = {event_id: version for event_id, version, _ in entries}
    assert expected, "没有可用的研究案例，测试无效"
    assert executed == len(expected) * len(VERSION_SENSITIVE_SUFFIXES), (
        f"应执行 {len(expected) * len(VERSION_SENSITIVE_SUFFIXES)} 条用例，实际 {executed} 条"
    )
    assert set(seen) == set(expected), (
        f"被调用的评测事件集合不匹配：{sorted(seen)} != {sorted(expected)}"
    )

    for event_id, version in expected.items():
        passed = {str(item) for item in seen[event_id]}
        assert passed == {version}, (
            f"{event_id} 应只使用自己的 inside 版本 {version}，"
            f"实际传入 {sorted(passed)}（疑似取到了循环中其他案例的版本）"
        )
