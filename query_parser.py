"""
用户查询解析模块。

当前负责最基础的输入清洗与校验，为后续意图识别、实体抽取和任务拆解保留边界。
"""


class QueryParser:
    """自然语言问题解析器。"""

    def parse(self, user_input: str) -> dict:
        """清洗用户输入并输出标准解析结构。"""
        question = user_input.strip()
        return {
            "original_question": question,
            "is_valid": bool(question),
        }

    def validate(self, parsed_query: dict) -> bool:
        """判断解析结果是否可进入生成链路。"""
        return bool(parsed_query.get("is_valid"))
