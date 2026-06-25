"""
SQL 诊断模块。

基于业务问题和生成 SQL 做轻量级规则检查，用于识别常见的字段、关联、时间、
过滤和聚合问题，帮助后续持续改进 Prompt 与规则库。
"""

import re
from collections import Counter
from typing import Optional


class ErrorAnalyzer:
    """SQL 生成结果诊断器。"""

    FIELD_ERROR = "field_error"
    JOIN_ERROR = "join_error"
    TIME_ERROR = "time_error"
    FILTER_ERROR = "filter_error"
    AGGREGATION_ERROR = "aggregation_error"
    SAFETY_ERROR = "safety_error"
    SYNTAX_ERROR = "syntax_error"
    UNKNOWN = "unknown"

    def analyze(
        self,
        question: str,
        sql: str,
        execution_error: Optional[str] = None,
    ) -> dict:
        """分析单条 SQL 的潜在问题。"""
        issues = []
        normalized_sql = sql.lower()

        if execution_error and self._looks_like_syntax_error(execution_error):
            issues.append(self._issue(
                self.SYNTAX_ERROR,
                "数据库无法解析生成的 SQL。",
                "检查括号、引号、关键字顺序和函数写法，必要时补充格式约束。",
            ))

        if self._has_write_operation(normalized_sql):
            issues.append(self._issue(
                self.SAFETY_ERROR,
                "SQL 包含非只读操作。",
                "模型输出必须限制为单条 SELECT 查询。",
            ))

        if self._uses_wrong_amount_field(question, normalized_sql):
            issues.append(self._issue(
                self.FIELD_ERROR,
                "收入或成本字段选择不符合业务口径。",
                "收入默认使用 net_amount，成本默认使用 material_cost + labor_cost。",
            ))

        if self._missing_exchange_rate(question, normalized_sql):
            issues.append(self._issue(
                self.JOIN_ERROR,
                "金额汇总缺少汇率表关联。",
                "按 order_date 和 currency 关联 exchange_rates，并使用 rate_to_cny 折算人民币。",
            ))

        if self._missing_dimension_join(question, normalized_sql):
            issues.append(self._issue(
                self.JOIN_ERROR,
                "维度分析缺少必要的维度表关联。",
                "按问题中的客户、产品、产品线等分析维度补齐对应 JOIN。",
            ))

        if self._missing_sales_filter(question, normalized_sql):
            issues.append(self._issue(
                self.FILTER_ERROR,
                "销售类统计缺少已完成订单过滤。",
                "收入、订单量、毛利等销售指标需要过滤 order_status = 'completed'。",
            ))

        if self._missing_dynamic_time_logic(question, normalized_sql):
            issues.append(self._issue(
                self.TIME_ERROR,
                "动态时间问题缺少稳定的时间边界。",
                "最近 N 个月、本月、本季度等问题应使用日期函数或闭开区间表达。",
            ))

        if self._has_grouping_mismatch(normalized_sql):
            issues.append(self._issue(
                self.AGGREGATION_ERROR,
                "聚合查询中的维度字段和 GROUP BY 不匹配。",
                "SELECT 中的非聚合字段需要全部出现在 GROUP BY 中。",
            ))

        return {
            "ok": not issues,
            "issues": issues,
            "primary_type": issues[0]["type"] if issues else None,
        }

    def analyze_batch(self, cases: list[dict]) -> list[dict]:
        """批量分析 SQL 案例。"""
        results = []
        for case in cases:
            result = self.analyze(
                question=case.get("question", ""),
                sql=case.get("sql", ""),
                execution_error=case.get("execution_error"),
            )
            result["question"] = case.get("question", "")
            result["sql"] = case.get("sql", "")
            results.append(result)
        return results

    def build_report(self, results: list[dict]) -> str:
        """生成文本诊断报告。"""
        issue_types = [
            issue["type"]
            for result in results
            for issue in result.get("issues", [])
        ]
        counts = Counter(issue_types)

        lines = [
            "SQL 诊断报告",
            f"案例数：{len(results)}",
            f"发现问题数：{len(issue_types)}",
            "",
            "问题分布：",
        ]
        if counts:
            lines.extend(f"- {issue_type}: {count}" for issue_type, count in counts.items())
        else:
            lines.append("- 未发现明显问题")

        lines.append("")
        lines.append("案例明细：")
        for index, result in enumerate(results, 1):
            lines.append(f"{index}. {result.get('question', '')}")
            if result.get("ok"):
                lines.append("   状态：通过")
                continue
            for issue in result["issues"]:
                lines.append(f"   类型：{issue['type']}")
                lines.append(f"   原因：{issue['reason']}")
                lines.append(f"   建议：{issue['suggestion']}")

        return "\n".join(lines)

    @staticmethod
    def _issue(issue_type: str, reason: str, suggestion: str) -> dict:
        return {
            "type": issue_type,
            "reason": reason,
            "suggestion": suggestion,
        }

    @staticmethod
    def _looks_like_syntax_error(error: str) -> bool:
        keywords = ("syntax", "parse", "near", "unexpected", "invalid", "unknown column")
        return any(keyword in error.lower() for keyword in keywords)

    @staticmethod
    def _has_write_operation(sql: str) -> bool:
        return bool(re.search(
            r"\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke)\b",
            sql,
        ))

    @staticmethod
    def _uses_wrong_amount_field(question: str, sql: str) -> bool:
        asks_revenue = any(word in question for word in ("收入", "销售额", "营收", "回款"))
        asks_cost = "成本" in question
        uses_tax_amount = "gross_amount" in sql and "含税" not in question
        uses_standard_cost = "standard_cost" in sql and asks_cost
        return bool((asks_revenue and uses_tax_amount) or uses_standard_cost)

    @staticmethod
    def _missing_exchange_rate(question: str, sql: str) -> bool:
        asks_money = any(word in question for word in ("收入", "销售额", "营收", "回款", "毛利"))
        aggregates_money = "sum(" in sql or "avg(" in sql
        return asks_money and aggregates_money and "exchange_rates" not in sql

    @staticmethod
    def _missing_dimension_join(question: str, sql: str) -> bool:
        needs_product = any(word in question for word in ("产品线", "产品分类", "技术路线", "产品"))
        needs_customer = any(word in question for word in ("客户类型", "客户行业", "客户", "国家"))
        product_missing = needs_product and "dim_products" not in sql
        customer_missing = needs_customer and "dim_customers" not in sql
        return product_missing or customer_missing

    @staticmethod
    def _missing_sales_filter(question: str, sql: str) -> bool:
        asks_sales = any(word in question for word in ("收入", "销售额", "订单", "客单价", "毛利"))
        mentions_order_table = "sales_orders" in sql
        return asks_sales and mentions_order_table and "order_status" not in sql

    @staticmethod
    def _missing_dynamic_time_logic(question: str, sql: str) -> bool:
        asks_dynamic_time = any(word in question for word in ("最近", "本月", "本季度", "上月", "今年"))
        has_time_logic = any(token in sql for token in (
            "curdate()",
            "date_sub",
            "date_format",
            "last_day",
            "makedate",
            "year(",
            "month(",
        ))
        return asks_dynamic_time and not has_time_logic

    @staticmethod
    def _has_grouping_mismatch(sql: str) -> bool:
        if " group by " not in sql or not re.search(r"\b(sum|avg|count|max|min)\s*\(", sql):
            return False

        select_match = re.search(r"select\s+(.*?)\s+from\s", sql, flags=re.DOTALL)
        group_match = re.search(r"group\s+by\s+(.*?)(order\s+by|limit|;|$)", sql, flags=re.DOTALL)
        if not select_match or not group_match:
            return False

        select_items = ErrorAnalyzer._split_select_items(select_match.group(1))
        group_text = group_match.group(1)
        non_aggregate_items = [
            item.split(" as ")[0].strip()
            for item in select_items
            if not re.search(r"\b(sum|avg|count|max|min|nullif)\s*\(", item)
        ]
        return any(item and item not in group_text for item in non_aggregate_items)

    @staticmethod
    def _split_select_items(select_clause: str) -> list[str]:
        """按顶层逗号拆分 SELECT 项，忽略函数参数内部的逗号。"""
        items = []
        current = []
        depth = 0

        for char in select_clause:
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1

            if char == "," and depth == 0:
                item = "".join(current).strip()
                if item:
                    items.append(item)
                current = []
                continue

            current.append(char)

        item = "".join(current).strip()
        if item:
            items.append(item)
        return items
