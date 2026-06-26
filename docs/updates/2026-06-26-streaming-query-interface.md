# 流式查询接口

## 背景

同步查询接口需要等待 SQL 生成和数据库执行全部完成后才返回结果。为了提升交互反馈速度，系统需要支持边生成 SQL 边推送内容，并在 SQL 完成后继续返回执行结果。

## 本次变更

- 增加模型流式生成方法，逐段返回 SQL 文本。
- 增加系统层流式查询流程，输出 `sql_chunk`、`sql_done`、`result` 和 `error` 事件。
- 增加 `POST /api/v1/query/stream` SSE 接口。
- 增加一个轻量前端页面，用于验证 SQL 流式展示和结果表格渲染。

## 关键文件

- `llm_client.py`
- `main.py`
- `api_service.py`
- `static/index.html`

## 验证结果

- 流式模型调用可逐段输出 SQL。
- SSE 接口可返回 SQL 片段、完整 SQL 和查询结果事件。
- 前端页面可通过 `/api/v1/query/stream` 展示流式 SQL 和最终表格。

## 后续衔接

后续可以在前端页面上继续补充对话历史、异常提示、SQL 复制和查询配置开关，让服务接口更适合业务人员直接使用。
