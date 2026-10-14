# Changelog

## Unreleased

- Received the two derived corpus copies that had been blocking four tests.
  `B_DERIVATIVE_CORPORA_20261012.zip` verified at 80,208,714 bytes / SHA-256
  `98bd19c5…961674a`, its 139 manifest entries checked one by one with zero
  mismatches, and both main databases hashed against the recorded values before
  they were put in place.  The suite no longer skips anything: **698 passed,
  0 skipped**, where the relation recheck, expansion and 2026-10-02 reeval
  modules alone went from 42 passed / 4 skipped to 46 passed / 0 skipped.
  The archive stays out of the repository, as the ignore rules and the task
  brief require.
- The test summary is now part of the shared snapshot, so the report's
  "automated tests" row cannot go stale on its own: pass it to
  `tools/refresh_metrics_snapshot.py --write --tests "698 passed, 0 skipped"`,
  and omitting it keeps the previous value rather than blanking the row.  Two
  places in the report generator still hard-coded the old figure and are now
  read from the snapshot.
- Made the dated metrics snapshot refreshable instead of hand-edited, after a
  reviewer found the report saying 596 events / 19 collection days while
  `docs/METRICS_BASELINE.md` said 548 / 18.  Both were live readings taken a day
  apart, which is the real defect: a hand-written snapshot goes stale within a
  day because the collection task adds events hourly.  `tools/refresh_metrics_snapshot.py`
  now rewrites the marked block in the baseline document and writes
  `docs/report/metrics_snapshot.json`, and `tools/build_technical_report.py`
  reads that same file for its headline and performance figures, so the two
  cannot disagree.
- Corrected an overclaim the refresh exposed: the report asserted the seven-day
  continuous-run target was met.  It was met for the window ending 2026-10-10,
  but the scheduled task's trigger window expired on 10-11, 10-12 has no
  scheduled run at all, and the streak has restarted.  The report now states the
  current status from the snapshot instead of a fixed claim.
- Added a term dictionary that treats a term as a first-class object.  Each of
  the 14 seeded AI-security terms is grounded in the stored corpus: how many
  documents carry it, which ones, and the sentence that introduces it, with the
  chunk id and character offset needed to read it back.  On the demo database
  10 of 14 are covered across 44 documents, and the four the corpus does not
  contain are reported as uncovered rather than given an invented definition.
  Terms stored as structured fields (CVSS, POC) report an event count instead
  of a quote, and `term_edges()` exposes the term → document link for callers
  that want it as a graph edge.
- Added the model fallback chain and the role binding table behind
  `GET /api/system/model-chain`: three levels with the reason each is skipped,
  plus which orchestration role consults a model and which is deterministic
  code.  The chain has three levels rather than a list of local models because
  this system has no local model runtime, and the endpoint says so instead of
  implying a tier that does not exist.
- Added the answer's technical detail section: the plan, the tool calls with
  their recorded result and row count, the elapsed time and the known
  limitations.  The trace table already existed, but the plan and the tool
  budget had no outlet in the interface at all.
- Added recommended questions taken from the frozen 50-question evaluation set,
  so what the page invites you to ask is the same population the report scores;
  refusal cases are left out of the suggestions.
- Fixed a defect found while building the term dictionary: ASCII aliases were
  matched as substrings, so `rag` matched `fragmenta` and the dictionary
  reported the wrong document with a nonsense definition sentence.  Aliases now
  require a word boundary, and the sentence search is case-insensitive against
  the original text so the reported offset stays correct.
- Extended self-healing from "retry once" to a bounded degradation policy.  A
  source that misses three collection attempts in a row now leaves the
  unattended set for a six-hour cooldown, or hands over to a substitute that is
  declared on the source itself (`arxiv` → `openalex`) instead of being
  invented.  Degradations live in their own table so existing databases pick
  them up without a migration runner, every substitution is written into the
  run record, and a source that answers again is un-degraded automatically.
  `tools/run_self_healing_drill.py` proves the loop on a database copy with an
  injected fault and writes `reports/self-healing-drill.json`.
- Added the two panels the review asked for: a source-health panel (per-source
  status, last success, consecutive failures, active degradation) and a system
  health panel (module states, cooldowns, recent alerts) on the scorecard tab,
  backed by a new `GET /api/system/health` that reports only persisted state.
- Added `docs/COMPETITION_RUBRIC_MAPPING.md`, which maps every scoring line to
  the tier it actually reaches with the evidence for it, plus the source
  classification table the review requested.  It records the three honest
  gaps: no real-time monitoring, timeliness reaching only the qualifying tier,
  and cross-document paths at 10/21.
- Added `docs/CASE_ENRICHMENT_INFERENCE.md` (a real event traced through CVSS,
  affected ranges and fixed versions, each step carrying its own source id) and
  `docs/CASE_QA_MULTITURN_CROSSDOC.md` (the multi-turn and cross-document demo
  script taken from the 50-question evaluation set).
- Added the technical report as Word and PDF, generated from one content model
  by `tools/build_technical_report.py` so the two files cannot drift apart,
  with four consistent figures.  `docs/report/` also keeps the figures.
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
