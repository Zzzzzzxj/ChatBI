"""
多表 Join 路径推导模块。

基于业务表关系图，为候选表集合选择 SQL 主表，并推导连接目标表所需的
JOIN 路径和 ON 条件。该模块接在表级召回与字段匹配之后，用于降低多表
查询中漏连表、错连表和错误关联条件的风险。
"""

from __future__ import annotations

from collections import deque
from typing import Any


TABLE_RELATIONSHIPS: dict[str, list[dict[str, str]]] = {
    "sales_orders": [
        {
            "target": "dim_customers",
            "fk_col": "customer_id",
            "pk_col": "customer_id",
            "join_type": "JOIN",
        },
        {
            "target": "dim_products",
            "fk_col": "product_id",
            "pk_col": "product_id",
            "join_type": "JOIN",
        },
        {
            "target": "exchange_rates",
            "fk_col": "order_date, currency",
            "pk_col": "rate_date, currency",
            "join_type": "LEFT JOIN",
        },
    ],
    "dim_customers": [
        {
            "target": "sales_orders",
            "fk_col": "customer_id",
            "pk_col": "customer_id",
            "join_type": "LEFT JOIN",
        },
    ],
    "dim_products": [
        {
            "target": "sales_orders",
            "fk_col": "product_id",
            "pk_col": "product_id",
            "join_type": "LEFT JOIN",
        },
    ],
    "exchange_rates": [
        {
            "target": "sales_orders",
            "fk_col": "rate_date, currency",
            "pk_col": "order_date, currency",
            "join_type": "LEFT JOIN",
        },
    ],
    "finance_expenses": [],
}


TABLE_TYPES = {
    "sales_orders": "fact",
    "finance_expenses": "fact",
    "dim_customers": "dimension",
    "dim_products": "dimension",
    "exchange_rates": "reference",
}


TABLE_KEYWORDS = {
    "sales_orders": [
        "收入",
        "销售额",
        "订单",
        "销售",
        "数量",
        "金额",
        "毛利",
        "利润",
        "net_amount",
        "gross_amount",
    ],
    "finance_expenses": [
        "费用",
        "研发",
        "销售费用",
        "管理费用",
        "财务费用",
        "期间费用",
        "expense",
    ],
    "dim_customers": ["客户", "客户类型", "OEM", "储能集成商", "电网集团", "customer"],
    "dim_products": ["产品", "产品线", "型号", "SKU", "product"],
    "exchange_rates": ["汇率", "币种", "人民币", "美元", "欧元", "rate"],
}


METRIC_SIGNALS = ["统计", "多少", "总计", "平均", "占比", "总和", "额", "量"]
ENTITY_SIGNALS = ["列出", "哪些", "所有", "没有", "明细", "每个"]
STRONG_METRIC_WORDS = ["收入", "销售额", "费用", "毛利", "利润", "金额", "数量"]


def _classify_intent(query: str) -> str:
    """判断查询更偏指标、实体还是模糊意图。"""
    metric_count = sum(1 for signal in METRIC_SIGNALS if signal in query)
    entity_count = sum(1 for signal in ENTITY_SIGNALS if signal in query)

    if any(word in query for word in STRONG_METRIC_WORDS):
        metric_count += 2

    if metric_count > entity_count:
        return "metric"
    if entity_count > metric_count:
        return "entity"
    return "ambiguous"


def _score_tables_by_keywords(query: str, candidate_tables: list[str]) -> dict[str, int]:
    """根据业务关键词命中数为候选表打分。"""
    scores = {}
    for table_name in candidate_tables:
        keywords = TABLE_KEYWORDS.get(table_name, [])
        scores[table_name] = sum(1 for keyword in keywords if keyword in query)
    return scores


def _bfs_shortest_path(
    start: str,
    end: str,
    relationships: dict[str, list[dict[str, str]]],
) -> list[str] | None:
    """使用 BFS 查找两张表之间的最短连接路径。"""
    if start == end:
        return [start]

    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        current, path = queue.popleft()
        for edge in relationships.get(current, []):
            next_table = edge["target"]
            if next_table in visited:
                continue

            next_path = path + [next_table]
            if next_table == end:
                return next_path

            visited.add(next_table)
            queue.append((next_table, next_path))

    return None


def _is_connected(
    anchor: str,
    target_tables: list[str],
    relationships: dict[str, list[dict[str, str]]],
) -> bool:
    """检查锚表是否可到达全部目标表。"""
    for target in target_tables:
        if target == anchor:
            continue
        if _bfs_shortest_path(anchor, target, relationships) is None:
            return False
    return True


def _most_central_table(
    candidate_tables: list[str],
    relationships: dict[str, list[dict[str, str]]],
) -> str:
    """选择到其他候选表总路径最短的表作为兜底锚表。"""
    total_distances = {}
    for table_name in candidate_tables:
        total = 0
        for target in candidate_tables:
            if target == table_name:
                continue
            path = _bfs_shortest_path(table_name, target, relationships)
            total += len(path) - 1 if path else 999
        total_distances[table_name] = total

    return min(candidate_tables, key=lambda table_name: total_distances[table_name])


