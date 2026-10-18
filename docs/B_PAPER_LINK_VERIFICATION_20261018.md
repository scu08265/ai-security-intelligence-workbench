# 论文关联 21 条：前后状态表（2026-10-18）

由 `tools/verify_paper_links.py` 生成，输入是
`evaluation/b_relation_candidates_20261010.json` 里 `dimension=paper_link`
且 `candidate_value` 有空字段的 21 条。判定规则：从 `pdf_url` 提取 DOI
（末尾 `.pdf` 先剥掉）与 OpenAlex 记录逐字比对；没有 DOI 时用 URL 里能读出的
标题 + 年份双匹配，两项都命中才算；其余写 `unknown` 并注明缺哪一项。

汇总：21 条里 **6 条 DOI 逐字一致**，
**15 条 unknown**（原因逐行写在最后一列）。

| 关系 ID | 事件 | 状态 | OpenAlex DOI | URL DOI | 标题匹配 | 年份匹配 | 缺失项 / 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BREL-PA-0001 | OPENALEX-W7214527440 | doi_match | 10.1186/s43556-026-00600-7 | 10.1186/s43556-026-00600-7 | — | — | DOI 逐字一致：10.1186/s43556-026-00600-7 |
| BREL-PA-0002 | OPENALEX-W7214558721 | doi_match | 10.1007/s44265-026-00088-7 | 10.1007/s44265-026-00088-7 | — | — | DOI 逐字一致：10.1007/s44265-026-00088-7 |
| BREL-PA-0003 | OPENALEX-W7214600341 | doi_match | 10.1186/s42400-026-00649-5 | 10.1186/s42400-026-00649-5 | — | — | DOI 逐字一致：10.1186/s42400-026-00649-5 |
| BREL-PA-0004 | OPENALEX-W7214526768 | doi_match | 10.1007/s44163-026-02344-3 | 10.1007/s44163-026-02344-3 | — | — | DOI 逐字一致：10.1007/s44163-026-02344-3 |
| BREL-PA-0005 | OPENALEX-W7214542908 | unknown | 10.1038/s41598-026-72755-w | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0006 | OPENALEX-W7214553113 | unknown | 10.33774/coe-2026-wp8dr | — | 是 | 否 | pdf_url 里没有 DOI；URL 里没有年份，双匹配缺一项 |
| BREL-PA-0007 | OPENALEX-W7214449097 | unknown | 10.38124/ijisrt/26sep879 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0008 | OPENALEX-W7214468787 | doi_match | 10.34218/ijaiml_05_02_007 | 10.34218/ijaiml_05_02_007 | — | — | DOI 逐字一致：10.34218/ijaiml_05_02_007 |
| BREL-PA-0010 | OPENALEX-W7125151750 | unknown | 10.70777/si.v3i3.18747 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0011 | OPENALEX-W7151534166 | unknown | 10.70777/si.v3i3.18746 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0012 | OPENALEX-W7213611819 | unknown | 10.70777/si.v3i3.18734 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0013 | OPENALEX-W7214295679 | unknown | 10.56201/rjpst.vol.8.no8.2025.pg142.212 | — | 是 | 否 | pdf_url 里没有 DOI；年份不一致（URL 2025 / OpenAlex 2026） |
| BREL-PA-0014 | OPENALEX-W7214338629 | unknown | 10.37547/tajmei/volume08issue09-04 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0015 | OPENALEX-W7214339430 | unknown | 10.15439/2026f6361 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0017 | OPENALEX-W7214152392 | doi_match | 10.1007/s10270-026-01425-2 | 10.1007/s10270-026-01425-2 | — | — | DOI 逐字一致：10.1007/s10270-026-01425-2 |
| BREL-PA-0018 | OPENALEX-W7214194099 | unknown | — | — | 否 | 否 | OpenAlex 记录缺 DOI；pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0019 | OPENALEX-W7214198864 | unknown | — | — | 否 | 否 | OpenAlex 记录缺 DOI；pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0020 | OPENALEX-W7214222573 | unknown | — | — | 否 | 否 | OpenAlex 记录缺 DOI；pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0021 | OPENALEX-W7214241047 | unknown | 10.64643/ijirt.208799-459 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0036 | OPENALEX-W7214062101 | unknown | 10.1016/j.ecmx.2026.102287 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |
| BREL-PA-0037 | OPENALEX-W7214100311 | unknown | 10.56557/ajoair/2026/v9i1575 | — | 否 | 否 | pdf_url 里没有 DOI；URL 路径读不出标题（需抓取页面标题才能双匹配） |

## 边界

- 这一列只回答“这条 pdf_url 是否属于该 OpenAlex 记录”，**不回答**“这篇论文讲的
  主题是否已被核验”。DOI 一致只说明标识符对得上，不代表内容被人工读过。
- `unknown` 的 15 条里，3 条连 OpenAlex 记录本身都没有 DOI（BREL-PA-0018/0019/0020），
  其余是 URL 里没有 DOI、且 URL 路径读不出可比标题；要解决只能抓取落地页标题，
  本轮没有抓。
- 没有改动 `evaluation/` 下的 10-10 冻结产物，也没有往任何关联表里写“已验证”。

