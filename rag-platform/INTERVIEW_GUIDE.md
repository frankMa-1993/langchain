# RAG AI 增强检索平台 — 结构化面试题与参考答案

> **项目背景**：本项目为基于 FastAPI + React 的 RAG（Retrieval-Augmented Generation）对话系统，支持多知识库管理、混合检索（BM25 + 向量语义 + RRF 融合）、流式 SSE 对话、ARQ 异步文档入库，具备全链路降级能力。

---

## 面试说明

- **目标岗位**：后端工程师 / 算法工程师 / 全栈工程师（RAG 方向）
- **面试时长**：60–90 分钟
- **题目分级**：⭐ 初级（校招/1–3年） | ⭐⭐ 中级（3–5年） | ⭐⭐⭐ 高级（5年+ / 架构师）
- **建议组合**：根据候选人职级，从 7 个维度中各选 1–2 题，共 10–14 题

---

## 一、核心技术原理（向量数据库、Embedding、检索融合）

### 题 1.1 ⭐⭐ 向量数据库选型 — 为什么项目选用 Qdrant？

**问题**：
本项目使用 Qdrant 作为向量数据库。请对比 Qdrant、Milvus、Pinecone、Weaviate 四类向量数据库，说明在本项目场景下选择 Qdrant 的技术依据，以及什么情况下你会考虑迁移到 Milvus 或 Pinecone。

**参考答案**：


| 维度          | Qdrant                    | Milvus          | Pinecone | Weaviate   |
| ----------- | ------------------------- | --------------- | -------- | ---------- |
| **部署模式**    | 本地磁盘 / Docker / 云原生       | K8s 集群 / 分布式    | 全托管 SaaS | 本地 / 托管    |
| **资源占用**    | 低（可单机 256MB）              | 高（需 etcd/minio） | 无运维成本    | 中等         |
| **过滤查询**    | 原生 Payload Filter         | 标量过滤强           | 元数据过滤    | GraphQL 过滤 |
| **与本项目契合点** | `.qdrant/` 本地目录启动，零依赖开箱即用 | —               | —        | —          |


**选型依据**：

1. **本地优先策略**：项目默认配置 `QDRANT_URL=./.qdrant`，单机磁盘模式即可运行，适合开发环境和轻量部署。
2. **低运维成本**：对比 Milvus 需要 etcd、minio、多节点协调，Qdrant 单机版几乎零配置。
3. **Payload 过滤**：本项目需要在 `kb_id` 维度过滤，Qdrant 的 `must: [key=kb_id]` 过滤性能足够。
4. **客户端生态**：`qdrant-client>=1.14` 与 Python 异步生态兼容良好。

**迁移考虑**：

- **迁 Milvus**：当文档量 > 1000 万、需要多租户隔离（Collection 级别）、或需要 GPU 索引加速时。
- **迁 Pinecone**：当团队无运维人力、需要自动扩缩容、且预算充足时。

**评分要点**：

- 能说出 2 个以上对比维度（部署/运维/过滤/成本）→ 及格
- 能结合本项目"本地优先、零依赖"的设计哲学分析 → 良好
- 能给出明确的迁移阈值（文档量级、团队规模）→ 优秀

---

### 题 1.2 ⭐⭐⭐ Embedding 模型选型的工程化考量

**问题**：
本项目的 `.env` 中允许 `SEMANTIC_MODEL` 与 `CHAT_MODEL` 使用不同的 API Key 和模型。请回答：

1. 为什么 Embedding 模型和对话模型要解耦配置？
2. 如果预算有限，只能选一个 Embedding 模型部署在本地，你会选择什么模型（如 BGE、GTE、E5）？选型依据是什么？
3. 如何评估 Embedding 模型在业务数据上的效果？

**参考答案**：

**1. 解耦配置的原因**：

- **成本分离**：Embedding 调用量远大于 LLM（每篇文档每个 chunk 都要 embed），可以选用更便宜的专用 Embedding API（如 OpenAI `text-embedding-3-small` 或本地模型）。
- **模型迭代独立**：Embedding 模型升级不影响对话模型，反之亦然。
- **多租户/多语言场景**：不同知识库可用不同 Embedding 模型（如中文用 BGE-M3，英文用 text-embedding-ada-002）。
- **故障隔离**：Embedding 服务故障时可降级为纯 BM25，对话服务仍可运行。

**2. 本地 Embedding 选型**：


| 模型           | 维度   | 上下文长度 | 中文效果 | 推理速度 | 推荐场景        |
| ------------ | ---- | ----- | ---- | ---- | ----------- |
| BGE-M3       | 1024 | 8192  | 强    | 中等   | 多语言、需稀疏向量混合 |
| GTE-large-zh | 1024 | 512   | 强    | 快    | 纯中文、短文本     |
| E5-large-v2  | 1024 | 512   | 中等   | 快    | 英文为主        |


**推荐 BGE-M3**：

- 支持 100+ 语言，中文效果 SOTA 级；
- 支持 Dense + Sparse + Multi-vec 混合表示，与当前 HybridRetriever 的 BM25+语义架构理念一致；
- `FlagEmbedding` 推理库优化成熟，ONNX/TensorRT 加速后单卡 QPS 可达 500+。

**3. 效果评估方法**：

