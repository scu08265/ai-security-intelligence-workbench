# Changelog

## Unreleased

- Fixed the mid-frequency retrieval regression that had been failing on the B
  corpus for days, and it was not the discriminative-term guard: `kernel-level`
  already passed.  A Chinese phrase in a question expands into several English
  synonyms (`论文` -> paper/study/arxiv) and every synonym was scored as its own
  term, so in a corpus of papers a chunk that merely contains the word "paper"
  collected roughly four times what the actual subject term scored.  Asking
  `multi-agent 主题出现在哪些论文中？` pushed the paper genuinely about
  multi-agent out of the top 8, while the same question phrased with 文章 or
  文档 retrieved it first.  A synonym group now counts as one concept, at the
  strength of its best member.
- Received and verified the B evaluation corpus: 47 files, every SHA-256 and
  byte count matching `MANIFEST.sha256`, restored to `D:\ICT\intel-data-b`
  (`intel.sqlite` = 8,183,808 B / `4095a5b1…8254285`).  The suite went from
  618 passed / 60 skipped to **674 passed / 4 skipped**; the four remaining
  skips need the two derived copies that were not in the archive
  (`intel-data-b-cvss-20261006`, `intel-data-b-poc-20261002`).
- Completed the local container acceptance on a real Docker Engine (29.8.1): the
  image builds, the Compose stack starts, the container reports `healthy` and
  `/api/health` answers `status=ok` with the version in `VERSION`.  The evidence
  is `reports/docker-acceptance.log` plus `reports/docker-validation.json`, which
  now records the nine individual checks instead of a hand-written summary.
  Two blockers were removed along the way: `scripts/run_docker_acceptance.cmd`
  hard-coded the CLI path to `C:\Program Files` (this machine installs under
  `D:\Docker`) and waited with `timeout`, which exits immediately when stdin is
  redirected, so the health wait never actually waited.  The build now passes
  `--build-arg APP_VERSION` from `VERSION` like CI does, so the container no
  longer reports 0.2.3 while the repository says 0.2.4.
- Stopped the container acceptance from copying credentials into a committed
  artifact: `docker compose config` and `docker inspect` both print resolved
  environment values, so the real `GITHUB_TOKEN` from `.env` landed in
  `reports/docker-acceptance.log` and GitHub push protection rejected the push.
  Compose is now pointed at a scratch `--env-file`, because clearing the shell
  variable alone makes Compose fall back to `./.env`, and the acceptance tool
  fails verification if any secret shape or `.env` value reaches the evidence.
- Made two tests independent of the checkout path and locale, so the suite
  passes from a Chinese working directory too: the config subprocess test now
  decodes the child with the same UTF-8 it pins, and the candidate-set
  comparison normalises line endings instead of comparing raw bytes.
- Fixed cumulative collection evidence being silently truncated by a page cap:
  `list_runs()` limited every read to 200 rows and `list_events()` to 500, so
  once the run log or the corpus outgrew the cap the oldest days dropped out of
  every total.  The 2026-10-08 batch alone produced 201 collection runs, which
  hid all earlier days and made "累计有采集日期" read 2 instead of 16 while the
  seven-day ledger showed 0 for 10-04..10-08.  Evidence aggregation now reads
  the whole table (`limit=None`); page-limited API reads stay capped.
- Added the teacher-recommended blog/community sources: Qianxin TI blog,
  FreeBuf, Securelist and Cisco Talos, plus Qianxin Butian community and
  AnQuanKe as additional sources.  FreeBuf uses a source-specific system-curl
  transport because its Aliyun WAF rejects the httpx TLS fingerprint with a
  JavaScript challenge even though the same official RSS endpoint is publicly
  accessible.
- Fixed AI-relevance classification for Chinese and punctuated headlines, which
  was the reason community feeds produced zero events:
  * CJK terms are matched as substrings; the ASCII token regex never produced
    them, so a Chinese headline could not qualify at all.
  * Unicode dashes (U+2010-U+2015) are normalised, so "AI‑powered" no longer
    hides the "ai" signal inside a single hyphenated token.
  * An AI component named in a headline (LiteLLM, Ollama) qualifies even when
    no `package` argument is supplied, as blog titles never carry one.
  * Security-intent words now include `security` and Chinese equivalents, so
    "AI security" is recognised without a CVE identifier.
- Added per-source `lookback_days` for the first collection.  Low-frequency
  blogs publish monthly, so the previous 30-day window skipped their newest
  post and the cursor then made it permanently unreachable.
- Corrected `collect_page` reporting: it no longer logs "已生成知识条目" when the
  event was actually filtered out.

## 0.2.3

- Added a real scheduled-run evidence path that distinguishes all collection
  executions from Windows Task Scheduler/cron executions.
- Unified scorecard, Markdown, and JSON timeliness denominators around the
  first monitored observation and excluded pre-monitoring backfill.
- Recorded authenticated CI and rollback evidence against repository commits.
- Hardened the latest Docker image acceptance and version checks.

## 0.2.2

- Completed NVD pagination so normal result sets drain all pages without partial status.
- Added optional NVD API key, page delay, and cursor advancement only after complete scans.
- Added hourly scheduler loop and updated Windows Task Scheduler/cron examples.
- Fixed source-health classification so `stale` sources are reported as failures
  with historical data and are included in the success-rate denominator.
- Merged upstream multi-agent runtime and bounded source self-healing.
- Fixed self-healing success detection to use post-retry source state.

## 0.2.1

- Completed engineering delivery for Docker, Compose, CI, health checks, structured logs, and alerts.
- Added deployment, health-check, and rollback scripts.
- Added CI dependency consistency, Compose validation, and container build checks.
- Added engineering delivery documentation.

## 0.2.0

- Added daily scheduled collection with task ID, planned time, and actual time.
- Added reliability, source-health, timeliness, and continuous-run reporting.
- Added external failure alerts, structured JSONL logs, and optional Webhook.
- Added Docker, Compose, CI, backup, restore, and rollback documentation.
- Added report charts and operational screenshots.
- Merged upstream retry, stale-source, timestamp, and frozen-evaluation fixes.

## 0.1.0

- Initial AI security intelligence workbench baseline.
