"""
大模型客户端模块。

封装 OpenAI-compatible Chat Completions 调用，并负责清理模型输出中的 SQL 文本。
"""

import re

from openai import OpenAI

from config import LLM_CONFIG


class LLMClient:
    """Text2SQL 模型客户端。"""

    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
        )
        self.model = LLM_CONFIG["model"]
        self.temperature = LLM_CONFIG["temperature"]
        self.max_tokens = LLM_CONFIG["max_tokens"]
        self.extra_body = LLM_CONFIG.get("extra_body")

    def generate_sql(self, system_message: str, prompt: str) -> str:
        """调用模型生成 SQL，并返回清理后的 SQL 字符串。"""
        request_args = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.extra_body:
            request_args["extra_body"] = self.extra_body

        response = self.client.chat.completions.create(**request_args)
        raw_output = response.choices[0].message.content or ""
        return self._extract_sql(raw_output)

    @staticmethod
    def _extract_sql(raw_output: str) -> str:
        """去除 Markdown 标记，只保留 SQL 文本。"""
        sql = re.sub(r"```sql|```", "", raw_output, flags=re.IGNORECASE).strip()
        sql = sql.rstrip(";").strip()
        return f"{sql};" if sql else ""
