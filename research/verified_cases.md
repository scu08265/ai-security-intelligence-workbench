# 已核验的 AI 推理组件漏洞案例

访问日期：2026-09-19  
核验原则：仅采用项目官方仓库安全公告、官方修复记录、官方发布页，以及 NVD/GitHub Advisory Database 等权威漏洞记录；未运行或下载 POC。本文区分“来源明确记载的事实”和“未知/未核验事项”。

## 1. Ollama：CVE-2026-7482 / GHSA-x8qc-fggm-mpqg

- 组件：Ollama（Go 包 `github.com/ollama/ollama`）
- 类型：GGUF 模型加载/量化路径中的堆越界读取（CWE-125）
- 严重性：High；GitHub Advisory Database 给出的 CVSS v4.0 为 8.8
- 受影响版本：`< 0.17.1`
- 修复版本：`0.17.1`
- 公开时间：2026-05-04；GitHub 复核时间：2026-05-08
- 触发前提：攻击者可向 `/api/create` 提交声明的张量偏移或大小超过实际文件长度的 GGUF 文件，使量化路径越界读取。公告还描述了经 `/api/push` 上传结果模型的泄露链。上游发行版的这两个端点无认证；默认绑定为 `127.0.0.1`，因此远程可达性取决于部署者是否扩大监听范围或通过代理暴露接口。
- 影响：公告称可能泄露进程内存内容，并影响可用性；未在本次核验中复现。
- 修复证据：GitHub 已审核公告将 `0.17.1` 标为修复版本，并链接 Ollama 官方 `v0.17.1` 发布页及官方仓库修复提交 `88d57d0`。官方发布页确认该版本存在，但发布说明正文未点名该 CVE。
- 证据：
  - GitHub Advisory Database（已审核）：https://github.com/advisories/GHSA-x8qc-fggm-mpqg
  - Ollama 官方发布页：https://github.com/ollama/ollama/releases/tag/v0.17.1
  - Ollama 官方仓库修复提交（公告所列短哈希）：https://github.com/ollama/ollama/commit/88d57d0
  - NVD：https://nvd.nist.gov/vuln/detail/CVE-2026-7482
- 未知/未核验：最初私下报告时间；官方是否确认已在野利用；不同操作系统、量化格式和部署代理下的可利用性；修复提交的完整 SHA（当前证据页仅列短哈希）；未运行 POC。

## 2. vLLM：CVE-2026-22778 / GHSA-4r2x-xpjr-7cvv

- 组件：vLLM（PyPI 包 `vllm`）
- 类型：视频处理链中的信息泄露与堆溢出组合，可导致远程代码执行（CWE-122、CWE-532）
- 严重性：Critical；官方项目安全公告给出的 CVSS v3.1 为 9.8
- 受影响版本：`>= 0.8.3, < 0.14.1`
- 修复版本：`0.14.1`
- 公开时间：2026-02-02
- 触发前提：部署正在提供视频模型服务；攻击者能够向 `/v1/chat/completions` 或 `/v1/invocations` 提交含远程 `video_url` 的请求；服务获取并通过 OpenCV/FFmpeg 解码恶意视频。官方公告指出默认无认证实例可受影响，并称即使启用 API key，`invocations` 路径仍可能在认证前处理载荷。
- 影响：官方公告描述地址泄露用于绕过 ASLR，并通过 JPEG2000 解码链中的堆溢出实现服务端任意命令执行。
- 修复证据：vLLM 官方安全公告将 `0.14.1` 标为修复版本，并列出修复 PR `#31987`、`#32319`、`#32668`；官方 `v0.14.1` 发布页说明该补丁版处理安全和内存泄露修复。
- 证据：
  - vLLM 官方安全公告：https://github.com/vllm-project/vllm/security/advisories/GHSA-4r2x-xpjr-7cvv
  - vLLM 官方发布页：https://github.com/vllm-project/vllm/releases/tag/v0.14.1
  - 官方修复 PR：https://github.com/vllm-project/vllm/pull/31987
  - 官方修复 PR：https://github.com/vllm-project/vllm/pull/32319
  - 官方修复 PR：https://github.com/vllm-project/vllm/pull/32668
  - NVD：https://nvd.nist.gov/vuln/detail/CVE-2026-22778
- 未知/未核验：最初私下报告日期；各 OpenCV/FFmpeg 构建组合是否均可利用；是否已在野利用；除公告列举端点外是否存在其他入口；未运行 POC。

## 3. vLLM：CVE-2026-54235 / GHSA-7h4p-rffg-7823

- 组件：vLLM（PyPI 包 `vllm`）
- 类型：非有限浮点参数验证不当导致 GPU 推理工作进程崩溃（CWE-1287）
- 严重性：Moderate；官方公告未给出可核验的 CVSS 数值
- 受影响版本：`<= 0.8.5`
- 修复版本：`>= 0.24.0`
- 公开时间：2026-06-11
- 触发前提：请求参数中的 `temperature` 为 `NaN` 或正无穷；Python 比较运算未拒绝这些值，它们进入 GPU 采样内核。负无穷会被既有检查拦截。
- 影响：GPU 内核出现未定义行为或 CUDA 错误，可能使推理工作进程崩溃，并影响并发用户的服务可用性。
- 修复证据：vLLM 官方安全公告要求在 `_verify_args()` 中使用 `math.isfinite()` 拒绝非有限值，并链接官方 PR `#45116`。该 PR 于 2026-06-11 合并，加入 `temperature` 与 `repetition_penalty` 的有限值校验及 12 个参数化测试。公告将 `>=0.24.0` 标为修复版本。
- 证据：
  - vLLM 官方安全公告：https://github.com/vllm-project/vllm/security/advisories/GHSA-7h4p-rffg-7823
  - vLLM 官方修复 PR：https://github.com/vllm-project/vllm/pull/45116
  - NVD：https://nvd.nist.gov/vuln/detail/CVE-2026-54235
- 未知/未核验：官方 CVSS 分数与向量；最初私下报告时间；哪些 GPU/驱动/内核组合必然崩溃；是否已在野利用；公告为何将较早的受影响上界与较晚的首个修复版本相隔较大版本区间，不能据此推断中间版本安全；未运行 POC。

## 数据使用注意事项

1. 资产匹配应严格使用各案例的版本范围及触发前提，不能仅凭组件名称判定受影响。
2. Ollama 案例的版本区间和漏洞描述来自 GitHub 已审核数据库；官方仓库提供发布和修复记录，但发布说明未点名 CVE。因此在证据等级中应标为“权威漏洞库 + 官方修复记录交叉核验”，不要写成维护者正式安全公告。
3. vLLM 两例来自项目官方安全公告，可作为一手漏洞来源；仍应保留公告中未给出的字段为未知。
4. 未收集、下载或执行任何 POC。本数据只用于知识库富化、版本匹配和问答评测。
