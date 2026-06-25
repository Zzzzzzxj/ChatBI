# Text2SQL Prompt 策略说明

本文档说明自然语言问题生成 SQL 的基础策略，目标是比较不同 Prompt 设计的效果边界。

## 版本说明

| 文件 | 策略 | 说明 |
| --- | --- | --- |
| `text2sql_v0.py` | Zero-shot | 只提供角色和用户问题，不注入 Schema |
| `text2sql_v1.py` | Schema + Few-shot | 注入手写 Schema 和少量 SQL 示例 |
| `text2sql_v2.py` | COT + 结构化约束 | 在 v1 基础上增加思考步骤和输出约束 |

## 运行方式

先在 `.env` 中配置模型调用参数：

```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen3.5-27B
```

同步依赖：

```bash
uv sync
```

运行不同版本：

```bash
uv run python text2sql_v0.py
uv run python text2sql_v1.py
uv run python text2sql_v2.py
```

生成 SQL 后，可复制到 MySQL 中验证：

```bash
mysql -h127.0.0.1 -P3306 -uroot -p123456 chatbi_mvp
```

## 观察重点

- Zero-shot 是否会编造表名或字段名。
- 注入 Schema 后字段选择是否更稳定。
- Few-shot 是否提升 JOIN、GROUP BY、WHERE 的一致性。
- 结构化约束是否让收入、成本、订单状态等业务口径更稳定。
- 使用 Qwen3.5 时关闭 thinking 模式，保证脚本直接返回 SQL 文本。