- **构建领域测试集**：从业务文档中抽样 500 条 query-doc 对，人工标注相关性（0/1）。
- **离线指标**：计算 Recall@K、MRR、NDCG@10。
- **对抗测试**：构造 hard negatives（同一文档的不同 chunk、相似主题的不同文档），测试模型区分能力。
- **A/B 测试**：线上灰度 10% 流量，对比切换 Embedding 模型后的用户满意度评分。

**评分要点**：

- 理解 Embedding 与 LLM 在调用频次和成本上的差异 → 及格
- 能给出具体模型名称并说明选型维度（语种/维度/上下文/速度） → 良好
- 能设计完整的 offline + online 评估方案 → 优秀

---

### 题 1.3 ⭐⭐⭐ 混合检索与 RRF 融合策略

**问题**：
本项目的 `HybridRetriever` 同时使用了 BM25 关键词检索和 Qdrant 语义检索，并通过 RRF（Reciprocal Rank Fusion）融合结果。请回答：

1. 为什么要用混合检索？BM25 和向量检索各自适合什么类型的 query？
2. RRF 的公式是什么？参数 `k=60` 在本项目中起什么作用？如何调参？
3. 当前代码中如果语义检索返回 12 条、BM25 返回 12 条、最终取 Top-6，是否存在结果截断风险？如何优化？

**参考答案**：

**1. 混合检索的必要性**：


| 检索方式 | 优势               | 劣势          | 适合 Query                        |
| ---- | ---------------- | ----------- | ------------------------------- |
| BM25 | 精确匹配、可解释性强、无向量延迟 | 无法理解同义词/语义  | "Python 3.9 安装教程"、"API 错误码 401" |
| 向量检索 | 语义理解、同义词泛化       | 对精确数字/专有名词弱 | "如何排查内存泄漏"、"性能优化最佳实践"           |


**互补性**：用户 query 中往往同时包含精确实体和语义描述，单一检索方式难以全覆盖。

**2. RRF 公式与调参**：

```
RRF_score(d) = Σ 1 / (k + rank_i(d))
```

- `k=60` 是平滑因子，防止高排名文档的得分过于悬殊，给低排名但多路同时命中的文档翻盘机会。
- **调参策略**：
  - `k` 越小 → 排名差异越敏感，倾向于相信高排名结果；
  - `k` 越大 → 越平等，适合两路检索质量相近的场景；
  - 可用网格搜索（k ∈ {20, 40, 60, 80, 100}）在标注集上选最优 NDCG。

**3. 截断风险与优化**：

**风险**：当前 `semantic_k=12`、`keyword_k=12`、`final_top_k=6`，若某路检索的 Top-6 全部未在另一路出现，RRF 融合后可能丢失优质结果。

**优化方案**：

- **增大每路召回量**：`semantic_k=keyword_k=50`，给 RRF 更充分的候选池。
- **动态截断**：根据 query 类型决定各路的 k 值。对含数字/英文缩写词 query，增大 keyword_k；对开放性问题，增大 semantic_k。
- **重排序（Rerank）**：在 RRF 后引入 Cross-Encoder（如 bge-reranker-v2-m3）做精排，Top-6 从精排结果取。

**评分要点**：

- 能举例说明 BM25 和向量检索的互补场景 → 及格
- 能写出 RRF 公式并解释 k 的作用 → 良好
- 能指出当前代码的截断风险并给出重排序等工程优化方案 → 优秀

---

## 二、端到端架构设计（数据流、服务划分、容错）

### 题 2.1 ⭐⭐ 文档入库与对话检索的数据流设计

**问题**：
请画出本项目中一条文档从上传到可检索的完整数据流，以及一条用户 query 从发起到获得流式响应的完整数据流。并指出其中可能成为瓶颈的环节。

**参考答案**：

**文档入库数据流**：

```
用户上传 → FastAPI Upload Endpoint
    → 校验（扩展名/大小） → 写入 ./uploads/{uuid}
    → 创建 Document(pending) + IngestTask
    → enqueue_ingest()
        ├── Redis 可用 → ARQ Job Queue → Worker 异步处理
        └── Redis 不可用 → run_in_executor() 同步降级处理
    → Worker: parse_document() → text_splitter() → embed_documents(batch=32)
    → 删除旧 chunks / 旧 Qdrant points → upsert Qdrant + 写入 PG chunks
    → 更新 Document(ready)
```

**对话检索数据流**：

```
用户提问 → POST /conversations/{id}/chat/stream
    → RAGService.stream_events()
        1. HybridRetriever.retrieve(query, kb_id)
            ├── embed_query() → Qdrant search(kb_id filter)
            ├── BM25Okapi on PG chunks
            └── RRF fusion → Top-6 chunks
        2. 发送 sources 事件（SSE）
        3. build_system_prompt(history + context)
        4. ChatOpenAI.astream() → delta 事件流
        5. 保存 user_msg + assistant_msg
        6. done 事件
```

**瓶颈环节**：

1. **Embedding 阶段**：`embed_documents()` 是同步调用外部 API，batch=32 在文档大时延迟高。
2. **BM25 全量加载**：每次对话都从 PG 加载该知识库全部 chunks 到内存建索引，知识库大时 OOM。
3. **Qdrant 单点**：本地 `.qdrant/` 是单机，并发高时磁盘 I/O 成为瓶颈。
4. **SSE 连接持有**：长连接占用 worker 线程，并发高时需要增加 worker 进程数。

**评分要点**：

- 能画出两路数据流并标注关键节点 → 及格
- 能指出 Embedding 和 BM25 全量加载两个核心瓶颈 → 良好
- 能给出瓶颈的量化影响（如大知识库 BM25 的内存占用估算） → 优秀

