"""
ChatBI API 服务入口。

将命令行查询链路封装为 REST API，便于前端页面、自动化流程或其他系统调用。
"""

from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import ChatBISystem


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("chatbi.api")


app = FastAPI(
    title="ChatBI API",
    version="0.1.0",
    description="面向企业经营分析场景的自然语言查询服务。",
    openapi_tags=[
        {"name": "query", "description": "自然语言查询接口"},
        {"name": "system", "description": "系统状态接口"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

system = ChatBISystem()
static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class QueryRequest(BaseModel):
    """自然语言查询请求。"""

    question: str = Field(..., min_length=1, description="业务人员输入的自然语言问题")
    use_few_shot: bool = Field(default=True, description="是否启用 Few-shot 示例")
    use_rules: bool = Field(default=True, description="是否启用业务规则")
    use_guards: bool = Field(default=True, description="是否启用错误防护")
    use_indicator_knowledge: bool = Field(default=True, description="是否注入指标知识")


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    database_connected: bool


class QuerySuccessResponse(BaseModel):
    """查询成功响应。"""

    success: bool = True
    question: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    formatted: str
    diagnostics: dict[str, Any]
    metadata: dict[str, Any]


class ErrorResponse(BaseModel):
    """统一错误响应。"""

    success: bool = False
    error: str
    error_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


def _rows_to_dicts(columns: list[str], rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """将数据库元组结果转换为字典列表。"""
    return [dict(zip(columns, row)) for row in rows]


def _error_status_code(error_type: str) -> int:
    """将系统错误类型映射为 HTTP 状态码。"""
    if error_type == "validation":
        return 400
    if error_type == "llm":
        return 502
    return 500


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """统一处理请求体校验错误。"""
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            ErrorResponse(
                error="请求参数校验失败",
                error_type="request_validation",
                metadata={
                    "path": str(request.url.path),
                    "details": exc.errors(),
                },
            )
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理，避免向调用方暴露内部堆栈。"""
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(
            ErrorResponse(
                error="服务内部异常",
                error_type="internal_server_error",
                metadata={"path": str(request.url.path)},
            )
        ),
    )


@app.get("/", tags=["system"])
def read_root() -> dict[str, str]:
    """返回服务入口信息。"""
    return {
        "name": "ChatBI API",
        "docs": "/docs",
        "web": "/static/index.html",
        "health": "/health",
        "query": "/api/v1/query",
        "query_stream": "/api/v1/query/stream",
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    """检查 API 服务与数据库连接状态。"""
    return HealthResponse(
        status="ok",
        database_connected=system.db.validate_connection(),
    )


@app.post(
    "/api/v1/query",
    response_model=QuerySuccessResponse,
    tags=["query"],
    summary="执行自然语言查询",
    responses={
        400: {"model": ErrorResponse, "description": "输入问题不合法"},
        422: {"model": ErrorResponse, "description": "请求参数校验失败"},
        500: {"model": ErrorResponse, "description": "数据库或服务内部异常"},
        502: {"model": ErrorResponse, "description": "模型调用失败"},
    },
)
def query_chatbi(payload: QueryRequest) -> QuerySuccessResponse | JSONResponse:
    """执行自然语言查询，并返回生成 SQL 与查询结果。"""
    started_at = perf_counter()
    logger.info("Received question: %s", payload.question)

    result = system.run(
        user_question=payload.question,
        use_few_shot=payload.use_few_shot,
        use_rules=payload.use_rules,
        use_guards=payload.use_guards,
        use_indicator_knowledge=payload.use_indicator_knowledge,
    )
    duration_ms = round((perf_counter() - started_at) * 1000, 2)

    metadata = {
        **result.get("metadata", {}),
        "duration_ms": duration_ms,
    }

    if not result["success"]:
        error_type = result.get("error_type", "internal_server_error")
        return JSONResponse(
            status_code=_error_status_code(error_type),
            content=jsonable_encoder(
                ErrorResponse(
                    error=result.get("error", "查询失败"),
                    error_type=error_type,
                    metadata=metadata,
                    diagnostics=result.get("diagnostics", {}),
                )
            ),
        )

    logger.info("Question handled successfully in %.2f ms", duration_ms)

    return QuerySuccessResponse(
        question=result["question"],
        sql=result["sql"],
        columns=result["columns"],
        rows=jsonable_encoder(_rows_to_dicts(result["columns"], result["rows"])),
        formatted=result["formatted"],
        diagnostics=result.get("diagnostics", {}),
        metadata=metadata,
    )


@app.post(
    "/api/v1/query/stream",
    tags=["query"],
    summary="流式执行自然语言查询",
)
def query_chatbi_stream(payload: QueryRequest) -> StreamingResponse:
    """执行自然语言查询，以 SSE 事件逐步返回 SQL 和结果。"""
    logger.info("Received stream question: %s", payload.question)

    def event_generator():
        yield from system.run_stream(
            user_question=payload.question,
            use_few_shot=payload.use_few_shot,
            use_rules=payload.use_rules,
            use_guards=payload.use_guards,
            use_indicator_knowledge=payload.use_indicator_knowledge,
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    uvicorn.run("api_service:app", host="0.0.0.0", port=8000, reload=True)
