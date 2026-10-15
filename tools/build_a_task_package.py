"""Assemble the A-task delivery package outside the repository.

Copies the evidence, documents, figures, screenshots and the tools that
produced them into one folder, writes an index, and zips it.  Nothing inside
the repository is modified.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REPORTS = [
    "continuous-run-check.json",
    "qa-partial-classification.json",
    "timeliness-attribution.json",
    "ci-validation.json",
    "reliability-report.json",
    "source-health.json",
    "latency-summary.json",
    "self-healing-drill.json",
    "docker-validation.json",
    "evidence-consistency.json",
]

DOCS = [
    "A_CONTINUOUS_RUN_STATUS_20261015.md",
    "A_QA_PARTIAL_CLASSIFICATION.md",
    "A_TIMELINESS_ATTRIBUTION.md",
    "A_DISPOSITION_LIVE_CLOSURE.md",
    "A_DISPOSITION_TECHNICAL_CONCLUSION.md",
    "DISPOSITION_CLOSURE.md",
    "COMPETITION_RUBRIC_MAPPING.md",
    "METRICS_BASELINE.md",
    "DOCKER_CI_GUIDE.md",
    "TASK_BRIEF_20261013.md",
    "TASK_BRIEF_20261014.md",
]

TOOLS = [
    "check_continuous_run.py",
    "classify_qa_partial_cases.py",
    "record_ci_validation.py",
    "build_timeliness_attribution.py",
    "build_technical_report.py",
    "refresh_metrics_snapshot.py",
    "browser_check.py",
    "capture_disposition_screenshots.py",
    "run_disposition_freeze_recheck.py",
    "scan_disposition_cohorts.py",
    "verify_disposition_backup.py",
]

BRANCHES = [
    "docs/a-timeliness-baseline-20261015",
    "chore/a-ci-continuous-run-20261015",
    "feat/a-qa-partial-classification-20261015",
]


def _copy(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT.parent / "A-task-deliverables-20261015")
    parser.add_argument("--zip", type=Path,
                        default=ROOT.parent / "A-task-deliverables-20261015.zip")
    args = parser.parse_args()

    target = args.output_dir.resolve()
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    copied, missing = [], []
    for name in REPORTS:
        (copied if _copy(ROOT / "reports" / name, target / "reports" / name)
         else missing).append(f"reports/{name}")
    for name in DOCS:
        (copied if _copy(ROOT / "docs" / name, target / "docs" / name)
         else missing).append(f"docs/{name}")
    for name in TOOLS:
        (copied if _copy(ROOT / "tools" / name, target / "tools" / name)
         else missing).append(f"tools/{name}")

    for name in ("AI安全知识情报系统技术报告.docx", "AI安全知识情报系统技术报告.pdf"):
        (copied if _copy(ROOT / "docs" / "report" / name, target / "docs" / "report" / name)
         else missing).append(f"docs/report/{name}")

    for folder, pattern in (("docs/report/figures", "*.png"), ("docs/screenshots", "*.png")):
        for path in sorted((ROOT / folder).glob(pattern)):
            destination = target / folder / path.name
            _copy(path, destination)
            copied.append(f"{folder}/{path.name}")

    # 有些产物只在某条分支上（例如 A1 的证据不在当前工作树里）。工作树里找不到时，
    # 回退到按分支读取该文件，并记录它的来源，避免包里出现"看起来缺失"的条目。
    recovered = []
    for name in list(missing):
        for branch in BRANCHES:
            result = subprocess.run(
                ["git", "-C", str(ROOT), "show", f"{branch}:{name}"],
                capture_output=True,
            )
            if result.returncode != 0:
                continue
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(result.stdout)
            copied.append(f"{name}（取自 {branch}）")
            recovered.append(f"{name}  ← {branch}")
            missing.remove(name)
            break

    bundle = target / "git" / "a-task-branches.bundle"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "-C", str(ROOT), "bundle", "create", str(bundle), *BRANCHES],
        capture_output=True, text=True,
    )
    notes = []
    if result.returncode == 0:
        notes.append(f"git bundle 已生成：{bundle.name}（含 {len(BRANCHES)} 条分支）")
    else:
        notes.append(f"git bundle 生成失败：{result.stderr.strip()[:200]}")

    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")
    index = [
        "# A 项交付材料（2026-10-15）",
        "",
        f"打包时间：{stamp}",
        f"仓库：{ROOT}",
        f"分支：{', '.join(BRANCHES)}",
        "",
        "## 目录",
        "",
        "- `reports/`  机读证据（连续运行核对、问答三分类、时效性归因、CI 校验、可靠性、来源健康、时延、自愈演练、容器验收、口径一致性）",
        "- `docs/`     报告与口径文档（含技术报告 docx/pdf、对照表、指标基线、连续运行状态、问答三分类、任务书）",
        "- `docs/report/figures/`  报告插图（含新增的图 5 采集状态机、图 6 自愈状态机）",
        "- `docs/screenshots/`     页面截图（09/10 两个健康面板，11 术语字典，12 模型降级链，13 推荐问法，14 技术详情）",
        "- `tools/`    产出上述证据的脚本，全部可重跑",
        "- `git/`      三条分支的 git bundle，可在别处 git fetch 还原（A3/A4 与 A2 同基，A1 独立）",
        "",
        "## 校验与复跑",
        "",
        "```powershell",
        ".\\tools\\check_continuous_run.py --days 7          # 逐日核对 trigger=scheduled 并算 target_met ETA",
        ".\\tools\\build_timeliness_attribution.py            # 时效性分列与上游归因",
        ".\\tools\\refresh_metrics_snapshot.py --write        # 必须在持有口径基线库的机器上跑",
        ".\\tools\\build_technical_report.py                  # 重新生成 docx 与 pdf",
        ".\\tools\\browser_check.py --base http://127.0.0.1:8020",
        "```",
        "",
        f"文件数：{len(copied)}；缺失：{len(missing)}",
    ]
    if recovered:
        index += ["", "## 按分支回取的文件", ""] + [f"- {line}" for line in recovered]
    if missing:
        index += ["", "## 未找到的文件", ""] + [f"- {name}" for name in missing]
    index += ["", "## 备注", ""] + [f"- {note}" for note in notes]
    (target / "说明.md").write_text("\n".join(index) + "\n", encoding="utf-8")

    if args.zip.exists():
        args.zip.unlink()
    shutil.make_archive(str(args.zip.with_suffix("")), "zip", target)
    size_mb = round(args.zip.stat().st_size / 1024 / 1024, 2)
    print(f"包目录：{target}")
    print(f"压缩包：{args.zip}（{size_mb} MB）")
    print(f"文件数：{len(copied)}，缺失：{len(missing)}")
    for name in missing:
        print("   缺失:", name)
    for note in notes:
        print("  ", note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
