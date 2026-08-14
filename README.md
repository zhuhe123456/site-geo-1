<div align="center">

# GEO Audit Service

## 出海站点救星

### 外贸独立站如何快速接入 AI，从“能被搜索”升级到“能被引用”

让品牌官网不只是上线可见，更能被 **ChatGPT、Google AI Mode、Google AI Overviews、Perplexity、Gemini 和 Grok** 访问、理解、提取、引用与信任。

**一个面向 GEO 时代的站点审计引擎**  
帮助出海品牌、外贸独立站、跨境 SaaS 和内容团队快速回答：

- 你的站点有没有被主流 AI crawler 放行
- 你的页面是不是足够适合被 AI 摘要、引用和复述
- 你的品牌实体、结构化数据和内容深度够不够支撑 AI 信任
- 你的官网距离“AI 可见、AI 可引用、AI 可推荐”还有多远

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://hub.docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[**Live Demo**](https://www.idtcpack.com/geo/brand-site-grader) · [Report Bug](https://github.com/your-org/geo-audit-service/issues) · [Request Feature](https://github.com/your-org/geo-audit-service/issues)

</div>

---

## 为什么不是传统 SEO 工具

传统 SEO 工具主要回答：

- 你有没有排名
- 关键词位置有没有变化

GEO Audit 关注的是另一层问题：

- AI 系统能不能访问你的内容
- AI 能不能理解你的实体、页面和关系
- 你的页面够不够适合被抽取、引用和复述
- 你的品牌是否足够可信，能作为答案来源被采用

对出海站点来说，这意味着你不只是“有页面”，而是要成为 **AI 产品中的可信答案源**。

---

## 核心能力

### Google 爬虫测试

独立 demo 页面：`GET /google-crawler-test`

- `POST /api/v1/google-crawler/googlebot`：模拟 Googlebot Smartphone，检查 robots.txt、HTTP、重定向、索引指令和初始 HTML；`raw_html.googlebot` 保留 Googlebot 原始响应，触发浏览器回退时 `raw_html.browser_control` 同时保留普通浏览器 UA 原始响应，并通过 `raw_html.active_source` 标记实际检测数据源。
- `POST /api/v1/google-crawler/google-render`：执行抓取前置检查后，用无头 Chromium 检查 JavaScript 渲染、渲染前后内容差异、控制台异常和失败资源；`rendered_html` 返回执行 JavaScript 后的 DOM HTML 快照（展示上限 2MB）。
- `POST /api/v1/google-crawler/test`：一次返回上述两项结果，适合双 Tab 页面展示。

本地启用渲染前需安装 Chromium 并打开开关：

```bash
.venv/bin/playwright install chromium
ALLOW_PLAYWRIGHT=true ./start.sh
```

该功能是基于公开 User-Agent 和本地 Chromium 的近似模拟，不来自 Google IP，也不替代 Search Console URL Inspection。

若运行平台明确使用 `198.18.0.0/15` 作为受控公网代理地址，可设置
`ALLOW_BENCHMARK_PROXY_IPS=true`。默认关闭，其他私网、回环、链路本地和保留地址始终拒绝。

### 1. Site Snapshot 发现层

系统不再只抓首页，而是构建站点级快照：

- `homepage`
- `about`
- `service`
- `article/news`
- `case_study`

并为页面生成统一画像：

- `title / meta_description / canonical / lang`
- `headings / word_count`
- `has_faq / has_author / has_publish_date`
- `has_quantified_data / answer_first / has_tldr / has_update_log`
- `has_reference_section / has_inline_citations`
- `internal_link_count / external_link_count / descriptive_link_ratios`
- `heading_quality_score / information_density_score / chunk_structure_score`
- `json_ld_summary / entity_signals`

### 2. 5 个审计模块

- `visibility`
- `technical`
- `content`
- `schema`
- `platform`

### 3. 6 个汇总维度

