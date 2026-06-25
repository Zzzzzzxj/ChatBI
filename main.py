"""
ChatBI 命令行入口。

串联查询解析、Prompt 构造、SQL 生成、数据库执行和结果展示，形成第一个完整可运行的 Text2SQL 链路。
"""

import sys

from database import DatabaseClient
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

    def run(self, user_question: str) -> dict:
        """执行一次自然语言到查询结果的完整流程。"""
        parsed = self.parser.parse(user_question)
        if not self.parser.validate(parsed):
            return {
                "success": False,
                "error_type": "validation",
                "error": "请输入有效问题。",
            }

        system_message, prompt = build_prompt(parsed["original_question"])

        try:
            sql = self.llm.generate_sql(system_message, prompt)
        except Exception as exc:
            return {
                "success": False,
                "error_type": "llm",
                "error": str(exc),
            }

        try:
            columns, rows = self.db.execute(sql)
            return {
                "success": True,
                "question": parsed["original_question"],
                "sql": sql,
                "columns": columns,
                "rows": rows,
                "formatted": self.formatter.format(columns, rows),
            }
        except Exception as exc:
            return {
                "success": False,
                "error_type": "database",
                "error": str(exc),
                "sql": sql,
            }


def print_result(result: dict) -> None:
    """输出单次运行结果。"""
    if result.get("sql"):
        print("\nSQL:")
        print(result["sql"])

    if result["success"]:
        print("\nResult:")
        print(result["formatted"])
        return

    print("\nError:")
    print(f"[{result['error_type']}] {result['error']}")


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
