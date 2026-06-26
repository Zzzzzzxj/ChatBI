# Text2SQL 查询链路

## 背景

项目需要从脚本验证进入可运行系统，把自然语言问题、Prompt 构造、模型调用、SQL 执行和结果展示串成完整闭环。

## 本次变更

- 增加 Zero-shot、Schema + Few-shot、结构化约束三种 Text2SQL 原型。
- 引入统一配置、模型客户端、数据库客户端、查询解析器和结果格式化器。
- 建立命令行入口，支持直接输入自然语言问题并返回 SQL 与查询结果。
- 接入 SiliconFlow OpenAI-compatible 调用方式，并适配 Qwen 模型配置。

## 关键文件

- `text2sql_v0.py`
- `text2sql_v1.py`
- `text2sql_v2.py`
- `main.py`
- `llm_client.py`

## 验证结果

- Python 编译检查通过。
- SiliconFlow API 调用正常。
- 示例问题“查询已完成订单的总数量”可返回 `completed_order_count = 5`。
- 收入类查询可以生成并执行关联产品和汇率表的 SQL。

## 后续衔接

后续应继续增强业务规则、错误防护和评估体系，让系统不只“能生成 SQL”，也能逐步提升业务口径可靠性。
