"""
Prompt 构造模块。

将数据库 Schema、Few-shot 示例、业务规则和用户问题组装为可控的 Text2SQL 输入。
"""


SCHEMA = """
表：dim_customers（客户维度表）
- customer_id INT 主键
- customer_name VARCHAR(100) 客户名称
- customer_type VARCHAR(50) 客户类型：OEM整车厂 / 储能集成商 / 电网集团 / 工商业用户 / 换电运营商 / 经销商
- industry VARCHAR(50) 客户行业：交通 / 能源 / 工业 / 特种交通
- country VARCHAR(50) 具体国家，如 Germany
- region VARCHAR(50) 大区，如 欧洲、北美

表：dim_products（产品维度表）
- product_id INT 主键
- product_name VARCHAR(100) 产品名称
- product_line VARCHAR(50) 产品线：动力电池-乘用车 / 动力电池-商用车 / 储能系统-电网级 / 储能系统-工商业 / 电池材料与回收
- category VARCHAR(50) 产品分类：高能量密度型 / 超快充型 / 混动专用型 / 低温适配型 / 商用车标准型 / 电网级储能型 / 工商业储能型
- tech_route VARCHAR(50) 技术路线：三元锂 / 磷酸铁锂 / 钠离子 / 固态电池
- standard_cost DECIMAL(10,2) 标准成本
- material_cost DECIMAL(10,2) 材料成本
- labor_cost DECIMAL(10,2) 人工成本

表：sales_orders（销售订单表）
- order_id BIGINT 主键
- order_no VARCHAR(50) 订单编号
- customer_id INT 外键 -> dim_customers.customer_id
- product_id INT 外键 -> dim_products.product_id
- region VARCHAR(50) 销售区域
- order_date DATE 订单日期
- order_status VARCHAR(20) 订单状态：completed / cancelled / pending
- quantity DECIMAL(10,2) 数量（MWh 或套数）
- unit_price DECIMAL(10,2) 单价（每 MWh 或每套价格，不含税）
- discount_amount DECIMAL(10,2) 折扣金额
- gross_amount DECIMAL(12,2) 含税总额
- net_amount DECIMAL(12,2) 不含税收入（财务口径的销售额）
- currency VARCHAR(10) 币种

表：exchange_rates（汇率表）
- rate_date DATE 日期
- currency VARCHAR(10) 币种
- rate_to_cny DECIMAL(10,4) 兑人民币汇率

表：finance_expenses（费用表）
- expense_id BIGINT 主键
- expense_date DATE 费用日期
- department VARCHAR(50) 部门
- rd_expense DECIMAL(12,2) 研发费用
- selling_expense DECIMAL(12,2) 销售费用
- admin_expense DECIMAL(12,2) 管理费用
- finance_expense DECIMAL(12,2) 财务费用
- marketing_expense DECIMAL(12,2) 市场费用（属于销售费用子项）
- logistics_expense DECIMAL(12,2) 物流费用
- warranty_expense DECIMAL(12,2) 质保费用
"""


FEW_SHOT_EXAMPLES = """
示例1：
问题：查询已完成订单的总数量
SQL：SELECT COUNT(*) AS completed_order_count FROM sales_orders WHERE order_status = 'completed';

示例2：
问题：按客户类型统计订单数量
SQL：SELECT c.customer_type, COUNT(*) AS order_count FROM sales_orders o JOIN dim_customers c ON o.customer_id = c.customer_id WHERE o.order_status = 'completed' GROUP BY c.customer_type;

示例3：
问题：查询2026年第一季度的总费用
SQL：SELECT SUM(rd_expense + selling_expense + admin_expense + finance_expense) AS total_expense FROM finance_expenses WHERE expense_date >= '2026-01-01' AND expense_date < '2026-04-01';

示例4：
问题：按产品线统计总收入
SQL：SELECT p.product_line, SUM(o.net_amount * er.rate_to_cny) AS revenue_rmb FROM sales_orders o JOIN dim_products p ON o.product_id = p.product_id JOIN exchange_rates er ON o.order_date = er.rate_date AND o.currency = er.currency WHERE o.order_status = 'completed' GROUP BY p.product_line;

示例5：
问题：各产品线的毛利率是多少
SQL：SELECT p.product_line, SUM(o.net_amount * er.rate_to_cny - (p.material_cost + p.labor_cost) * o.quantity) / NULLIF(SUM(o.net_amount * er.rate_to_cny), 0) AS gross_margin_rate FROM sales_orders o JOIN dim_products p ON o.product_id = p.product_id JOIN exchange_rates er ON o.order_date = er.rate_date AND o.currency = er.currency WHERE o.order_status = 'completed' GROUP BY p.product_line;
"""


