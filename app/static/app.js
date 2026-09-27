'use strict';

/* =========================================================================
 * AI 安全知识情报系统 · 单页控制台
 *
 * 三条硬约束贯穿本文件：
 *   1. 任何来自 API 的数据一律通过 createElement + textContent 渲染，
 *      innerHTML 只用于本文件内写死的字面量（图标 SVG）。
 *   2. 界面不接收任何 URL 输入：数据源只能从 /api/sources 的固定列表勾选，
 *      渲染外部链接前必须校验 scheme 为 http/https，否则按纯文本展示。
 *   3. 只展示后端返回的真实数值；列表为空时给出明确的空状态，不编造占位数据。
 * ========================================================================= */

(function () {
  /* ------------------------------------------------------------------ 文案 */

  const L = {
    eventStatus: { confirmed: '已确认', needs_review: '待复核', withdrawn: '已撤回' },
    eventStatusClass: { confirmed: 'confirmed', needs_review: 'needs-confirmation', withdrawn: 'withdrawn' },
    // User-facing type, derived by the backend from the collector that produced
    // each event.  The values are already Chinese, so only the badge colour
    // needs stating here.  This replaced a two-value kind map (漏洞/知识) in
    // which the word 论文 never appeared, so the arXiv items were unfindable.
    category: { '漏洞': '漏洞', '论文': '论文', '标准与框架': '标准与框架', '政策法规': '政策法规' },
    categoryClass: { '漏洞': 'accent', '论文': 'model', '标准与框架': 'model', '政策法规': 'model' },
    assessStatus: { affected: '受影响', not_affected: '当前规则下不受影响', needs_confirmation: '待补信息', not_applicable: '未评估' },
    assessStatusClass: { affected: 'affected', not_affected: 'not-affected', needs_confirmation: 'needs-confirmation', not_applicable: 'not-applicable' },
    priority: { critical: '紧急', high: '高', medium: '中', low: '低', unknown: '未知' },
    runStatus: { ok: '成功', partial: '部分成功', failed: '失败', skipped: '已跳过', idle: '未运行', completed: '已完成', running: '执行中', aborted: '已中断', stale: '历史数据可用' },
    severity: { critical: '严重', high: '高', medium: '中', low: '低', none: '无评级', unknown: '未知' },
    exposure: { public: '公网', internal: '内网', unknown: '未知' },
    criticality: { high: '高', medium: '中', low: '低' },
    trust: {
      authoritative: '权威来源', vendor_blog: '厂商博客', preprint: '预印本',
      scholarly_index: '学术索引', community_standard: '社区标准',
      government: '政府来源', fixture: '测试夹具'
    },
    dimension: {
      affected_versions: '受影响版本范围', remediation: '修复版本 / 缓解',
      severity: '严重性 / CVSS', poc: 'POC 资料与验证状态',
      relationships: '关系 / 攻击链证据', official_sources: '原始来源'
    },
    // Plain-language role names.  These deliberately match the backend's
    // ROLE_LABELS so a card rendered from a stream frame and one rendered
    // from a stored run record read the same.
    role: {
      planner: '规划员', retriever: '查证员', auditor: '审核员', evidence_auditor: '证据审核员',
      scheduler: '调度员', collector: '采集员', normalizer: '标准化员', deduplicator: '查重员',
      assessor: '影响分析员', bounded_model_planner: '受限模型规划'
    },
    stageStatus: {
      running: '进行中', done: '已完成', warn: '需注意', failed: '失败', skipped: '已跳过'
    },
    stageStatusClass: {
      running: 'running', done: 'ok', warn: 'needs-confirmation',
      failed: 'failed', skipped: 'skipped'
    },
    // The four questions every step answers, in the order they are shown.
    stageFields: [
      { key: 'action', label: '做了什么', cls: '' },
      { key: 'obtained', label: '得到什么', cls: 'stage-row--obtained' },
      { key: 'output', label: '产出什么', cls: 'stage-row--output' },
      { key: 'effect', label: '有什么影响', cls: 'stage-row--effect' }
    ],
    streamSource: { local: '本地证据结论', model: '大模型转述' },
    runKind: { collect: '采集', enrich: '富化', assess: '研判', chat: '问答', evaluation: '评测' },
    answerMode: {
      local_evidence_extraction: '本地证据抽取',
      model_assisted_evidence_selection: '模型辅助事件选择（结论仍由证据拼装）'
    },
    sourceMode: { api: 'API', feed: 'Feed', rss: 'RSS', page: '页面', pdf: 'PDF 文档' }
  };

  const DASH = '—';

  function labelOf(map, value) {
    if (value === null || value === undefined || value === '') return null;
    const key = String(value);
    return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : key;
  }

  function conditionLabel(value) {
    const raw = textOr(value, '未知条件');
    const known = { remote_api: '远程接口开放', public_access: '公网可访问', authentication: '身份认证',
      video_endpoint: '视频处理入口', untrusted_model: '不可信模型输入' };
    if (Object.prototype.hasOwnProperty.call(known, raw)) return known[raw];
    const match = /^prerequisite_(\d+)$/.exec(raw);
    return match ? `触发条件 ${match[1]}` : raw;
  }

  function humanizeReason(value) {
    return textOr(value).replace(/prerequisite_(\d+)/g, '触发条件 $1')
      .replace(/not_affected/g, '不受影响').replace(/needs_confirmation/g, '待确认')
      .replace(/not_applicable/g, '不适用').replace(/affected/g, '受影响');
  }

  /* ------------------------------------------------------------- DOM 工具 */

  function appendChildren(node, children) {
    for (const child of children) {
      if (child === null || child === undefined || child === false) continue;
      if (Array.isArray(child)) { appendChildren(node, child); continue; }
      node.appendChild(
        typeof child === 'string' || typeof child === 'number'
          ? document.createTextNode(String(child))
          : child
      );
    }
  }

  /**
   * 创建元素。所有来自接口的数据都必须经 `text`（textContent）写入，
   * 这里不提供 raw HTML 入口：一旦存在这样的入口，后续很容易被误用于
   * 上游不可信文本（公告标题、摘要、引用摘录等），从而引入 XSS。
   * 图标等固定内容由 icon() 单独处理，仅使用本文件内的字面量。
   */
  function h(tag, props, ...children) {
    const node = document.createElement(tag);
    if (props) {
      for (const key of Object.keys(props)) {
        const value = props[key];
        if (value === null || value === undefined || value === false) continue;
        if (key === 'class') node.className = value;
        else if (key === 'text') node.textContent = String(value);
        else if (key === 'dataset') { for (const dk of Object.keys(value)) node.dataset[dk] = String(value[dk]); }
        else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
        else if (value === true) node.setAttribute(key, '');
        else node.setAttribute(key, String(value));
      }
    }
    appendChildren(node, children);
    return node;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function bodyOf(id) { return document.getElementById('body-' + id); }
  function setBox(node, ...children) { clear(node); appendChildren(node, children); }

  const ICON_SVG = {
    refresh: '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M13.1 6.6A5.6 5.6 0 1 0 13.7 9.3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M13.6 3.2v3.5h-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    play: '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4.8 3.2 12.4 8l-7.6 4.8V3.2Z" fill="currentColor"/></svg>',
    trash: '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.6 4.6h8.8M6.6 4.6V3.1h2.8v1.5M4.9 4.6l.5 8h5.2l.5-8M6.8 6.7v3.9M9.2 6.7v3.9" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    plus: '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 3.4v9.2M3.4 8h9.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    send: '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M2.6 8 13.4 2.9 10.7 13.3 8.3 9.6 2.6 8Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
    warn: '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 2.5 14.3 13.1H1.7L8 2.5Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M8 6.4v3.1M8 11.5v.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>'
  };

  function icon(name) {
    const span = h('span', { class: 'icon', 'aria-hidden': 'true' });
    span.innerHTML = ICON_SVG[name] || '';
    return span;
  }

  /* ------------------------------------------------------------ 格式化工具 */

  function textOr(value, fallback) {
    if (value === null || value === undefined || value === '') return fallback === undefined ? DASH : fallback;
    return String(value);
  }

  function fmtTime(value) {
    if (!value) return null;
    const raw = String(value);
    const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/.exec(raw);
    return m ? `${m[1]} ${m[2]} UTC` : raw;
  }

  function fmtDuration(ms) {
    if (typeof ms !== 'number' || !isFinite(ms)) return null;
    return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
  }

  function shortHash(value) {
    if (!value) return null;
    const raw = String(value);
    return raw.length > 16 ? raw.slice(0, 16) + '…' : raw;
  }

  /* P1 RAG 前端兼容契约。文档接口可补充 content_scope、sections、
   * chunks；问答接口可补充 context_chunks。字段缺失时必须显示“未入库”，
   * 不能把来源摘录伪装成全文或可定位的检索块。 */
  function arrayOr(value) { return Array.isArray(value) ? value : []; }

  function ragDocument(raw) {
    const doc = raw || {};
    const ingestion = doc.ingestion && typeof doc.ingestion === 'object' ? doc.ingestion : {};
    const sections = arrayOr(doc.sections).length ? arrayOr(doc.sections) : arrayOr(ingestion.sections);
    let chunks = arrayOr(doc.chunks).length ? arrayOr(doc.chunks) : arrayOr(ingestion.chunks);
    if (!chunks.length && sections.length) {
      chunks = sections.flatMap((section) => arrayOr(section.chunks).map((chunk) => Object.assign({
        section: chunk.section || section.title || section.name || null
      }, chunk)));
    }
    const rawScope = String(doc.content_scope || doc.content_level || ingestion.content_scope || '').toLowerCase();
    const fullText = doc.has_full_text === true || doc.full_text === true || Number(doc.chunk_count) > 0 ||
      ['fulltext', 'full_text', 'full', '正文'].includes(rawScope);
    const hasExcerpt = Boolean(doc.abstract || doc.excerpt || doc.summary);
    const scope = fullText ? 'fulltext' : (hasExcerpt ? 'excerpt' : 'metadata');
    const statedChunkCount = Number(doc.chunk_count ?? ingestion.chunk_count);
    const statedSectionCount = Number(doc.section_count ?? ingestion.section_count);
    return Object.assign({}, doc, {
      rag_scope: scope,
      rag_scope_label: scope === 'fulltext' ? '全文' : (scope === 'excerpt' ? '摘要/摘录' : '仅元数据'),
      rag_chunks: chunks,
      rag_chunk_count: Number.isFinite(statedChunkCount) ? statedChunkCount : chunks.length,
      rag_sections: sections,
      rag_section_count: Number.isFinite(statedSectionCount) ? statedSectionCount : sections.length
    });
  }

  function ragChunk(raw, fallback) {
    const chunk = raw || {};
    const source = fallback || {};
    const sectionPath = arrayOr(chunk.section_path || (chunk.metadata && chunk.metadata.section_path));
    return {
      id: chunk.chunk_id || chunk.id || chunk.ref_id || null,
      document_id: chunk.document_id || chunk.doc_id || source.document_id || source.id || null,
      document_title: chunk.document_title || chunk.title || source.title || null,
      section: chunk.section || chunk.section_title || chunk.heading || (sectionPath.length ? sectionPath.join(' / ') : null),
      page: chunk.page || chunk.page_number || null,
      text: chunk.text || chunk.content || chunk.excerpt || chunk.quote || null,
      char_start: chunk.char_start ?? null,
      char_end: chunk.char_end ?? null,
      score: chunk.rerank_score ?? chunk.score ?? null,
      retrieval: chunk.retrieval || chunk.method || null
    };
  }

  function answerContextChunks(data) {
    const direct = arrayOr(data && data.context_chunks);
    const rag = data && data.rag && typeof data.rag === 'object'
      ? (arrayOr(data.rag.context_chunks).length ? arrayOr(data.rag.context_chunks)
        : arrayOr(data.rag.context && data.rag.context.citations)) : [];
    const retrieval = data && data.retrieval && typeof data.retrieval === 'object'
      ? (arrayOr(data.retrieval.context_chunks).length ? arrayOr(data.retrieval.context_chunks) : arrayOr(data.retrieval.chunks)) : [];
    return (direct.length ? direct : (rag.length ? rag : retrieval)).map((item) => ragChunk(item));
  }

  function mono(value, cls) {
    return h('span', { class: 'mono' + (cls ? ' ' + cls : '') }, value);
  }

  /** 时间行：无值时不显示占位数字，显示明确的“未记录”。 */
  function timeCell(value) {
    const text = fmtTime(value);
    return text ? mono(text) : mono(DASH, 'dim');
  }

  /**
   * 外部链接安全渲染：只有 http/https 才渲染为可点击链接，
   * 其余（含空值、非 http scheme）一律按纯文本展示。
   */
  function safeLink(url, fallbackText) {
    const raw = (url === null || url === undefined) ? '' : String(url).trim();
    if (/^https?:\/\//i.test(raw)) {
      return h('a', { href: raw, target: '_blank', rel: 'noopener noreferrer nofollow', class: 'break' }, fallbackText || raw);
    }
    return h('span', { class: 'mono dim break', title: '非 http(s) 链接，仅按纯文本展示' }, fallbackText || raw || DASH);
  }

  /* ----------------------------------------------------------------- API */

  function ApiError(message) { this.name = 'ApiError'; this.message = message; }
  ApiError.prototype = Object.create(Error.prototype);

  function describeDetail(payload, fallback) {
    const detail = payload && payload.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail)) {
      const parts = detail.map((item) => {
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
          return (loc ? loc + '：' : '') + (item.msg || item.message || JSON.stringify(item));
        }
        return String(item);
      });
      if (parts.length) return parts.join('；');
    }
    return fallback;
  }

  async function request(method, path, body) {
    const init = { method: method, headers: { Accept: 'application/json' } };
    if (body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await fetch(path, init);
    } catch (err) {
      throw new ApiError('无法连接后端服务：' + ((err && err.message) ? err.message : '网络错误'));
    }
    const text = await response.text();
    let payload = null;
    if (text) {
      try { payload = JSON.parse(text); } catch (err) { payload = null; }
    }
    if (!response.ok) {
      throw new ApiError(describeDetail(payload, `请求失败（HTTP ${response.status}）`));
    }
    if (payload === null) throw new ApiError('后端返回了无法解析的响应内容');
    return payload;
  }

  const api = {
    get: (path) => request('GET', path),
    post: (path, body) => request('POST', path, body),
    del: (path) => request('DELETE', path)
  };

  /* ------------------------------------------------------------ 流式请求 */

  /* Reads a Server-Sent Events response and hands each frame to `onFrame`.
   *
   * The backend emits a frame at the moment a real unit of work finishes, so
   * frames arrive at the speed the system actually works.  Nothing here adds
   * a delay or replays anything -- if a step took 40 ms, its card appears
   * after 40 ms and says 40 ms. */
  async function streamPost(path, body, onFrame, signal) {
    let response;
    try {
      response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(body),
        signal: signal
      });
    } catch (err) {
      if (err && err.name === 'AbortError') throw err;
      throw new ApiError('无法连接后端服务：' + ((err && err.message) ? err.message : '网络错误'));
    }

    if (!response.ok) {
      const text = await response.text();
      let payload = null;
      try { payload = JSON.parse(text); } catch (err) { payload = null; }
      throw new ApiError(describeDetail(payload, `请求失败（HTTP ${response.status}）`));
    }
    if (!response.body) throw new ApiError('当前浏览器不支持流式读取，无法显示实时过程');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });

      let split;
      while ((split = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        let name = 'message';
        const dataLines = [];
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) name = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
        }
        if (!dataLines.length) continue;
        let payload = null;
        try { payload = JSON.parse(dataLines.join('\n')); } catch (err) { payload = null; }
        if (payload === null) continue;
        onFrame(name, payload);
      }
    }
  }

  /* ------------------------------------------------------------------ 状态 */

  const state = {
    health: null,
    dashboard: null,
    dashboardRisks: [],
    dashboardAssessments: [],
    inited: new Set(),
    dom: {},
    sources: [],
    selection: new Set(),
    collect: { running: false, result: null, error: null, stopTimer: null },
    events: {
      items: [], total: 0, loading: false, error: null,
      filters: { q: '', status: '', category: '', limit: 100 },
      selectedId: null, detail: null, detailLoading: false, detailError: null
    },
    knowledge: { documents: [], sources: [], total: 0, loading: false, error: null },
    enrich: { running: false, result: null, error: null },
    assets: { items: [], loading: false, error: null, running: false },
    assessments: { items: [], loading: false, error: null, running: false, filter: '' },
    chat: {
      turns: [], history: [], pending: false, initialized: false,
      useModel: false, controller: null, confirmation: null,
      context: {
        threadId: `CTX-${Date.now().toString(36).toUpperCase()}`,
        segment: 1, events: [], assets: [], documents: [], chunks: [],
        snapshot: null,
        inheritedConstraints: [
          '只使用本地已保存的证据；查不到时拒绝猜测',
          '前端最多传递最近 20 条消息，实际采用内容以后端返回为准',
          '大模型只可转述已有结论，不能新增事实'
        ]
      }
    },
    live: {
      running: false, frames: [], final: null, error: null,
      startedAt: null, stopTimer: null, controller: null, pending: {},
      closeGaps: true, enrichLimit: 6, autoScroll: true
    },
    onboarding: {
      quickDemoRunning: false, error: null,
      pendingAutoDemo: false, autoDemoStarted: false
    },
    runs: { items: [], loading: false, error: null },
    evaluation: { data: null, loading: false, error: null, running: false },
    scorecard: { data: null, loading: false, error: null },
    workbench: { data: null, loading: false, error: null },
    simulation: {
      bom: null, preview: null, assets: [], source: null, confirmed: false, running: false,
      plan: null, imported: [], assessments: [], selected: null, result: null, error: null
    }
  };

  /* ----------------------------------------------------------- 通用渲染件 */

  function badge(kind, text, titleAttr) {
    return h('span', { class: 'badge badge--' + kind, title: titleAttr || null }, text);
  }

  function statusBadge(map, classMap, value) {
    const key = String(value === null || value === undefined || value === '' ? 'unknown' : value);
    const cls = classMap && Object.prototype.hasOwnProperty.call(classMap, key) ? classMap[key] : key;
    return badge(cls, labelOf(map, key) || key, key);
  }

  function eventStatusBadge(value) { return statusBadge(L.eventStatus, L.eventStatusClass, value); }
  function assessStatusBadge(value) { return statusBadge(L.assessStatus, L.assessStatusClass, value); }
  function runStatusBadge(value) { return statusBadge(L.runStatus, null, value); }
  function priorityBadge(value) { return statusBadge(L.priority, null, value); }

  function emptyState(main, hint) {
    return h('div', { class: 'empty' },
      h('p', { class: 'empty-main' }, main),
      hint ? h('p', { class: 'empty-hint' }, hint) : null);
  }

  function errorBlock(message, retry) {
    return h('div', { class: 'alert alert--error', role: 'alert' },
      h('p', { class: 'alert-title' }, '加载失败'),
      h('p', { class: 'mono break' }, message),
      retry ? h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: retry }, '重试') : null);
  }

  function alertBox(kind, title, ...content) {
    return h('div', { class: 'alert alert--' + kind, role: kind === 'error' ? 'alert' : null },
      title ? h('p', { class: 'alert-title' }, title) : null,
      content);
  }

  function loadingBlock(text) {
    return h('div', { class: 'loading-inline' }, h('span', { class: 'spinner' }), h('span', {}, text));
  }

  function sectionBlock(title, ...children) {
    return h('section', { class: 'section' },
      h('h4', { class: 'block-title' }, title),
      children);
  }

  function dataTable(headers, rows) {
    const head = h('thead', {}, h('tr', {}, headers.map((col) => h('th', { scope: 'col', class: col.cls || null }, col.text))));
    const body = h('tbody', {}, rows.map((cells) => h('tr', {}, cells.map((cell, i) => {
      const col = headers[i];
      return h('td', { class: col && col.cls ? col.cls : null }, cell);
    }))));
    return h('div', { class: 'table-wrap' }, h('table', {}, head, body));
  }

  function kvList(pairs) {
    const dl = h('dl', { class: 'kv' });
    for (const pair of pairs) {
      if (!pair) continue;
      dl.appendChild(h('dt', {}, pair[0]));
      dl.appendChild(h('dd', {}, pair[1]));
    }
    return dl;
  }

  function tile(label, value, opts) {
    const options = opts || {};
    return h('div', { class: 'tile' },
      h('span', { class: 'tile-label' }, label),
      h('div', { class: 'tile-value' + (options.tone ? ' is-' + options.tone : '') }, String(value)),
      options.sub ? h('span', { class: 'tile-sub' }, options.sub) : null);
  }

  function card(title, ...children) {
    return h('div', { class: 'card' },
      title ? h('div', { class: 'card-head' }, h('span', { class: 'card-title' }, title)) : null,
      children);
  }

  function toast(message, kind) {
    const box = document.getElementById('toasts');
    if (!box) return;
    const node = h('div', { class: 'toast' + (kind ? ' toast--' + kind : '') }, message);
    box.appendChild(node);
    window.setTimeout(() => { if (node.parentNode) node.parentNode.removeChild(node); }, 7000);
  }

  function beginElapsed(span) {
    const started = Date.now();
    const tick = () => {
      const seconds = Math.floor((Date.now() - started) / 1000);
      span.textContent = `已用时 ${seconds} 秒`;
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }

  /* ------------------------------------------------------------- 标签页 */

  const PANELS = {
    overview: { init: initWorkbench, load: loadDashboard },
    knowledge: { init: initKnowledgeSurface, load: loadKnowledge },
    scorecard: { init: initScorecard, load: loadScorecard }
  };

  function activate(tabId) {
    const tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
    for (const tab of tabs) {
      const on = tab.dataset.tab === tabId;
      tab.setAttribute('aria-selected', on ? 'true' : 'false');
      tab.tabIndex = on ? 0 : -1;
    }
    for (const panel of document.querySelectorAll('.panel')) {
      panel.hidden = panel.id !== 'panel-' + tabId;
    }
    const meta = PANELS[tabId];
    if (!meta) return;
    if (!state.inited.has(tabId)) {
      state.inited.add(tabId);
      meta.init();
    }
    if (meta.load) meta.load();
  }

  function wireTabs() {
    const tablist = document.querySelector('.tablist');
    const tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
    for (const tab of tabs) {
      tab.addEventListener('click', () => activate(tab.dataset.tab));
    }
    const modeLink = document.getElementById('mode-link');
    if (modeLink) modeLink.addEventListener('click', () => activate('scorecard'));
    tablist.addEventListener('keydown', (event) => {
      const keys = ['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
      if (keys.indexOf(event.key) < 0) return;
      const index = tabs.indexOf(document.activeElement);
      if (index < 0) return;
      event.preventDefault();
      let next = index;
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      tabs[next].focus();
      activate(tabs[next].dataset.tab);
    });
  }

  /* --------------------------------------------------------- 健康与模式 */

  async function loadHealth() {
    try {
      state.health = await api.get('/api/health');
    } catch (err) {
      state.health = { error: err.message };
    }
    renderModeBanner();
    const version = document.getElementById('rail-version');
    const dataDir = document.getElementById('rail-datadir');
    if (state.health && !state.health.error) {
      version.textContent = '版本 ' + textOr(state.health.version);
      dataDir.textContent = '数据目录 ' + textOr(state.health.data_dir);
      dataDir.title = '数据目录：' + textOr(state.health.data_dir);
    } else {
      version.textContent = '版本 —';
      dataDir.textContent = '数据目录 —';
    }
  }

  function renderModeBanner() {
    const banner = document.getElementById('mode-banner');
    const text = document.getElementById('mode-text');
    const sub = document.getElementById('mode-sub');
    banner.classList.remove('is-model', 'is-error');
    const health = state.health;
    if (!health) return;
    if (health.error) {
      banner.classList.add('is-error');
      text.textContent = '无法连接后端服务：' + health.error;
      if (sub) sub.textContent = '';
      return;
    }
    if (health.model_configured) {
      banner.classList.add('is-model');
      text.textContent = '证据辅助模式：结论仍由本地证据拼装';
    } else {
      text.textContent = '本地证据抽取模式：未配置大模型，所有结论完全由本地已存资料拼装';
    }
    /* The one-line answer to "AI 在做什么", kept on screen at all times so the
     * question is answerable without opening anything. */
    if (sub) {
      sub.textContent = health.model_configured
        ? '模型仅参与事件选择与表达；监测、富化、研判、检索和拒答由可审计规则执行'
        : '监测、富化、研判、检索和拒答均由本地可审计规则执行';
    }
    syncChatControls();
  }

  async function refreshDashboardQuiet() {
    try {
      if (state.dom.overview) await loadDashboard();
      else state.dashboard = await api.get('/api/dashboard');
    } catch (err) {
      /* 静默：后台刷新失败不打断当前面板操作 */
    }
  }

  /* ------------------------------------------------------------- 总览 */

  function initWorkbench() {
    initOnboarding();
    initSimulation();
    initOverview();
    initOrchestrationMap();
    initLive();
    wireInlineModules();
  }

  /* --------------------------------------------------------- 上手向导 */

  function countValue(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function onboardingStep(number, title, detail, stateName) {
    const stateLabel = stateName === 'done' ? '已完成' : stateName === 'current' ? '现在做' : '待开始';
    const stateKind = stateName === 'done' ? 'ok' : stateName === 'current' ? 'accent' : 'plain';
    return h('article', { class: 'onboarding-step is-' + stateName },
      h('div', { class: 'onboarding-step-top' },
        h('span', { class: 'onboarding-index' }, number),
        badge(stateKind, stateLabel)),
      h('h4', {}, title),
      h('p', {}, detail));
  }

  function resultLegend() {
    return h('details', { class: 'onboarding-help', open: true },
      h('summary', {}, '四个结论怎么读？'),
      h('div', { class: 'onboarding-legend' },
        h('div', {}, assessStatusBadge('affected'), h('span', {}, '当前资产命中已知漏洞条件，优先处理。')),
        h('div', {}, assessStatusBadge('needs_confirmation'), h('span', {}, '版本或配置不够，系统不会猜成安全。')),
        h('div', {}, assessStatusBadge('not_affected'), h('span', {}, '按当前证据不命中，但仍要持续监测。')),
        h('div', {}, assessStatusBadge('not_applicable'), h('span', {}, '资产未授权或组件不匹配，本次不判断。'))));
  }

  function initOnboarding() {
    const body = bodyOf('onboarding');
    if (!body) return;
    state.dom.onboarding = body;
    renderOnboarding();
  }

  function renderOnboarding() {
    const body = state.dom.onboarding;
    if (!body) return;
    const dash = state.dashboard;
    if (!dash) {
      setBox(body, h('section', { class: 'onboarding' },
        h('div', { class: 'onboarding-copy' },
          h('span', { class: 'step-kicker' }, '第一次使用 · 先看这里'),
          h('h3', { id: 'onboarding-title' }, '正在判断你现在应该做什么…'),
          h('p', {}, '系统正在读取情报、资产和研判状态。'))));
      return;
    }

    const counts = dash.counts || {};
    const events = countValue(counts.events);
    const assets = countValue(counts.assets);
    const assessments = countValue(counts.assessments);
    if (state.onboarding.pendingAutoDemo && !state.onboarding.autoDemoStarted) {
      state.onboarding.autoDemoStarted = true;
      state.onboarding.pendingAutoDemo = false;
      window.setTimeout(() => runGuidedDemo(null), 0);
    }
    const monitoring = dash.monitoring || {};
    const coverage = monitoring.coverage || {};
    const producingSources = countValue(coverage.endpoints_with_data);
    const registeredSources = countValue(coverage.endpoints);

    let nextKey = 'assets';
    let nextLabel = '先添加我的资产';
    let headline = '告诉系统“我运行了什么”，它才能判断哪些风险与你有关。';
    let explanation = `公开情报已经有了 ${events} 条。当前资产为 0，所以“受影响资产 0”只表示无法判断，不代表你的系统安全。`;

    if (events === 0 && assets === 0) {
      nextKey = 'sources';
      nextLabel = '先获取公开情报';
      headline = '先让系统知道外面发生了什么，再告诉它你运行了什么。';
      explanation = '当前情报库和资产清单都是空的。可以点击下方“一键体验完整流程”，或按步骤分别操作。';
    } else if (events === 0) {
      nextKey = 'sources';
      nextLabel = '先采集公开情报';
      headline = '现在还没有可研判的公开情报。';
      explanation = `你已经录入 ${assets} 条资产，但情报库为空，系统暂时没有风险事件可以和资产匹配。`;
    } else if (assets === 0) {
      nextKey = 'assets';
      nextLabel = '先添加我的资产';
      headline = '系统已经找到外部情报，但还不知道“哪些东西属于你”。';
      explanation = `公开情报已有 ${events} 条，来自 ${producingSources} / ${registeredSources} 个有效来源。` +
        '请先录入资产；否则系统只能展示新闻，不能告诉你自己的组件是否受影响。';
    } else if (assessments === 0) {
      nextKey = 'assessments';
      nextLabel = '生成影响结论';
      headline = '情报和资产都准备好了，下一步是逐项判断影响。';
      explanation = `系统会用 ${events} 条情报与 ${assets} 条资产做组件、版本和配置匹配，生成“受影响 / 待补信息 / 不受影响 / 不适用”四类结论。`;
    } else {
      nextKey = 'assessments';
      nextLabel = '查看我的处置清单';
      headline = '影响判断已经生成，现在可以查看风险、依据和处置建议。';
      explanation = `当前已有 ${assessments} 条研判结论。先处理“受影响”和“待补信息”，再回到问答区追问原因。`;
    }

    const stepAssets = assets > 0 ? 'done' : (nextKey === 'assets' ? 'current' : 'waiting');
    const stepEvents = events > 0 ? 'done' : (nextKey === 'sources' ? 'current' : 'waiting');
    const stepAssess = assessments > 0 ? 'done' : (nextKey === 'assessments' ? 'current' : 'waiting');

    const primary = h('button', {
      type: 'button', class: 'btn btn--primary',
      onclick: () => openInlineModule(nextKey)
    }, nextLabel);
    const demo = h('button', {
      type: 'button', class: 'btn btn--ghost',
      disabled: state.onboarding.quickDemoRunning,
      onclick: () => runGuidedDemo(demo)
    }, state.onboarding.quickDemoRunning ? '正在准备演示…' : '一键体验完整流程');
    const knowledge = h('button', {
      type: 'button', class: 'btn btn--ghost',
      onclick: () => activate('knowledge')
    }, '查看已获取的情报');

    setBox(body, h('section', { class: 'onboarding' },
      h('div', { class: 'onboarding-copy' },
        h('span', { class: 'step-kicker' }, '第一次使用 · 先看这里'),
        h('h3', { id: 'onboarding-title' }, headline),
        h('p', {}, explanation),
        h('div', { class: 'onboarding-actions' }, primary, demo, knowledge),
        h('p', { class: 'onboarding-notice' },
          '“一键体验”会创建明确标记为合成演示的资产，并使用当前已保存情报运行一次完整研判，不会扫描或改动任何真实系统。' + (state.onboarding.error ? ' 上次演示失败：' + state.onboarding.error : ''))),
      h('div', { class: 'onboarding-status' },
        h('div', { class: 'onboarding-counts' },
          h('span', {}, h('b', {}, String(events)), ' 条情报'),
          h('span', {}, h('b', {}, String(assets)), ' 条资产'),
          h('span', {}, h('b', {}, String(assessments)), ' 条研判结论')),
        h('div', { class: 'onboarding-steps' },
          onboardingStep('01', '告诉系统我有什么', assets
            ? `已录入 ${assets} 条资产及组件、版本和授权范围。`
            : '录入你实际使用的组件、版本和暴露面。', stepAssets),
          onboardingStep('02', '获取外面发生了什么', events
            ? `已保存 ${events} 条公开情报；当前有 ${producingSources} 个来源产出数据。`
            : '从已登记来源采集漏洞、厂商公告、论文和标准。', stepEvents),
          onboardingStep('03', '判断影响并告诉我先做什么', assessments
            ? `已生成 ${assessments} 条影响结论，可按优先级处理。`
            : '把情报与你的资产逐条匹配，给出四档结论和处置建议。', stepAssess)),
        resultLegend())));
  }

  async function runGuidedDemo(button) {
    if (state.onboarding.quickDemoRunning) return;
    state.onboarding.quickDemoRunning = true;
    state.onboarding.error = null;
    renderOnboarding();
    try {
      const counts = (state.dashboard && state.dashboard.counts) || {};
      if (countValue(counts.events) === 0) await api.post('/api/seed');
      await api.post('/api/assets/demo');
      const result = await api.post('/api/assessments/run');
      await loadDashboard();
      if (state.inited.has('inline:assets')) loadAssets();
      if (state.inited.has('inline:assessments')) loadAssessments();
      toast(`演示流程完成：已生成 ${textOr(result.assessments, '0')} 条研判结论`);
      openInlineModule('assessments');
    } catch (err) {
      state.onboarding.error = err.message;
      toast(err.message, 'error');
      renderOnboarding();
    } finally {
      state.onboarding.quickDemoRunning = false;
      renderOnboarding();
    }
  }

  /* The map is a read-only projection of the registered Agent design.  It is
   * deliberately kept beside the task input, rather than promoted to a new
   * navigation entry, so a viewer can understand the handoffs before running
   * anything.  Older deployments only expose /api/orchestration, therefore
   * the renderer accepts that reduced shape too. */
  function initOrchestrationMap() {
    const body = document.getElementById('body-orchestration-map');
    if (!body) return;
    state.dom.orchestrationMap = body;
    loadOrchestrationMap();
  }

  function workbenchLayers(data) {
    const layers = Array.isArray(data && data.layers) ? data.layers : [];
    const find = (id) => layers.find((item) => item && item.id === id) || {};
    const orchestration = find('orchestration');
    const rawPhases = Array.isArray(orchestration.items) ? orchestration.items
      : (Array.isArray(data && data.phases) ? data.phases : []);
    return {
      input: Array.isArray(find('input').items) ? find('input').items : [
        { id: 'question', label: '问题与任务目标' },
        { id: 'assets', label: '已授权资产' },
        { id: 'source_registry', label: '登记来源选择' }
      ],
      phases: rawPhases.filter((item) => item && item.id !== 'summary' && item.id !== 'answer'),
      tools: Array.isArray(find('tool').items) ? find('tool').items
        : (Array.isArray(data && data.tools) ? data.tools : [])
    };
  }

  function renderOrchestrationMap() {
    const body = state.dom.orchestrationMap;
    if (!body) return;
    if (state.workbench.loading) {
      setBox(body, loadingBlock('正在读取任务编排…'));
      return;
    }
    if (state.workbench.error) {
      setBox(body, errorBlock(state.workbench.error, () => loadOrchestrationMap()));
      return;
    }
    const data = state.workbench.data;
    if (!data) {
      setBox(body, emptyState('暂未读取任务编排', '服务启动后会在这里展示输入、交接和工具边界。'));
      return;
    }
    const layers = workbenchLayers(data);
    const roleLabels = {};
    arrayOr(data.roles).forEach((role) => { if (role && role.id) roleLabels[role.id] = role.label || role.id; });
    const phaseCards = layers.phases.length ? layers.phases.map((phase, index) => {
      const role = phase.role || phase.owner || phase.agent || '';
      return h('article', { class: 'orchestration-node', 'data-phase-id': phase.id || null },
        h('span', { class: 'orchestration-index' }, String(index + 1).padStart(2, '0')),
        h('div', { class: 'orchestration-node-main' },
          h('strong', {}, textOr(phase.label, phase.id)),
          role ? h('span', {}, textOr(roleLabels[role], role)) : null),
        index < layers.phases.length - 1 ? h('span', { class: 'orchestration-arrow', 'aria-hidden': 'true' }, '→') : null);
    }) : [h('p', { class: 'muted' }, '后端尚未返回可执行阶段。')];
    const inputChips = layers.input.map((item) => h('span', { class: 'chip' }, textOr(item.label, item.id)));
    const toolCards = layers.tools.length ? layers.tools.slice(0, 8).map((tool) =>
      h('span', { class: 'orchestration-tool', title: textOr(tool.last_error, '') },
        h('i', { class: `tool-state tool-state--${textOr(tool.status, 'idle')}`, 'aria-hidden': 'true' }),
        textOr(tool.name, tool.label || tool.id))) : [h('span', { class: 'muted' }, '工具清单尚未读取')];
    setBox(body,
      h('div', { class: 'orchestration-map', 'aria-label': 'Agent 任务编排图' },
        h('div', { class: 'orchestration-lane orchestration-lane--input' },
          h('span', { class: 'orchestration-lane-label' }, '输入层'),
          h('div', { class: 'orchestration-chips' }, ...inputChips)),
        h('div', { class: 'orchestration-flow', 'aria-label': '角色交接顺序' }, ...phaseCards),
        h('div', { class: 'orchestration-lane orchestration-lane--tools' },
          h('span', { class: 'orchestration-lane-label' }, '工具层'),
          h('div', { class: 'orchestration-tools' }, ...toolCards))));
  }

  async function loadOrchestrationMap() {
    if (!state.dom.orchestrationMap) return;
    state.workbench.loading = true;
    state.workbench.error = null;
    renderOrchestrationMap();
    try {
      let data = await optionalGet('/api/agent/workbench');
      if (!data) data = await api.get('/api/orchestration');
      state.workbench.data = data;
    } catch (err) {
      state.workbench.error = err.message;
      state.workbench.data = null;
    } finally {
      state.workbench.loading = false;
      renderOrchestrationMap();
    }
  }

  function initKnowledgeSurface() {
    initKnowledge();
    wireInlineModules();
  }

  const INLINE_MODULES = {
    assessments: { init: initAssessments, load: loadAssessments },
    chat: { init: initChat, load: null },
    assets: { init: initAssets, load: loadAssets },
    sources: { init: () => { initCollect(); renderTools(); }, load: loadSources },
    events: { init: initEvents, load: loadEvents },
    quality: { init: initQuality, load: loadQuality },
    'agent-evidence': { init: () => { renderAiSection(); initLabels(); }, load: null }
  };

  function wireInlineModules() {
    document.querySelectorAll('details[data-module]').forEach((details) => {
      if (details.dataset.wired) return;
      details.dataset.wired = '1';
      details.addEventListener('toggle', () => {
        if (!details.open) return;
        const key = details.dataset.module;
        const meta = INLINE_MODULES[key];
        if (!meta) return;
        const flag = 'inline:' + key;
        if (!state.inited.has(flag)) {
          state.inited.add(flag);
          meta.init();
        }
        if (meta.load) meta.load();
      });
    });
  }

  function openInlineModule(key) {
    const details = document.querySelector(`details[data-module="${key}"]`);
    if (!details) return;
    if (!details.open) details.open = true;
    details.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function openKnowledgeEvent(eventId) {
    activate('knowledge');
    window.setTimeout(() => {
      openInlineModule('events');
      window.setTimeout(() => selectEvent(eventId), 0);
    }, 0);
  }

  /* ----------------------------------------------------- 标准资产仿真 */

  const SIMULATION_SAMPLE_BOM = {
    bomFormat: 'CycloneDX', specVersion: '1.6', serialNumber: 'urn:uuid:5bd17420-42cc-4be7-b1cc-competition-demo', version: 1,
    metadata: { timestamp: '2026-09-20T12:25:00Z', tools: [{ name: 'Syft', version: '1.52.0' }],
      component: { type: 'application', name: 'vLLM 视频推理服务（标准SBOM仿真）', 'bom-ref': 'app:vllm-video-simulation' } },
    components: [
      { type: 'library', name: 'vllm', version: '0.10.0', purl: 'pkg:pypi/vllm@0.10.0', 'bom-ref': 'pkg:pypi/vllm@0.10.0' },
      { type: 'library', name: 'fastapi', version: '0.115.0', purl: 'pkg:pypi/fastapi@0.115.0', 'bom-ref': 'pkg:pypi/fastapi@0.115.0' },
      { type: 'library', name: 'uvicorn', version: '0.30.6', purl: 'pkg:pypi/uvicorn@0.30.6', 'bom-ref': 'pkg:pypi/uvicorn@0.30.6' }
    ]
  };

  function initSimulation() {
    const body = bodyOf('simulation');
    if (!body) return;
    state.dom.simulation = { body: body };
    renderSimulation();
  }

  function ecosystemFromPurl(purl) {
    const type = String(purl || '').match(/^pkg:([^/]+)/);
    const known = { pypi: 'PyPI', golang: 'Go', npm: 'npm', maven: 'Maven', nuget: 'NuGet', cargo: 'Cargo' };
    return type ? (known[type[1].toLowerCase()] || type[1]) : '';
  }

  async function prepareSimulationBom(doc, source) {
    const preview = await api.post('/api/assets/cyclonedx/dry-run', { bom: doc });
    state.simulation.bom = doc;
    state.simulation.preview = preview;
    state.simulation.assets = Array.isArray(preview.assets) ? preview.assets : [];
    state.simulation.source = source;
    state.simulation.confirmed = false;
    state.simulation.imported = [];
    state.simulation.assessments = [];
    state.simulation.selected = null;
    state.simulation.result = null;
    state.simulation.error = null;
    await loadSimulationPlan();
  }

  function loadSimulationFile(file) {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      state.simulation.error = '文件超过 2 MB，请拆分后导入。';
      renderSimulation();
      return;
    }
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const doc = JSON.parse(String(reader.result || ''));
        await prepareSimulationBom(doc, { type: 'CycloneDX JSON', name: file.name, observedAt: new Date().toISOString(), synthetic: true });
      } catch (err) {
        state.simulation.error = err.message;
        renderSimulation();
      }
    };
    reader.onerror = () => { state.simulation.error = '无法读取文件。'; renderSimulation(); };
    reader.readAsText(file, 'utf-8');
  }

  async function useSimulationSample() {
    try {
      await prepareSimulationBom(JSON.parse(JSON.stringify(SIMULATION_SAMPLE_BOM)),
        { type: '内置标准样例', name: 'Syft 风格 CycloneDX 合成清单', observedAt: new Date().toISOString(), synthetic: true });
    } catch (err) {
      state.simulation.error = err.message;
      renderSimulation();
    }
  }

  async function loadSimulationPlan() {
    state.simulation.plan = await optionalGet('/api/orchestration');
    renderSimulation();
  }

  function simulationAssumptions() {
    const backend = state.simulation.preview && Array.isArray(state.simulation.preview.assumptions)
      ? state.simulation.preview.assumptions : [];
    return [...backend, '这是资产影响仿真；不会扫描网络、安装组件或执行漏洞利用。',
      '未知的暴露面、业务重要性和运行条件保持未知，不使用 ALL_TRUE 假设。'];
  }

  function renderSimulation() {
    const body = state.dom.simulation && state.dom.simulation.body;
    if (!body) return;
    const sim = state.simulation;
    const fileInput = h('input', { type: 'file', id: 'simulation-file', accept: '.json,application/json', class: 'sr-file',
      onchange: (event) => loadSimulationFile(event.target.files && event.target.files[0]) });
    const importBox = h('section', { class: 'simulation-step' },
      h('div', { class: 'simulation-step-head' }, h('span', {}, '1'), h('div', {}, h('h4', {}, '导入标准清单'), h('p', {}, '选择 CycloneDX JSON，或使用内置合成样例快速体验。'))),
      h('div', { class: 'btn-row' },
        h('label', { class: 'btn btn--primary', for: 'simulation-file' }, '选择 CycloneDX JSON'), fileInput,
        h('button', { type: 'button', class: 'btn btn--ghost', onclick: useSimulationSample }, '使用内置标准样例')),
      sim.error ? alertBox('error', '清单无法使用', h('p', {}, sim.error)) : null);

    if (!sim.assets.length) {
      setBox(body, importBox, h('div', { class: 'simulation-empty' }, '导入后将在这里预览资产、核对假设并生成执行计划。'));
      return;
    }

    const previewRows = sim.assets.map((item) => [
      h('div', {}, textOr(item.name), item.is_demo ? h('span', { class: 'badge badge--demo' }, '合成') : null),
      textOr(item.component), textOr(item.ecosystem, '未识别'), textOr(item.version, '未提供'),
      textOr((item.sbom || {}).purl, '未提供'), textOr((item.sbom || {}).bom_ref, '未提供')
    ]);
    const source = sim.source || {};
    const confirm = h('input', { type: 'checkbox', checked: sim.confirmed,
      onchange: (event) => { state.simulation.confirmed = event.target.checked; renderSimulation(); } });
    const assumptions = simulationAssumptions();
    const assumptionBox = h('section', { class: 'simulation-step' },
      h('div', { class: 'simulation-step-head' }, h('span', {}, '2'), h('div', {}, h('h4', {}, '核对来源与仿真假设'), h('p', {}, '确认前不会写入资产库，也不会开始研判。'))),
      h('div', { class: 'simulation-provenance' },
        h('div', {}, h('span', {}, '清单来源'), h('strong', {}, textOr(source.type))),
        h('div', {}, h('span', {}, '来源名称'), h('strong', {}, textOr(source.name))),
        h('div', {}, h('span', {}, '导入时间'), h('strong', {}, textOr(fmtTime(source.observedAt)))),
        h('div', {}, h('span', {}, '数据性质'), h('strong', {}, source.synthetic ? '合成仿真数据' : '用户提供清单'))),
      h('ul', { class: 'assumption-list' }, ...assumptions.map((item) => h('li', {}, item))),
      h('label', { class: 'simulation-confirm' }, confirm, h('span', {}, '我已核对以上来源和假设，同意将清单纳入本次评估范围。')));

    const plan = sim.plan || {};
    const phases = Array.isArray(plan.phases) ? plan.phases.filter((item) => item.id !== 'summary' && item.id !== 'answer') : [];
    const planBox = h('section', { class: 'simulation-step' },
      h('div', { class: 'simulation-step-head' }, h('span', {}, '3'), h('div', {}, h('h4', {}, 'Agent 执行计划'), h('p', {}, '计划、工具预算和停止条件来自运行中的编排接口。'))),
      h('div', { class: 'simulation-plan' },
        ...(phases.length ? phases.map((phase, index) => h('div', { class: 'simulation-plan-node' }, h('b', {}, String(index + 1)), h('span', {}, textOr(phase.label)))) : [h('p', { class: 'muted' }, '编排信息尚未读取。')]),
        plan.scheduling ? h('p', { class: 'simulation-budget' }, `边界：最多 ${textOr(plan.scheduling.max_rounds)} 轮，最多 ${textOr(plan.scheduling.tool_budget)} 次外部工具调用。`) : null));
    const runBtn = h('button', { type: 'button', class: 'btn btn--primary', disabled: !sim.confirmed || sim.running,
      onclick: () => runSimulation(runBtn) }, icon('play'), sim.running ? '正在运行…' : `运行 ${sim.assets.length} 条资产仿真`);
    planBox.appendChild(h('div', { class: 'btn-row' }, runBtn));

    const preview = h('section', { class: 'simulation-step' },
      h('div', { class: 'simulation-step-head' }, h('span', {}, '清单'), h('div', {}, h('h4', {}, `预览 ${sim.assets.length} 条受管软件/服务`), h('p', {}, '版本缺失会保留为待补信息。'))),
      h('div', { class: 'table-wrap' }, dataTable([{ text: '资产' }, { text: '组件' }, { text: '生态' }, { text: '版本' }, { text: 'PURL' }, { text: 'bom-ref' }], previewRows)));

    setBox(body, importBox, preview, assumptionBox, planBox, renderSimulationResults());
  }

  async function runSimulation(button) {
    if (state.simulation.running || !state.simulation.confirmed) return;
    state.simulation.running = true;
    state.simulation.error = null;
    renderSimulation();
    try {
      if (!state.simulation.bom) throw new Error('请先导入并预览 CycloneDX 清单。');
      const imported = await api.post('/api/assets/cyclonedx/import', { bom: state.simulation.bom, authorized: true });
      const result = await api.post('/api/assets/cyclonedx/' + encodeURIComponent(imported.batch_id) + '/assess');
      state.simulation.imported = state.simulation.assets;
      state.simulation.result = result;
      state.simulation.assessments = Array.isArray(result.relationships) ? result.relationships : [];
      toast('标准资产仿真已完成');
    } catch (err) {
      state.simulation.error = err.message;
      toast(err.message, 'error');
    } finally {
      state.simulation.running = false;
      renderSimulation();
      refreshDashboardQuiet();
    }
  }

  function renderSimulationResults() {
    const sim = state.simulation;
    if (!sim.imported.length && !sim.assessments.length) return null;
    const affectedIds = new Set(sim.assessments.filter((x) => x.status === 'affected').map((x) => x.asset_id));
    const pendingIds = new Set(sim.assessments.filter((x) => x.status === 'needs_confirmation').map((x) => x.asset_id));
    const rows = sim.assessments.map((item) => [
      textOr(item.asset_name, item.asset_id), textOr(item.event_title, item.event_id), assessStatusBadge(item.status),
      priorityBadge(item.priority),
      h('button', { type: 'button', class: 'link-button', onclick: () => loadSimulationDetail(item) }, '查看依据与建议')
    ]);
    return h('section', { class: 'simulation-step simulation-results' },
      h('div', { class: 'simulation-step-head' }, h('span', {}, '4'), h('div', {}, h('h4', {}, '匹配结论'), h('p', {}, '资产数按 asset_id 去重；匹配项表示风险与资产之间的关系数。'))),
      h('div', { class: 'tiles' },
        tile('导入资产', sim.imported.length), tile('受影响资产', affectedIds.size, { tone: affectedIds.size ? 'bad' : null }),
        tile('待补信息资产', pendingIds.size, { tone: pendingIds.size ? 'alert' : null }), tile('风险—资产匹配项', sim.assessments.length)),
      rows.length ? dataTable([{ text: '受管资产' }, { text: '风险事件' }, { text: '结论' }, { text: '规则优先级' }, { text: '详情' }], rows)
        : emptyState('没有生成匹配项', '这不会判定为安全；当前事件库中可能没有组件匹配记录。'),
      h('div', { id: 'simulation-detail', class: 'simulation-detail' },
        sim.selected ? renderSimulationDetail(sim.selected) : emptyState('选择一条匹配项查看四层依据')));
  }

  async function loadSimulationDetail(assessment) {
    const asset = state.simulation.imported.find((item) => item.id === assessment.asset_id) || {};
    state.simulation.selected = { assessment: assessment, asset: asset, event: null, loading: true };
    renderSimulation();
    try {
      const event = await api.get('/api/events/' + encodeURIComponent(assessment.event_id));
      state.simulation.selected = { assessment: assessment, asset: asset, event: event, loading: false };
    } catch (err) {
      state.simulation.selected = { assessment: assessment, asset: asset, event: null, loading: false, error: err.message };
    }
    renderSimulation();
    const detail = document.getElementById('simulation-detail');
    if (detail) detail.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function renderSimulationDetail(selected) {
    if (selected.loading) return loadingBlock('正在读取事件证据…');
    if (selected.error) return errorBlock(selected.error);
    const assessment = selected.assessment || {};
    const asset = selected.asset || {};
    const event = selected.event || {};
    const sources = Array.isArray(event.sources) ? event.sources : [];
    const fixed = (Array.isArray(event.affected) ? event.affected : []).find((item) => item.fixed_version);
    const unknowns = [];
    if (!asset.version) unknowns.push('资产版本未提供');
    if (!asset.ecosystem) unknowns.push('组件生态未识别');
    if (!Object.keys(asset.conditions || {}).length) unknowns.push('运行配置未提供；若公告存在触发条件，结论可能需要补充确认');
    if (!sources.length) unknowns.push('事件没有可展示的引用来源');
    const advice = assessment.status === 'affected'
      ? (fixed ? `核对平台、分支和配置后，升级到 ${fixed.fixed_version} 或更高的已核验修复版本。` : '优先隔离暴露面并向厂商核对修复方案；当前证据未给出可引用的修复版本。')
      : assessment.status === 'needs_confirmation' ? '先补齐资产版本和关键配置，再决定升级或缓解措施。'
        : assessment.status === 'not_affected' ? '在当前资产快照与规则范围内无需升级，继续监测来源更新。' : '该记录未纳入本次影响判断。';
    return h('div', { class: 'evidence-layers' },
      h('h4', {}, '证据与建议'),
      h('section', { class: 'evidence-layer fact' }, h('h5', {}, '来源事实'),
        sources.length ? h('ul', {}, ...sources.map((source) => h('li', {}, textOr(source.title, source.id), ' · ', textOr(source.publisher, '发布方未标注')))) : h('p', {}, '暂无可展示来源'),
        h('p', {}, '事件：', textOr(event.title, assessment.event_id), '；发布时间：', textOr(fmtTime(event.published_at), '未记录'))),
      h('section', { class: 'evidence-layer input' }, h('h5', {}, '资产输入'),
        kvList([['名称', textOr(asset.name)], ['组件 / 生态', `${textOr(asset.component)} / ${textOr(asset.ecosystem, '未识别')}`], ['版本', textOr(asset.version, '未提供')], ['清单来源', textOr((state.simulation.source || {}).name)], ['数据性质', asset.is_demo ? '合成仿真数据' : '用户提供清单']])),
      h('section', { class: 'evidence-layer derived' }, h('h5', {}, '系统推导'),
        h('p', {}, '结论：', assessStatusBadge(assessment.status), '；', '规则优先级：', priorityBadge(assessment.priority)),
        Array.isArray(assessment.reasons) ? h('ul', {}, ...assessment.reasons.map((reason) => h('li', {}, humanizeReason(reason)))) : null,
        h('p', { class: 'plain-note' }, '优先级用于处置排序，不等同于来源给出的漏洞官方评级。')),
      h('section', { class: 'evidence-layer unknown' }, h('h5', {}, '未知与假设'),
        unknowns.length ? h('ul', {}, ...unknowns.map((item) => h('li', {}, item))) : h('p', {}, '本次固定检查维度未发现缺项；不代表不存在其他未知信息。')),
      h('section', { class: 'simulation-advice' }, h('span', {}, '建议动作'), h('strong', {}, advice),
        Array.isArray(assessment.evidence_ids) && assessment.evidence_ids.length
          ? h('p', {}, '关联证据：', assessment.evidence_ids.join('、')) : h('p', {}, '当前结论没有关联证据 ID，执行前需人工复核。')));
  }

  function initOverview() {
    const body = bodyOf('overview');
    clear(body);

    const seedBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => runSeed(seedBtn, seedResult) },
      icon('plus'), '载入已核验演示案例');
    const collectBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => openInlineModule('sources') }, '查看可用工具');
    const actionBtn = h('button', { type: 'button', class: 'btn btn--primary', onclick: () => openInlineModule('assessments') }, '打开处置结论');
    const refreshBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => { refreshBtn.disabled = true; loadDashboard().finally(() => { refreshBtn.disabled = false; }); } },
      icon('refresh'), '刷新');
    const seedResult = h('div', { class: 'panel-body' });

    const story = h('div', { class: 'risk-story', role: 'list', 'aria-label': '风险研判流程' },
      ['公开披露', '系统发现', '证据确认', '关联资产', '给出处置', '留痕验证'].map((label, index) =>
        h('div', { class: 'risk-story-step', role: 'listitem' },
          h('span', { class: 'risk-story-no' }, String(index + 1)), h('span', {}, label))));
    const liveBtn = h('button', { type: 'button', id: 'live-open', class: 'btn btn--live',
      onclick: () => document.getElementById('body-live').scrollIntoView({ behavior: 'smooth', block: 'start' }) }, icon('play'), '开始研判任务');

    const taskBrief = h('div', { class: 'task-brief', role: 'group', 'aria-label': '当前任务输入' },
      h('div', { class: 'task-brief-item' }, h('span', { class: 'task-brief-key' }, '任务目标'),
        h('strong', {}, '识别新增安全风险并形成可执行处置建议')),
      h('div', { class: 'task-brief-item' }, h('span', { class: 'task-brief-key' }, '已有上下文'),
        h('span', {}, '公开披露、本地证据库、授权资产清单')),
      h('div', { class: 'task-brief-item' }, h('span', { class: 'task-brief-key' }, '执行约束'),
        h('span', {}, '固定来源 · 有限轮次 · 证据不足时拒绝下结论')));
    const actions = card('当前任务',
      taskBrief,
      story,
      h('div', { class: 'btn-row' }, liveBtn, actionBtn, collectBtn, seedBtn, refreshBtn),
      h('p', { class: 'dim' }, '初始化演示数据会导入 research/cases.json 中人工核验的案例，并创建明确标注 is_demo=true 的合成演示资产。'),
      seedResult);

    const tiles = h('div', { class: 'tiles' });
    const cards = h('div', { class: 'grid-cards grid-cards--wide' });

    state.dom.overview = { tiles: tiles, cards: cards };
    body.append(actions, tiles, cards);
    renderOverview();
  }

  /* ------------------------------------------------------------- 知识库 */

  function initKnowledge() {
    const body = bodyOf('knowledge');
    clear(body);
    const refresh = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => {
      refresh.disabled = true;
      loadKnowledge().finally(() => { refresh.disabled = false; });
    } }, icon('refresh'), '刷新知识视图');
    const summary = h('div');
    const visual = h('div');
    state.dom.knowledge = { summary: summary, visual: visual };
    body.append(card('知识资产概览', h('div', { class: 'btn-row' }, refresh), summary), visual);
    renderKnowledge();
  }

  async function loadKnowledge() {
    const view = state.dom.knowledge;
    if (!view) return;
    state.knowledge.loading = true;
    renderKnowledge();
    try {
      /* A full-text index is additive.  A temporarily unavailable RAG endpoint
       * must not blank the whole knowledge product when the collected corpus
       * and source registry are still readable. */
      const results = await Promise.allSettled([
        api.get('/api/knowledge/documents?limit=200'),
        api.get('/api/rag/documents?limit=200'),
        api.get('/api/sources')
      ]);
      const valueOf = (result) => result.status === 'fulfilled' ? result.value : null;
      const failures = results.filter((result) => result.status === 'rejected');
      const eventResult = valueOf(results[0]);
      const fullTextResult = valueOf(results[1]);
      const sourceResult = valueOf(results[2]);
      if (!eventResult && !fullTextResult && !sourceResult) {
        throw new Error(failures.map((result) => result.reason && result.reason.message).filter(Boolean).join('；') || '知识服务暂不可用');
      }
      const eventDocuments = arrayOr(eventResult && eventResult.items);
      const fullTextDocuments = arrayOr(fullTextResult && fullTextResult.items);
      state.knowledge.documents = [...fullTextDocuments, ...eventDocuments].map(ragDocument);
      state.knowledge.total = state.knowledge.documents.length;
      state.knowledge.sources = Array.isArray(sourceResult && sourceResult.items) ? sourceResult.items : (Array.isArray(sourceResult) ? sourceResult : []);
      state.knowledge.error = null;
    } catch (err) {
      state.knowledge.error = err.message;
    }
    state.knowledge.loading = false;
    renderKnowledge();
  }

  function renderRagChunk(chunkValue, index) {
    const chunk = ragChunk(chunkValue);
    const location = [
      chunk.section ? `章节：${chunk.section}` : '章节未记录',
      chunk.page ? `第 ${chunk.page} 页` : null,
      chunk.char_start !== null && chunk.char_end !== null ? `字符 ${chunk.char_start}–${chunk.char_end}` : null,
      chunk.retrieval ? `检索：${chunk.retrieval}` : null,
      typeof chunk.score === 'number' ? `相关度 ${chunk.score.toFixed(3)}` : null
    ].filter(Boolean).join(' · ');
    return h('article', { class: 'rag-chunk', 'data-chunk-id': chunk.id || null },
      h('div', { class: 'rag-chunk-head' },
        mono(chunk.id || `块 ${index + 1}`),
        h('span', { class: 'muted' }, location)),
      h('p', { class: 'excerpt' }, textOr(chunk.text, '该块未返回可显示的原文。')));
  }

  function renderRagDocument(item) {
    const scopeKind = item.rag_scope === 'fulltext' ? 'confirmed' : (item.rag_scope === 'excerpt' ? 'needs-confirmation' : 'plain');
    const sectionNames = item.rag_sections.map((section) => section.title || section.name || section.heading).filter(Boolean);
    const chunks = item.rag_chunks.slice(0, 8);
    return h('details', { class: 'knowledge-document rag-document' },
      h('summary', {},
        h('span', { class: 'knowledge-document-title' }, textOr(item.title, item.id)),
        h('span', { class: 'rag-document-status' }, badge(scopeKind, item.rag_scope_label),
          mono(`${item.rag_section_count} 章节 · ${item.rag_chunk_count} 块`, 'dim'))),
      h('div', { class: 'rag-document-body' },
        h('p', { class: 'knowledge-document-meta' },
          textOr(item.category, '未分类'), ' · ', textOr(fmtTime(item.published_at), '时间未记录'),
          ' · ', textOr(item.publisher, '发布者未记录')),
        item.rag_scope !== 'fulltext'
          ? alertBox('warn', '全文尚未入库', h('p', {}, item.rag_scope === 'excerpt'
            ? '当前只有摘要或来源摘录，不能用于论文正文级多跳问答。'
            : '当前只有文档元数据，不能作为正文事实证据。'))
          : null,
        sectionNames.length
          ? h('p', { class: 'rag-sections' }, h('strong', {}, '章节：'), sectionNames.slice(0, 8).join(' / '))
          : h('p', { class: 'muted' }, '章节未索引'),
        item.rag_chunks.length
          ? h('details', { class: 'rag-chunk-drawer' },
            h('summary', {}, `正文块（${item.rag_chunk_count}）`),
            h('div', { class: 'rag-chunk-list' }, ...chunks.map(renderRagChunk)))
          : emptyState('没有可下钻的正文块'),
        h('div', { class: 'btn-row' },
          item.event_id ? h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: () => openKnowledgeEvent(item.event_id) }, '查看关联风险') : null,
          safeLink(item.url, '打开原始来源'))));
  }

  function renderKnowledge() {
    const view = state.dom.knowledge;
    if (!view) return;
    if (state.knowledge.loading) {
      setBox(view.summary, loadingBlock('正在整理本地知识资产…'));
      setBox(view.visual);
      return;
    }
    if (state.knowledge.error) {
      setBox(view.summary, errorBlock(state.knowledge.error, () => loadKnowledge()));
      setBox(view.visual);
      return;
    }
    const documents = state.knowledge.documents;
    const sources = state.knowledge.sources;
    if (!documents.length && !sources.length) {
      setBox(view.summary, emptyState('知识库尚无内容'));
      setBox(view.visual);
      return;
    }
    const categoryCounts = {};
    documents.forEach((item) => {
      const category = textOr(item.category, '未分类');
      categoryCounts[category] = (categoryCounts[category] || 0) + 1;
    });
    const fullTextCount = documents.filter((item) => item.rag_scope === 'fulltext').length;
    const excerptCount = documents.filter((item) => item.rag_scope === 'excerpt').length;
    const chunkCount = documents.reduce((sum, item) => sum + item.rag_chunk_count, 0);
    const sectionCount = documents.reduce((sum, item) => sum + item.rag_section_count, 0);
    const maxCategory = Math.max(1, ...Object.keys(categoryCounts).map((key) => categoryCounts[key]));
    const sourceCategories = {};
    sources.forEach((source) => {
      const label = textOr(source.category_label, '未分类来源');
      sourceCategories[label] = (sourceCategories[label] || 0) + 1;
    });
    setBox(view.summary,
      h('div', { class: 'tiles knowledge-tiles' },
        tile('全文文档', fullTextCount, { sub: `共 ${state.knowledge.total} 份文档` }),
        tile('摘要/摘录', excerptCount),
        tile('可检索块', chunkCount),
        tile('已索引章节', sectionCount)));

    const categoryBars = h('div', { class: 'knowledge-bars', role: 'img', 'aria-label': '知识文档类别分布' },
      ...Object.keys(categoryCounts).sort((a, b) => categoryCounts[b] - categoryCounts[a]).map((name) =>
        h('div', { class: 'knowledge-bar-row' },
          h('span', { class: 'knowledge-bar-label' }, name),
          h('progress', { class: 'knowledge-bar-track', max: String(maxCategory), value: String(categoryCounts[name]), 'aria-label': `${name} ${categoryCounts[name]} 条` }),
          h('strong', { class: 'mono' }, String(categoryCounts[name])))));

    const sourceChips = Object.keys(sourceCategories).sort((a, b) => sourceCategories[b] - sourceCategories[a]).map((name) =>
      h('span', { class: 'chip', title: sources.filter((source) => textOr(source.category_label, '未分类来源') === name)
        .map((source) => textOr(source.name, source.id)).join(' · ') }, `${name} ${sourceCategories[name]}`));

    const recentDocuments = documents.slice(0, 6).map((item) => h('li', {}, renderRagDocument(item)));

    const relation = h('div', { class: 'knowledge-map', role: 'img', 'aria-label': '来源、文档与研判关系图' },
      h('div', { class: 'knowledge-map-column' }, h('span', { class: 'knowledge-map-title' }, '来源'),
        ...Object.keys(sourceCategories).slice(0, 5).map((name) => h('span', { class: 'knowledge-node source' }, name))),
      h('div', { class: 'knowledge-map-flow', 'aria-hidden': 'true' }, h('span', {}, '采集'), h('b', {}, '→')),
      h('div', { class: 'knowledge-map-column' }, h('span', { class: 'knowledge-map-title' }, '文档'),
        h('span', { class: 'knowledge-node document' }, `${fullTextCount} 全文 · ${excerptCount} 摘要/摘录`),
        h('span', { class: 'knowledge-node document' }, `${state.knowledge.total - fullTextCount - excerptCount} 仅元数据`)),
      h('div', { class: 'knowledge-map-flow', 'aria-hidden': 'true' }, h('span', {}, '解析分块'), h('b', {}, '→')),
      h('div', { class: 'knowledge-map-column' }, h('span', { class: 'knowledge-map-title' }, '章节与块'),
        h('span', { class: 'knowledge-node chunk' }, `${sectionCount} 个章节`),
        h('span', { class: 'knowledge-node chunk' }, `${chunkCount} 个可引用块`)),
      h('div', { class: 'knowledge-map-flow', 'aria-hidden': 'true' }, h('span', {}, '检索引用'), h('b', {}, '→')),
      h('div', { class: 'knowledge-map-column' }, h('span', { class: 'knowledge-map-title' }, '知识'),
        ...Object.keys(categoryCounts).slice(0, 5).map((name) => h('button', { type: 'button', class: 'knowledge-node category', onclick: () => {
          activate('knowledge');
          openInlineModule('events');
          state.events.filters.category = name;
          loadEvents();
        } }, `${name} ${categoryCounts[name]}`))));

    setBox(view.visual,
      card('知识关系与覆盖', relation),
      h('div', { class: 'grid-cards grid-cards--wide knowledge-grid' },
        card('文档类别分布', categoryBars),
        card('来源覆盖', sourceChips.length ? h('div', { class: 'chips knowledge-source-chips' }, ...sourceChips) : emptyState('尚无来源登记')),
        card('文档', recentDocuments.length
          ? h('ul', { class: 'knowledge-documents' }, ...recentDocuments)
          : emptyState('尚无可下钻文档'))));
  }

  /* ----------------------------------------------------------- 赛题指标 */

  function initScorecard() {
    const body = bodyOf('scorecard');
    clear(body);
    const refresh = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => {
      refresh.disabled = true;
      loadScorecard().finally(() => { refresh.disabled = false; });
    } }, icon('refresh'), '刷新证据');
    const status = h('div');
    const grid = h('div', { class: 'score-grid' });
    state.dom.scorecard = { status: status, grid: grid };
    body.append(h('div', { class: 'scorecard-toolbar' },
      h('p', {}, '数据来自当前运行记录和本地证据，不使用演示占位分数。'), refresh), status, grid);
    wireInlineModules();
    renderScorecard();
  }

  async function optionalGet(path) {
    try { return await api.get(path); } catch (err) { return null; }
  }

  async function loadScorecard() {
    if (!state.dom.scorecard) return;
    state.scorecard.loading = true;
    renderScorecard();
    try {
      const results = await Promise.all([
        optionalGet('/api/competition/scorecard'),
        optionalGet('/api/dashboard'),
        optionalGet('/api/monitoring/evidence?days=7'),
        optionalGet('/api/evaluation'),
        optionalGet('/api/orchestration'),
        optionalGet('/api/ai-participation')
      ]);
      state.scorecard.data = {
        official: results[0], dashboard: results[1], monitoring: results[2],
        evaluation: results[3], orchestration: results[4], participation: results[5]
      };
      state.scorecard.error = null;
    } catch (err) {
      state.scorecard.error = err.message;
    }
    state.scorecard.loading = false;
    renderScorecard();
  }

  function firstValue(object, paths) {
    for (const path of paths) {
      let value = object;
      for (const key of path.split('.')) value = value && value[key];
      if (value !== null && value !== undefined && value !== '') return value;
    }
    return null;
  }

  function evidenceValue(value, suffix) {
    return value === null || value === undefined
      ? h('span', { class: 'score-missing' }, '暂无运行证据')
      : h('strong', { class: 'score-value' }, String(value) + (suffix || ''));
  }

  function scoreCapability(title, stateLabel, facts, note) {
    return h('article', { class: 'score-capability' },
      h('div', { class: 'score-capability-head' }, h('h3', {}, title), badge(stateLabel === '已验证' ? 'ok' : 'plain', stateLabel)),
      h('div', { class: 'score-facts' }, ...facts.map((fact) =>
        h('div', { class: 'score-fact' }, h('span', {}, fact[0]), evidenceValue(fact[1], fact[2])))),
      h('p', { class: 'plain-note' }, note));
  }

  function renderScorecard() {
    const view = state.dom.scorecard;
    if (!view) return;
    if (state.scorecard.loading) {
      setBox(view.status, loadingBlock('正在汇总赛题证据…'));
      setBox(view.grid);
      return;
    }
    if (state.scorecard.error) {
      setBox(view.status, errorBlock(state.scorecard.error, () => loadScorecard()));
      setBox(view.grid);
      return;
    }
    const all = state.scorecard.data;
    if (!all) {
      setBox(view.status, emptyState('尚未读取赛题证据', '点击刷新，或等待页面自动加载。'));
      return;
    }
    const official = all.official || {};
    const dashboard = all.dashboard || {};
    const monitoring = all.monitoring || {};
    const evaluation = all.evaluation || {};
    const orchestration = all.orchestration || {};
    const coverage = (dashboard.monitoring || {}).coverage || {};
    const metrics = evaluation.metrics || {};
    const completeDays = firstValue(monitoring, ['complete_days', 'summary.complete_days']);
    const within24h = firstValue(monitoring, ['within_24h_ratio', 'latency.within_24h_ratio', 'summary.within_24h_ratio']);
    const toolCount = Array.isArray(orchestration.tools) ? orchestration.tools.length : null;
    const phaseCount = Array.isArray(orchestration.phases) ? orchestration.phases.filter((x) => x.id !== 'summary' && x.id !== 'answer').length : null;
    const officialReady = Object.keys(official).length > 0;

    setBox(view.status,
      h('div', { class: 'scorecard-status' },
        badge(officialReady ? 'ok' : 'plain', officialReady ? '已接入统一计分接口' : '兼容模式'),
        h('span', {}, officialReady
          ? '当前优先消费 /api/competition/scorecard。'
          : '统一计分接口尚未提供，当前由现有监测、评测和编排接口汇总；接口上线后会自动优先使用。')));
    setBox(view.grid,
      scoreCapability('持续监测', completeDays !== null ? '已验证' : '待积累', [
        ['完整运行天数', completeDays, ' 天'],
        ['来源分类', firstValue(official, ['monitoring.source_categories']) || coverage.categories, ' 类'],
        ['有效端点', coverage.endpoints_with_data, '']
      ], '证据来自最近 7 天监测记录与来源覆盖统计。'),
      scoreCapability('知识富化', dashboard.latest_enrichment || (dashboard.counts || {}).events ? '已验证' : '待运行', [
        ['知识事件', firstValue(official, ['enrichment.documents']) || (dashboard.counts || {}).events, ' 条'],
        ['工具数量', toolCount, ' 个'],
        ['受限轮次', firstValue(orchestration, ['scheduling.max_rounds']), ' 轮']
      ], '补证受工具预算和停止条件约束，缺口会保留。'),
      scoreCapability('证据问答', metrics.cases_total ? '已验证' : '待评测', [
        ['评测用例', metrics.cases_total, ' 个'],
        ['通过用例', metrics.cases_passed, ' 个'],
        ['准确率', metrics.accuracy, '']
      ], '答案只从本地证据拼装，并携带引用；资料不足时拒答。'),
      scoreCapability('时效与性能', within24h !== null ? '已验证' : '待积累', [
        ['24 小时内发现', within24h, typeof within24h === 'number' && within24h <= 1 ? '' : '%'],
        ['最近采集状态', firstValue(dashboard, ['latest_collection.status']), ''],
        ['完整运行天数', completeDays, ' 天']
      ], '发布时间到发现时间的延迟来自真实采集证据，不做前端估算。'),
      scoreCapability('Agent 编排证据', phaseCount ? '已验证' : '待读取', [
        ['任务阶段', phaseCount, ' 个'],
        ['固定工具', toolCount, ' 个'],
        ['工具预算', firstValue(orchestration, ['scheduling.tool_budget']), ' 次']
      ], '计划、检索、审核、停止条件和工具调用均可在任务运行记录中核查。'));
  }

  async function loadDashboard() {
    const tiles = state.dom.overview ? state.dom.overview.tiles : null;
    if (tiles && !state.dashboard) setBox(tiles, emptyState('正在加载总览…'));
    try {
      const results = await Promise.all([
        api.get('/api/dashboard'),
        api.get('/api/assessments?limit=200'),
        api.get('/api/events?status=needs_review&limit=100')
      ]);
      state.dashboard = results[0];
      state.dashboardAssessments = Array.isArray(results[1].items) ? results[1].items : [];
      const today = new Date().toISOString().slice(0, 10);
      state.dashboardRisks = (Array.isArray(results[2].items) ? results[2].items : [])
        .filter((item) => String(item.collected_at || '').slice(0, 10) === today);
    } catch (err) {
      if (tiles) setBox(tiles, errorBlock(err.message, () => loadDashboard()));
      return;
    }
    renderOverview();
  }

  function renderOverview() {
    const view = state.dom.overview;
    if (!view) return;
    const dash = state.dashboard;

    /* 计数瓦片 */
    if (!dash) {
      setBox(view.tiles, emptyState('尚未取得总览数据', '点击「刷新」重新加载。'));
      setBox(view.cards);
      return;
    }
    const counts = dash.counts || {};
    const assessments = state.dashboardAssessments || [];
    const affected = assessments.filter((item) => item.status === 'affected');
    const uncertain = assessments.filter((item) => item.status === 'needs_confirmation');
    const urgent = assessments.filter((item) => item.status === 'affected' && (item.priority === 'critical' || item.priority === 'high'));
    const assetCount = countValue(counts.assets);
    const eventCount = countValue(counts.events);
    setBox(view.tiles,
      tile('今日新增风险', textOr(state.dashboardRisks.length, '0'), {
        tone: state.dashboardRisks.length ? 'alert' : null,
        sub: `情报库共 ${eventCount} 条；0 只表示今天没有新增`
      }),
      tile('受影响资产', textOr(affected.length, '0'), {
        tone: affected.length ? 'bad' : null,
        sub: assetCount ? '来自已执行的资产研判' : '尚未录入资产，不能判断'
      }),
      tile('待补信息', textOr(uncertain.length, '0'), {
        tone: uncertain.length ? 'alert' : null,
        sub: '版本或配置不足，系统不会猜成安全'
      }),
      tile('优先处置', textOr(urgent.length, '0'), {
        tone: urgent.length ? 'bad' : null,
        sub: assetCount ? '已研判后按优先级统计' : '添加资产并研判后出现'
      }));

    /* 监测覆盖 */
    const monitoring = dash.monitoring || {};
    const coverage = monitoring.coverage || {};
    const withData = coverage.endpoints_with_data;
    const totalEndpoints = coverage.endpoints;
    const coverageBody = [];
    const coverageRows = [
      ['覆盖分类', `${textOr(coverage.categories)} 类`],
      ['分类清单', Array.isArray(coverage.category_labels) && coverage.category_labels.length
        ? h('div', { class: 'chips' }, coverage.category_labels.map((item) => h('span', { class: 'chip' }, String(item))))
        : DASH],
      ['登记端点', textOr(totalEndpoints)],
      ['独立发布来源', textOr(coverage.independent_origins)],
      ['实时能力端点', textOr(coverage.realtime_capable)],
      ['已产生有效数据的端点', `${textOr(withData)} / ${textOr(totalEndpoints)}`],
      ['未产生数据的端点', textOr(coverage.endpoints_without_data)]
    ];
    coverageBody.push(kvList(coverageRows));
    if (typeof withData === 'number' && typeof totalEndpoints === 'number' && totalEndpoints > 0) {
      coverageBody.push(h('div', { class: 'progress', role: 'img', 'aria-label': `端点覆盖率 ${withData} / ${totalEndpoints}` },
        h('div', { class: 'progress-bar' })));
    }
    coverageBody.push(h('p', { class: 'note-verbatim' }, '说明（原文照录）：' + textOr(coverage.note)));

    /* 最近一次采集 */
    const latest = dash.latest_collection;
    const collectionBody = latest
      ? kvList([
        ['运行 ID', mono(textOr(latest.id))],
        ['状态', runStatusBadge(latest.status)],
        ['完成时间', timeCell(latest.finished_at)],
        ['摘要', textOr(latest.summary)]
      ])
      : emptyState('尚未执行采集', '前往「监测采集」选择数据源并执行采集，或先初始化演示数据。');

    /* 最近一次评测 */
    const evaluation = dash.evaluation || {};
    let evaluationBody;
    if (evaluation.status === 'completed') {
      const metrics = evaluation.metrics || {};
      evaluationBody = kvList([
        ['状态', badge('completed', '已完成')],
        ['最近执行', timeCell(evaluation.executed_at)],
        ['摘要', textOr(evaluation.summary)],
        ['通过率', metrics.accuracy === null || metrics.accuracy === undefined
          ? DASH
          : `${textOr(metrics.cases_passed)} / ${textOr(metrics.cases_total)}（${String(metrics.accuracy)}）`]
      ]);
    } else {
      const limitations = Array.isArray(evaluation.limitations) ? evaluation.limitations : [];
      evaluationBody = emptyState('尚未执行评测', limitations[0] || '未执行时不提供任何分数。');
    }

    const queue = urgent.concat(uncertain).slice(0, 6);
    const queueBody = queue.length
      ? dataTable([{ text: '风险' }, { text: '资产' }, { text: '结论' }, { text: '优先级' }, { text: '下一步' }],
        queue.map((item) => [
          h('button', { type: 'button', class: 'link-button', onclick: () => openKnowledgeEvent(item.event_id) }, textOr(item.event_title, item.event_id)),
          textOr(item.asset_name, item.asset_id), assessStatusBadge(item.status), priorityBadge(item.priority),
          item.status === 'affected' ? '核对修复版本并安排升级' : '补齐版本或关键配置'
        ]))
      : assetCount === 0
        ? emptyState('现在还不能判断你的资产风险', '系统已有情报，但资产清单为空。请先添加资产，或在顶部点击“一键体验完整流程”。')
        : countValue(counts.assessments) === 0
          ? emptyState('还没有生成影响结论', '打开下方“最终结论与处置清单”，执行一次研判后即可看到优先级和依据。')
          : emptyState('当前没有紧急处置项', '系统不会把证据不足的项目判定为安全；请继续关注待复核风险。');
    setBox(view.cards,
      card('优先处置', queueBody,
        h('div', { class: 'btn-row' }, h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => openInlineModule('assessments') }, '查看全部处置项'))),
      card('今日新增待研判', state.dashboardRisks.length
        ? h('ul', { class: 'event-list' }, state.dashboardRisks.slice(0, 5).map((item) => h('li', {},
          h('button', { type: 'button', class: 'event-item', onclick: () => openKnowledgeEvent(item.id) },
            h('div', { class: 'event-item-title' }, textOr(item.title, item.id)),
            h('div', { class: 'event-item-meta' }, h('span', {}, textOr(item.component, '组件未知')), h('span', {}, '待核验证据'))))))
        : emptyState('今天没有新增待研判条目', eventCount
          ? `知识库中仍有 ${eventCount} 条历史情报，可在“知识图谱”中查看。`
          : '情报库还是空的，请先采集来源或载入演示案例。')),
      h('details', { class: 'advanced-card' }, h('summary', {}, '高级信息：来源覆盖、最近运行与质量验证'),
        h('div', { class: 'grid-cards grid-cards--wide advanced-card-body' },
          card('来源覆盖', ...coverageBody), card('最近一次采集', collectionBody), card('质量验证', evaluationBody))));
    renderOnboarding();
  }

  async function runSeed(button, resultBox) {
    button.disabled = true;
    setBox(resultBox, loadingBlock('正在初始化演示数据…'));
    try {
      const result = await api.post('/api/seed');
      const research = result.research || {};
      const demo = result.demo_assets || {};
      const lines = [];
      if (research.error) {
        lines.push(alertBox('warn', '核验案例未导入', h('p', { class: 'mono break' }, String(research.error))));
      } else {
        lines.push(kvList([
          ['核验案例', `导入 ${textOr(research.seeded, '0')} 条` + (research.accessed_at ? `（核验时间 ${textOr(research.accessed_at)}）` : '')],
          ['合成演示资产', `创建 ${textOr(demo.created, '0')} 条`]
        ]));
      }
      if (demo.notice) lines.push(h('p', { class: 'note-verbatim' }, String(demo.notice)));
      if (result.notice) lines.push(h('p', { class: 'note-verbatim' }, String(result.notice)));
      setBox(resultBox, ...lines);
      toast('演示数据已初始化');
      await refreshDashboardQuiet();
      if (state.inited.has('assets')) loadAssets();
    } catch (err) {
      setBox(resultBox, errorBlock(err.message));
      toast(err.message, 'error');
    } finally {
      button.disabled = false;
    }
  }

  /* --------------------------------------------------------- 监测采集 */

  function initCollect() {
    const body = bodyOf('collect');
    clear(body);

    const selectAll = h('input', {
      type: 'checkbox',
      onchange: () => {
        if (selectAll.checked) {
          state.sources.forEach((source) => state.selection.add(source.id));
        } else {
          state.selection.clear();
        }
        renderSources();
      }
    });
    const selectedCount = h('span', { class: 'muted' });
    const startBtn = h('button', { type: 'button', class: 'btn btn--primary', onclick: () => startCollect(false) }, icon('play'), '开始采集选中来源');
    const allBtn = h('button', { type: 'button', class: 'btn', onclick: () => startCollect(true) }, icon('play'), '采集推荐来源');
    const refreshBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => { refreshBtn.disabled = true; loadSources().finally(() => { refreshBtn.disabled = false; }); } }, icon('refresh'), '刷新来源列表');
    const seedBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => runSeed(seedBtn, state.dom.collect.seedResult) }, icon('plus'), '初始化演示数据');

    const statusBox = h('div', { class: 'panel-body' });
    const tableBox = h('div');
    const resultBox = h('div');
    const seedResult = h('div');

    state.dom.collect = {
      selectAll: selectAll,
      selectedCount: selectedCount,
      startBtn: startBtn,
      allBtn: allBtn,
      status: statusBox,
      table: tableBox,
      result: resultBox,
      seedResult: seedResult,
      elapsedSpan: h('span', { class: 'mono elapsed' })
    };

    body.append(
      card('采集控制',
        h('div', { class: 'btn-row' },
          h('label', { class: 'check' }, selectAll, h('span', {}, '全选')),
          selectedCount,
          h('span', { class: 'spacer' }),
          startBtn, allBtn, refreshBtn, seedBtn),
        h('p', { class: 'dim' }, '推荐来源自动排除需要 Token 的 GitHub Advisory 和当前网络不稳定的 arXiv；仍可在表格中手动选择这些来源。'),
        seedResult),
      statusBox,
      tableBox,
      resultBox);

    renderCollectStatus();
  }

  async function loadSources() {
    const view = state.dom.collect;
    if (!view) return;
    setBox(view.table, loadingBlock('正在加载数据源…'));
    try {
      const data = await api.get('/api/sources');
      state.sources = Array.isArray(data.items) ? data.items : [];
      const known = new Set(state.sources.map((source) => source.id));
      Array.from(state.selection).forEach((id) => { if (!known.has(id)) state.selection.delete(id); });
      renderSources();
    } catch (err) {
      setBox(view.table, errorBlock(err.message, () => loadSources()));
    }
  }

  function renderSources() {
    const view = state.dom.collect;
    if (!view) return;
    const running = state.collect.running;

    const allSelected = state.sources.length > 0 && state.selection.size === state.sources.length;
    view.selectAll.checked = allSelected;
    view.selectAll.indeterminate = !allSelected && state.selection.size > 0;
    view.selectAll.disabled = running;
    view.selectedCount.textContent = `已选 ${state.selection.size} / ${state.sources.length} 个来源`;
    view.startBtn.disabled = running || state.selection.size === 0;
    view.allBtn.disabled = running;

    if (!state.sources.length) {
      setBox(view.table, emptyState('后端未返回任何数据源', '请检查服务端 sources 注册表。'));
      return;
    }

    const rows = state.sources.map((source) => {
      const checkbox = h('input', {
        type: 'checkbox',
        'aria-label': `选择数据源：${textOr(source.name, source.id)}（${textOr(source.category_label, '未分类')}）`,
        disabled: running,
        onchange: () => {
          if (checkbox.checked) state.selection.add(source.id); else state.selection.delete(source.id);
          renderSources();
        }
      });
      checkbox.checked = state.selection.has(source.id);
      const checkboxLabel = h('label', { class: 'check check--block' },
        checkbox,
        h('span', { class: 'muted' }, textOr(source.category_label, '未分类')));

      const statusCell = [
        runStatusBadge(source.status || 'idle'),
        (source.status === 'failed' || source.status === 'stale') && countValue(source.events_count) > 0
          ? badge('plain', '历史数据仍可用')
          : null,
        source.last_error ? h('p', { class: 'err-text break' }, '最近错误：' + String(source.last_error)) : null
      ];

      return [
        checkboxLabel,
        h('div', {},
          h('div', {}, textOr(source.name, source.id)),
          h('div', {}, mono(source.id, 'dim'), ' ', source.auto_default === false ? badge('plain', '需手动选择') : badge('ok', '推荐'))),
        h('div', {},
          mono(labelOf(L.sourceMode, source.mode) || textOr(source.mode)),
          source.requires_token_env ? h('div', {}, badge('plain', '需 Token：' + String(source.requires_token_env))) : null),
        source.realtime ? badge('ok', '是') : badge('neutral', '否'),
        source.independent_origin ? badge('ok', '是') : badge('neutral', '否'),
        statusCell,
        timeCell(source.last_success),
        textOr(source.events_count, '0')
      ];
    });

    setBox(view.table,
      h('h3', { class: 'block-title' }, '登记数据源', h('span', { class: 'count' }, `共 ${state.sources.length} 个 · 已接入判定以是否产生数据为准`)),
      dataTable([
        { text: '选择（分类）' },
        { text: '数据源' },
        { text: '接入方式' },
        { text: '实时' },
        { text: '独立来源' },
        { text: '状态' },
        { text: '最近成功' },
        { text: '累计采集事件', cls: 'num' }
      ], rows));
  }

  function renderCollectStatus() {
    const view = state.dom.collect;
    if (!view) return;
    const wrap = h('div', { class: 'panel-body' });

    if (state.collect.running) {
      view.elapsedSpan.textContent = '已用时 0 秒';
      wrap.append(alertBox('info', '正在采集',
        h('div', { class: 'elapsed-block' },
          h('span', { class: 'spinner' }),
          h('span', { class: 'pulse' }, '采集进行中…'),
          view.elapsedSpan),
        h('p', { class: 'dim' }, '采集可能持续 30–120 秒，期间请勿关闭页面；完成后将展示每个来源的抓取、保留、过滤与备注明细。')));
    } else if (state.collect.error) {
      wrap.append(errorBlock(state.collect.error));
    }

    if (!state.collect.running && state.collect.result) {
      const result = state.collect.result;
      wrap.append(card('最近一次采集结果',
        kvList([
          ['运行 ID', mono(textOr(result.run_id))],
          ['状态', runStatusBadge(result.status)],
          ['新增事件', textOr(result.events_added, '0')],
          ['更新事件', textOr(result.events_updated, '0')],
          ['总耗时', textOr(fmtDuration(result.duration_ms))]
        ])));
    }
    setBox(view.status, wrap);
  }

  async function startCollect(allSources) {
    if (state.collect.running) return;
    const sourceIds = allSources ? null : Array.from(state.selection);
    if (!allSources && sourceIds.length === 0) return;

    state.collect.running = true;
    state.collect.error = null;
    state.collect.result = null;
    renderSources();
    renderCollectStatus();
    state.collect.stopTimer = beginElapsed(state.dom.collect.elapsedSpan);

    try {
      const result = await api.post('/api/collect', allSources ? {} : { source_ids: sourceIds });
      state.collect.result = result;
      renderCollectResults(result);
      toast(`采集完成：新增 ${result.events_added}，更新 ${result.events_updated}`);
      await Promise.all([loadSources(), refreshDashboardQuiet()]);
      if (state.inited.has('events')) loadEvents();
    } catch (err) {
      state.collect.error = err.message;
      toast(err.message, 'error');
    } finally {
      state.collect.running = false;
      if (state.collect.stopTimer) { state.collect.stopTimer(); state.collect.stopTimer = null; }
      renderSources();
      renderCollectStatus();
    }
  }

  function renderCollectResults(result) {
    const view = state.dom.collect;
    if (!view) return;
    const results = Array.isArray(result.results) ? result.results : [];
    if (!results.length) {
      setBox(view.result, emptyState('本次采集没有返回逐来源结果'));
      return;
    }
    const rows = results.map((item) => {
      const notes = Array.isArray(item.notes) ? item.notes.filter((note) => note !== null && note !== undefined && note !== '') : [];
      const detail = [];
      if (item.error) detail.push(h('p', { class: 'err-text break' }, '错误：' + String(item.error)));
      if (notes.length) {
        detail.push(h('ul', { class: 'cell-list' }, notes.map((note) => h('li', { class: 'muted break' }, String(note)))));
      }
      if (item.snapshot_hash) {
        detail.push(h('p', {}, mono('快照 SHA-256：', 'dim'), h('span', { class: 'mono dim', title: String(item.snapshot_hash) }, shortHash(item.snapshot_hash))));
      }
      if (!detail.length) detail.push(mono(DASH, 'dim'));

      return [
        h('div', {}, h('div', {}, textOr(item.name, item.source_id)), mono(item.source_id, 'dim')),
        runStatusBadge(item.status),
        textOr(item.fetched, '0'),
        textOr(item.kept, '0'),
        textOr(item.filtered, '0'),
        textOr(item.events_added, '0'),
        textOr(item.events_updated, '0'),
        textOr(fmtDuration(item.duration_ms)),
        detail
      ];
    });

    setBox(view.result,
      h('h3', { class: 'block-title' }, '逐来源结果', h('span', { class: 'count' }, '抓取 / 保留 / 过滤、备注与错误均如实展示')),
      dataTable([
        { text: '数据源' }, { text: '状态' }, { text: '抓取', cls: 'num' }, { text: '保留', cls: 'num' },
        { text: '过滤', cls: 'num' }, { text: '新增', cls: 'num' }, { text: '更新', cls: 'num' },
        { text: '耗时', cls: 'num' }, { text: '备注与错误' }
      ], rows));
  }

  /* --------------------------------------------------------- 情报事件 */

  /* Display order for the type filter.  Kept here rather than read from the
   * response so the dropdown does not reorder itself between loads. */
  const CATEGORY_ORDER = ['漏洞', '论文', '标准与框架', '政策法规'];

  /* The backend counts the whole matching set, not just the current page, and
   * returns null when that set is too large to count honestly -- in which case
   * the options show bare names rather than a wrong number. */
  function renderCategoryOptions(select, counts) {
    const current = select.value;
    clear(select);
    select.append(h('option', { value: '' }, '全部类型'));
    for (const name of CATEGORY_ORDER) {
      const count = counts && typeof counts[name] === 'number' ? counts[name] : null;
      select.append(h('option', { value: name },
        count === null ? name : name + '（' + count + '）'));
    }
    select.value = current;
  }

  function initEvents() {
    const body = bodyOf('events');
    clear(body);

    const qInput = h('input', { type: 'search', class: 'input', id: 'events-q', placeholder: '事件 ID / 组件 / 关键词，如 CVE-2025-1234', maxlength: '200', 'aria-label': '搜索事件' });
    const statusSelect = h('select', { class: 'select', id: 'events-status', 'aria-label': '按状态筛选' },
      h('option', { value: '' }, '全部状态'),
      h('option', { value: 'confirmed' }, '已确认'),
      h('option', { value: 'needs_review' }, '待复核'),
      h('option', { value: 'withdrawn' }, '已撤回'));
    const categorySelect = h('select', { class: 'select', id: 'events-category', 'aria-label': '按类型筛选' },
      h('option', { value: '' }, '全部类型'),
      ...CATEGORY_ORDER.map((name) => h('option', { value: name }, name)));
    const limitSelect = h('select', { class: 'select', id: 'events-limit', 'aria-label': '返回条数' },
      h('option', { value: '50' }, '50 条'),
      h('option', { value: '100' }, '100 条'),
      h('option', { value: '200' }, '200 条'));
    limitSelect.value = String(state.events.filters.limit);

    const queryForm = h('form', {
      class: 'btn-row query-row',
      onsubmit: (event) => {
        event.preventDefault();
        state.events.filters.q = qInput.value.trim();
        state.events.filters.status = statusSelect.value;
        state.events.filters.category = categorySelect.value;
        state.events.filters.limit = Number(limitSelect.value) || 100;
        loadEvents();
      }
    },
      h('span', { class: 'field', 'aria-label': '关键词' }, qInput),
      statusSelect, categorySelect, limitSelect,
      h('button', { type: 'submit', class: 'btn btn--primary' }, '查询'));

    const enrichBtn = h('button', { type: 'button', class: 'btn', onclick: () => startEnrichment(enrichBtn) }, icon('play'), '执行补证调度（最多 10 条）');
    const refreshBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => { refreshBtn.disabled = true; loadEvents().finally(() => { refreshBtn.disabled = false; }); } }, icon('refresh'), '刷新');
    const enrichResult = h('div');

    const listBox = h('div', { class: 'event-pane' });
    const detailBox = h('div', { class: 'detail-pane' });

    state.dom.events = { list: listBox, detail: detailBox, enrichResult: enrichResult,
                         categorySelect: categorySelect };

    body.append(
      card('检索与调度',
        queryForm,
        h('div', { class: 'btn-row' }, refreshBtn, enrichBtn),
        h('p', { class: 'dim' }, '补证调度会对有证据缺口的事件执行受限检索（NVD / CVE Program / OSV / CISA KEV），受工具调用预算限制并记录停止原因。'),
        enrichResult),
      h('div', { class: 'split' }, listBox, detailBox));

    renderEventDetail();
  }

  async function loadEvents() {
    const view = state.dom.events;
    if (!view) return;
    state.events.loading = true;
    setBox(view.list, loadingBlock('正在加载事件…'));
    const filters = state.events.filters;
    const params = new URLSearchParams();
    if (filters.q) params.set('q', filters.q);
    if (filters.status) params.set('status', filters.status);
    if (filters.category) params.set('category', filters.category);
    params.set('limit', String(filters.limit));
    try {
      const data = await api.get('/api/events?' + params.toString());
      state.events.items = Array.isArray(data.items) ? data.items : [];
      state.events.total = typeof data.total === 'number' ? data.total : state.events.items.length;
      state.events.error = null;
      if (view.categorySelect) renderCategoryOptions(view.categorySelect, data.categories);
    } catch (err) {
      state.events.error = err.message;
      state.events.items = [];
      state.events.total = 0;
    }
    state.events.loading = false;
    renderEventList();
  }

  function renderEventList() {
    const view = state.dom.events;
    if (!view) return;
    if (state.events.error) {
      setBox(view.list, errorBlock(state.events.error, () => loadEvents()));
      return;
    }
    if (!state.events.items.length) {
      const hasFilter = state.events.filters.q || state.events.filters.status || state.events.filters.kind;
      setBox(view.list, hasFilter
        ? emptyState('没有符合当前条件的事件', '可调整关键词或筛选条件后重试。')
        : emptyState('尚未采集到任何事件', '前往「监测采集」执行采集，或先在「总览」初始化演示数据。'));
      return;
    }

    const list = h('ul', { class: 'event-list', role: 'list' });
    for (const item of state.events.items) {
      const gaps = Array.isArray((item.enrichment || {}).gaps) ? item.enrichment.gaps.length : null;
      const button = h('button', {
        type: 'button',
        class: 'event-item',
        'aria-current': state.events.selectedId === item.id ? 'true' : 'false',
        onclick: () => selectEvent(item.id)
      },
        h('div', { class: 'event-item-top' },
          h('span', { class: 'event-item-id' }, textOr(item.id)),
          item.category ? badge(L.categoryClass[item.category] || 'plain', item.category) : null,
          eventStatusBadge(item.status),
          item.severity ? badge(String(item.severity), labelOf(L.severity, item.severity)) : null,
          item.withdrawn ? badge('withdrawn', '已撤回') : null),
        h('div', { class: 'event-item-title' }, textOr(item.title, '（无标题）')),
        h('div', { class: 'event-item-meta' },
          h('span', {}, '组件：' + textOr(item.component, '未知')),
          h('span', {}, '发布：' + textOr(fmtTime(item.published_at), '未记录')),
          h('span', {}, gaps === null ? '证据缺口：未评估' : `证据缺口：${gaps} 个`)));
      list.appendChild(h('li', {}, button));
    }

    setBox(view.list,
      h('h3', { class: 'block-title' }, '事件列表',
        h('span', { class: 'count' }, `共 ${state.events.total} 条，显示 ${state.events.items.length} 条`)),
      list);
  }

  async function selectEvent(eventId) {
    if (state.events.selectedId === eventId && state.events.detail) return;
    state.events.selectedId = eventId;
    state.events.detail = null;
    state.events.detailError = null;
    state.events.detailLoading = true;
    renderEventList();
    renderEventDetail();
    try {
      const data = await api.get('/api/events/' + encodeURIComponent(eventId));
      if (state.events.selectedId !== eventId) return;
      state.events.detail = data;
    } catch (err) {
      if (state.events.selectedId !== eventId) return;
      state.events.detailError = err.message;
    }
    state.events.detailLoading = false;
    renderEventDetail();
  }

  function severityBadge(value) {
    if (!value) return badge('unknown', '来源未给出严重性');
    return badge(String(value), labelOf(L.severity, value));
  }

  function renderEventDetail() {
    const view = state.dom.events;
    if (!view) return;

    if (!state.events.selectedId) {
      setBox(view.detail, emptyState('未选择事件', '点击左侧任意事件查看摘要、受影响范围、证据缺口、流水线轨迹与研判结论。'));
      return;
    }
    if (state.events.detailLoading) {
      setBox(view.detail, loadingBlock('正在加载事件详情…'));
      return;
    }
    if (state.events.detailError) {
      setBox(view.detail, errorBlock(state.events.detailError, () => { state.events.detail = null; selectEvent(state.events.selectedId); }));
      return;
    }
    const event = state.events.detail;
    if (!event) return;

    const blocks = [];

    const assessments = Array.isArray(event.assessments) ? event.assessments : [];
    const affectedAssets = assessments.filter((item) => item.status === 'affected');
    const pendingAssets = assessments.filter((item) => item.status === 'needs_confirmation');
    const gapsNow = Array.isArray((event.enrichment || {}).gaps) ? event.enrichment.gaps : [];
    const actionText = event.withdrawn ? '停止使用当前结论，核对替代公告'
      : affectedAssets.length ? '优先核对修复版本并安排受影响资产升级'
        : pendingAssets.length ? '先补齐资产版本或关键配置，再决定是否升级'
          : '持续监测来源更新，当前无需紧急处置';
    blocks.push(h('section', { class: 'risk-conclusion', 'aria-label': '风险结论' },
      h('div', { class: 'risk-conclusion-main' },
        h('span', { class: 'eyebrow' }, '研判结论'),
        h('h3', {}, actionText),
        h('p', {}, `已关联 ${assessments.length} 条资产结论，其中受影响 ${affectedAssets.length} 条、待确认 ${pendingAssets.length} 条。`)),
      h('div', { class: 'risk-conclusion-facts' },
        h('div', {}, h('span', {}, '建议动作'), h('strong', {}, actionText)),
        h('div', {}, h('span', {}, '证据状态'), h('strong', {}, gapsNow.length ? `仍有 ${gapsNow.length} 项缺口` : '当前证据完整')))));

    /* 头部 */
    const meta = kvList([
      ['事件 ID', mono(textOr(event.id))],
      ['类型', event.category ? event.category : DASH],
      ['组件 / 生态', `${textOr(event.component, '未知')} / ${textOr(event.ecosystem, '未知')}`],
      ['发布时间', textOr(fmtTime(event.published_at), '未记录')],
      ['修改时间', textOr(fmtTime(event.modified_at), '未记录')],
      ['采集时间', textOr(fmtTime(event.collected_at), '未记录')],
      ['内容哈希', mono(textOr(event.content_hash), 'dim')]
    ]);
    blocks.push(h('div', { class: 'detail-head' },
      h('div', { class: 'event-item-top' },
        event.category ? badge(L.categoryClass[event.category] || 'plain', event.category) : null,
        eventStatusBadge(event.status),
        severityBadge(event.severity),
        event.withdrawn ? badge('withdrawn', '已撤回') : null),
      h('h3', { class: 'detail-title' }, textOr(event.title, '（无标题）')),
      h('p', { class: 'excerpt' }, textOr(event.summary, '来源未提供摘要。')),
      meta));

    if (event.withdrawn || event.status === 'withdrawn') {
      blocks.push(alertBox('warn', '事件已撤回',
        h('p', {}, '来源标注为撤回或失效：本事件的结论不得作为当前有效的影响判断依据，需核对替代公告。')));
    }

    /* 撤销的替代公告？来源间冲突（显著位置） */
    const conflicts = Array.isArray(event.conflicts) ? event.conflicts : [];
    if (conflicts.length) {
      blocks.push(alertBox('warn', `来源间冲突（${conflicts.length} 处，系统未做取舍，并列保留）`,
        dataTable([{ text: '字段' }, { text: '对象' }, { text: '并列取值' }, { text: '备注' }],
          conflicts.map((conflict) => [
            mono(textOr(conflict.field)),
            textOr(conflict.package),
            h('div', { class: 'chips' }, (Array.isArray(conflict.values) ? conflict.values : []).map((value) => h('span', { class: 'chip' }, String(value)))),
            textOr(conflict.note)
          ]))));
    }

    /* 受影响范围 */
    const affected = Array.isArray(event.affected) ? event.affected : [];
    blocks.push(sectionBlock('受影响版本范围', affected.length
      ? dataTable([{ text: '包' }, { text: '生态' }, { text: '影响区间' }, { text: '修复版本' }, { text: '来源 ID' }],
        affected.map((entry) => [
          textOr(entry.package),
          textOr(entry.ecosystem),
          mono(textOr(entry.range)),
          entry.fixed_version ? mono(entry.fixed_version) : mono('未提供修复版本', 'dim'),
          mono(entry.source_id ? (Array.isArray(entry.source_ids) && entry.source_ids.length > 1
            ? entry.source_ids.join('、') : entry.source_id) : DASH, 'dim')
        ]))
      : emptyState('来源未提供可解析的受影响版本区间', '区间无法可靠解析时系统不会猜测。')));

    /* 触发条件 */
    const conditions = Array.isArray(event.conditions) ? event.conditions : [];
    blocks.push(sectionBlock('触发条件', conditions.length
      ? dataTable([{ text: '配置项' }, { text: '期望值' }, { text: '说明' }, { text: '来源 ID' }],
        conditions.map((entry) => [
          conditionLabel(entry.name),
          mono(entry.value === null || entry.value === undefined ? DASH : String(entry.value)),
          textOr(entry.description),
          mono(textOr(entry.source_id), 'dim')
        ]))
      : emptyState('来源未给出触发条件')));

    /* CVSS 与 CWE */
    const cvss = Array.isArray(event.cvss) ? event.cvss : [];
    const cwes = Array.isArray(event.cwes) ? event.cwes : [];
    blocks.push(sectionBlock('严重性 / CVSS', cvss.length
      ? dataTable([{ text: '版本' }, { text: '得分' }, { text: '向量' }, { text: '来源 ID' }],
        cvss.map((entry) => {
          let scoreCell;
          if (entry.score === null || entry.score === undefined) {
            scoreCell = h('span', { class: 'muted' }, entry.vector ? '仅有向量，来源未给出数值' : '来源未给出数值');
          } else {
            scoreCell = mono(String(entry.score));
          }
          return [
            mono(textOr(entry.version)),
            scoreCell,
            entry.vector ? mono(entry.vector, 'break') : mono(DASH, 'dim'),
            mono(textOr(entry.source_id), 'dim')
          ];
        }))
      : emptyState('来源未给出 CVSS 记录'),
      cwes.length ? h('div', { class: 'chips' }, cwes.map((cwe) => h('span', { class: 'chip' }, String(cwe)))) : null));

    /* KEV / 在野利用提示（poc 维度）在富化里体现 */
    const enrichment = event.enrichment || {};
    const dimensions = Array.isArray(enrichment.dimensions) ? enrichment.dimensions : [];
    const gaps = Array.isArray(enrichment.gaps) ? enrichment.gaps : [];
    blocks.push(sectionBlock('证据完整度（富化维度）',
      dimensions.length
        ? dataTable([{ text: '维度' }, { text: '状态' }, { text: '证据 ID' }, { text: '明细' }],
          dimensions.map((dim) => [
            labelOf(L.dimension, dim.name) || textOr(dim.name),
            dim.status === 'present' ? badge('ok', '已具备') : badge('needs-confirmation', '缺失'),
            Array.isArray(dim.evidence_ids) && dim.evidence_ids.length
              ? h('div', { class: 'chips' }, dim.evidence_ids.map((id) => h('span', { class: 'chip' }, String(id))))
              : mono(DASH, 'dim'),
            textOr(dim.detail)
          ]))
        : emptyState('尚未执行富化评估', '可在上方点击「执行补证调度」生成证据缺口报告。'),
      gaps.length
        ? alertBox('warn', `证据缺口（${gaps.length} 个，缺失不等于不存在）`,
          h('ul', { class: 'cell-list' }, gaps.map((gap) => h('li', {}, String(gap)))))
        : (dimensions.length ? alertBox('info', '未报告证据缺口', h('p', {}, '当前快照中未发现缺口维度。')) : null)));

    /* 流水线轨迹 */
    const pipeline = event.pipeline || {};
    const history = Array.isArray(pipeline.history) ? pipeline.history : [];
    const schedulerTrace = Array.isArray(pipeline.scheduler_trace) ? pipeline.scheduler_trace : [];
    blocks.push(h('details', { class: 'advanced-card' }, h('summary', {}, '高级信息：处理轨迹与调度明细'), sectionBlock('处理轨迹',
      kvList([
        ['当前状态', badge('plain', textOr(pipeline.state))],
        ['工具调用次数', textOr(pipeline.tool_calls, '0')],
        ['停止原因', textOr(pipeline.stop_reason, '未记录')]
      ]),
      history.length
        ? h('ul', { class: 'timeline' }, history.map((step) => h('li', {},
          h('span', { class: 'tl-role' }, labelOf(L.role, step.role) || textOr(step.role)),
          h('span', {}, textOr(step.note)),
          h('span', { class: 'tl-at' }, textOr(fmtTime(step.at), '时间未记录')))))
        : null,
      schedulerTrace.length
        ? h('details', { class: 'raw' },
          h('summary', {}, `补证调度轨迹（${schedulerTrace.length} 条）`),
          dataTable([{ text: '轮次', cls: 'num' }, { text: '工具' }, { text: '动作' }, { text: '结果' }, { text: '新增', cls: 'num' }, { text: '耗时', cls: 'num' }],
            schedulerTrace.map((step) => [
              textOr(step.round, '1'),
              mono(textOr(step.tool)),
              textOr(step.action),
              textOr(step.result),
              textOr(step.found, '0'),
              textOr(fmtDuration(step.duration_ms))
            ])))
        : null)));

    /* 研判结论 */
    blocks.push(sectionBlock('本事件的研判结论', assessments.length
      ? dataTable([{ text: '资产 ID' }, { text: '状态' }, { text: '优先级' }, { text: '判定理由' }],
        assessments.map((item) => [
          mono(textOr(item.asset_id)),
          assessStatusBadge(item.status),
          priorityBadge(item.priority),
          Array.isArray(item.reasons) && item.reasons.length
            ? h('ul', { class: 'cell-list' }, item.reasons.map((reason) => h('li', {}, humanizeReason(reason))))
            : mono(DASH, 'dim')
        ]))
      : emptyState('尚未对该事件生成研判结论', '可在「研判结论」面板执行研判（需先录入资产）。')));

    /* 引用来源（证据） */
    const sources = Array.isArray(event.sources) ? event.sources : [];
    blocks.push(sectionBlock('引用来源（证据）', sources.length
      ? sources.map((source) => h('div', { class: 'citation' },
        h('div', { class: 'citation-head' },
          badge('plain', textOr(source.trust ? (labelOf(L.trust, source.trust) || source.trust) : '未标注')),
          mono(textOr(source.id), 'dim')),
        h('div', { class: 'citation-title' }, textOr(source.title, '（无标题）')),
        h('p', { class: 'muted' }, `发布者：${textOr(source.publisher, '未标注')} · 类型：${textOr(source.source_type, '未标注')} · 采集：${textOr(fmtTime(source.collected_at), '未记录')}`),
        h('p', { class: 'excerpt' }, textOr(source.excerpt, '来源未提供摘录。')),
        h('p', {}, safeLink(source.url, '来源链接')),
        source.content_hash ? h('p', {}, mono('内容哈希：', 'dim'), h('span', { class: 'mono dim', title: String(source.content_hash) }, shortHash(source.content_hash))) : null))
      : emptyState('事件没有附带来源记录')));

    /* POC */
    const poc = Array.isArray(event.poc) ? event.poc : [];
    blocks.push(sectionBlock('POC 资料（仅记录，不执行）', poc.length
      ? dataTable([{ text: '链接' }, { text: '状态' }, { text: '说明' }, { text: '来源 ID' }],
        poc.map((entry) => [
          safeLink(entry.url, '查看链接'),
          mono(textOr(entry.status)),
          textOr(entry.reason),
          mono(textOr(entry.source_id), 'dim')
        ]))
      : alertBox('info', '未收录 POC 资料', h('p', {}, '未收录不等同于不存在：本地来源中没有对应的 POC 记录。'))));

    /* 关系 */
    const relationships = Array.isArray(event.relationships) ? event.relationships : [];
    if (relationships.length) {
      blocks.push(sectionBlock('有来源的关系 / 攻击链',
        dataTable([{ text: '主体' }, { text: '关系' }, { text: '客体' }, { text: '证据 ID' }],
          relationships.map((relation) => [
            textOr(relation.subject),
            mono(textOr(relation.predicate)),
            textOr(relation.object),
            Array.isArray(relation.evidence_ids) && relation.evidence_ids.length
              ? h('div', { class: 'chips' }, relation.evidence_ids.map((id) => h('span', { class: 'chip' }, String(id))))
              : mono(DASH, 'dim')
          ]))));
    }

    /* 别名 / 标签 / AI 相关性 */
    const aliases = Array.isArray(event.aliases) ? event.aliases : [];
    const tags = Array.isArray(event.tags) ? event.tags : [];
    const aiRelevance = event.ai_relevance || {};
    blocks.push(sectionBlock('标识与分类',
      kvList([
        ['别名', aliases.length ? h('div', { class: 'chips' }, aliases.map((alias) => h('span', { class: 'chip' }, String(alias)))) : DASH],
        ['标签', tags.length ? h('div', { class: 'chips' }, tags.map((tag) => h('span', { class: 'chip' }, String(tag)))) : DASH],
        ['AI 相关性', aiRelevance.included === false ? badge('neutral', '未纳入') : badge('accent', '纳入'),
          h('span', { class: 'muted' }, ' ' + textOr(aiRelevance.reason, ''))]
      ])));

    setBox(view.detail, card(null, ...blocks));
  }

  async function startEnrichment(button) {
    if (state.enrich.running) return;
    state.enrich.running = true;
    state.enrich.result = null;
    state.enrich.error = null;
    button.disabled = true;
    const elapsedSpan = h('span', { class: 'mono elapsed' });
    setBox(state.dom.events.enrichResult, loadingBlock('正在执行补证调度（可能触发外网检索）…'));
    const stopTimer = beginElapsed(elapsedSpan);
    state.dom.events.enrichResult.appendChild(elapsedSpan);
    try {
      const result = await api.post('/api/enrichment/run?limit=10');
      state.enrich.result = result;
      setBox(state.dom.events.enrichResult, kvList([
        ['运行 ID', mono(textOr(result.run_id))],
        ['处理事件数', textOr(result.events, '0')],
        ['缺口减少事件数', textOr(result.gaps_closed, '0')],
        ['工具调用次数', textOr(result.tool_calls, '0')],
        ['耗时', textOr(fmtDuration(result.duration_ms))]
      ]));
      toast(`富化完成：处理 ${result.events} 条，${result.gaps_closed} 条缺口减少`);
      await Promise.all([loadEvents(), refreshDashboardQuiet()]);
    } catch (err) {
      state.enrich.error = err.message;
      setBox(state.dom.events.enrichResult, errorBlock(err.message));
      toast(err.message, 'error');
    } finally {
      stopTimer();
      state.enrich.running = false;
      button.disabled = false;
    }
  }

  /* ------------------------------------------------------------- 资产 */

  function initAssets() {
    const body = bodyOf('assets');
    clear(body);

    const demoBtn = h('button', { type: 'button', class: 'btn', onclick: () => createDemoAssets(demoBtn, demoResult) }, icon('plus'), '生成合成演示资产');
    const refreshBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => { refreshBtn.disabled = true; loadAssets().finally(() => { refreshBtn.disabled = false; }); } }, icon('refresh'), '刷新');
    const demoResult = h('div');
    const tableBox = h('div');

    const nameInput = h('input', { class: 'input', id: 'asset-name', maxlength: '200', placeholder: '例如：推理服务 A', 'aria-label': '资产名称' });
    const componentInput = h('input', { class: 'input', id: 'asset-component', maxlength: '200', placeholder: '例如：Ollama', 'aria-label': '组件' });
    const ecosystemInput = h('input', { class: 'input', id: 'asset-ecosystem', maxlength: '120', placeholder: '例如：PyPI / Go', 'aria-label': '生态' });
    const versionInput = h('input', { class: 'input mono', id: 'asset-version', maxlength: '120', placeholder: '例如：0.16.0', 'aria-label': '版本' });
    const exposureSelect = h('select', { class: 'select', id: 'asset-exposure', 'aria-label': '暴露面' },
      h('option', { value: 'unknown' }, '未知'),
      h('option', { value: 'public' }, '公网'),
      h('option', { value: 'internal' }, '内网'));
    const criticalitySelect = h('select', { class: 'select', id: 'asset-criticality', 'aria-label': '业务重要性' },
      h('option', { value: 'medium' }, '中'),
      h('option', { value: 'high' }, '高'),
      h('option', { value: 'low' }, '低'));
    const authorizedCheck = h('input', { type: 'checkbox', id: 'asset-authorized' });
    authorizedCheck.checked = true;
    const conditionsInput = h('textarea', { class: 'textarea mono', id: 'asset-conditions', rows: '3', placeholder: '{ "remote_api": true }', 'aria-label': '触发条件 JSON' });
    const formError = h('p', { class: 'field-error', role: 'alert' });
    const formResult = h('div');

    const submitBtn = h('button', { type: 'submit', class: 'btn btn--primary' }, icon('plus'), '添加资产');
    const form = h('form', {
      onsubmit: (event) => {
        event.preventDefault();
        submitAsset(submitBtn, formError, formResult);
      }
    },
      h('div', { class: 'form-grid' },
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '名称', h('span', { class: 'req' }, '*')), nameInput),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '组件', h('span', { class: 'req' }, '*')), componentInput),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '生态'), ecosystemInput),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '版本'), versionInput),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '暴露面'), exposureSelect),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '业务重要性'), criticalitySelect),
        h('label', { class: 'field span-2' }, h('span', { class: 'field-label' }, '触发条件（JSON 对象，可留空）'), conditionsInput)),
      h('div', { class: 'form-actions' },
        h('label', { class: 'check' }, authorizedCheck, h('span', {}, '已在授权范围内（未授权的资产系统不作影响判断）')),
        h('span', { class: 'spacer' }),
        submitBtn),
      formError,
      formResult);

    state.dom.assets = { table: tableBox, demoResult: demoResult };

    body.append(
      card('资产清单',
        h('div', { class: 'btn-row' }, refreshBtn, demoBtn),
        h('p', { class: 'dim' }, '演示资产为合成数据，全部带 is_demo 标记，不代表任何真实公网资产。'),
        demoResult,
        tableBox),
      card('新增单个资产', form));

    renderAssets();
  }

  async function loadAssets() {
    const view = state.dom.assets;
    if (!view) return;
    state.assets.loading = true;
    setBox(view.table, loadingBlock('正在加载资产…'));
    try {
      const data = await api.get('/api/assets');
      state.assets.items = Array.isArray(data.items) ? data.items : [];
      state.assets.error = null;
    } catch (err) {
      state.assets.error = err.message;
      state.assets.items = [];
    }
    state.assets.loading = false;
    renderAssets();
  }

  function renderAssets() {
    const view = state.dom.assets;
    if (!view) return;
    if (state.assets.error) {
      setBox(view.table, errorBlock(state.assets.error, () => loadAssets()));
      return;
    }
    const items = state.assets.items;
    if (!items.length) {
      setBox(view.table, emptyState('尚未录入任何资产', '可在下方表单添加单个资产，或点击「生成合成演示资产」创建 5 条带 is_demo 标记的演示数据。'));
      return;
    }

    const rows = items.map((asset) => {
      const deleteBtn = h('button', {
        type: 'button',
        class: 'btn btn--sm btn--danger',
        'aria-label': `删除资产：${textOr(asset.name, asset.id)}`,
        onclick: () => deleteAsset(asset, deleteBtn)
      }, icon('trash'), '删除');

      const conditions = asset.conditions && typeof asset.conditions === 'object' ? Object.keys(asset.conditions) : [];
      return [
        h('div', {},
          h('div', {}, textOr(asset.name, '（未命名）')),
          mono(textOr(asset.id), 'dim')),
        textOr(asset.component),
        mono(textOr(asset.version, DASH)),
        textOr(asset.ecosystem, DASH),
        badge(asset.exposure === 'public' ? 'high' : 'neutral', labelOf(L.exposure, asset.exposure) || textOr(asset.exposure)),
        badge(asset.business_criticality === 'high' ? 'critical' : (asset.business_criticality === 'low' ? 'low' : 'medium'), labelOf(L.criticality, asset.business_criticality) || DASH),
        asset.authorized === false ? badge('affected', '未授权') : badge('ok', '在授权范围'),
        asset.is_demo ? badge('demo', '合成演示 is_demo') : badge('plain', '用户录入'),
        conditions.length
          ? h('div', { class: 'chips' }, conditions.map((name) => h('span', { class: 'chip' }, name)))
          : mono(DASH, 'dim'),
        timeCell(asset.updated_at),
        deleteBtn
      ];
    });

    setBox(view.table,
      h('h3', { class: 'block-title' }, '资产列表', h('span', { class: 'count' }, `共 ${items.length} 条`)),
      dataTable([
        { text: '名称 / ID' }, { text: '组件' }, { text: '版本' }, { text: '生态' }, { text: '暴露面' },
        { text: '业务重要性' }, { text: '授权' }, { text: '来源类型' }, { text: '已声明的条件' },
        { text: '更新时间' }, { text: '操作' }
      ], rows));
  }

  async function deleteAsset(asset, button) {
    if (!window.confirm(`确认删除资产「${textOr(asset.name, asset.id)}」？与它相关的研判结论会一并删除。`)) return;
    button.disabled = true;
    try {
      const result = await api.del('/api/assets/' + encodeURIComponent(asset.id));
      if (result.deleted) {
        toast('已删除资产：' + textOr(asset.name, asset.id));
      } else {
        toast('后端未找到该资产，未发生删除', 'warn');
      }
      await Promise.all([loadAssets(), refreshDashboardQuiet()]);
    } catch (err) {
      toast(err.message, 'error');
      button.disabled = false;
    }
  }

  async function createDemoAssets(button, resultBox) {
    button.disabled = true;
    setBox(resultBox, loadingBlock('正在生成合成演示资产…'));
    try {
      const result = await api.post('/api/assets/demo');
      const parts = [kvList([['创建条数', textOr(result.created, '0')]])];
      if (result.notice) parts.push(h('p', { class: 'note-verbatim' }, String(result.notice)));
      setBox(resultBox, ...parts);
      toast(`已生成 ${textOr(result.created, '0')} 条合成演示资产（is_demo=true）`);
      await Promise.all([loadAssets(), refreshDashboardQuiet()]);
    } catch (err) {
      setBox(resultBox, errorBlock(err.message));
      toast(err.message, 'error');
    } finally {
      button.disabled = false;
    }
  }

  async function submitAsset(button, errorBox, resultBox) {
    const name = document.getElementById('asset-name').value.trim();
    const component = document.getElementById('asset-component').value.trim();
    const ecosystem = document.getElementById('asset-ecosystem').value.trim();
    const version = document.getElementById('asset-version').value.trim();
    const exposure = document.getElementById('asset-exposure').value;
    const criticality = document.getElementById('asset-criticality').value;
    const authorized = document.getElementById('asset-authorized').checked;
    const conditionsRaw = document.getElementById('asset-conditions').value.trim();

    errorBox.textContent = '';
    if (!name || !component) {
      errorBox.textContent = '名称与组件为必填项。';
      return;
    }
    let conditions = {};
    if (conditionsRaw) {
      try {
        conditions = JSON.parse(conditionsRaw);
      } catch (err) {
        errorBox.textContent = '触发条件不是合法 JSON：' + err.message;
        return;
      }
      if (conditions === null || typeof conditions !== 'object' || Array.isArray(conditions)) {
        errorBox.textContent = '触发条件必须是 JSON 对象，例如 {"remote_api": true}。';
        return;
      }
    }

    button.disabled = true;
    setBox(resultBox, loadingBlock('正在提交…'));
    try {
      const created = await api.post('/api/assets', {
        name: name,
        component: component,
        ecosystem: ecosystem,
        version: version || null,
        exposure: exposure,
        business_criticality: criticality,
        conditions: conditions,
        authorized: authorized
      });
      setBox(resultBox, kvList([['已创建资产 ID', mono(textOr(created.id))]]));
      toast('资产已创建：' + textOr(created.name, created.id));
      ['asset-name', 'asset-component', 'asset-ecosystem', 'asset-version'].forEach((id) => { document.getElementById(id).value = ''; });
      document.getElementById('asset-conditions').value = '';
      await Promise.all([loadAssets(), refreshDashboardQuiet()]);
    } catch (err) {
      setBox(resultBox, errorBlock(err.message));
      toast(err.message, 'error');
    } finally {
      button.disabled = false;
    }
  }

  /* --------------------------------------------------------- 研判结论 */

  function initAssessments() {
    const body = bodyOf('assessments');
    clear(body);

    const runBtn = h('button', { type: 'button', class: 'btn btn--primary', onclick: () => runAssessments(runBtn) }, icon('play'), '重新执行研判');
    const refreshBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => { refreshBtn.disabled = true; loadAssessments().finally(() => { refreshBtn.disabled = false; }); } }, icon('refresh'), '刷新');
    const filterSelect = h('select', { class: 'select', 'aria-label': '按状态筛选研判结论', onchange: () => { state.assessments.filter = filterSelect.value; renderAssessments(); } },
      h('option', { value: '' }, '全部状态'),
      h('option', { value: 'affected' }, '受影响'),
      h('option', { value: 'needs_confirmation' }, '待确认'),
      h('option', { value: 'not_affected' }, '不受影响'),
      h('option', { value: 'not_applicable' }, '不适用'));

    const runResult = h('div');
    const statsBox = h('div');
    const tableBox = h('div');

    state.dom.assessments = { table: tableBox, stats: statsBox, runResult: runResult };

    body.append(
      card('研判控制',
        h('div', { class: 'btn-row' }, runBtn, refreshBtn, filterSelect),
        h('p', { class: 'dim' }, '对全部事件与全部资产执行影响判断；未标记授权的资产会被记录为“不适用”而非静默跳过。'),
        runResult),
      statsBox,
      tableBox);

    renderAssessments();
  }

  async function loadAssessments() {
    const view = state.dom.assessments;
    if (!view) return;
    setBox(view.table, loadingBlock('正在加载研判结论…'));
    try {
      const data = await api.get('/api/assessments?limit=200');
      state.assessments.items = Array.isArray(data.items) ? data.items : [];
      state.assessments.error = null;
    } catch (err) {
      state.assessments.error = err.message;
      state.assessments.items = [];
    }
    renderAssessments();
  }

  function renderAssessments() {
    const view = state.dom.assessments;
    if (!view) return;

    if (state.assessments.error) {
      setBox(view.stats);
      setBox(view.table, errorBlock(state.assessments.error, () => loadAssessments()));
      return;
    }

    const items = state.assessments.items;
    const counts = { affected: 0, needs_confirmation: 0, not_affected: 0, not_applicable: 0 };
    for (const item of items) {
      if (Object.prototype.hasOwnProperty.call(counts, item.status)) counts[item.status] += 1;
    }
    setBox(view.stats, h('div', { class: 'chips' },
      h('span', { class: 'chip' }, `共 ${items.length} 条`),
      badge('affected', `受影响 ${counts.affected}`),
      badge('needs-confirmation', `待确认 ${counts.needs_confirmation}`),
      badge('not-affected', `不受影响 ${counts.not_affected}`),
      badge('not-applicable', `不适用 ${counts.not_applicable}`)),
      resultLegend());

    const filtered = state.assessments.filter
      ? items.filter((item) => item.status === state.assessments.filter)
      : items;

    if (!filtered.length) {
      setBox(view.table, items.length
        ? emptyState('当前筛选条件下没有结论', '切换状态筛选查看其他结论。')
        : countValue(((state.dashboard || {}).counts || {}).assets) === 0
          ? emptyState('还不能开始研判', '资产清单为空。请先添加你的组件和版本，或在顶部点击“一键体验完整流程”。')
          : emptyState('尚无研判结论', '点击「重新执行研判」对全部事件与资产执行影响判断。'));
      return;
    }

    const rows = filtered.map((item) => [
      h('div', {}, h('div', {}, textOr(item.event_title, '（无标题）')), mono(textOr(item.event_id), 'dim')),
      h('div', {}, h('div', {}, textOr(item.asset_name, '（未知资产）')), mono(textOr(item.asset_id), 'dim')),
      assessStatusBadge(item.status),
      priorityBadge(item.priority),
      Array.isArray(item.reasons) && item.reasons.length
        ? h('ul', { class: 'cell-list' }, item.reasons.map((reason) => h('li', {}, humanizeReason(reason))))
        : mono(DASH, 'dim'),
      Array.isArray(item.evidence_ids) && item.evidence_ids.length
        ? h('div', { class: 'chips' }, item.evidence_ids.map((id) => h('span', { class: 'chip' }, String(id))))
        : mono(DASH, 'dim')
    ]);

    setBox(view.table,
      h('h3', { class: 'block-title' }, '研判结论', h('span', { class: 'count' }, `显示 ${filtered.length} / ${items.length} 条`)),
      dataTable([
        { text: '事件' }, { text: '资产' }, { text: '状态' }, { text: '优先级' },
        { text: '判定理由' }, { text: '证据 ID' }
      ], rows));
  }

  async function runAssessments(button) {
    if (state.assessments.running) return;
    const dashCounts = (state.dashboard || {}).counts || {};
    if (countValue(dashCounts.assets) === 0) {
      setBox(state.dom.assessments.runResult, alertBox('warn', '需要先添加资产',
        h('p', {}, '系统不能凭公开漏洞猜哪些系统属于你。请先录入资产，或使用合成演示资产。')));
      openInlineModule('assets');
      return;
    }
    if (countValue(dashCounts.events) === 0) {
      setBox(state.dom.assessments.runResult, alertBox('warn', '还没有可研判的情报',
        h('p', {}, '请先采集来源或载入演示案例，再执行影响研判。')));
      openInlineModule('sources');
      return;
    }
    state.assessments.running = true;
    button.disabled = true;
    setBox(state.dom.assessments.runResult, loadingBlock('正在执行研判…'));
    try {
      const result = await api.post('/api/assessments/run');
      setBox(state.dom.assessments.runResult, kvList([
        ['运行 ID', mono(textOr(result.run_id))],
        ['事件数', textOr(result.events, '0')],
        ['资产数', textOr(result.assets, '0')],
        ['生成结论', textOr(result.assessments, '0')],
        ['其中不适用（未授权）', textOr(result.not_applicable, '0')],
        ['耗时', textOr(fmtDuration(result.duration_ms))]
      ]));
      toast(`研判完成：生成 ${result.assessments} 条结论`);
      await Promise.all([loadAssessments(), refreshDashboardQuiet()]);
    } catch (err) {
      setBox(state.dom.assessments.runResult, errorBlock(err.message));
      toast(err.message, 'error');
    } finally {
      state.assessments.running = false;
      button.disabled = false;
    }
  }

  /* ------------------------------------------------------------- 问答 */

  /* --------------------------------------------------------------- 提问 */

  function uniqueContextItems(items) {
    const seen = new Set();
    return items.filter((item) => {
      const key = String(item && (item.id || item.chunk_id || item.title) || '');
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function contextFocusList(items, emptyText) {
    return items.length
      ? h('div', { class: 'chips' }, ...items.slice(0, 8).map((item) => h('span', {
        class: 'chip', title: textOr(item.title, item.id)
      }, textOr(item.id, item.title))))
      : h('span', { class: 'muted' }, emptyText);
  }

  function renderChatContext() {
    const view = state.dom.chat;
    if (!view || !view.context) return;
    const context = state.chat.context;
    const turnCount = state.chat.history.filter((item) => item.role === 'user').length;
    setBox(view.context,
      h('div', { class: 'context-snapshot-head' },
        h('div', {}, badge('accent', '当前线程'), mono(context.threadId),
          h('span', { class: 'muted' }, `上下文段 ${context.segment} · ${turnCount} 轮问答`)),
        h('span', { class: 'muted' }, '只读快照 · 由实际问答结果更新')),
      h('div', { class: 'context-focus-grid' },
        h('div', { class: 'context-focus' }, h('span', { class: 'context-focus-label' }, '焦点事件'),
          contextFocusList(context.events, '尚未确定')),
        h('div', { class: 'context-focus' }, h('span', { class: 'context-focus-label' }, '焦点资产'),
          contextFocusList(context.assets, '尚未确定')),
        h('div', { class: 'context-focus' }, h('span', { class: 'context-focus-label' }, '焦点文档'),
          contextFocusList(context.documents, '尚未确定')),
        h('div', { class: 'context-focus' }, h('span', { class: 'context-focus-label' }, '本轮实际使用块'),
          contextFocusList(context.chunks, context.chunks.length ? '' : '后端尚未返回块级上下文'))),
      h('details', { class: 'context-constraints' },
        h('summary', {}, `继承约束（${context.inheritedConstraints.length}）`),
        h('ul', { class: 'cell-list' }, ...context.inheritedConstraints.map((item) => h('li', {}, item)))));

    if (!view.confirmation) return;
    const pending = state.chat.confirmation;
    setBox(view.confirmation, pending ? alertBox('warn', pending.type === 'switch' ? '检测到话题切换' : '指代可能有歧义',
      h('p', {}, pending.message),
      h('p', { class: 'muted' }, '待发送：', h('strong', {}, pending.question)),
      h('div', { class: 'btn-row context-confirm-actions' },
        h('button', { type: 'button', class: 'btn btn--sm btn--primary', onclick: () => confirmContextQuestion() },
          pending.type === 'switch' ? '新建上下文段并发送' : '确认指代并发送'),
        h('button', { type: 'button', class: 'btn btn--sm btn--ghost', onclick: () => cancelContextQuestion() }, '返回补充问题'))) : null);
  }

  function questionContextWarning(question) {
    const context = state.chat.context;
    const ids = Array.from(new Set((String(question).match(/CVE-\d{4}-\d{4,}/gi) || []).map((id) => id.toUpperCase())));
    const focused = new Set(context.events.map((item) => String(item.id).toUpperCase()));
    if (focused.size && ids.length && ids.every((id) => !focused.has(id))) {
      return { type: 'switch', message: `问题中的 ${ids.join('、')} 与当前焦点事件不同。确认后将开启新的上下文段，不把上一话题的历史消息传给后端。` };
    }
    const ambiguous = /(前者|后者|其中一个|那一个|上一个)/.test(question) ||
      (/(它|这个漏洞|该漏洞|这个资产|该资产|这篇|该文档)/.test(question) &&
        (context.events.length + context.assets.length + context.documents.length !== 1));
    if (ambiguous) {
      return { type: 'ambiguous', message: '问题包含指代词，但当前焦点为空或存在多个候选。请确认你接受按当前上下文解析，或返回补充明确编号。' };
    }
    return null;
  }

  function resetChatContextSegment() {
    const context = state.chat.context;
    context.segment += 1;
    context.events = [];
    context.assets = [];
    context.documents = [];
    context.chunks = [];
    context.snapshot = null;
    state.chat.history = [];
  }

  function confirmContextQuestion() {
    const pending = state.chat.confirmation;
    if (!pending) return;
    if (pending.type === 'switch') resetChatContextSegment();
    state.chat.confirmation = null;
    renderChatContext();
    sendQuestion(true);
  }

  function cancelContextQuestion() {
    state.chat.confirmation = null;
    renderChatContext();
    if (state.dom.chat && state.dom.chat.input) state.dom.chat.input.focus();
  }

  function updateChatContext(data) {
    const context = state.chat.context;
    const snapshot = data && data.context_snapshot && typeof data.context_snapshot === 'object'
      ? data.context_snapshot : {};
    context.snapshot = snapshot;
    if (data && data.thread_id) context.threadId = String(data.thread_id);
    const eventIds = arrayOr(snapshot.selected_event_ids).length ? arrayOr(snapshot.selected_event_ids) : arrayOr(data && data.related_event_ids);
    context.events = uniqueContextItems(eventIds.map((item) => typeof item === 'object' ? item : { id: item }));
    const assessments = arrayOr(data && data.assessments);
    const assets = arrayOr(snapshot.selected_asset_ids).length ? arrayOr(snapshot.selected_asset_ids)
      : assessments.map((item) => ({ id: item.asset_id, title: item.asset_name }));
    context.assets = uniqueContextItems(assets);
    const citations = [...arrayOr(data && data.citations), ...arrayOr(data && data.document_citations)];
    const documents = arrayOr(snapshot.selected_document_ids).length ? arrayOr(snapshot.selected_document_ids)
      : citations.map((item) => ({ id: item.document_id || item.id, title: item.title }));
    context.documents = uniqueContextItems(documents);
    context.chunks = uniqueContextItems(answerContextChunks(data).map((item) => ({
      id: item.id, title: [item.document_title, item.section].filter(Boolean).join(' · ')
    })));
    if (snapshot.inherited_constraints && typeof snapshot.inherited_constraints === 'object') {
      context.inheritedConstraints = Object.keys(snapshot.inherited_constraints).length
        ? [JSON.stringify(snapshot.inherited_constraints)] : [];
    }
    renderChatContext();
  }

  function initChat() {
    const body = bodyOf('chat');
    clear(body);

    const log = h('div', { class: 'chat-log', role: 'log', 'aria-live': 'polite', 'aria-label': '问答记录' });
    const input = h('textarea', {
      class: 'textarea',
      maxlength: '2000',
      rows: '2',
      placeholder: '例如：CVE-2026-22778 会影响我的哪些资产？ / 这个漏洞的攻击链是什么？',
      'aria-label': '问题输入'
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendQuestion();
      }
    });
    input.addEventListener('input', () => {
      if (state.chat.confirmation && state.chat.confirmation.question !== input.value.trim()) {
        state.chat.confirmation = null;
        renderChatContext();
      }
    });
    const sendBtn = h('button', { type: 'button', class: 'btn btn--primary', onclick: () => sendQuestion() }, icon('send'), '发送');
    const stopBtn = h('button', { type: 'button', class: 'btn btn--danger', onclick: () => stopAnswer() }, '停止');
    stopBtn.disabled = true;

    const modelToggle = h('input', { type: 'checkbox' });
    const modelCheck = h('label', { class: 'live-check' }, modelToggle,
      '让大模型换个说法（可选，需已配置密钥）');
    modelToggle.addEventListener('change', () => { state.chat.useModel = modelToggle.checked; });

    const context = h('div', { class: 'context-snapshot', 'aria-live': 'polite' });
    const confirmation = h('div', { class: 'context-confirmation', role: 'status' });
    state.dom.chat = {
      log: log, input: input, sendBtn: sendBtn, stopBtn: stopBtn,
      modelToggle: modelToggle, modelCheck: modelCheck,
      context: context, confirmation: confirmation
    };
    state.chat.initialized = true;

    body.append(
      card('当前 Agent 上下文', context),
      confirmation,
      log,
      card('提问',
        h('div', { class: 'chat-form' }, input, sendBtn, stopBtn),
        h('div', { class: 'live-toolbar' }, modelCheck),
        h('p', { class: 'chat-hints' },
          '回车发送，Shift+回车换行。回答只使用本地已经存下来的资料，资料里没有的会直接说不知道。'),
        h('p', { class: 'chat-hints' },
          '打开上面的开关后，大模型会把已有结论换个更口语的说法，并逐字实时显示出来。它只能改措辞、不能加事实；两边的说法不一致时，一律以本地结论为准。')));

    renderChat();
    renderChatContext();
    syncChatControls();
  }

  /* The model toggle is only usable when a key is configured, and the reason
   * it is unavailable is stated rather than left as a dead greyed-out box. */
  function syncChatControls() {
    const view = state.dom.chat;
    if (!view) return;
    const available = !!(state.health && state.health.model_configured);
    view.modelToggle.disabled = !available;
    view.modelCheck.classList.toggle('live-check--off', !available);
    if (!available) {
      view.modelToggle.checked = false;
      state.chat.useModel = false;
    }
  }

  function stopAnswer() {
    if (state.chat.controller) state.chat.controller.abort();
  }

  /* One evidence-bound sentence = one paragraph.  Local frames never split
   * mid-sentence, so each becomes a complete readable line. */
  function chatLineNode(line) {
    const evidence = Array.isArray(line.evidence_ids) ? line.evidence_ids : [];
    return h('p', { class: 'stream-line' },
      h('span', { class: 'from' },
        (labelOf(L.streamSource, line.source) || line.source)
        + (evidence.length ? ' · ' + evidence.slice(0, 3).join('、') : '')),
      document.createTextNode(line.delta));
  }

  /* The model returns one token per frame.  Those are appended to a single
   * growing paragraph -- one paragraph per token would be unreadable, and a
   * typewriter split across paragraphs is not what streaming text looks like. */
  function modelLine(shell) {
    if (!shell.modelLine) {
      const caret = h('span', { class: 'caret' });
      shell.modelCaret = caret;
      shell.modelLine = h('p', { class: 'stream-line stream-line--model' },
        h('span', { class: 'from' }, '大模型转述 · 逐字实时输出（不是证据）'),
        caret);
    }
    return shell.modelLine;
  }

  function renderChat() {
    const view = state.dom.chat;
    if (!view) return;
    clear(view.log);

    if (!state.chat.turns.length) {
      view.log.appendChild(emptyState(
        '还没有提问',
        '可以先在「全流程直播」跑一遍，把资料存进来，再用漏洞编号或软件名在这里提问。'
        + '回答会一段一段实时出现，每段都标着它来自哪条证据。'));
    }

    for (const turn of state.chat.turns) {
      if (turn.type === 'user') {
        view.log.appendChild(h('div', { class: 'chat-turn chat-user' },
          h('div', { class: 'chat-user-bubble' }, turn.text)));
      } else if (turn.type === 'error') {
        view.log.appendChild(h('div', { class: 'chat-turn' }, errorBlock(turn.message)));
      } else {
        view.log.appendChild(turn.node || renderAnswer(turn.data));
      }
    }

    view.log.scrollTop = view.log.scrollHeight;
  }

  /* Builds the live container for one answer.  Stage cards and text lines are
   * appended to it as frames arrive, so the reader watches the work happen
   * instead of waiting for a finished block. */
  function chatAnswerShell() {
    const stages = h('div', { class: 'live-feed' });
    const lines = h('div', { class: 'stream-lines' });
    const textBlock = h('div', { class: 'stream-block' },
      h('div', { class: 'stream-head' },
        badge('accent', '本地证据结论'),
        h('span', { class: 'muted' }, '每段话下面都标着它引用的证据编号')),
      // The engine's own wording is reproduced verbatim (it is the recorded
      // answer, so changing it here would make screen and record disagree).
      // It prints the raw status codes, so this legend translates them.
      h('p', { class: 'plain-note' },
        '正文里的英文是系统内部的判断代号，对应关系：'
        + 'affected = 受影响；not_affected = 不受影响；'
        + 'needs_confirmation = 待确认（不等于安全）；'
        + 'not_applicable = 不在本次判断范围内（该资产未授权，或它的组件与这条情报对不上），'
        + '系统因此不给结论。'),
      lines);
    const details = h('div', {});
    const node = h('div', { class: 'chat-answer' }, stages, textBlock, details);
    return { node: node, stages: stages, lines: lines, textBlock: textBlock, details: details, lastPhase: null };
  }

  function renderAnswer(data) {
    const blocks = [];
    blocks.push(h('p', { class: 'answer-text' }, textOr(data.answer, '（空回答）')));

    const contextChunks = answerContextChunks(data);
    blocks.push(sectionBlock(`Agent 本轮上下文块（${contextChunks.length}）`, contextChunks.length
      ? h('div', { class: 'rag-context', 'aria-label': 'Agent 本轮实际使用的检索上下文' },
        h('p', { class: 'plain-note' }, '以下是本轮送入回答阶段的具体文本块，不等同于整篇文档。'),
        ...contextChunks.map((chunk, index) => h('article', { class: 'rag-chunk context-chunk', 'data-chunk-id': chunk.id || null },
          h('div', { class: 'rag-chunk-head' },
            mono(chunk.id || `上下文块 ${index + 1}`),
            h('span', { class: 'muted' }, [chunk.document_title, chunk.section, chunk.page ? `第 ${chunk.page} 页` : null]
              .filter(Boolean).join(' · ') || '文档位置未记录')),
          h('p', { class: 'excerpt' }, textOr(chunk.text, '该上下文块未返回可显示的原文。')))))
      : emptyState('后端未返回块级上下文', '当前回答可能只使用事件摘要或来源摘录，不能据此声称完成全文RAG。')));

    const trace = Array.isArray(data.trace) ? data.trace : [];
    if (trace.length) {
      blocks.push(sectionBlock('系统都做了什么（执行轨迹）',
        dataTable([{ text: '第几步', cls: 'num' }, { text: '谁在做' }, { text: '做了什么' }, { text: '结果' }, { text: '为什么停' }],
          trace.map((step) => [
            textOr(step.step),
            h('div', {}, textOr(labelOf(L.role, step.role) || step.role),
              Array.isArray(step.evidence_ids) && step.evidence_ids.length
                ? h('div', { class: 'chips' }, step.evidence_ids.slice(0, 6).map((id) => h('span', { class: 'chip' }, String(id))))
                : null),
            mono(textOr(step.action)),
            textOr(step.result || step.note),
            textOr(step.stop_reason, DASH)
          ]))));
    }

    const citations = [...arrayOr(data.citations), ...arrayOr(data.document_citations)];
    blocks.push(sectionBlock(`这段话引用了哪些来源（${citations.length}）`, citations.length
      ? citations.map((citation) => {
        let chunks = arrayOr(citation.chunks);
        if (!chunks.length && citation.chunk && typeof citation.chunk === 'object') chunks = [citation.chunk];
        if (!chunks.length && (citation.chunk_id || citation.section || citation.page)) chunks = [citation];
        const normalized = chunks.map((chunk) => ragChunk(chunk, citation));
        return h('details', { class: 'citation citation-drilldown' },
          h('summary', {},
            h('span', { class: 'citation-head' },
              badge('plain', textOr(citation.trust ? (labelOf(L.trust, citation.trust) || citation.trust) : '未标注')),
              mono(textOr(citation.id), 'dim'),
              normalized.length ? badge('confirmed', `${normalized.length} 个具体块`) : badge('needs-confirmation', '仅来源级')),
            h('span', { class: 'citation-title' }, textOr(citation.title, '（无标题）'))),
          h('div', { class: 'citation-body' },
            h('p', { class: 'muted' }, '发布者：' + textOr(citation.publisher, '未标注')),
            normalized.length
              ? h('div', { class: 'rag-chunk-list' }, ...normalized.map(renderRagChunk))
              : alertBox('warn', '无法下钻到具体块', h('p', {}, '后端只返回了来源级证据；下面是来源摘录，不是带章节定位的全文块。')),
            h('p', { class: 'excerpt' }, textOr(citation.excerpt, '来源未提供摘录。')),
            h('p', {}, safeLink(citation.url, '打开原始来源'))));
      })
      : emptyState('本次回答没有引用任何来源')));

    const claims = Array.isArray(data.claims) ? data.claims : [];
    blocks.push(sectionBlock(`每一句话对应哪条证据（${claims.length}）`, claims.length
      ? h('ul', { class: 'cell-list' }, claims.map((claim) => h('li', {},
        h('span', {}, textOr(claim.text)),
        Array.isArray(claim.evidence_ids) && claim.evidence_ids.length
          ? h('div', { class: 'chips' }, claim.evidence_ids.map((id) => h('span', { class: 'chip' }, String(id))))
          : null)))
      : emptyState('本次回答没有产生证据陈述')));

    const assessments = Array.isArray(data.assessments) ? data.assessments : [];
    blocks.push(sectionBlock('资产影响判断', assessments.length
      ? dataTable([{ text: '资产 ID' }, { text: '状态' }, { text: '优先级' }, { text: '理由' }],
        assessments.map((item) => [
          mono(textOr(item.asset_id)),
          assessStatusBadge(item.status),
          priorityBadge(item.priority),
          Array.isArray(item.reasons) ? item.reasons.join('；') : DASH
        ]))
      : h('p', { class: 'muted' }, '本次回答未生成资产影响判断。')));

    const limitations = Array.isArray(data.limitations) ? data.limitations : [];
    blocks.push(sectionBlock('这次回答的局限（请务必看一眼）',
      limitations.length
        ? alertBox('warn', null, h('ul', { class: 'cell-list' }, limitations.map((item) => h('li', {}, String(item)))))
        : h('p', { class: 'muted' }, '后端未返回局限性说明。')));

    const related = Array.isArray(data.related_event_ids) ? data.related_event_ids : [];
    blocks.push(h('div', { class: 'chat-meta' },
      badge('accent', labelOf(L.answerMode, data.mode) || textOr(data.mode)),
      fmtDuration(data.duration_ms) ? mono('耗时 ' + fmtDuration(data.duration_ms), 'dim') : null,
      related.length
        ? h('span', { class: 'chips' }, related.map((id) => h('span', { class: 'chip' }, String(id))))
        : h('span', { class: 'muted' }, '无关联事件')));

    return h('div', { class: 'chat-answer' }, ...blocks);
  }

  async function sendQuestion(contextConfirmed) {
    const view = state.dom.chat;
    if (!view || state.chat.pending) return;
    const question = view.input.value.trim();
    if (!question) return;

    if (!contextConfirmed) {
      const warning = questionContextWarning(question);
      if (warning) {
        state.chat.confirmation = Object.assign({ question: question }, warning);
        renderChatContext();
        return;
      }
    }
    state.chat.confirmation = null;

    state.chat.turns.push({ type: 'user', text: question });
    state.chat.history.push({ role: 'user', content: question });
    state.chat.pending = true;
    view.input.value = '';
    view.sendBtn.disabled = true;
    view.stopBtn.disabled = false;
    view.input.disabled = true;
    renderChat();
    renderChatContext();

    const shell = chatAnswerShell();
    const turn = { type: 'answer', data: null, node: shell.node };
    state.chat.turns.push(turn);
    view.log.appendChild(shell.node);

    const scroll = () => { view.log.scrollTop = view.log.scrollHeight; };
    const controller = new AbortController();
    state.chat.controller = controller;
    let modelBlock = null;
    let sawError = false;

    try {
      await streamPost('/api/stream/answer', {
        question: question,
        history: state.chat.history.slice(0, -1).slice(-20),
        use_model: state.chat.useModel,
        thread_id: state.chat.context.threadId,
        context_snapshot: state.chat.context.snapshot
      }, (name, payload) => {
        if (name === 'stage') {
          if (payload.phase !== shell.lastPhase) {
            shell.lastPhase = payload.phase;
            shell.stages.appendChild(phaseSeparator(payload.phase_label));
          }
          shell.stages.appendChild(stageCard(payload));
        } else if (name === 'text') {
          if (payload.source === 'model') {
            if (!modelBlock) {
              shell.modelLines = h('div', { class: 'stream-lines' });
              modelBlock = h('div', { class: 'stream-block stream-block--model' },
                h('div', { class: 'stream-head' },
                  badge('model', '大模型转述（仅供阅读）'),
                  h('span', { class: 'muted' }, '模型只能改写措辞，不能新增事实；不一致时以本地结论为准')),
                shell.modelLines);
              shell.node.appendChild(modelBlock);
            }
            // Tokens grow one paragraph in place rather than creating a new one.
            const line = modelLine(shell);
            if (!shell.modelLines.contains(line)) shell.modelLines.appendChild(line);
            line.insertBefore(document.createTextNode(payload.delta), shell.modelCaret);
          } else {
            shell.lines.appendChild(chatLineNode(payload));
          }
        } else if (name === 'final') {
          turn.data = payload;
        } else if (name === 'error') {
          sawError = true;
          shell.details.appendChild(errorBlock(payload.message));
        }
        scroll();
      }, controller.signal);
    } catch (err) {
      if (err && err.name === 'AbortError') {
        // The user's question is already in state.chat.history and is replayed
        // with the next question, so the message must not claim otherwise.
        shell.details.appendChild(alertBox('warn', '已停止',
          h('p', {}, '上面保留下来的内容已经完成了。这次回答没有写入运行记录，'
            + '你的提问仍留在本次对话里，下一个问题会一并带上。')));
      } else {
        sawError = true;
        turn.type = 'error';
        turn.message = err.message;
        toast(err.message, 'error');
      }
    } finally {
      state.chat.controller = null;
      state.chat.pending = false;
      view.sendBtn.disabled = false;
      view.stopBtn.disabled = true;
      view.input.disabled = false;
      // The blinking caret means "still arriving"; once stopped it would lie.
      if (shell.modelCaret && shell.modelCaret.parentNode) {
        shell.modelCaret.parentNode.removeChild(shell.modelCaret);
      }

      if (turn.type === 'answer' && turn.data) {
        shell.details.appendChild(renderAnswer(turn.data));
        state.chat.history.push({ role: 'assistant', content: textOr(turn.data.answer, '') });
        updateChatContext(turn.data);
      } else if (!sawError) {
        turn.data = null;
      }

      renderChat();
      scroll();
      view.input.focus();
      refreshDashboardQuiet();
    }
  }

  /* --------------------------------------------------------- 运行日志 */

  function initRuns() {
    const body = bodyOf('runs');
    clear(body);

    const refreshBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => { refreshBtn.disabled = true; loadRuns().finally(() => { refreshBtn.disabled = false; }); } }, icon('refresh'), '刷新');
    const tableBox = h('div');
    state.dom.runs = { table: tableBox };

    body.append(card('运行记录', h('div', { class: 'btn-row' }, refreshBtn), tableBox));
    renderRuns();
  }

  async function loadRuns() {
    const view = state.dom.runs;
    if (!view) return;
    setBox(view.table, loadingBlock('正在加载运行记录…'));
    try {
      const data = await api.get('/api/runs?limit=30');
      state.runs.items = Array.isArray(data.items) ? data.items : [];
      state.runs.error = null;
    } catch (err) {
      state.runs.error = err.message;
      state.runs.items = [];
    }
    renderRuns();
  }

  function renderRuns() {
    const view = state.dom.runs;
    if (!view) return;
    if (state.runs.error) {
      setBox(view.table, errorBlock(state.runs.error, () => loadRuns()));
      return;
    }
    const items = state.runs.items;
    if (!items.length) {
      setBox(view.table, emptyState('暂无运行记录', '采集、富化、研判、问答与评测执行后都会在这里留下记录。'));
      return;
    }

    const rows = items.map((run) => {
      let detailNode = mono(DASH, 'dim');
      if (run.detail !== null && run.detail !== undefined) {
        let pretty;
        try { pretty = JSON.stringify(run.detail, null, 2); } catch (err) { pretty = String(run.detail); }
        detailNode = h('details', { class: 'raw' },
          h('summary', {}, '查看明细'),
          h('pre', {}, pretty));
      }
      return [
        mono(textOr(run.id)),
        labelOf(L.runKind, run.kind) || textOr(run.kind),
        runStatusBadge(run.status),
        timeCell(run.started_at),
        timeCell(run.finished_at),
        textOr(run.summary),
        detailNode
      ];
    });

    setBox(view.table,
      h('h3', { class: 'block-title' }, '运行记录', h('span', { class: 'count' }, `最近 ${items.length} 条`)),
      dataTable([
        { text: '运行 ID' }, { text: '类型' }, { text: '状态' }, { text: '开始' }, { text: '完成' },
        { text: '摘要' }, { text: '明细' }
      ], rows));
  }

  /* ------------------------------------------------------------- 评测 */

  function initEvaluation() {
    const body = bodyOf('evaluation');
    clear(body);

    const runBtn = h('button', { type: 'button', class: 'btn btn--primary', onclick: () => runEvaluation(runBtn) }, icon('play'), '执行本地回归评测');
    const refreshBtn = h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => { refreshBtn.disabled = true; loadEvaluation().finally(() => { refreshBtn.disabled = false; }); } }, icon('refresh'), '刷新');
    const resultBox = h('div');
    state.dom.evaluation = { result: resultBox, runBtn: runBtn };

    body.append(
      card('评测控制',
        h('div', { class: 'btn-row' }, runBtn, refreshBtn),
        h('p', { class: 'dim' }, '评测在本地对真实引擎执行回归：核验案例（research/cases.json）+ 标注 synthetic 的合成夹具。未执行时不提供任何分数。'),
        resultBox));

    renderEvaluation();
  }

  async function loadEvaluation() {
    const view = state.dom.evaluation;
    if (!view) return;
    state.evaluation.loading = true;
    setBox(view.result, loadingBlock('正在读取评测状态…'));
    try {
      state.evaluation.data = await api.get('/api/evaluation');
      state.evaluation.error = null;
    } catch (err) {
      state.evaluation.error = err.message;
      state.evaluation.data = null;
    }
    state.evaluation.loading = false;
    renderEvaluation();
  }

  function renderEvaluation() {
    const view = state.dom.evaluation;
    if (!view) return;

    if (state.evaluation.error) {
      setBox(view.result, errorBlock(state.evaluation.error, () => loadEvaluation()));
      return;
    }
    const data = state.evaluation.data;
    if (!data) {
      setBox(view.result, emptyState('尚未加载评测状态'));
      return;
    }

    const blocks = [];

    if (data.status !== 'completed') {
      const limitations = Array.isArray(data.limitations) ? data.limitations : [];
      blocks.push(emptyState('尚未执行评测', '未执行时不提供任何分数；点击「执行本地回归评测」后生成结果。'));
      if (limitations.length) {
        blocks.push(alertBox('warn', '说明',
          h('ul', { class: 'cell-list' }, limitations.map((item) => h('li', {}, String(item))))));
      }
      setBox(view.result, ...blocks);
      return;
    }

    /* 摘要 */
    blocks.push(card('最近一次评测',
      kvList([
        ['状态', badge('completed', '已完成')],
        ['执行时间', timeCell(data.executed_at)],
        ['摘要', textOr(data.summary)],
        ['范围', textOr(data.scope, '（本次仅返回摘要，重新执行可查看完整范围）')]
      ]),
      data.note ? h('p', { class: 'note-verbatim' }, String(data.note)) : null));

    /* 指标 */
    const metrics = data.metrics || {};
    const metricRows = [];
    if (metrics.cases_total !== undefined) {
      metricRows.push(['用例总数', textOr(metrics.cases_total, '0')]);
      metricRows.push(['通过', textOr(metrics.cases_passed, '0')]);
      metricRows.push(['失败', textOr(metrics.cases_failed, '0')]);
      let accuracyText = DASH;
      if (metrics.accuracy !== null && metrics.accuracy !== undefined) {
        accuracyText = `${(Number(metrics.accuracy) * 100).toFixed(2)}%（${textOr(metrics.cases_passed, '0')} / ${textOr(metrics.cases_total, '0')}）`;
      }
      metricRows.push(['通过率', accuracyText]);
      metricRows.push(['真实核验案例', `${textOr(metrics.real_case_passed, '0')} / ${textOr(metrics.real_case_count, '0')}`]);
      metricRows.push(['合成夹具', `${textOr(metrics.synthetic_case_passed, '0')} / ${textOr(metrics.synthetic_case_count, '0')}`]);
    }
    blocks.push(card('指标', metricRows.length
      ? h('div', {}, metricRows.map((row) => h('div', { class: 'metric-row' },
        h('span', {}, row[0]),
        h('span', { class: 'metric-value' + (row[0] === '通过率' ? ' accent' : '') }, row[1]))))
      : emptyState('本次返回未包含指标明细', '重新执行评测以获取完整指标。')));

    /* 分类明细 */
    const byCategory = metrics.by_category && typeof metrics.by_category === 'object' ? metrics.by_category : null;
    if (byCategory) {
      const names = Object.keys(byCategory);
      blocks.push(card('分类通过率', names.length
        ? h('div', {}, names.map((name) => {
          const bucket = byCategory[name] || {};
          const total = Number(bucket.total) || 0;
          const passed = Number(bucket.passed) || 0;
          const ratio = total > 0 ? passed / total : 0;
          const fill = h('div', { class: 'bar-fill' + (ratio < 1 ? ' is-bad' : '') });
          fill.style.width = (ratio * 100).toFixed(1) + '%';
          return h('div', { class: 'bar-row' },
            h('span', {}, name),
            h('div', { class: 'bar-track' }, fill),
            mono(`${passed} / ${total}`));
        }))
        : emptyState('无分类数据')));
    }

    /* 逐条结果 */
    const results = Array.isArray(data.results) ? data.results : [];
    if (results.length) {
      blocks.push(card(`逐条结果（${results.length}）`,
        results.map((item) => h('div', { class: 'result-item' + (item.passed ? '' : ' is-failed') },
          h('div', { class: 'result-item-head' },
            item.passed ? badge('ok', '通过') : badge('failed', '未通过'),
            h('span', { class: 'result-item-id' }, textOr(item.id)),
            item.synthetic ? badge('demo', '合成夹具 synthetic') : badge('accent', '真实核验案例'),
            badge('plain', textOr(item.category))),
          h('p', {}, textOr(item.description)),
          h('p', { class: 'muted' }, '明细：' + textOr(item.detail)),
          item.error ? h('p', { class: 'err-text break' }, '异常：' + String(item.error)) : null,
          item.source ? h('p', {}, mono('来源：' + textOr(item.source), 'dim')) : null))));
    } else {
      blocks.push(card('逐条结果', emptyState('本次响应未包含逐条结果', '点击「执行本地回归评测」可在本页生成完整逐条结果。')));
    }

    /* 局限性——显著展示 */
    const limitations = Array.isArray(data.limitations) ? data.limitations : [];
    blocks.push(alertBox('warn', '局限性（必读）',
      limitations.length
        ? h('ul', { class: 'cell-list' }, limitations.map((item) => h('li', {}, String(item))))
        : h('p', {}, '后端未返回局限性说明。')));

    setBox(view.result, ...blocks);
  }

  async function runEvaluation(button) {
    if (state.evaluation.running) return;
    state.evaluation.running = true;
    button.disabled = true;
    setBox(state.dom.evaluation.result, loadingBlock('正在执行本地回归评测…'));
    try {
      const data = await api.post('/api/evaluation/run');
      state.evaluation.data = data;
      state.evaluation.error = null;
      renderEvaluation();
      toast('评测完成：' + textOr(data.summary, '已生成结果'));
      await refreshDashboardQuiet();
    } catch (err) {
      setBox(state.dom.evaluation.result, errorBlock(err.message));
      toast(err.message, 'error');
    } finally {
      state.evaluation.running = false;
      button.disabled = false;
    }
  }

  /* ---------------------------------------------------------- 全流程直播 */

  /* One step of the pipeline.
   *
   * The colour convention is the whole point of this card: a teal solid rule
   * marks what the system *produced*, a violet dashed rule marks what it
   * *received from outside*.  A reader can tell the two apart without reading
   * the labels, which matters when the two differ (a tool returns nothing and
   * the step outputs "still missing"). */
  function stageCard(stage) {
    const rows = [];
    for (const field of L.stageFields) {
      const value = stage[field.key];
      if (value === null || value === undefined || value === '') continue;
      rows.push(h('div', { class: 'stage-row ' + field.cls },
        h('span', { class: 'k' }, field.label),
        h('p', { class: 'v' }, String(value))));
    }

    const refs = (Array.isArray(stage.refs) ? stage.refs : []).filter(Boolean);
    const time = fmtDuration(stage.duration_ms);

    return h('article', { class: 'stage-card stage-card--' + (stage.status || 'done') },
      h('div', { class: 'stage-head' },
        h('span', { class: 'stage-seq' }, '#' + textOr(stage.seq, '?')),
        badge('plain', labelOf(L.role, stage.role) || textOr(stage.role_label, stage.role)),
        h('span', { class: 'stage-title' }, textOr(stage.title, '（未命名步骤）')),
        stage.status && stage.status !== 'done'
          ? statusBadge(L.stageStatus, L.stageStatusClass, stage.status)
          : null,
        time ? h('span', { class: 'stage-time' }, time) : null),
      rows.length ? h('div', { class: 'stage-body' }, rows) : null,
      stage.note ? h('p', { class: 'stage-note' }, '备注：' + stage.note) : null,
      refs.length
        ? h('div', { class: 'stage-refs' }, refs.slice(0, 8).map((id) => h('span', { class: 'chip' }, String(id))))
        : null);
  }

  function phaseSeparator(label) {
    return h('div', { class: 'phase-sep' }, textOr(label, ''), h('span', {}, ''));
  }

  function liveStats() {
    const frames = state.live.frames;
    const stages = frames.filter((f) => f.name === 'stage').map((f) => f.data);
    let produced = 0;
    for (const stage of stages) if (stage.output) produced += 1;
    let obtained = 0;
    for (const stage of stages) if (stage.obtained) obtained += 1;
    const failed = stages.filter((s) => s.status === 'failed').length;
    const skipped = stages.filter((s) => s.status === 'skipped').length;

    const items = [
      ['已走步骤', stages.length],
      ['产出内容', produced],
      ['外部取回', obtained],
      ['失败', failed],
      ['已跳过', skipped]
    ];
    return h('div', { class: 'live-stats' }, items.map(([k, v]) =>
      h('div', { class: 'live-stat' }, h('span', { class: 'k' }, k), h('span', { class: 'v' }, String(v)))));
  }

  function initLive() {
    const body = bodyOf('live');
    clear(body);

    const sourceSelect = h('select', { class: 'select live-source', 'aria-label': '选择要抓取的来源' },
      h('option', { value: '' }, '全部登记来源（耗时最长，约 1~2 分钟）'));
    const enrichSelect = h('select', { class: 'select live-enrich', 'aria-label': '补证条数上限' },
      [0, 3, 6, 10].map((n) => h('option', { value: String(n), selected: n === 6 ? 'selected' : null },
        n === 0 ? '不补证（只抓取）' : `最多补证 ${n} 条`)));

    const autoScroll = h('input', { type: 'checkbox', checked: 'checked' });
    autoScroll.addEventListener('change', () => { state.live.autoScroll = autoScroll.checked; });

    const startBtn = h('button', { type: 'button', class: 'btn btn--primary' }, icon('play'), '开始跑一遍');
    startBtn.addEventListener('click', () => startPipeline());

    const stopBtn = h('button', { type: 'button', class: 'btn btn--danger' }, '停止');
    stopBtn.disabled = true;
    stopBtn.addEventListener('click', stopPipeline);

    const selector = h('label', { class: 'field' },
      h('span', { class: 'field-label' }, '抓哪些来源'), sourceSelect);
    const enricher = h('label', { class: 'field' },
      h('span', { class: 'field-label' }, '补证强度'), enrichSelect);

    const toolbar = h('div', { class: 'live-toolbar' },
      selector, enricher,
      h('div', { class: 'btn-row' }, startBtn, stopBtn),
      h('div', { class: 'spacer' }),
      h('label', { class: 'live-check' }, autoScroll, '自动滚到最新'));

    const progress = h('div', { class: 'live-progress', hidden: 'hidden' },
      h('div', { class: 'now' }, h('span', { class: 'spinner' }), h('span', { class: 'now-text' }, '准备中…')),
      h('div', { class: 'elapsed' }),
      h('div', { class: 'stats' }));

    const feed = h('div', { class: 'live-feed', role: 'log', 'aria-live': 'polite' });

    state.dom.live = {
      feed: feed, progress: progress, startBtn: startBtn, stopBtn: stopBtn,
      sourceSelect: sourceSelect, enrichSelect: enrichSelect,
      nowText: progress.querySelector('.now-text'),
      elapsed: progress.querySelector('.elapsed'),
      stats: progress.querySelector('.stats')
    };

    body.append(toolbar, progress, card('运行记录', feed));

    renderLiveEmpty();
    loadLiveSources();
  }

  function renderLiveEmpty() {
    const view = state.dom.live;
    if (!view) return;
    clear(view.feed);
    view.feed.appendChild(emptyState('尚未运行'));
  }

  async function loadLiveSources() {
    const view = state.dom.live;
    if (!view) return;
    try {
      const data = await api.get('/api/sources');
      state.sources = Array.isArray(data.items) ? data.items : [];
    } catch (err) {
      return; // 下拉框保留“全部来源”一项，功能不受影响
    }
    for (const item of state.sources) {
      view.sourceSelect.appendChild(h('option', { value: item.id },
        `${item.name}${item.events_count ? '' : '（尚未取到数据）'}`));
    }
  }

  function liveTick() {
    const view = state.dom.live;
    if (!view || !state.live.startedAt) return;
    const seconds = ((Date.now() - state.live.startedAt) / 1000).toFixed(1);
    clear(view.elapsed);
    view.elapsed.appendChild(document.createTextNode('已用时 ' + seconds + ' 秒'));
  }

  function setLiveRunning(running) {
    const view = state.dom.live;
    state.live.running = running;
    if (!view) return;
    view.startBtn.disabled = running;
    view.stopBtn.disabled = !running;
    view.sourceSelect.disabled = running;
    view.enrichSelect.disabled = running;
    view.progress.hidden = false;
    clear(view.progress.querySelector('.now'));
    view.progress.querySelector('.now').appendChild(
      running ? h('span', { class: 'spinner' }) : h('span', {}, ''));
    view.progress.querySelector('.now').appendChild(
      h('span', { class: 'now-text' }, running ? '正在运行…' : '已结束'));
    if (!running) state.live.startedAt = null;
  }

  async function startPipeline() {
    const view = state.dom.live;
    if (!view || state.live.running) return;

    state.live.frames = [];
    state.live.final = null;
    state.live.error = null;
    state.live.startedAt = Date.now();
    state.live.lastPhase = null;
    state.live.pending = {};
    clear(view.feed);
    view.stats.textContent = '';
    view.stats.appendChild(liveStats());

    const sourceId = view.sourceSelect.value;
    const enrichLimit = parseInt(view.enrichSelect.value, 10) || 0;
    const controller = new AbortController();
    state.live.controller = controller;
    setLiveRunning(true);
    liveTick();
    state.live.stopTimer = window.setInterval(liveTick, 200);

    const finish = () => {
      if (state.live.stopTimer) window.clearInterval(state.live.stopTimer);
      state.live.stopTimer = null;
      const wallMs = state.live.startedAt ? Date.now() - state.live.startedAt : null;
      // A phase that ends without producing any result leaves its placeholder
      // on screen.  With no assets (or no component matches) the assess phase
      // emits no frames at all, so the run would finish still showing 进行中.
      for (const phase of Object.keys(state.live.pending)) {
        const node = state.live.pending[phase];
        if (node && node.parentNode) node.parentNode.removeChild(node);
      }
      state.live.pending = {};
      setLiveRunning(false);
      clear(view.stats);
      view.stats.appendChild(liveStats());
      view.progress.hidden = false;
      // Replace the ticking clock with the measured total, so the number that
      // stays on screen is the backend's own timing rather than the last tick.
      const finalMs = state.live.final ? state.live.final.duration_ms : wallMs;
      clear(view.elapsed);
      if (finalMs !== null && finalMs !== undefined) {
        view.elapsed.appendChild(document.createTextNode('共耗时 ' + (fmtDuration(finalMs) || DASH)));
      }
    };

    try {
      await streamPost('/api/stream/pipeline', {
        source_ids: sourceId ? [sourceId] : null,
        close_gaps: true,
        enrich_limit: enrichLimit
      }, (name, payload) => {
        if (name === 'stage') {
          state.live.frames.push({ name: name, data: payload });
          if (payload.phase !== state.live.lastPhase) {
            state.live.lastPhase = payload.phase;
            view.feed.appendChild(phaseSeparator(payload.phase_label));
          }
          if (payload.status === 'running') {
            // A "still working" placeholder.  It is removed as soon as the
            // phase reports its first real result, so a finished run never
            // leaves a card behind claiming to be 进行中.
            const placeholder = stageCard(payload);
            view.feed.appendChild(placeholder);
            state.live.pending[payload.phase] = placeholder;
          } else {
            const stale = state.live.pending[payload.phase];
            if (stale && stale.parentNode) stale.parentNode.removeChild(stale);
            delete state.live.pending[payload.phase];
            view.feed.appendChild(stageCard(payload));
          }
          view.nowText.textContent = payload.title;
          // Counters describe the run so far, so they advance with it.
          clear(view.stats);
          view.stats.appendChild(liveStats());
          if (state.live.autoScroll) view.feed.scrollTop = view.feed.scrollHeight;
        } else if (name === 'final') {
          state.live.final = payload;
        } else if (name === 'error') {
          state.live.error = payload.message;
          view.feed.appendChild(errorBlock(payload.message));
        }
      }, controller.signal);
    } catch (err) {
      if (err && err.name === 'AbortError') {
        view.feed.appendChild(alertBox('warn', '已手动停止',
          h('p', {}, '运行被中途停止。已经完成的步骤保留在下面，运行记录里也会留下痕迹。')));
      } else {
        state.live.error = err.message;
        view.feed.appendChild(errorBlock(err.message));
        toast(err.message, 'error');
      }
    } finally {
      finish();
      view.feed.appendChild(renderLiveSummary());
      if (state.live.autoScroll) view.feed.scrollTop = view.feed.scrollHeight;
      refreshDashboardQuiet();
    }
  }

  function stopPipeline() {
    if (state.live.controller) state.live.controller.abort();
  }

  function renderLiveSummary() {
    const final = state.live.final;
    if (!final) {
      return alertBox('warn', '本次没有跑完', h('p', {}, '上方最后一个步骤说明了停在哪里。'));
    }
    const sources = Array.isArray(final.sources) ? final.sources : [];
    return card('本次结果',
      h('div', { class: 'live-stats' },
        h('div', { class: 'live-stat' }, h('span', { class: 'k' }, '新增情报'), h('span', { class: 'v' }, String(final.events_added))),
        h('div', { class: 'live-stat' }, h('span', { class: 'k' }, '更新情报'), h('span', { class: 'v' }, String(final.events_updated))),
        h('div', { class: 'live-stat' }, h('span', { class: 'k' }, '补证条目'), h('span', { class: 'v' }, String(final.enriched))),
        h('div', { class: 'live-stat' }, h('span', { class: 'k' }, '外部查证次数'), h('span', { class: 'v' }, String(final.tool_calls))),
        h('div', { class: 'live-stat' }, h('span', { class: 'k' }, '影响结论'), h('span', { class: 'v' }, String(final.assessments))),
        h('div', { class: 'live-stat' }, h('span', { class: 'k' }, '总耗时'), h('span', { class: 'v' }, fmtDuration(final.duration_ms) || DASH))),
      sources.length
        ? dataTable([{ text: '来源' }, { text: '状态' }, { text: '取回' }, { text: '保留' }, { text: '剔除' }, { text: '耗时' }],
          sources.map((s) => [
            textOr(s.name, s.source_id),
            runStatusBadge(s.status),
            textOr(s.fetched),
            textOr(s.kept),
            textOr(s.filtered),
            fmtDuration(s.duration_ms) || DASH
          ]))
        : null,
      h('p', { class: 'live-hint' },
        '“剔除”指与 AI 安全无关、被规则过滤掉的记录。状态为“已跳过”的来源表示它需要额外凭据，本次没有取到数据 —— 这不会被算作成功。'));
  }

  /* ---------------------------------------------------------- 标注说明 */

  function initLabels() {
    const body = bodyOf('labels');
    clear(body);

    body.append(
      card('颜色约定：一眼分清“它生成的”和“它拿到的”',
        h('div', { class: 'gloss-grid' },
          h('div', { class: 'gloss-item gloss-item--output' },
            h('h4', {}, '青色实线 = 系统自己产出的内容'),
            h('p', {}, '例如：统一的格式、生成的补证计划、最终的影响结论、回答的句子。这些都是系统算出来的。')),
          h('div', { class: 'gloss-item gloss-item--obtained' },
            h('h4', {}, '紫色虚线 = 从外部拿回来的内容'),
            h('p', {}, '例如：NVD 返回的版本范围、CISA 的回应、模型接口返回的文字。这些是别人给的，系统只是转述。'))),
        h('p', { class: 'plain-note' },
          '这条约定贯穿“全流程直播”和“提问”两个页面。分清这两者，才能判断一句话到底是系统的结论还是外部资料。')),

      card('运行模式：两种，界面上永远标明当前是哪一种',
        h('div', { class: 'legend-row' },
          badge('accent', '本地证据抽取模式'),
          h('span', {}, '没有配置大模型时使用。答案完全由本地已存的资料拼装，系统不会声称用了大模型。')),
        h('div', { class: 'legend-row' },
          badge('model', '模型辅助模式'),
          h('span', {}, '配置了密钥时可用。大模型只能做两件事：从候选列表里挑事件、把已有结论换个说法。它不能新增事实。')),
        h('p', { class: 'plain-note' },
          '“提问”页有一个“让大模型换个说法”的开关，默认关闭。开启后模型逐字返回的内容会用紫色虚线标出来，并注明“以本地结论为准”。')),

      card('结论徽章：四种，没有第五种',
        h('div', { class: 'legend-row' }, assessStatusBadge('affected'),
          h('span', {}, '受影响 —— 版本命中且触发条件满足，需要处理。')),
        h('div', { class: 'legend-row' }, assessStatusBadge('not_affected'),
          h('span', {}, '不受影响 —— 版本不在已知范围内，或有条件明确不成立。')),
        h('div', { class: 'legend-row' }, assessStatusBadge('needs_confirmation'),
          h('span', {}, '待确认 —— 版本可能命中，但有些条件查不到。这一档绝不等同于安全。')),
        h('div', { class: 'legend-row' }, assessStatusBadge('not_applicable'),
          h('span', {}, '不适用 —— 不在本次判断范围内：该资产未授权，或它的组件与这条情报对不上。'
            + '系统拒绝给结论，而不是假装它安全。')),
        h('p', { class: 'plain-note' },
          '注意“不适用”有两种原因，看判定理由那一栏能区分：写“未授权”的是越权保护，'
          + '写“组件不匹配”的是两者对不上，不能当成“已排查过”。'),
        h('p', { class: 'plain-note' },
          '重要：系统不会把“没查到证据”当成“没有问题”。查不到就是查不到，会明说。')),

      card('数据来源徽章',
        h('div', { class: 'legend-row' }, badge('demo', '合成演示数据'),
          h('span', {}, '人工编出来的假数据，用来演示功能。所有演示资产都带 is_demo 标记，不代表任何真实系统。')),
        h('div', { class: 'legend-row' }, badge('plain', 'synthetic 测试夹具'),
          h('span', {}, '自动化测试用的假数据，只出现在测试代码里，不会进入正式数据。')),
        h('div', { class: 'legend-row' }, runStatusBadge('skipped'),
          h('span', {}, '已跳过 —— 该来源需要额外凭据而本次没配置，没有取到数据。')),
        h('div', { class: 'legend-row' }, runStatusBadge('failed'),
          h('span', {}, '失败 —— 真的出错了，原始错误信息会保留下来。'))),

      card('证据相关：这些词是什么意思',
        h('div', { class: 'gloss-grid' },
          h('div', { class: 'gloss-item' },
            h('h4', {}, '证据缺口 ', h('span', { class: 'tech-tag' }, 'gap')),
            h('p', {}, '这条情报还缺哪些关键信息，比如不知道修复版本、没有版本范围。缺口不会被自动“补齐”，只会如实列出。')),
          h('div', { class: 'gloss-item' },
            h('h4', {}, '内容快照 ', h('span', { class: 'tech-tag' }, 'snapshot')),
            h('p', {}, '抓取时把原始返回原封不动存一份，并用内容算出的哈希命名。任何人都可以拿哈希去核对，确认系统没有篡改原始资料。')),
          h('div', { class: 'gloss-item' },
            h('h4', {}, '查重 ', h('span', { class: 'tech-tag' }, 'dedupe')),
            h('p', {}, '同一条漏洞可能出现在多个来源。系统会合并它们并保留全部来源，不会因为“看起来像”就把两条不同的漏洞合并成一条。')),
          h('div', { class: 'gloss-item' },
            h('h4', {}, '受限调度 ', h('span', { class: 'tech-tag' }, 'bounded scheduling')),
            h('p', {}, '补证最多跑 2 轮、最多调 3 次外部接口，然后必须停下并说明为什么停。这是为了防止系统无休止地查下去。')))),

      card('这个界面不做什么',
        h('ul', { class: 'cell-list' },
          h('li', {}, '不会为了好看而编造数据。抓不到就显示抓不到。'),
          h('li', {}, '不会伪造耗时。所有时间都是真实测量的。'),
          h('li', {}, '不会把“查不到”说成“安全”。'),
          h('li', {}, '不会让前端访问任意网址。来源清单固定在后端，前台只能勾选。'),
          h('li', {}, '不会在没跑过自测的情况下显示分数。')),
        h('p', { class: 'plain-note' },
          '如果界面上某处看起来“不够漂亮”或“不够满”，很可能正是这些约束在起作用，而不是程序出错。')));
  }

  /* --------------------------------------------------------- 系统说明 */

  /* Sub-tabs of 系统说明.  Four of the five reuse the panel code that used to
   * own a top-level tab (`initCollect` and friends) unchanged -- they write to
   * the same `body-*` nodes, which now live inside these sub-panels. */
  const SUBTABS = {
    ai: { init: renderAiSection, load: null },
    tools: { init: renderTools, load: null },
    sources: { init: initCollect, load: loadSources },
    quality: { init: initQuality, load: loadQuality },
    legend: { init: initLabels, load: null }
  };

  function initQuality() {
    initRuns();
    initEvaluation();
  }

  function loadQuality() {
    loadRuns();
    loadEvaluation();
  }

  function initManual() {
    wireSubtabs();
    showSubtab('ai');
  }

  function wireSubtabs() {
    const list = document.getElementById('manual-subtabs');
    if (!list || list.dataset.wired) return;
    list.dataset.wired = '1';
    const buttons = Array.prototype.slice.call(list.querySelectorAll('.subtab'));
    for (const button of buttons) {
      button.addEventListener('click', () => showSubtab(button.dataset.sub));
    }
    list.addEventListener('keydown', (event) => {
      const keys = ['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
      if (keys.indexOf(event.key) < 0) return;
      const index = buttons.indexOf(document.activeElement);
      if (index < 0) return;
      event.preventDefault();
      let next = index;
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = (index + 1) % buttons.length;
      if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = (index - 1 + buttons.length) % buttons.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = buttons.length - 1;
      buttons[next].focus();
      showSubtab(buttons[next].dataset.sub);
    });
  }

  function showSubtab(key) {
    const meta = SUBTABS[key];
    if (!meta) return;
    for (const button of document.querySelectorAll('#manual-subtabs .subtab')) {
      const on = button.dataset.sub === key;
      button.setAttribute('aria-selected', on ? 'true' : 'false');
      button.tabIndex = on ? 0 : -1;
    }
    for (const panel of document.querySelectorAll('.subpanel')) {
      panel.hidden = panel.id !== 'subpanel-' + key;
    }
    const flag = 'sub:' + key;
    if (state.inited.has(flag)) return;
    state.inited.add(flag);
    meta.init();
    if (meta.load) meta.load();
  }

  /* 「AI 做了什么」-- the answer to the question the console used to leave
   * implicit.  Prompts come from the backend, which reads them off the same
   * constants the real calls send, so this page cannot drift from reality. */
  async function renderAiSection() {
    const node = document.getElementById('subpanel-ai');
    if (!node) return;
    setBox(node, emptyState('正在读取 AI 参与点…'));
    let data;
    try {
      data = await api.get('/api/ai-participation');
    } catch (err) {
      setBox(node, errorBlock(err.message));
      return;
    }
    const parts = [card('结论先说：这套系统里，AI 只做两件事',
      h('p', {}, '除此之外的每一项——抓到什么、算不算重复、缺哪些证据、资产受不受影响、'
        + '检索到什么、什么时候该拒答——都由本地规则算出，没有模型参与。'),
      h('p', { class: 'plain-note' },
        '当前运行模式：', badge(data.model_configured ? 'model' : 'plain',
          data.model_configured ? '模型辅助模式' : '本地证据抽取模式'),
        data.model_name ? '（模型 ' + data.model_name + '）' : '（未配置模型）'))];

    data.participations.forEach((item, index) => {
      parts.push(card('AI 参与点 ' + (index + 1) + '：' + item.name,
        h('dl', { class: 'kv' },
          h('dt', {}, '什么时候用'), h('dd', {}, item.when),
          h('dt', {}, '在哪段代码'), h('dd', {}, h('code', {}, item.where)),
          h('dt', {}, '喂进去什么'), h('dd', {}, item.input),
          h('dt', {}, '拿回来什么'), h('dd', {}, item.output),
          h('dt', {}, '有哪些限制'), h('dd', {}, item.bound)),
        h('p', { class: 'plain-note' }, '真正发出去的系统提示词（原文，直接从运行中的代码读出）：'),
        h('pre', { class: 'prompt-block' }, item.prompt)));
    });

    parts.push(card('这些都不是 AI 做的',
      h('div', { class: 'gloss-grid' },
        ...data.not_ai.map((x) => h('div', { class: 'gloss-item' },
          h('h4', {}, x.name), h('p', {}, x.detail))))));

    setBox(node, parts);
  }

  /* 「工具与编排」-- every string here is read from the run tables, including
   * the honest note that the roles are one process, not independent agents. */
  async function renderTools() {
    const node = document.getElementById('body-tools');
    if (!node) return;
    setBox(node, emptyState('正在读取编排信息…'));
    let info;
    try {
      info = await api.get('/api/orchestration');
    } catch (err) {
      setBox(node, errorBlock(err.message));
      return;
    }

    const toolRows = info.tools.map((tool) => h('tr', {},
      h('td', {}, tool.name),
      h('td', {}, tool.category_label),
      h('td', {}, badge(tool.group === '漏洞' ? 'accent' : 'model', tool.group)),
      h('td', {}, tool.requires_token ? '需要 ' + tool.requires_token : '不需要令牌')));

    const phases = info.phases.filter((p) => p.id !== 'summary' && p.id !== 'answer');
    setBox(node,
      card('执行边界',
        h('div', { class: 'orchestration-flow', 'aria-label': '任务阶段' }, ...phases.map((phase, index) =>
          h('div', { class: 'orchestration-node' },
            h('span', { class: 'orchestration-index' }, String(index + 1).padStart(2, '0')),
            h('div', { class: 'orchestration-node-main' }, h('strong', {}, textOr(phase.label, phase.id))),
            index < phases.length - 1 ? h('span', { class: 'orchestration-arrow', 'aria-hidden': 'true' }, '→') : null))),
        h('div', { class: 'chips' },
          h('span', { class: 'chip' }, `补证 ${textOr(info.scheduling.max_rounds, '—')} 轮`),
          h('span', { class: 'chip' }, `外部调用 ${textOr(info.scheduling.tool_budget, '—')} 次`))),
      card('登记工具（' + String(info.tools.length) + '）',
        h('div', { class: 'table-wrap' },
          h('table', { class: 'data-table' },
            h('thead', {}, h('tr', {},
              h('th', {}, '来源'), h('th', {}, '类别'), h('th', {}, '归入'), h('th', {}, '凭证'))),
            h('tbody', {}, ...toolRows)))));
  }

  /* ------------------------------------------------------------- 启动 */

  function boot() {
    wireTabs();
    loadHealth();
    try {
      state.onboarding.pendingAutoDemo =
        new URLSearchParams(window.location.search).get('demo') === '1';
    } catch (err) {
      state.onboarding.pendingAutoDemo = false;
    }
    activate('overview');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
