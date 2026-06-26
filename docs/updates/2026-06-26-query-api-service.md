# 查询 API 服务化

## 背景

命令行查询链路完成后，需要把系统封装成可被前端页面、自动化流程和其他服务调用的 API。服务层需要提供标准请求结构、响应结构和健康检查能力。

## 本次变更

- 新增 FastAPI 服务入口。
- 提供 `GET /`、`GET /health` 和 `POST /api/v1/query`。
- 定义查询请求、成功响应、错误响应和健康检查响应模型。
- 增加 CORS 支持、请求校验错误处理和兜底异常处理。
- 在 API 响应中返回 SQL、列名、行数据、格式化结果、诊断信息和 metadata。

## 关键文件

- `api_service.py`
- `pyproject.toml`
- `uv.lock`

## 验证结果

- API 服务模块编译通过。
- `GET /health` 返回数据库连接正常。
- `GET /openapi.json` 可生成接口文档。
- `POST /api/v1/query` 对“查询已完成订单的总数量”返回 `completed_order_count = 5`。

## 后续衔接

后续可以在 API 基础上接入前端交互、流式输出、权限控制和更完整的错误提示，让系统从本地工具逐步演进为可交互服务。
