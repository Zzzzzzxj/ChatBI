"""
ChatBI 命令行入口。

串联查询解析、Prompt 构造、SQL 生成、数据库执行和结果展示，形成第一个完整可运行的 Text2SQL 链路。
"""

import sys

from database import DatabaseClient
from error_analyzer import ErrorAnalyzer
from indicator_knowledge import IndicatorKnowledge
from llm_client import LLMClient
from prompt_builder import build_prompt
from query_parser import QueryParser
from result_formatter import ResultFormatter


class ChatBISystem:
    """ChatBI 主流程编排器。"""

    def __init__(self) -> None:
        self.parser = QueryParser()
        self.llm = LLMClient()
        self.db = DatabaseClient()
        self.formatter = ResultFormatter()
        self.analyzer = ErrorAnalyzer()
        self.indicator_knowledge = IndicatorKnowledge()

    def run(
        self,
        user_question: str,
        use_few_shot: bool = True,
        use_rules: bool = True,
        use_guards: bool = True,
        use_indicator_knowledge: bool = True,
    ) -> dict:
        """执行一次自然语言到查询结果的完整流程。"""
        parsed = self.parser.parse(user_question)
        if not self.parser.validate(parsed):
            return {
                "success": False,
                "error_type": "validation",
                "error": "请输入有效问题。",
            }

        indicator_context = {"detected_indicators": [], "indicator_block": ""}
        if use_indicator_knowledge:
            indicator_context = self.indicator_knowledge.get_indicator_context(
                parsed["original_question"]
            )

        system_message, prompt = build_prompt(
            parsed["original_question"],
            use_few_shot=use_few_shot,
            use_rules=use_rules,
            use_guards=use_guards,
            indicator_knowledge=indicator_context["indicator_block"],
        )

        try:
            sql = self.llm.generate_sql(system_message, prompt)
        except Exception as exc:
            return {
                "success": False,
                "error_type": "llm",
                "error": str(exc),
                "metadata": {
                    "detected_indicators": indicator_context["detected_indicators"],
                    "used_indicator_knowledge": use_indicator_knowledge,
                },
            }

        diagnostics = self.analyzer.analyze(parsed["original_question"], sql)

        try:
            columns, rows = self.db.execute(sql)
            return {
                "success": True,
                "question": parsed["original_question"],
                "sql": sql,
                "columns": columns,
                "rows": rows,
                "formatted": self.formatter.format(columns, rows),
                "diagnostics": diagnostics,
                "metadata": {
                    "detected_indicators": indicator_context["detected_indicators"],
                    "used_indicator_knowledge": use_indicator_knowledge,
                },
            }
        except Exception as exc:
            diagnostics = self.analyzer.analyze(
                parsed["original_question"],
                sql,
                execution_error=str(exc),
            )
            return {
                "success": False,
                "error_type": "database",
                "error": str(exc),
                "sql": sql,
                "diagnostics": diagnostics,
                "metadata": {
                    "detected_indicators": indicator_context["detected_indicators"],
                    "used_indicator_knowledge": use_indicator_knowledge,
                },
            }


def print_result(result: dict) -> None:
    """输出单次运行结果。"""
    if result.get("sql"):
        print("\nSQL:")
        print(result["sql"])

    if result["success"]:
        print("\nResult:")
        print(result["formatted"])
        if not result.get("diagnostics", {}).get("ok", True):
            print("\nDiagnostics:")
            for issue in result["diagnostics"]["issues"]:
                print(f"- {issue['type']}: {issue['reason']}")
        return

    print("\nError:")
    print(f"[{result['error_type']}] {result['error']}")
    if result.get("diagnostics", {}).get("issues"):
        print("\nDiagnostics:")
        for issue in result["diagnostics"]["issues"]:
            print(f"- {issue['type']}: {issue['reason']}；{issue['suggestion']}")


def run_cli() -> None:
    """命令行运行入口。"""
    system = ChatBISystem()

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print_result(system.run(question))
        return

    print("ChatBI Text2SQL")
    print("输入 exit / quit / q 退出")

    while True:
        try:
            question = input("\n> ").strip()
        except KeyboardInterrupt:
            print()
            return

        if question.lower() in {"exit", "quit", "q"}:
            return
        print_result(system.run(question))


if __name__ == "__main__":
    run_cli()
