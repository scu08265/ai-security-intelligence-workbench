# Changelog

## Unreleased

- Added five blog/community sources: Qianxin TI blog, Qianxin Butian community,
  AnQuanKe, Securelist and Cisco Talos.  FreeBuf was evaluated and dropped: its
  Aliyun WAF returns a JavaScript challenge to non-browser clients, so it can
  never be collected honestly.
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