---

### 题 2.2 ⭐⭐⭐ 从单体到微服务的拆分策略

**问题**：
当前项目是典型的单体 FastAPI 应用。假设业务增长，需要支撑 1000 个知识库、10 万级日活用户，你会如何拆分微服务？请说明拆分后的服务边界、通信协议和数据一致性策略。

**参考答案**：

**服务拆分**：


| 服务                    | 职责                    | 技术选型                        |
| --------------------- | --------------------- | --------------------------- |
| **API Gateway**       | 路由、鉴权、限流、日志           | Kong / Nginx + Lua          |
| **Chat Service**      | 对话管理、SSE 流、上下文组装      | FastAPI + WebSocket(可选)     |
| **Retrieval Service** | 检索编排（Hybrid / Rerank） | FastAPI + gRPC              |
| **Ingest Service**    | 文档解析、分块、Embedding 流水线 | ARQ / Celery + 独立 Worker    |
| **Vector Store**      | Qdrant 集群             | Qdrant 分布式                  |
| **Metadata Store**    | PostgreSQL 集群         | PG + 读写分离                   |
| **Embedding Service** | Embedding 模型推理        | Triton / vLLM + BGE-M3 ONNX |
| **Rerank Service**    | Cross-Encoder 精排      | Triton + bge-reranker       |


**通信协议**：

- **同步**：Chat → Retrieval 用 gRPC（低延迟、强类型）。
- **异步**：Ingest 完成后通知 Chat Service 刷新缓存，用 Kafka / RabbitMQ。
- **事件驱动**：文档状态变更（pending → ready）发事件，前端轮询可改为 WebSocket push。

**数据一致性**：

- **最终一致性**：Qdrant 向量与 PostgreSQL chunks 允许短暂不一致（秒级），以 PG 为准。
- **补偿机制**：Ingest 失败时写入死信队列，定时任务扫描并重试。
- **分布式事务**：文档重索引时，先写 PG 事务标记为 "reindexing"，成功后再改为 "ready"，失败回滚。

**评分要点**：

- 能给出 4 个以上服务的合理拆分 → 及格
- 能区分同步/异步通信的适用场景 → 良好
- 能设计向量与元数据的一致性方案和补偿机制 → 优秀

---

### 题 2.3 ⭐⭐ 全链路降级与容错机制

**问题**：
本项目的 `config.py` 和 `services/` 中设计了多层降级策略（Redis 降级为内存、Qdrant 降级为纯 BM25、LLM 降级为本地摘要）。请评价这套降级设计的优缺点，并补充你认为还缺少的降级场景。

**参考答案**：

**现有降级策略梳理**：


| 依赖                 | 正常模式          | 降级模式                          | 实现位置                  |
| ------------------ | ------------- | ----------------------------- | --------------------- |
| Redis              | ARQ 异步队列      | `loop.run_in_executor()` 同步处理 | `document_service.py` |
| Redis              | Redis 缓存/限流   | 内存字典缓存                        | `cache.py`            |
| Qdrant / Embedding | 语义检索          | 纯 BM25 关键词检索                  | `hybrid_retriever.py` |
| LLM API            | ChatOpenAI 流式 | `_local_fallback_answer()`    | `rag_service.py`      |
| PostgreSQL         | PG 元数据        | SQLite 本地文件                   | `database.py`         |


**优点**：

1. **分层防御**：每层依赖独立降级，不级联故障。
2. **用户体验不中断**：即使 LLM 挂了，用户仍能拿到检索摘要；即使向量库挂了，仍能关键词搜索。
3. **开发友好**：本地零外部依赖即可启动。

**缺点**：

1. **降级后性能无保障**：内存缓存无 LRU 淘汰，大流量下可能 OOM。
2. **降级后质量不可测**：纯 BM25 对语义 query 效果差，但用户无感知，可能体验下降却不自知。
3. **无自动恢复探测**：Redis 恢复后不会自动切回，需重启服务。
4. **无分级降级**：比如 LLM 降级直接变成摘要，没有中间态（如换更便宜的备用模型）。

**建议补充的降级场景**：

1. **Embedding 服务降级**：主模型故障时切换到备用模型（如从 `text-embedding-3-large` 降级到 `text-embedding-3-small`）。
2. **BM25 索引降级**：大知识库内存放不下时，降级为 PG `LIKE '%query%'` 模糊查询（慢但可用）。
3. **流式降级**：LLM 流式故障时，降级为非流式一次性返回（兼容更多模型）。
4. **自动恢复**：增加健康检查轮询，依赖恢复后自动切回正常模式。

**评分要点**：

- 能列出至少 3 个现有降级策略 → 及格
- 能分析出"无自动恢复"或"质量不可感知"等深层问题 → 良好
- 能设计分级降级和自动恢复机制 → 优秀

---

## 三、性能与可扩展性（QPS、延迟、增量更新）

### 题 3.1 ⭐⭐⭐ 百万级文档 QPS 优化与 P99<500ms

**问题**：
当前项目使用本地 SQLite + 本地 Qdrant，显然无法支撑大规模。假设需要支撑 100 万文档、100 QPS 的对话流量，且 P99 延迟 < 500ms，请给出系统性的优化方案。

**参考答案**：

**1. 检索层优化（目标：< 100ms）**：

