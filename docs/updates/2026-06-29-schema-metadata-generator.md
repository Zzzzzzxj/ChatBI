# Schema 元数据生成器

## 背景

ChatBI 当前的 Prompt 仍依赖手写 Schema 文本。随着业务表和字段增多，固定维护方式会增加遗漏字段、外键关系不一致和上下文冗余的风险。系统需要具备从数据库自动读取结构信息的能力，为后续动态 Schema 选择和字段匹配提供基础。

## 本次变更

- 新增项目级 `schema_generator.py` 模块，自动读取 MySQL 表、字段、主键、字段注释和外键关系。
- 支持输出 Prompt 友好的 Schema 文本。
- 支持输出结构化 Schema 元数据，便于后续表级召回、字段匹配和关联路径推导复用。
- 将 `scripts/schema_generator.py` 调整为命令行入口，复用项目级模块。

## 关键文件

- `schema_generator.py`
- `scripts/schema_generator.py`

## 验证结果

- Python 模块编译检查通过。
- 数据库 Schema 文本生成成功。
- 结构化元数据读取成功。
- 敏感表述扫描通过。

## 后续衔接

后续可以基于结构化元数据增加表选择、字段选择和 Join 关系推导能力，让 Prompt 只注入与当前问题相关的 Schema 上下文。