def select_anchor(
    query: str,
    candidate_tables: list[str],
    relationships: dict[str, list[dict[str, str]]] | None = None,
) -> tuple[str, str]:
    """
    根据查询意图和候选表选择 SQL 的锚表。

    指标型问题优先选择事实表，实体型问题优先选择维度表或参考表；如果候选表
    无法全部连通，则尝试切换到可连通所有目标表的候选表。
    """
    if relationships is None:
        relationships = TABLE_RELATIONSHIPS

    if not candidate_tables:
        raise ValueError("候选表集合不能为空")

    unknown_tables = [table for table in candidate_tables if table not in relationships]
    if unknown_tables:
        raise ValueError(f"候选表未配置关联关系：{unknown_tables}")

    if len(candidate_tables) == 1:
        return candidate_tables[0], "仅有一张候选表"

    intent = _classify_intent(query)
    scores = _score_tables_by_keywords(query, candidate_tables)
    fact_tables = [
        table for table in candidate_tables
        if TABLE_TYPES.get(table) == "fact"
    ]
    non_fact_tables = [
        table for table in candidate_tables
        if TABLE_TYPES.get(table) != "fact"
    ]

    if intent == "metric" and fact_tables:
        anchor = max(fact_tables, key=lambda table: scores.get(table, 0))
        reason = f"指标型问题，选择事实表 {anchor} 作为锚表"
    elif intent == "entity" and non_fact_tables:
        anchor = max(non_fact_tables, key=lambda table: scores.get(table, 0))
        reason = f"实体型问题，选择实体相关表 {anchor} 作为锚表"
    else:
        anchor = _most_central_table(candidate_tables, relationships)
        reason = f"意图不明确，选择连接距离最短的 {anchor} 作为锚表"

    if not _is_connected(anchor, candidate_tables, relationships):
        for candidate in sorted(
            candidate_tables,
            key=lambda table: scores.get(table, 0),
            reverse=True,
        ):
            if _is_connected(candidate, candidate_tables, relationships):
                reason += f"；原锚表无法连通全部目标，切换为 {candidate}"
                anchor = candidate
                break

    return anchor, reason


def _get_edge_info(
    from_table: str,
    to_table: str,
    relationships: dict[str, list[dict[str, str]]],
) -> dict[str, str]:
    """获取两张表之间的边配置。"""
    for edge in relationships.get(from_table, []):
        if edge["target"] == to_table:
            return edge
    raise ValueError(f"未找到从 {from_table} 到 {to_table} 的关联关系")


def _build_on_clause(from_table: str, to_table: str, edge: dict[str, str]) -> str:
    """根据边配置生成 ON 条件。"""
    fk_columns = [column.strip() for column in edge["fk_col"].split(",")]
    pk_columns = [column.strip() for column in edge["pk_col"].split(",")]

    return " AND ".join(
        f"{from_table}.{fk} = {to_table}.{pk}"
        for fk, pk in zip(fk_columns, pk_columns)
    )


def resolve_joins(
    anchor_table: str,
    target_tables: list[str],
    relationships: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """
    从锚表出发推导连接所有目标表的 Join 路径。

    如果目标表之间不存在连接路径，会在 unreachable 中返回，调用方可据此决定
    是否拆成独立查询。
    """
    if relationships is None:
        relationships = TABLE_RELATIONSHIPS

    if anchor_table not in relationships:
        raise ValueError(f"锚表未配置关联关系：{anchor_table}")

    all_targets = set(target_tables)
    all_targets.add(anchor_table)

    visited_edges = set()
    joins = []
    unreachable = []

    for target in sorted(all_targets):
        if target == anchor_table:
            continue

        path = _bfs_shortest_path(anchor_table, target, relationships)
        if path is None:
            unreachable.append(target)
            continue

        for index in range(len(path) - 1):
            from_table = path[index]
            to_table = path[index + 1]
            edge_key = (from_table, to_table)
            if edge_key in visited_edges:
                continue

            visited_edges.add(edge_key)
            edge = _get_edge_info(from_table, to_table, relationships)
            joins.append(
                {
                    "from_table": from_table,
                    "to_table": to_table,
                    "join_type": edge["join_type"],
                    "on_clause": _build_on_clause(from_table, to_table, edge),
                }
            )

    return {
        "anchor": anchor_table,
        "joins": joins,
        "unreachable": unreachable,
        "sql_fragment": build_sql_fragment(anchor_table, joins),
    }


def build_sql_fragment(anchor_table: str, joins: list[dict[str, str]]) -> str:
    """生成 FROM/JOIN SQL 片段。"""
    sorted_joins = sorted(joins, key=lambda join: 0 if join["join_type"] == "JOIN" else 1)
    lines = [anchor_table]
    for join in sorted_joins:
        lines.append(f"{join['join_type']} {join['to_table']} ON {join['on_clause']}")
    return "\n".join(lines)


def resolve_query_joins(query: str, candidate_tables: list[str]) -> dict[str, Any]:
    """组合锚表选择与 Join 路径推导。"""
    anchor, reason = select_anchor(query, candidate_tables)
    join_path = resolve_joins(anchor, candidate_tables)
    return {
        **join_path,
        "anchor_reason": reason,
    }


def main() -> None:
    """命令行入口：输出一个典型多表查询的 Join 片段。"""
    result = resolve_query_joins(
        "按客户类型统计各产品线的收入，需要换算成人民币",
        ["sales_orders", "dim_customers", "dim_products", "exchange_rates"],
    )
    print(result["sql_fragment"])


if __name__ == "__main__":
    main()