- **Qdrant 集群化**：部署 3 节点 Qdrant 集群，分片数 = 节点数 × 2，查询并行化。
- **HNSW 参数调优**：`ef=128`、`m=16`，在召回率和延迟间平衡。
- **BM25 预建索引**：不再每次查询全量加载，改用 `whoosh` / `elasticsearch` 持久化索引，增量更新。
- **缓存检索结果**：相同 query 的检索结果缓存 5 分钟（Redis），命中率预计 30%+。

**2. Embedding 层优化（目标：< 50ms）**：

- **本地部署 Embedding**：使用 `optimum[onnxruntime]` 将 BGE-M3 转为 ONNX，Batch=32，单卡 QPS 500+。
- **Embedding 缓存**：query 的 embedding 结果缓存 24 小时，避免重复编码。

**3. LLM 层优化（目标：< 300ms 首 token）**：

- **上下文压缩**：用 LLM 对检索到的 6 个 chunk 做摘要压缩，减少输入 token 数。
- **Prompt 缓存**：对高频系统 prompt 启用 vLLM 的 Prefix Caching。
- **流式响应**：保持 SSE，首 token < 300ms 即可让用户感知到响应开始。

**4. 架构层优化**：

- **读写分离**：PostgreSQL 主从分离，查询走从库。
- **连接池**：PG 连接池大小 = `2 × CPU 核数 + 1`，避免连接风暴。
- **CDN / 边缘缓存**：前端静态资源 CDN 加速。

**5. 延迟预算分配**：


| 环节            | 预算        | 优化后预估      |
| ------------- | --------- | ---------- |
| Embedding     | 50ms      | 30ms（缓存命中） |
| Qdrant 检索     | 50ms      | 30ms       |
| BM25 检索       | 30ms      | 20ms（预建索引） |
| RRF + Rerank  | 50ms      | 40ms       |
| LLM 首 token   | 300ms     | 200ms      |
| 网络/序列化        | 20ms      | 10ms       |
| **Total P99** | **500ms** | **330ms**  |


**评分要点**：

- 能给出检索/Embedding/LLM 三层的具体优化手段 → 及格
- 能做延迟预算分配并给出量化预估 → 良好
- 能提到 HNSW 参数、ONNX 加速、Prefix Caching 等深度优化点 → 优秀

---

### 题 3.2 ⭐⭐ 增量更新与实时性保障

**问题**：
当前文档更新需要全量重索引（先删旧 chunks/旧 Qdrant points，再重新 embed）。如果业务要求新文档上传后 30 秒内可检索，如何设计增量更新机制？

**参考答案**：

**问题分析**：
当前 `ingest_document_sync()` 的逻辑是：解析 → 分块 → 删除旧数据 → 插入新数据。对于大文档，重索引可能需要分钟级。

**增量更新方案**：

1. **Diff 感知更新**：
  - 文档上传时计算文件哈希（如 SHA-256）。
  - 若哈希未变 → 跳过处理。
  - 若哈希变化 → 对比旧 chunks 和新 chunks 的 `content_hash`，仅更新变化的 chunk。
2. **流式分块插入**：
  - 边解析边分块，每生成一个 chunk 立即 embed + upsert Qdrant，不等全文解析完成。
  - 前端可显示 "已索引 30%" 的进度。
3. **近实时可见性**：
  - Qdrant 默认 `wait=true` 同步写入，确保立即可检索。
  - 或配置 `consistency=ALL` 保证强一致性。
4. **删除优化**：
  - 旧 chunks 标记为 `deleted_at`（软删除），定时任务物理清理，避免阻塞写入。
  - Qdrant 使用 `payload` 中的 `deleted` 标记，检索时过滤。
5. **并发控制**：
  - 同一文档的多次更新需要串行化（Redis 分布式锁），避免竞争条件导致数据不一致。

**代码层面改造**：

```python
# 伪代码：增量更新逻辑
async def incremental_ingest(doc_id, file_content):
    new_hash = sha256(file_content)
    old_doc = await get_document(doc_id)
    if old_doc and old_doc.file_hash == new_hash:
        return  # 无变化，跳过

    new_chunks = parse_and_split(file_content)
    old_chunks = await get_chunks(doc_id)

    # 计算 diff
    to_delete = [c for c in old_chunks if c.content_hash not in {nc.content_hash for nc in new_chunks}]
    to_insert = [nc for nc in new_chunks if nc.content_hash not in {c.content_hash for c in old_chunks}]

    await delete_chunks(to_delete)      # 软删除
    await insert_chunks(to_insert)      # 增量插入
    await update_document(doc_id, file_hash=new_hash)
```

**评分要点**：

- 能提出基于哈希的 diff 感知 → 及格
- 能设计软删除 + 定时清理机制 → 良好
- 能考虑并发控制和流式分块插入 → 优秀

---

## 四、质量评估体系（召回率、BLEU、幻觉率、自动化测试）

### 题 4.1 ⭐⭐⭐ 检索与生成质量的评测方案设计

**问题**：
业务要求：检索召回率 ≥ 95%、答案 BLEU ≥ 45、幻觉率 < 3%。请设计一套可落地的评测方案和自动化测试框架，并说明如何在 CI/CD 中集成。

**参考答案**：

**1. 评测数据集构建**：