| 维度 | 权重 | 说明 |
|---|---:|---|
| AI 可见性 | 25% | AI crawler 放行、citability、llms 指引、基础实体存在 |
| 品牌权威 | 20% | 外链质量、品牌提及、实体一致性、企业信息完整度 |
| 内容与 E-E-A-T | 20% | 内容深度、作者、日期、FAQ、数据点、证据引用、链接语义、结构质量 |
| 技术基础 | 15% | HTTPS、SSR、性能、Sitemap、安全头、图片、唯一 H1 与 freshness headers |
| 结构化数据 | 10% | JSON-LD、Organization、Article、Service、sameAs、机器日期、可见内容一致性 |
| 平台适配 | 10% | 面向 ChatGPT、Google AI、Perplexity、Gemini、Grok 的 readiness |

### 4. Full Audit 扩展诊断

除了站点级评分，系统还可以扩展采样更多页面，并返回：

- `page_diagnostics`

用于逐页查看：

- citability
- content
- technical
- schema
- overall score
- full issue list
- categorized issue details

说明：
- `page_diagnostics` 仍然基于 full audit 抓取到的画像页集合返回，不等于站点全部 URL。
- 但对于进入画像集合的每个页面，现在会返回完整 `issues` / `recommendations`，并按 `citability / content / evidence / linking / technical / semantic_html / schema / freshness / trust / ux` 分类展开。

### 5. AI 认知快照

`summary` 现在会额外返回一组不计分的站点级 AI 认知画像：

- `ai_perception.positive_percentage`
- `ai_perception.neutral_percentage`
- `ai_perception.controversial_percentage`
- `ai_perception.cognition_keywords`

用于描述 AI 可能如何“理解”该站点，例如更像：

- 行业先知
- 反应迅速
- 证据充分
- 结构清晰

### 6. Discovery Reuse

`audit_full` 支持直接复用传入的 `discovery`，避免重复抓取，方便：

- 批量任务
- 管道式处理
- 外部编排系统

### 7. 会员 AI 增强

`premium` 模式下可对以下模块做语义增强：

- `visibility`
- `content`
- `platform`
- `summary`

`technical` 和 `schema` 仍保持规则驱动，优先保证确定性。

### 8. 研究导向补强

在保持现有诊断层与表达层结构不变的前提下，v3 额外补充了几类更贴近论文观点的规则信号：

- `机器可读新鲜度`：响应头中的 `ETag / Last-Modified`，以及 Schema 中的 `datePublished / dateModified`
- `语义化 HTML`：唯一 `H1` 与标题层级质量联合判断
- `Schema 一致性`：JSON-LD 文本与页面可见内容的一致性评分
- `证据与引用`：参考资料区、内联引用、TL;DR、更新记录
- `RAG 友好链接`：内部/外部链接数量与描述性锚文本比例

---

## GEO Audit v3 的设计重点

### 从“首页检测”升级为“站点快照”

不再只看首页，而是围绕关键页面做判断，真正更像 GEO 审计引擎。

### 从“SEO 结构检查”升级为“AI 可引用性”

系统会输出：

- `homepage_citability`
- `best_page_citability`
- `citation_probability`

其中 `citation_probability` 为：

- `LOW`
- `MEDIUM`
- `HIGH`

### 从“基础结构化数据”升级为“机器可读一致性”

结构化数据不再只检查 `@type` 是否存在，还会额外关注：

- `BreadcrumbList`
- `datePublished / dateModified`
- `visible_alignment_score`

也就是：

- 机器是否能读到发布时间或更新时间
- Schema 中的名称、描述、FAQ 和主张是否和页面可见内容一致

这是一次必要的评分公式调整，但没有改变原有返回结构，只是补强了 `schema.checks / findings / recommendations` 的语义。

### 从“基础内容深度”升级为“证据与检索上下文”

内容层除了词数、FAQ、作者、日期、量化数据之外，还会补看：

- `has_reference_section`
- `has_inline_citations`
- `has_tldr`
- `has_update_log`
- `descriptive_internal_link_ratio`
- `descriptive_external_link_ratio`

这些信号用于更贴近论文中的：

- `Evidence & Citations`
- `RAG-friendly internal/external linking`
- `UX / microcontent / answer-first`

