"""
应用配置模块。

集中读取数据库连接、模型服务和运行参数，避免业务代码直接依赖环境变量。
"""

import os
from typing import Any

from dotenv import load_dotenv


load_dotenv()


DB_CONFIG: dict[str, Any] = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "chatbi_mvp"),
    "charset": "utf8mb4",
}


LLM_CONFIG: dict[str, Any] = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "base_url": os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
    "model": os.getenv("LLM_MODEL", "Qwen/Qwen3.5-27B"),
    "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
    "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "1000")),
    "extra_body": {"enable_thinking": False},
}