| 数据集                   | 规模    | 标注方式                          | 用途           |
| --------------------- | ----- | ----------------------------- | ------------ |
| **Golden Set**        | 500 对 | 业务专家标注 query + 标准答案 chunk     | 检索召回率评测      |
| **QA Pair Set**       | 200 对 | 人工书写理想答案                      | 生成质量 BLEU 评测 |
| **Hallucination Set** | 100 对 | 构造边界 case（无答案 query、模糊 query） | 幻觉率评测        |


**2. 指标计算**：

- **检索召回率 Recall@K** = 标准答案 chunk 出现在 Top-K 中的比例。
  ```python
  recall = sum(1 for q in golden_set if golden_chunk[q] in retrieved_chunks[q][:K]) / len(golden_set)
  ```
- **BLEU-4**：用 `sacrebleu` 计算生成答案与参考答案的 n-gram 重叠。
- **幻觉率**：
  - 自动指标：用 NLI model（如 `moritzlaurer/DeBERTa-v3-large-zeroshot-v2.0`）判断答案是否被 context 支撑。
  - 人工抽检：每周抽检 50 条，标记"包含幻觉"的比例。

**3. 自动化测试框架**：

```python
# tests/evaluation/test_rag_quality.py
import pytest
from rag_service import RAGService
from hybrid_retriever import HybridRetriever

class TestRetrievalQuality:
    @pytest.mark.parametrize("query,expected_chunk_id", load_golden_set())
    async def test_recall_at_6(self, query, expected_chunk_id):
        chunks = await HybridRetriever().retrieve(query, kb_id="test_kb")
        chunk_ids = [c.id for c in chunks]
        assert expected_chunk_id in chunk_ids, f"Query '{query}' missed golden chunk"

class TestGenerationQuality:
    @pytest.mark.parametrize("query,expected_answer", load_qa_pairs())
    async def test_bleu_score(self, query, expected_answer):
        answer = await RAGService().answer(query, kb_id="test_kb")
        bleu = compute_bleu(answer, expected_answer)
        assert bleu >= 0.45, f"BLEU {bleu} < 0.45 for query '{query}'"
```

**4. CI/CD 集成**：

- **Pre-commit**：单元测试（解析、分块等纯函数）。
- **PR 阶段**：运行 Golden Set 评测（~5 分钟），召回率下降 > 2% 自动阻断合并。
- **Nightly**：全量 QA Pair Set + Hallucination Set 评测（~30 分钟），生成质量报告推送 Slack。
- **Release 前**：人工抽检 100 条，确认幻觉率达标后打 tag。

**5. 监控告警**：

- 线上真实 query 抽样 5%，用 NLI 模型实时检测幻觉，幻觉率 > 3% 触发告警。

**评分要点**：

- 能定义三个指标的计算方式 → 及格
- 能写出 pytest 自动化测试代码框架 → 良好
- 能设计 CI/CD 集成策略和线上幻觉监控 → 优秀

---

### 题 4.2 ⭐⭐ 当前项目测试体系缺失的补全方案

**问题**：
经调研，当前项目中没有任何测试文件。如果由你负责搭建测试体系，请给出测试策略（单元测试/集成测试/E2E 测试的覆盖范围）、关键测试用例设计，以及 Mock 外部依赖（Qdrant、OpenAI API、Redis）的方案。

**参考答案**：

**1. 测试金字塔策略**：


| 层级         | 比例  | 工具                           | 覆盖范围                        |
| ---------- | --- | ---------------------------- | --------------------------- |
| **单元测试**   | 70% | pytest + pytest-asyncio      | 解析、分块、RRF 算法、Prompt 构建、配置校验 |
| **集成测试**   | 20% | pytest + TestClient + Docker | API 端点、DB 事务、缓存读写           |
| **E2E 测试** | 10% | Playwright                   | 前端上传 → 后端处理 → 对话交互          |


**2. 关键测试用例**：

**单元测试**：

- `test_recursive_splitter()`：验证 1000 字符文本按 chunk_size=1000, overlap=200 正确分割。
- `test_rrf_fusion()`：构造固定排名的语义/关键词列表，验证 RRF 输出顺序。
- `test_prompt_length_limit()`：验证上下文 + 历史超过模型 max_tokens 时的截断逻辑。

**集成测试**：

- `test_upload_and_ingest()`：上传 PDF → 轮询状态 → 确认 chunks 写入 PG 和 Qdrant。
- `test_chat_stream()`：发送 query → 验证 SSE 事件序列（sources → delta → done）。
- `test_rate_limit()`：连续发送 61 次请求，验证第 61 次返回 429。

**E2E 测试**：

- `test_full_workflow()`：前端创建知识库 → 上传文档 → 等待状态 ready → 提问 → 验证答案包含来源。

**3. Mock 方案**：

```python
# Mock OpenAI API
@pytest.fixture
def mock_openai():
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(return_value=httpx.Response(200, json={
            "choices": [{"delta": {"content": "test answer"}}]
        }))
        yield mock

# Mock Qdrant
class MockQdrantClient:
    def search(self, **kwargs):
        return [ScoredPoint(id="1", score=0.9, payload={"content": "mock chunk"})]

# Mock Redis
@pytest.fixture
def mock_redis():
    fakeredis.aioredis.FakeRedis().flushall()
    return fakeredis.aioredis.FakeRedis()
```

**4. CI 配置示例**（`.github/workflows/test.yml`）：

```yaml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres: { image: postgres:16 }
      qdrant: { image: qdrant/qdrant:v1.12 }
      redis: { image: redis:7 }
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt && pip install pytest pytest-asyncio httpx
      - run: pytest tests/ -v --cov=app --cov-report=xml
      - run: bash <(curl -s https://codecov.io/bash)
```