### 从“品牌存在”升级为“品牌权威”

品牌权威已经作为独立一级维度存在，并预留了：

- `BrandAuthorityService`

后续可以进一步拆成独立服务。

### 从“统一站点评分”升级为“平台适配”

当前支持 6 个 GEO 渠道视角：

- ChatGPT
- Google AI Mode
- Google AI Overviews
- Perplexity
- Gemini
- Grok

---

## Preview

### 1. Overview

![Overview](./preview/1%E3%80%81overview.png)

### 2. Summary

![Summary](./preview/2%E3%80%81summary.png)

### 3. Issues and TODO

![Issues and TODO](./preview/3%E3%80%81issue%26todo.png)

### 4. How to Fix

![How to Fix](./preview/4%E3%80%81how-to-fix.png)

### 5. Key Snapshot

![Key Snapshot](./preview/5%E3%80%81key-snapshot.png)

---

## 技术栈

- Python 3.10+
- FastAPI
- Pydantic
- Async task pipeline
- Optional OpenRouter LLM enhancement
- Optional Semrush backlink enrichment

---

## 运行方式

### 本地运行

```bash
python -m venv .venv     //启用配置文件
.venv\\Scripts\\activate  //启用虚拟环境
pip install -r requirements.txt  //安装相关依赖
uvicorn app.main:app --reload --port 8023  //指定端口启动脚本

然后浏览器打开  http://127.0.0.1:8023 就可以访问了
```

访问：

```text
http://127.0.0.1:8023
```

### Docker

推荐使用 Compose。服务器首次部署和以后更新均执行：

```bash
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` 会依次拉取最新代码、重建镜像、重建容器并等待健康检查。
容器参数统一维护在 `compose.yaml` 中；Google Render 的 Playwright 开关由
Compose 强制启用，镜像构建时会安装 Chromium。脚本优先使用新版
`docker compose`；仅有已停止维护的旧版 `docker-compose` v1 或未安装
Compose 时，会自动使用纯 Docker 命令。

常用维护命令：

```bash
docker compose ps
docker compose logs -f --tail 100 geo-audit-service
docker compose restart geo-audit-service
docker compose down
```

---

## 环境变量

### 基础

```env
APP_ENV=development
APP_DEBUG=true
HOST=0.0.0.0
PORT=8023
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=15
REQUEST_RETRIES=3
MAX_SITEMAP_URLS=50
MAX_SITEMAP_INDEXES=10
CACHE_TTL_DAYS=7
CACHE_DIR=.cache/audits
MYSQL_ENABLED=false
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=site_geo_audit
MYSQL_USER=site_geo_audit
MYSQL_PASSWORD=
MYSQL_CONNECT_TIMEOUT_SECONDS=5
MYSQL_READ_TIMEOUT_SECONDS=15
MYSQL_WRITE_TIMEOUT_SECONDS=15
MYSQL_POOL_SIZE=5
MYSQL_POOL_MAX_OVERFLOW=10
MYSQL_POOL_TIMEOUT_SECONDS=10
MYSQL_POOL_RECYCLE_SECONDS=1800
MYSQL_POOL_PRE_PING=true
MYSQL_RECOVERY_PROBE_INTERVAL_SECONDS=1
MYSQL_STORE_RAW_HTML=false
MYSQL_STORE_PARSED_CONTENT=true
DISCOVERY_FETCH_CONCURRENCY=8
DEFAULT_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
ALLOW_PLAYWRIGHT=false
GOOGLE_RENDER_TIMEOUT_SECONDS=25
GOOGLE_RENDER_NETWORK_IDLE_SECONDS=5
ALLOW_BENCHMARK_PROXY_IPS=false
```

### AI 增强

```env
LLM_REQUEST_TIMEOUT_SECONDS=30
DEFAULT_OPENROUTER_MODEL=openai/gpt-4.1
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=http://127.0.0.1:8023
OPENROUTER_APP_NAME=geo-audit-service
```

### Semrush

