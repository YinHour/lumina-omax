# Open-Notebook 科研领域知识图谱（Knowledge Graph）设计思路与架构原理

本文档系统性总结了针对科研论文和实验报告场景，如何在现有的 Open-Notebook 架构下，从零设计并落地的混合（Hybrid）知识图谱抽取与检索系统。

## 1. 核心设计思路：面向科研场景的“Hub Node”建模

传统的知识图谱往往采用简单的实体-关系-实体（Entity-Relation-Entity）三元组模式。但在科研文献（如材料实验报告）中，单纯的三元组会遇到严重的信息断层问题：
例如：“在 90℃ 下，将材料 A 和化学品 B 混合，产生了 80% 转化率的结果”。如果直接提取为 `(材料A)-[产生]->(80%转化率)`，就会丢失关键的条件信息（90℃、化学品B）。

**解决方案：引入 `EXPERIMENT`（实验）枢纽节点（Hub Node）**
- **设计哲学**：我们将每一个具体的实验视为一个核心节点，所有参与该实验的要素全部辐射并连接到这个枢纽节点上。
- **关联路径**：
  - `(MATERIAL: 材料A) -[USES_MATERIAL]-> (EXPERIMENT: 实验1)`
  - `(CHEMICAL: 化学品B) -[CONTAINS_CHEMICAL]-> (EXPERIMENT: 实验1)`
  - `(CONDITION: 90℃) -[HAS_CONDITION]-> (EXPERIMENT: 实验1)`
  - `(EXPERIMENT: 实验1) -[YIELDS_RESULT]-> (RESULT: 80%转化率)`
- **优势**：这种 Hyper-relational Graph（超关系图）模型，完美保留了复杂科学实验中 N 元关系的完整上下文，使得多跳推理（Multi-hop Reasoning）不再会串接错误的实验条件。

## 2. 抽取引擎：无切块（Chunk-free）全篇处理与数值消歧

在文献内容提取环节，针对长文本科研报告，采用了突破性的处理策略：

- **废弃文本切块（Bypass Chunking）**：
  - 传统向量检索强依赖文本切块，但切块极易斩断跨段落的指代与因果关系。
  - **原理支撑**：我们利用了诸如 Qwen (qwen3.5-plus/deepseek-reasoner) 等模型高达 60k tokens 以上的庞大输出窗口（我们设定了 `max_tokens=60000`）。将单篇文档全量喂给 LLM 进行单次端到端抽取。
  
- **防幻觉数值消歧（Ambiguity Filter）**：
  - 科学文献中充满了无关数字（页码、图表序号、随机计量）。
  - 在 `prompts/kg/extraction.jinja` 的规则中，明确约束了数值（Number）的提取机制：**孤立的数值禁止成为节点**。它们只能作为实体或关系的 `description` 属性存储，或者在该数值是核心结论时，才能使用专门的 `RESULT` 实体类型。这大幅降低了图谱中的噪音节点。

## 3. 持久化层：SurrealDB 的原生图能力与高并发应对

现有的 SurrealDB 是一个强大的多模态数据库（文档+图+向量）。

- **图数据模型落地**：
  - 核心利用了 SurrealDB 的 `RELATE` 语句能力，这比关系型数据库中通过中间表做 JOIN 效率要高数个量级。
  - 我们创建了 `kg_entity` 表来存放节点（并对关键字段创建了 BM25 倒排索引），通过 `kg_relation` 表定义了明确的有向边。
  
- **UPSERT 与实体消歧（Entity Resolution）**：
  - 不同的文献可能提到同一个实体。为了融合（Merge）这些知识，我们引入了 `slugify` 算法，将实体名转换为唯一标识符作为 SurrealDB 的行 ID。
  - 在入库时使用 `UPSERT` 语法，当不同文档提取到同名同类实体时，它会自动合并，避免节点冗余。

- **并发事务冲突的化解（Transaction Conflict）**：
  - 在大批量异步协程（`asyncio.gather`）同时向 SurrealDB 写入交叉边和节点时，由于图库底层的强一致性事务机制，会导致剧烈的 Write-Conflict 报错。
  - **解决方案**：在 LangGraph 的 `ingest_to_db` 节点中，将网络 IO 层面的极致并发退坡为顺序的 `for loop` 处理（Sequential Write），以牺牲毫秒级的吞吐来换取底层事务的 100% 可靠性。

## 4. 检索融合：对 Ask 模式无缝入侵的 Hybrid RAG

这是架构上最优雅的一环。知识图谱检索并不作为独立的前端入口，而是作为一种底层的**检索能力增强（Augmentation）**，静默接入到现有的 Ask（多步提问）模式中。

**工作原理：入口节点召回 + 子图扩展（Subgraph Expansion）**
1. **语义分发**：当用户的复杂问题被 Ask 模式的 Agent 拆解为多个子检索词（例如：“什么是材料A的转化率”）后。
2. **多路召回 (`provide_answer` 节点)**：
   - 传统路线：针对这些词去执行 Vector Search（向量相似度）。
   - 图谱路线：同时并发触发 `graph_search`。系统先利用 BM25 全文检索在 `kg_entity` 表中找到包含关键词的“入口实体（Entry Nodes）”。
3. **1-hop 边遍历**：拿到入口实体后，系统立刻在 SurrealDB 中发起 1-hop 遍历，不仅把入口节点本身取出来，还把它通过关系连接的相邻实体（及其边描述）一并抓取。这就是所谓的**子图扩展（Subgraph Expansion）**。
4. **统一拼装**：最后，无论是向量召回的大段文本，还是图谱召回的高度结构化的“节点-边-节点”的路径文本，被无脑合并成一个 Context，统一丢给应答模型做局部摘要萃取。

这种架构设计，不仅保留了现有向量检索在处理长段落和模糊语义时的“软匹配”优势，又补充了知识图谱在跨越多个实体寻找确切逻辑链路时的“硬推理”能力。