**评分要点**：

- 能划分三层测试并给出比例 → 及格
- 能写出具体测试用例和 Mock 代码 → 良好
- 能设计 CI/CD 配置和覆盖率门禁 → 优秀

---

## 五、安全合规（数据脱敏、权限、审计）

### 题 5.1 ⭐⭐⭐ 企业级 RAG 系统的安全合规设计

**问题**：
当前项目仅有一个全局 `API_KEY` 做简单鉴权。假设要部署到金融/医疗行业，需要满足等保三级要求，请设计一套完整的安全合规方案，覆盖数据脱敏、权限控制、审计日志。

**参考答案**：

**1. 数据脱敏**：


| 数据类型       | 脱敏策略                                      | 实现位置               |
| ---------- | ----------------------------------------- | ------------------ |
| **身份证号**   | 正则匹配 `\d{17}[\dXx]` → 替换为 `******`**      | `parsing.py` 解析后处理 |
| **手机号**    | `1\d{10}` → `138****8888`                 | 同上                 |
| **银行卡号**   | 保留后 4 位                                   | 同上                 |
| **PII 实体** | 用 Presidio / 自研 NER 模型识别并替换为 `[PERSON_1]` | 独立脱敏微服务            |


**实现方式**：

- 在 `parse_document()` 后增加 `sanitize_pii(text)` 步骤，默认启用，允许管理员关闭。
- 对 Embedding 和检索使用脱敏后的文本，但原始文件加密存储（AES-256）以备审计。

**2. 权限控制（RBAC）**：

```python
# 扩展 ORM 模型
class User(Base):
    id = Column(Integer, primary_key=True)
    role = Column(Enum("admin", "editor", "viewer"))

class KnowledgeBase(Base):
    # ... 现有字段 ...
    owner_id = Column(ForeignKey("users.id"))
    acl = Column(JSON)  # {"users": [1,2,3], "groups": [10]}
```

- **Admin**：全权限，可管理用户和全局配置。
- **Editor**：可创建/编辑知识库、上传文档、查看对话。
- **Viewer**：仅可查看指定知识库的文档和对话。
- **知识库级隔离**：`HybridRetriever` 检索时强制过滤 `kb_id IN user.accessible_kb_ids()`。

**3. 审计日志**：

```python
# models/audit_log.py
class AuditLog(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    action = Column(Enum("UPLOAD", "DELETE", "CHAT", "EXPORT"))
    resource_type = Column(String)
    resource_id = Column(Integer)
    ip_address = Column(String)
    user_agent = Column(String)
    request_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON)  # 如：query 摘要、token 消耗
```

- **全量记录**：所有写操作（上传、删除、修改）和敏感读操作（导出、对话）必须记录。
- **不可篡改**：审计日志单独写入只读数据库（或 WORM 存储），应用无删除权限。
- **合规报告**：每月自动生成审计报告，包含：用户活跃度、异常访问（如非工作时间大量下载）、数据导出记录。

**4. 传输与存储安全**：

- **TLS 1.3**：所有 API 强制 HTTPS。
- **字段级加密**：数据库中 `messages.content` 和 `chunks.content` 敏感字段启用列级加密。
- **密钥管理**：使用 AWS KMS / HashiCorp Vault 管理加密密钥，不硬编码在 `.env`。

**评分要点**：

- 能列出 2 类以上 PII 脱敏策略 → 及格
- 能设计 RBAC 权限模型并关联到知识库隔离 → 良好
- 能设计不可篡改审计日志和合规报告机制 → 优秀

---

## 六、实际业务落地（冷启动、标注闭环、反馈迭代）

### 题 6.1 ⭐⭐ 冷启动与数据准备策略

**问题**：
一个新客户接入 RAG 系统，手头有 1 万份历史文档（PDF/Word/扫描件），但没有任何问答历史。如何在 2 周内完成数据准备并上线可用？请给出具体执行计划。

**参考答案**：

**Week 1：数据治理与入库**


| 天数  | 任务                                                 | 产出           |
| --- | -------------------------------------------------- | ------------ |
| 1–2 | **文档清洗**：去重（MD5）、格式统一（扫描件 OCR）、分类（按业务主题）           | 清洗后文档 9500 份 |
| 3–4 | **质量抽检**：抽样 100 份人工检查解析质量，标记解析错误的类型（表格错乱/编码错误）     | 解析质量报告       |
| 5   | **分块策略调优**：根据文档类型调整 chunk_size（技术手册 1500/法律合同 800） | 分块配置参数       |
| 6–7 | **批量入库**：并行入库（控制 Qdrant 写入速率 < 1000 point/s），监控失败率 | 入库完成，99% 成功  |


**Week 2：评测与优化**


| 天数    | 任务                                         | 产出                    |
| ----- | ------------------------------------------ | --------------------- |
| 8–9   | **种子问题生成**：用 LLM 基于文档生成 500 个候选问题，业务专家审核   | 200 个种子问题             |
| 10–11 | **种子问题测试**：运行种子问题，人工评估答案质量，标记 bad case     | Bad case 列表（目标 < 20%） |
| 12–13 | **Bad case 修复**：调优 prompt / 调整分块 / 补充同义词词典 | 修复后重新测试               |
| 14    | **上线准备**：编写用户手册、培训客户管理员、配置监控告警             | 正式上线                  |


