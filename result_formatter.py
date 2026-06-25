"""
查询结果格式化模块。

将数据库返回的列和行格式化为命令行中易读的文本表格。
"""

from decimal import Decimal
from typing import Any


class ResultFormatter:
    """结果格式化器。"""

    def format(self, columns: list[str], rows: list[tuple[Any, ...]]) -> str:
        """将查询结果格式化为文本表格。"""
        if not columns:
            return "查询已执行，但没有返回列。"
        if not rows:
            return "查询结果为空。"

        display_rows = [[self._format_value(value) for value in row] for row in rows]
        widths = []
        for idx, column in enumerate(columns):
            max_value_width = max(len(row[idx]) for row in display_rows)
            widths.append(max(len(column), max_value_width))

        header = " | ".join(column.ljust(widths[idx]) for idx, column in enumerate(columns))
        separator = "-+-".join("-" * width for width in widths)
        body = [
            " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(row))
            for row in display_rows
        ]

        return "\n".join([header, separator, *body])

    @staticmethod
    def _format_value(value: Any) -> str:
        """统一格式化数据库返回值。"""
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return f"{value:.2f}"
        return str(value)