BUSINESS_RULES = """
【业务规则】
1. 收入、销售额、营收默认使用 sales_orders.net_amount，不使用 gross_amount，除非用户明确要求含税金额。
2. 成本默认使用 dim_products.material_cost + dim_products.labor_cost，不使用 standard_cost 代替实际成本。
3. 统计收入、订单量、客单价等销售指标时，必须过滤 order_status = 'completed'。
4. 查询收入、销售额、营收、回款等金额汇总时，默认输出人民币口径，必须通过 order_date 和 currency 关联 exchange_rates，使用 rate_to_cny 折算。
5. 费用汇总时，selling_expense 已包含 marketing_expense、logistics_expense、warranty_expense，不要重复相加。
6. 毛利 = net_amount - (material_cost + labor_cost) * quantity。
7. 毛利率 = 毛利 / 收入，分母使用 NULLIF 防止除零。
8. “最近 N 个月”使用 DATE_SUB(CURDATE(), INTERVAL N MONTH) 作为起始边界。
"""


ERROR_GUARDS = """
【错误防护】
- 字段选择：金额字段先判断含税/不含税；默认收入用 net_amount，默认成本用 material_cost + labor_cost。
- 关联路径：涉及产品线、技术路线、产品分类时必须 JOIN dim_products；涉及客户类型、行业、国家、大区时必须 JOIN dim_customers。
- 汇率换算：收入、销售额、营收、毛利等金额跨币种汇总时必须 JOIN exchange_rates，条件为 order_date = rate_date 且 currency 相等。
- 过滤条件：销售收入、订单数量、毛利、客单价等销售指标必须包含 order_status = 'completed'。
- 时间边界：月份、季度、最近 N 个月使用闭开区间，避免重复统计边界日期。
- 聚合维度：SELECT 中的非聚合字段必须全部出现在 GROUP BY 中。
- 查询安全：只能输出 SELECT 查询，不能输出会修改结构或数据的语句。
"""


def build_prompt(
    user_question: str,
    use_few_shot: bool = True,
    use_rules: bool = True,
    use_guards: bool = True,
    indicator_knowledge: str = "",
) -> tuple[str, str]:
    """构造发送给大模型的 system message 与 user prompt。"""
    system_message = (
        "你是企业经营分析场景下的 SQL 生成助手，"
        "只能根据给定 Schema 生成只读 MySQL 查询，并严格遵守业务口径和防错约束。"
    )

    prompt = f"""【数据库 Schema】
{SCHEMA}
"""

    if use_rules:
        prompt += f"""
{BUSINESS_RULES}
"""

    if use_few_shot:
        prompt += f"""
【示例】
{FEW_SHOT_EXAMPLES}
"""

    if use_guards:
        prompt += f"""
{ERROR_GUARDS}
"""

    if indicator_knowledge:
        prompt += f"""
{indicator_knowledge}
"""

    prompt += f"""
【用户问题】
{user_question}

【输出要求】
1. 只输出一条 SQL，不要解释，不要 Markdown 代码块。
2. 只能生成 SELECT 查询，不要生成 INSERT、UPDATE、DELETE、DROP、ALTER 等语句。
3. 表名和字段名必须来自上方 Schema。
4. 涉及多表时必须写出清晰的 JOIN 条件。
5. GROUP BY 字段必须覆盖 SELECT 中的非聚合字段。
6. 涉及业务指标时优先遵守【业务规则】和【错误防护】。
7. 如果提供了【指标知识】，优先使用其中的定义、公式、数据来源和强制过滤条件。

请直接输出 SQL：
"""
    return system_message, prompt
