# 数据环境说明

本阶段建立 ChatBI MVP 的核心业务数据环境。数据域参考制造业和新能源企业经营分析场景，覆盖客户、产品、销售订单、汇率和费用五类核心数据。

## 数据表

| 表名 | 说明 |
| --- | --- |
| `dim_customers` | 客户维度表，描述客户名称、类型、行业、国家和区域 |
| `dim_products` | 产品维度表，描述产品线、分类、技术路线和成本 |
| `sales_orders` | 销售订单事实表，记录订单状态、数量、金额、币种和关联维度 |
| `exchange_rates` | 汇率表，用于将多币种收入折算为人民币 |
| `finance_expenses` | 费用事实表，记录研发、销售、管理、财务等费用 |

## 初始化方式

先创建本地环境文件：

```bash
cp .env.example .env
```

在 `.env` 中配置 MySQL 连接信息后，按顺序执行：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p < sql/01_schema.sql
mysql -h 127.0.0.1 -P 3306 -u root -p < sql/02_seed_data.sql
mysql -h 127.0.0.1 -P 3306 -u root -p < sql/03_validation_queries.sql
```

## Schema 生成

安装依赖后可自动读取数据库结构并生成 Prompt 所需的 Schema 文本：

```bash
uv sync
uv run python scripts/schema_generator.py
```

## 验证目标

`sql/03_validation_queries.sql` 用于验证数据环境是否满足后续 Text2SQL 的基础查询需求：

- 核心表都有数据。
- 可以查询已完成订单数量。
- 可以按客户类型统计订单。
- 可以按产品线统计收入。
- 可以按区域做人民币收入折算。
- 可以统计第一季度总费用。