```env
SEMRUSH_ENABLED=true
SEMRUSH_API_KEY=
SEMRUSH_BASE_URL=https://api.semrush.com/
SEMRUSH_TARGET_TYPE=root_domain
```

### MySQL 站点资产库

启用后，系统会将站点主记录、URL 清单、页面快照、站点知识图谱投影和任务记录写入 MySQL：

- `geo_sites`
- `geo_urls`
- `geo_page_snapshots`
- `geo_graph_entities`
- `geo_graph_edges`
- `geo_graph_evidence`
- `geo_site_graph_snapshots`
- `geo_audit_tasks`

初始化表结构：

```bash
PYTHONPATH=. .venv/bin/python scripts/init_mysql_schema.py
```

建表 SQL 位于：

- `sql/mysql/001_geo_asset_schema.sql`

启用后，`discovery` 会优先复用 MySQL 中的站点资产；传入 `force_refresh=true` 时会清空该站点的页面快照并重新抓取。

当前 MySQL 基础设施包含：

- 连接池复用：`MYSQL_POOL_SIZE` + `MYSQL_POOL_MAX_OVERFLOW`
- 借出前探活：`MYSQL_POOL_PRE_PING=true`
- 长连接回收：`MYSQL_POOL_RECYCLE_SECONDS`
- 短暂故障后的自动恢复尝试：`MYSQL_RECOVERY_PROBE_INTERVAL_SECONDS`
- 操作级重试：`MYSQL_RETRY_ATTEMPTS` + `MYSQL_RETRY_BACKOFF_MS`

异步任务创建时还支持：

- `build_knowledge_graph`: 是否在 discovery 完成后，基于 MySQL 已保存的页面快照构建站点知识图谱投影；默认 `true`

知识图谱构建是附加流程：

- 默认不会改变现有审计打分逻辑
- 构建失败不会让原有 audit 任务失败
- 当前图谱以 MySQL 投影表形式落地，适合做站点级实体、页面、关系和证据溯源
- 任务完成后可通过 `GET /api/v1/tasks/{task_id}/knowledge-graph` 拉取整张图谱结构数据

---

## API

统一响应格式：

```json
{ "success": true, "data": {} }
{ "success": false, "message": "...", "errors": {} }
```

### 推荐：异步任务模式

提交任务：

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

查询任务：

```bash
curl http://127.0.0.1:8023/api/v1/tasks/{task_id}
```

完成后的 `result.summary` 会包含：

```json
{
  "composite_geo_score": 70,
  "status": "good",
  "summary": "...",
  "ai_perception": {
    "positive_percentage": 58,
    "neutral_percentage": 29,
    "controversial_percentage": 13,
    "cognition_keywords": ["Thought Leader", "Well-structured", "Evidence-led", "Trustworthy"]
  }
}
```

说明：

- `ai_perception` 不参与综合分计算
- 三个百分比相加恒为 `100`
- `cognition_keywords` 固定返回 4 个词
- `feedback_lang="zh"` 时，这些词会尽量中文化；JSON key 保持英文

导出报告：

```bash
curl -L http://127.0.0.1:8023/api/v1/tasks/{task_id}/report -o report.md
```

### 直接调用完整审计

```bash
curl -X POST http://127.0.0.1:8023/api/v1/audit/full \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

同步完整审计返回中同样包含 `summary.ai_perception`。
当 MySQL 资产库启用时，`result.discovery.asset_summary` 会返回当前站点的 URL 存量、页面快照数量、URL 类型分布和快照复用情况。

### 单独调用 discovery

```bash
curl -X POST http://127.0.0.1:8023/api/v1/discovery \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

---

## 适用场景

- 出海品牌官网 GEO 体检
- 外贸独立站 AI 可见性诊断
- 跨境 SaaS 官网内容与实体信号排查
- 代理商给客户做 GEO 报告
- 内部增长团队做站点 readiness 基线检查

---

## 一句话总结

**GEO Audit 不只是检查你的网站“有没有写对 SEO”，而是判断你的站点是否已经准备好进入 AI 搜索时代。**
