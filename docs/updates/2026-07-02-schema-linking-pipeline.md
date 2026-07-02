# Schema Linking 编排

## 背景

系统已经具备表级召回、字段级匹配和 Join 路径推导能力，但这些能力此前还没有形成统一链路。为了让 SQL 生成阶段获得更小、更相关的 Schema 上下文，需要将三类能力串联为动态 Schema 构造流程，并接入 Prompt 构造。

## 本次变更

- 新增 Schema Linking 编排模块，将表召回、字段匹配和 Join 路径推导串联起来。
- 支持生成包含候选表、关键字段、锚表标记和 Join 条件的动态 Schema 文本。
- 为指标型问题增加事实表兜底逻辑，降低仅召回维度表导致无法聚合的风险。
- Prompt 构造支持可选动态 Schema 注入，并保留全量 Schema 回退机制。
- 查询 API 和流式查询接口增加动态 Schema 上下文开关。

## 关键文件

- `schema_linker.py`
- `prompt_builder.py`
- `main.py`
- `api_service.py`

## 验证结果

- Python 模块编译检查通过。
- 动态 Schema 构造链路验证通过。
- Prompt 在启用动态 Schema 时可以注入精简 Schema。
- API 请求模型包含动态 Schema 上下文开关。
- 敏感表述扫描通过。

## 后续衔接

后续可以对动态 Schema 的召回质量、字段排序和不可关联表处理策略继续做评估，并将最终效果纳入 SQL 生成准确率基准。
