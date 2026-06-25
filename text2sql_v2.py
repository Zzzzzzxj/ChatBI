"""
Text2SQL 原型版本2：COT + 结构化约束（ICIO 框架）

在 v1 基础上增加 Chain-of-Thought 引导与结构化输出约束，
展示 Prompt 工程进阶技巧的效果。

运行方式：
    uv run python text2sql_v2.py
"""

import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from text2sql_v1 import FEW_SHOT_EXAMPLES, SCHEMA


load_dotenv()


# ==================== COT 引导与结构化约束 ====================
COT_INSTRUCTION = """
【思考步骤】
在生成 SQL 之前，请按以下步骤思考：
1. 识别问题中涉及的核心表和字段
2. 判断是否需要 JOIN 以及 JOIN 的条件
3. 确认金额口径（net_amount vs gross_amount）和成本口径
4. 确认是否需要过滤 order_status = 'completed'
5. 确认时间范围和汇率转换需求
6. 最后生成 SQL
"""


OUTPUT_CONSTRAINTS = """
【输出约束】
1. 只输出 SQL 语句，不需要解释
2. 使用标准 MySQL 语法
3. 确保字段名和表名与 Schema 一致
4. 如果涉及多表查询，使用 JOIN 连接
5. 收入口径统一使用 net_amount，成本口径使用 material_cost + labor_cost
6. 统计销售额时，需要按订单日期的汇率转换为人民币
7. 所有收入类统计必须包含 WHERE order_status = 'completed'
"""


def build_prompt(user_question: str) -> str:
    """构造包含 COT 和结构化约束的 Prompt（ICIO 框架）。"""
    prompt = f"""你是一个专业的 SQL 生成助手，擅长根据业务问题生成标准 MySQL 查询语句。

【数据库Schema】
{SCHEMA}

【示例】
{FEW_SHOT_EXAMPLES}

{COT_INSTRUCTION}

{OUTPUT_CONSTRAINTS}

【用户问题】
{user_question}

请直接输出 SQL：
"""
    return prompt


def generate_sql(user_question: str) -> str:
    """调用 LLM 生成 SQL。"""
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
    )

    prompt = build_prompt(user_question)

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "Qwen/Qwen3.5-27B"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1000,
        extra_body={"enable_thinking": False},
    )

    raw_output = response.choices[0].message.content.strip()
    sql = re.sub(r"```sql|```", "", raw_output).strip()
    return sql


def run(question: str) -> None:
    """运行并输出生成的 SQL。"""
    print(f"\n{'=' * 60}")
    print(f"问题：{question}")
    print(f"{'=' * 60}")
    sql = generate_sql(question)
    print(f"\n生成 SQL：\n{sql}")
    print("\n可将上述 SQL 复制到 MySQL 客户端执行验证。")


if __name__ == "__main__":
    questions = [
        "查询已完成订单的总数量",
        "按产品线统计总收入",
        "欧洲市场最近三个月的销售额是多少",
        "各产品线的毛利率是多少",
    ]
    for q in questions:
        run(q)
