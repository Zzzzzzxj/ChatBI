"""
数据库访问模块。

负责 MySQL 连接验证、只读 SQL 校验和查询执行。
"""

import re
from typing import Any

import pymysql

from config import DB_CONFIG


READONLY_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE | re.DOTALL)
BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class DatabaseClient:
    """MySQL 数据库客户端。"""

    def __init__(self) -> None:
        self.config = DB_CONFIG

    def validate_connection(self) -> bool:
        """验证数据库连接是否正常。"""
        try:
            conn = pymysql.connect(**self.config)
            conn.close()
            return True
        except Exception:
            return False

    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """校验并执行只读 SQL。"""
        self._validate_readonly_sql(sql)

        conn = pymysql.connect(**self.config)
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return columns, rows
        finally:
            conn.close()

    @staticmethod
    def _validate_readonly_sql(sql: str) -> None:
        """限制系统只执行 SELECT 查询。"""
        normalized_sql = sql.strip()
        if not normalized_sql:
            raise ValueError("SQL 为空")
        if not READONLY_PATTERN.search(normalized_sql):
            raise ValueError("仅允许执行 SELECT 查询")
        if BLOCKED_KEYWORDS.search(normalized_sql):
            raise ValueError("SQL 包含非只读关键字，已拒绝执行")
