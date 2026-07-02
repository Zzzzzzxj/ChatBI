"""
Schema Linking 编排模块。

将表级召回、字段级匹配和 Join 路径推导串联为完整的动态 Schema 构造流程。
输出结果可直接注入 SQL 生成 Prompt，用更小、更相关的 Schema 上下文替代
全量 Schema。
"""

from __future__ import annotations

from typing import Any

from field_matcher import build_field_index, match_fields
from join_resolver import (
    STRONG_METRIC_WORDS,
    TABLE_KEYWORDS,
    TABLE_TYPES,
    resolve_joins,
    select_anchor,
)
from table_retriever import build_index, retrieve_tables


def _score_table_by_keywords(query: str, table_name: str) -> int:
    """计算查询与表的业务关键词匹配分数。"""
    return sum(
        1
        for keyword in TABLE_KEYWORDS.get(table_name, [])
        if keyword in query
    )


def _ensure_fact_table_for_metric(query: str, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """指标型问题必须包含相关事实表，避免只召回维度表导致 SQL 无法聚合。"""
    if not any(word in query for word in STRONG_METRIC_WORDS):
        return tables

    existing_names = {table["table_name"] for table in tables}
    recalled_fact_tables = [
        table
        for table in tables
        if TABLE_TYPES.get(table["table_name"]) == "fact"
    ]

    all_tables = retrieve_tables(query, top_k=10, score_threshold=0.0)
    all_fact_tables = [
        table
        for table in all_tables
        if TABLE_TYPES.get(table["table_name"]) == "fact"
    ]
    if not all_fact_tables:
        return tables

    best_fact = max(
        all_fact_tables,
        key=lambda table: _score_table_by_keywords(query, table["table_name"]),
    )
    if best_fact["table_name"] not in existing_names:
        tables = tables + [best_fact]

    if not recalled_fact_tables and not any(
        TABLE_TYPES.get(table["table_name"]) == "fact"
        for table in tables
    ):
        tables = tables + [all_fact_tables[0]]

    return tables


def schema_link(
    query: str,
    table_top_k: int = 3,
    field_top_k: int = 12,
    table_threshold: float = 0.3,
    field_threshold: float = 0.25,
    include_join: bool = True,
) -> dict[str, Any]:
    """
    执行 Schema Linking 流程。

    Returns:
        包含候选表、候选字段、锚表、Join 路径、动态 Schema 文本和元数据的字典。
    """
    tables = retrieve_tables(
        query,
        top_k=table_top_k,
        score_threshold=table_threshold,
    )
    tables = _ensure_fact_table_for_metric(query, tables)
    candidate_table_names = [table["table_name"] for table in tables]

    if not candidate_table_names:
        return {
            "tables": [],
            "fields": [],
            "anchor": "",
            "join_path": {
                "anchor": "",
                "joins": [],
                "sql_fragment": "",
                "unreachable": [],
            },
            "dynamic_schema": "",
            "metadata": {
                "table_count": 0,
                "field_count": 0,
                "join_count": 0,
                "has_unreachable": False,
            },
        }

    anchor, anchor_reason = select_anchor(query, candidate_table_names)

    fields = match_fields(
        query,
        candidate_tables=candidate_table_names,
        top_k=field_top_k,
        score_threshold=field_threshold,
    )

    join_path = {
        "anchor": anchor,
        "joins": [],
        "sql_fragment": "",
        "unreachable": [],
    }
    if include_join:
        join_path = resolve_joins(anchor, candidate_table_names)

    dynamic_schema = assemble_dynamic_schema(
        tables=tables,
        fields=fields,
        join_path=join_path,
    )

    return {
        "tables": tables,
        "fields": fields,
        "anchor": anchor,
        "anchor_reason": anchor_reason,
        "join_path": join_path,
        "dynamic_schema": dynamic_schema,
        "metadata": {
            "table_count": len(tables),
            "field_count": len(fields),
            "join_count": len(join_path.get("joins", [])),
            "has_unreachable": bool(join_path.get("unreachable")),
        },
    }


def assemble_dynamic_schema(
    tables: list[dict[str, Any]],
    fields: list[dict[str, Any]],
    join_path: dict[str, Any],
) -> str:
    """将表、字段和 Join 结果组装为 Prompt 可用的动态 Schema 文本。"""
    table_fields_map: dict[str, list[dict[str, Any]]] = {
        table["table_name"]: []
        for table in tables
    }
    for field in fields:
        if field["table"] in table_fields_map:
            table_fields_map[field["table"]].append(field)

    lines = []
    for table in tables:
        table_name = table["table_name"]
        domain = table.get("domain", "")
        anchor_tag = " [锚表]" if table_name == join_path.get("anchor") else ""
        lines.append(f"表：{table_name}（{domain}）{anchor_tag}")

        field_list = table_fields_map.get(table_name, [])
        if field_list:
            for field in field_list:
                description = field.get("description", "")
                short_description = description.split("。")[0]
                rule_tag = f" [{field['rule_applied']}]" if field.get("rule_applied") else ""
                lines.append(f"  - {field['field']} {short_description}{rule_tag}")
        else:
            key_fields = table.get("key_fields", "")
            lines.append(f"  - 关键字段：{key_fields}")

        lines.append("")

    if join_path.get("joins"):
        lines.append("表间关联：")
        for join in join_path["joins"]:
            lines.append(f"  {join['join_type']} {join['to_table']} ON {join['on_clause']}")
        lines.append("")

    if join_path.get("unreachable"):
        unreachable = ", ".join(join_path["unreachable"])
        lines.append(f"无法直接关联的表：{unreachable}")
        lines.append("")

    return "\n".join(lines).strip()


def build_dynamic_prompt_schema(query: str) -> str:
    """返回可注入 Prompt 的动态 Schema 文本；失败时返回空字符串供调用方回退。"""
    try:
        result = schema_link(query)
    except Exception:
        return ""

    if result["metadata"]["table_count"] == 0:
        return ""
    return result["dynamic_schema"]


def ensure_indexes(force_rebuild: bool = False) -> None:
    """确保表索引和字段索引存在。"""
    build_index(force_rebuild=force_rebuild)
    build_field_index(force_rebuild=force_rebuild)


def main() -> None:
    """命令行入口：输出一次动态 Schema 构造结果。"""
    result = schema_link("按客户类型统计各产品线的收入，需要换算成人民币")
    print(result["dynamic_schema"])


if __name__ == "__main__":
    main()
