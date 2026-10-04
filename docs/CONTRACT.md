# 参赛系统协作接口契约

工作目录 `D:/prj/.2/competition`。父智能体负责存储、数据源、API、运行和集成；intelligence负责人只写引擎与引擎测试；前端负责人只写static和USER_GUIDE；研究负责人只写research。所有成果必须区分实测与规划，不得伪造比赛成绩。

## Python领域数据

事件event是dict：
- id: string，本地稳定ID，推荐GHSA或CVE；aliases: string[]；title, summary: string；component: string；ecosystem: string。
- published_at, modified_at, collected_at: ISO UTC字符串或null；withdrawn: bool；status: confirmed|needs_review|withdrawn。
- affected: [{package: string, ecosystem: string, range: string, fixed_version: string|null, source_id: string}]。range采用常见 `>=0.1.0, <0.2.0` 或GHSA的 `< 0.2.0`，无法可靠解析则unknown，禁止硬猜。
- conditions: [{name: string,value: string|bool,description: string,source_id: string}]；配置未知时待确认。
- severity: string|null；cvss: [{version,score,vector,source_id}]；cwes:string[]。
- sources: [{id:string,url:string,title:string,publisher:string,source_type:string,excerpt:string,published_at:string|null,collected_at:string,content_hash:string,trust:string}]。excerpt仅来源事实，不含模型推测。sources是引用对象。
- references: string[]；poc:[{url,status,reason,source_id}]，只记录不执行。
- ai_relevance: {included:bool,reason:string}；tags:string[]；enrichment:dict可选。
- relationships: [{subject,predicate,object,conditions:dict,evidence_ids:string[]}]可选；攻击链仅从有来源关系展示。

资产asset：id,name,component,ecosystem,version:string|null,exposure:public|internal|unknown,business_criticality:critical|high|medium|low|unknown,conditions:dict,policy:dict|null,is_demo:bool,authorized:bool,updated_at。policy只保存调用方明确提供的维护窗口、禁止动作、负责人和可接受停机时间。
assets由用户主动导入；初始提供明确标注is_demo的合成资产，不声称是真实公网资产。

## intelligence.py接口

`assess_asset(event:dict, asset:dict)->dict` 返回event_id,asset_id,status:affected|not_affected|needs_confirmation|not_applicable, reasons:string[],evidence_ids:string[],priority:critical|high|medium|low|unknown。不能将条件未知、组件不明或事件撤回视为不受影响。
`enrich_event(event:dict)->dict` 返回完整事件副本并附enrichment={dimensions:[{name,status,evidence_ids,detail}],gaps:string[],trace:[...]}，不网络抓取、不编造缺失事实。
`answer_question(question,events,assets,history=None,model_config=None)->dict` 返回answer:string,citations:source[],claims:[{text,evidence_ids}],trace:[{step,role,action,evidence_ids,result,stop_reason?}],limitations:string[],mode:string,related_event_ids:string[],assessments:dict[]。事件数据与资产快照由父传入。model_config可含base_url/model/api_key_env/planner；不能硬编码或泄露密钥。网络可选模型调用有限时限。

## REST API前端契约

- GET /api/health -> {status,version,mode,model_configured}
- GET /api/dashboard -> {counts:{events,sources,assets,needs_review}, latest_collection, mode, monitoring:{...}, evaluation:{...}}
- GET /api/sources -> {items:[{id,name,category,url,enabled,status,last_run,last_success,last_error,events_count,mode}]}。
- POST /api/collect JSON {source_ids?:string[]} -> {run_id,status,results:[...],events_added,events_updated,duration_ms}，可能20秒；前端处理loading。
- GET /api/events?q=&status=&limit=100 -> {items:event[],total}。事件附enrichment。
- GET /api/events/{id} -> event（包含enrichment, assessments）。ID用encodeURIComponent。
- GET /api/assets -> {items:asset[]}
- POST /api/assets JSON单个资产(无需id) -> asset；POST /api/assets/import JSON {items:asset[]} -> {imported,items}。
- DELETE /api/assets/{id} -> {deleted:bool}
- GET /api/assessments -> {items:assessment[]}，assessment附asset_name,event_title,disposition,disposition_status。
- GET /api/dispositions -> {items:disposition[],total,status_labels}；处置状态 open|in_progress|fixed|verified|accepted。
- GET /api/dispositions/metrics -> {high_priority_total,high_priority_closed,high_priority_verified,high_priority_in_progress,closure_rate,verified_rate,mean_time_to_close_hours,status_breakdown,findings_total}。
- GET /api/dispositions/{event_id}/{asset_id} -> disposition（缺省返回 status=open，不写库）。
- PUT /api/dispositions/{event_id}/{asset_id} JSON {status,assignee?,note?,evidence_ids?,version_before?,version_after?,operator?,run_verification?} -> {disposition,assessment_status,assessment_priority,verification,requested_status,applied_status}；status=verified 时系统重新研判该资产，只有资产已不命中受影响区间才置为 verified，否则降级为 fixed 并记录失败复测。原始 assessment.status 不被覆盖。
- POST /api/chat JSON {question:string,history:[{role,content}]?} -> answer_question返回结果加duration_ms。
- GET /api/runs?limit=30 -> {items:[{id,kind,status,started_at,finished_at,summary,detail}]}
- GET /api/evaluation -> {status:not_run|completed,scope,metrics:dict,results:[],limitations:[],...}；只有真实执行后有分数。
- GET /api/evaluation/b -> B 任务冻结产物投影；人工问答、性能、关系 Precision 和多跳路径均为只读字段，Recall 不可计算时保持 null。
- POST /api/evaluation/run -> 同上，执行本地回归/金标准样例评估，明确小样本不代表正式盲测；无代码执行接口。
- GET /api/export -> JSON snapshot，用下载链接即可。

API错误统一HTTP非2xx以及{detail:string}（框架参数校验可能detail数组）。查询输入限制、输出不含密钥。服务默认127.0.0.1，仅本地使用；部署公开环境须另加身份鉴权。

## 质量要求

不使用不存在的源、伪造延迟或样本；测试夹具必须标synthetic。模型未配置时UI明确“本地证据抽取模式”，不可称大模型推理已验证。所有项目数据保存在data，原始快照有来源和哈希。数据源任意URL不能由前端发起，避免SSRF；初始仅后端登记官方端点。静态UI防XSS、服务限制跨域和Origin写请求。