**关键技术点**：

- **OCR 兜底**：对扫描件先用 `paddleocr` / `tesseract` 提取文本，人工校验关键页。
- **领域词典**：导入客户行业术语（如金融领域的 "ABS"、"MPA"），增强 BM25 匹配。
- **Embedding 微调**：若有 1000+ 标注的 query-doc 对，可用 LoRA 微调 BGE-M3（1–2 天）。

**评分要点**：

- 能给出两周的具体时间线 → 及格
- 能提到 OCR、领域词典、Embedding 微调等关键技术 → 良好
- 能设计 bad case 修复的闭环流程 → 优秀

---

### 题 6.2 ⭐⭐⭐ 用户反馈驱动的持续迭代体系

**问题**：
系统上线后，如何收集用户反馈并转化为模型/系统的迭代？请设计一个完整的反馈闭环，包括：反馈收集方式、数据存储、归因分析、以及迭代动作。

**参考答案**：

**1. 反馈收集方式**：


| 反馈类型         | 收集方式                      | 存储位置                    |
| ------------ | ------------------------- | ----------------------- |
| **👍/👎 点踩** | 前端每条答案旁放置 thumbs up/down  | `message_feedback` 表    |
| **原因选择**     | 点踩后弹出多选（答案不对/没找到/看不懂/有幻觉） | 同上                      |
| **人工修改**     | 允许用户编辑答案并保存为"标准答案"        | `message_correction` 表  |
| **对话评分**     | 会话结束后 1–5 星评分             | `conversation_rating` 表 |


**2. 归因分析框架**：

收到点踩后，自动归因到以下环节：

```python
# 归因决策树
def root_cause_analysis(query, answer, sources, feedback):
    if not sources:
        return "RETRIEVAL_MISS"  # 检索未找到相关文档
    if max(s.score for s in sources) < 0.7:
        return "RETRIEVAL_LOW_CONFIDENCE"  # 检索质量差
    if not nli_verify(answer, sources):
        return "HALLUCINATION"  # 幻觉
    if semantic_similarity(answer, expected) < 0.5:
        return "GENERATION_QUALITY"  # 生成质量差（非幻觉但没用）
    return "UNKNOWN"
```

**3. 迭代动作矩阵**：


| 根因                           | 占比  | 迭代动作                                   | 负责人   |
| ---------------------------- | --- | -------------------------------------- | ----- |
| **RETRIEVAL_MISS**           | 40% | 补充同义词、调优 chunk_size、添加 FAQ 文档          | 算法工程师 |
| **RETRIEVAL_LOW_CONFIDENCE** | 25% | 引入 Rerank 模型、微调 Embedding              | 算法工程师 |
| **HALLUCINATION**            | 15% | Prompt 中加 "严格基于上下文" 约束、调低 temperature  | 算法工程师 |
| **GENERATION_QUALITY**       | 15% | 优化 System Prompt（加 Few-shot 示例）、更换 LLM | 算法工程师 |
| **UNKNOWN**                  | 5%  | 人工分析，补充归因类别                            | 产品经理  |


**4. 数据闭环**：

- **每周**：自动生成反馈报告（点踩率、归因分布、Top-10 bad query）。
- **每月**：将用户修正的答案纳入 Golden Set，重新评测系统指标。
- **每季度**：基于积累的数据微调 Embedding 模型或 LLM（如有 5000+ 高质量标注对）。

**评分要点**：

- 能设计 2 种以上反馈收集方式 → 及格
- 能构建归因分析决策树 → 良好
- 能将归因结果映射到具体迭代动作并形成闭环 → 优秀

---

## 七、故障排查与调优（Bad Case、Prompt、微调）

### 题 7.1 ⭐⭐⭐ Bad Case 系统性归因与调优

**问题**：
用户反馈一个典型 bad case：query 是 "2024 年 Q3 营收增长了多少？"，系统返回了 2023 年的数据。请给出系统性的排查思路，定位问题环节，并给出至少 3 种不同层面的修复方案。

**参考答案**：

**排查思路（分层定位）**：

1. **检索层排查**：
  - 检查 Top-6 chunks 是否包含 "2024 年 Q3" 相关内容。
  - 若未包含 → **检索遗漏**：可能是 Embedding 未理解 "Q3" 与 "第三季度" 的关联，或 BM25 对数字匹配弱。
  - 若包含但排名靠后 → **排序问题**：RRF 融合时 2023 年的文档因词频高被排前。
2. **生成层排查**：
  - 检查 chunks 中是否同时存在 2023 和 2024 的数据。
  - 若存在 → **LLM 未区分年份**：prompt 中未明确要求按年份筛选。
  - 若不存在 2024 数据 → **知识库缺失**：文档未更新到 2024 年 Q3。
3. **数据层排查**：
  - 检查原始文档中是否真的有 2024 Q3 数据。
  - 若文档是扫描件 → **OCR 错误**：数字识别错误（如 2024 → 2023）。

**修复方案**：


| 层级      | 方案                                                          | 实施成本 | 预期效果 |
| ------- | ----------------------------------------------------------- | ---- | ---- |
| **数据层** | 更新知识库，补充 2024 Q3 财报；扫描件人工校对 OCR                             | 高    | 根治   |
| **检索层** | 对时间类 query 做实体识别（NER），在检索时强制过滤 `year=2024` 的 payload        | 中    | 精准召回 |
| **检索层** | 引入 Rerank 模型，对含时间词的 query 提升时间匹配度的权重                        | 中    | 排序改善 |
| **生成层** | Prompt 中加约束："如果上下文中有多个年份的数据，优先回答最近一年的数据。若找不到指定年份，明确告知用户。"   | 低    | 减少幻觉 |
| **生成层** | 使用 Function Calling：识别时间实体 → 先查询数据库确认是否有 2024 Q3 数据 → 再生成答案 | 高    | 完全避免 |


