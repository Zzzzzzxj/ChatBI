"""
数据库 Schema 生成模块。

从 MySQL 元数据中读取表、字段、注释和外键关系，生成适合注入 Text2SQL
Prompt 的结构化 Schema 文本。该模块作为后续动态 Schema 选择和字段匹配
能力的基础。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pymysql

from config import DB_CONFIG


@dataclass(frozen=True)
class ColumnMeta:
    """数据库字段元数据。"""

    name: str
    data_type: str
    nullable: bool
    key: str
    default: Any
    comment: str


@dataclass(frozen=True)
class ForeignKeyMeta:
    """数据库外键元数据。"""

    column: str
    ref_table: str
    ref_column: str


def get_tables(cursor) -> list[str]:
    """获取当前数据库的业务表名。"""
    cursor.execute("SHOW TABLES")
    return [row[0] for row in cursor.fetchall()]


def get_columns(cursor, table_name: str) -> list[ColumnMeta]:
    """获取指定表的字段元数据。"""
    cursor.execute(f"SHOW FULL COLUMNS FROM `{table_name}`")
    columns = []
    for row in cursor.fetchall():
        columns.append(
            ColumnMeta(
                name=row[0],
                data_type=row[1],
                nullable=row[3].upper() == "YES",
                key=row[4] or "",
                default=row[5],
                comment=row[8] or "",
            )
        )
    return columns


def get_foreign_keys(cursor, table_name: str) -> list[ForeignKeyMeta]:
    """获取指定表的外键关系。"""
    cursor.execute(
        """
        SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY ORDINAL_POSITION
        """,
        (table_name,),
    )
    return [
        ForeignKeyMeta(
            column=row[0],
            ref_table=row[1],
            ref_column=row[2],
        )
        for row in cursor.fetchall()
    ]


def describe_table(cursor, table_name: str) -> dict[str, Any]:
    """返回单张表的结构化元数据。"""
    columns = get_columns(cursor, table_name)
    foreign_keys = get_foreign_keys(cursor, table_name)
    fk_map = {fk.column: fk for fk in foreign_keys}

    return {
        "table": table_name,
        "columns": [
            {
                "name": col.name,
                "type": col.data_type,
                "nullable": col.nullable,
                "key": col.key,
                "default": col.default,
                "comment": col.comment,
                "foreign_key": {
                    "ref_table": fk_map[col.name].ref_table,
                    "ref_column": fk_map[col.name].ref_column,
                }
                if col.name in fk_map
                else None,
            }
            for col in columns
        ],
        "foreign_keys": [
            {
                "column": fk.column,
                "ref_table": fk.ref_table,
                "ref_column": fk.ref_column,
            }
            for fk in foreign_keys
        ],
    }


def build_schema_string(cursor, table_name: str) -> str:
    """为单张表生成 Prompt 友好的 Schema 文本。"""
    table_meta = describe_table(cursor, table_name)
    lines = [f"表：{table_meta['table']}"]

    for col in table_meta["columns"]:
        parts = [f"- {col['name']} {col['type']}"]

        if col["key"] == "PRI":
            parts.append("主键")

        if col["foreign_key"]:
            fk = col["foreign_key"]
            parts.append(f"外键 -> {fk['ref_table']}.{fk['ref_column']}")
        elif col["comment"]:
            parts.append(col["comment"])

        lines.append(" ".join(parts))

    return "\n".join(lines)


def generate_schema() -> str:
    """连接数据库，生成所有业务表的 Schema 文本。"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            schemas = [build_schema_string(cursor, table) for table in get_tables(cursor)]
            return "\n\n".join(schemas)
    finally:
        conn.close()


def generate_schema_metadata() -> list[dict[str, Any]]:
    """连接数据库，返回所有业务表的结构化元数据。"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            return [describe_table(cursor, table) for table in get_tables(cursor)]
    finally:
        conn.close()


def main() -> None:
    """命令行入口：打印当前数据库 Schema 文本。"""
    print(generate_schema())


if __name__ == "__main__":
    main()