**评分要点**：

- 能按检索/生成/数据三层排查 → 及格
- 能给出至少 2 个不同层级的修复方案 → 良好
- 能设计 NER 过滤、Function Calling 等高阶方案 → 优秀

---

### 题 7.2 ⭐⭐ Prompt 工程与模型微调抉择

**问题**：
系统上线后发现：对于 "总结这份文档的核心观点" 类 query，生成的答案过于冗长且抓不住重点。你会先尝试 Prompt 调优还是模型微调？各自的适用边界是什么？请给出具体的 Prompt 优化版本和微调数据构造方案。

**参考答案**：

**决策逻辑**：


| 维度       | Prompt 调优      | 模型微调               |
| -------- | -------------- | ------------------ |
| **成本**   | 低（几小时）         | 高（标注数据 + GPU 训练）   |
| **效果上限** | 受基础模型能力限制      | 可突破基础模型局限          |
| **适用场景** | 格式控制、风格调整、简单约束 | 复杂推理、领域知识内化、长期记忆   |
| **数据需求** | 无              | 需要 500–5000 条高质量标注 |


**结论**：先 Prompt 调优，若效果仍不达标再微调。

**Prompt 优化方案**：

```markdown
# 原始 Prompt（问题）
请根据以下上下文回答用户问题：
{context}
用户问题：{query}

# 优化后 Prompt
你是一位专业的文档分析师，擅长用简洁的语言提炼核心观点。

## 任务要求
1. 回答必须严格基于提供的上下文，不要引入外部知识。
2. 使用 "总-分" 结构：先用 1 句话概括核心观点，再分 2-4 条列出支撑论据。
3. 每条论据不超过 30 字。
4. 如果上下文信息不足以回答，直接回复 "根据现有资料无法确定"。

## 上下文
{context}

## 用户问题
{query}

## 输出格式
核心观点：[一句话概括]
1. [论据一]
2. [论据二]
...
```

**微调数据构造方案**（若 Prompt 调优后仍不达标）：

1. **数据采集**：
  - 从线上日志中抽取 1000 条 "总结类" query。
  - 用 GPT-4 生成参考答案（作为初始标注）。
  - 业务专家审核并修正 500 条高质量 pair。
2. **数据格式**（LLaMA-Factory / Unsloth）：

```json
{
  "instruction": "请总结以下文档的核心观点，要求简洁、结构化输出。",
  "input": "[文档正文...]",
  "output": "核心观点：本文提出了xxx。\n1. 论据一...\n2. 论据二..."
}
```

1. **微调配置**：
  - 模型：Qwen2.5-7B-Instruct（中文总结能力强，资源消耗适中）。
  - 方法：LoRA，rank=64，学习率 1e-4。
  - 数据：500 条总结类数据 + 2000 条通用指令数据（防止灾难性遗忘）。
  - 训练：2 个 epoch，A100 40G 约 30 分钟。

**评分要点**：

- 能比较 Prompt 和微调的适用边界 → 及格
- 能写出结构化的优化 Prompt（含格式约束） → 良好
- 能给出完整的微调数据构造和训练配置方案 → 优秀

---

## 面试评分总表


| 考察维度   | 题目编号    | 初级目标    | 中级目标     | 高级目标              |
| ------ | ------- | ------- | -------- | ----------------- |
| 核心技术原理 | 1.1–1.3 | 能解释技术选型 | 能对比多种方案  | 能设计改进方案并量化收益      |
| 端到端架构  | 2.1–2.3 | 能描述数据流  | 能识别瓶颈    | 能设计微服务拆分和一致性方案    |
| 性能与扩展性 | 3.1–3.2 | 能列出优化点  | 能做延迟预算   | 能设计增量更新和并发控制      |
| 质量评估   | 4.1–4.2 | 能定义指标   | 能写测试用例   | 能设计 CI/CD 集成和线上监控 |
| 安全合规   | 5.1     | 能列出安全点  | 能设计 RBAC | 能设计审计和合规报告        |
| 业务落地   | 6.1–6.2 | 能描述流程   | 能制定计划    | 能设计反馈闭环和迭代体系      |
| 故障排查   | 7.1–7.2 | 能定位问题   | 能给出修复方案  | 能设计系统性归因框架        |


**总体评级**：

- **通过（P）**：5 个维度以上达到中级目标。
- **良好（G）**：7 个维度均达到中级，且 3 个以上达到高级目标。
- **优秀（E）**：5 个以上维度达到高级目标，且能提出超越参考答案的见解。

---

> **使用建议**：
>
> 1. 初面（45 分钟）：从 ⭐ 和 ⭐⭐ 中选取 6–8 题，覆盖全部维度。
> 2. 终面（60 分钟）：从 ⭐⭐⭐ 中选取 4–6 题，深入追问工程细节和量化分析。
> 3. 可根据候选人回答情况灵活追问，如问到 Qdrant 时追问 HNSW 索引原理，问到 RRF 时追问 Learned Sparse Retrieval。

