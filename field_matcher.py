"""
字段级 Schema 匹配模块。

在表级召回基础上，对候选表中的字段进行语义匹配，并结合业务规则处理
常见字段歧义，例如收入口径、含税金额、费用层级和汇率换算字段选择。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from config import LLM_CONFIG
from table_retriever import retrieve_tables


FIELD_METADATA: dict[str, dict[str, str]] = {
    "dim_customers.customer_id": {
        "table": "dim_customers",
        "field": "customer_id",
        "description": "客户唯一标识，主键，用于关联 sales_orders.customer_id。",
        "domain": "维度表",
    },
    "dim_customers.customer_name": {
        "table": "dim_customers",
        "field": "customer_name",
        "description": "客户名称，例如宝马集团、国家电网、特斯拉，用于查询特定客户的订单或收入。",
        "domain": "维度表",
    },
    "dim_customers.customer_type": {
        "table": "dim_customers",
        "field": "customer_type",
        "description": "客户类型，枚举值包括 OEM整车厂、储能集成商、电网集团、工商业用户、换电运营商、经销商，用于按客户类型分析收入和订单分布。",
        "domain": "维度表",
    },
    "dim_customers.industry": {
        "table": "dim_customers",
        "field": "industry",
        "description": "客户所属行业，枚举值包括交通、能源、工业、特种交通，用于按行业分析客户和收入。",
        "domain": "维度表",
    },
    "dim_customers.country": {
        "table": "dim_customers",
        "field": "country",
        "description": "客户所在国家，例如 Germany、United States、Japan、China；提到具体国家时使用此字段。",
        "domain": "维度表",
    },
    "dim_customers.region": {
        "table": "dim_customers",
        "field": "region",
        "description": "客户所属销售大区，例如欧洲、北美、亚太、中东非洲、拉美；按市场或大区汇总时使用此字段。",
        "domain": "维度表",
    },
    "dim_products.product_id": {
        "table": "dim_products",
        "field": "product_id",
        "description": "产品唯一标识，主键，用于关联 sales_orders.product_id。",
        "domain": "维度表",
    },
    "dim_products.product_name": {
        "table": "dim_products",
        "field": "product_name",
        "description": "产品名称，例如电池包、储能柜等，用于查询特定产品销量、收入或成本。",
        "domain": "维度表",
    },
    "dim_products.product_line": {
        "table": "dim_products",
        "field": "product_line",
        "description": "产品线，枚举值包括动力电池-乘用车、动力电池-商用车、储能系统-电网级、储能系统-工商业、电池材料与回收，用于按业务板块分析收入和毛利。",
        "domain": "维度表",
    },
    "dim_products.category": {
        "table": "dim_products",
        "field": "category",
        "description": "产品分类，比产品线更细，用于按高能量密度型、超快充型、低温适配型等细分品类分析。",
        "domain": "维度表",
    },
    "dim_products.tech_route": {
        "table": "dim_products",
        "field": "tech_route",
        "description": "技术路线，枚举值包括三元锂、磷酸铁锂、钠离子、固态电池，用于技术路线维度分析。",
        "domain": "维度表",
    },
    "dim_products.standard_cost": {
        "table": "dim_products",
        "field": "standard_cost",
        "description": "产品标准成本，用于标准成本核算；毛利计算优先使用 material_cost + labor_cost。",
        "domain": "维度表",
    },
    "dim_products.material_cost": {
        "table": "dim_products",
        "field": "material_cost",
        "description": "材料成本，毛利计算核心字段，毛利 = net_amount - (material_cost + labor_cost) * quantity。",
        "domain": "维度表",
    },
    "dim_products.labor_cost": {
        "table": "dim_products",
        "field": "labor_cost",
        "description": "人工成本，毛利计算核心字段，毛利 = net_amount - (material_cost + labor_cost) * quantity。",
        "domain": "维度表",
    },
    "sales_orders.order_id": {
        "table": "sales_orders",
        "field": "order_id",
        "description": "订单唯一标识，主键。",
        "domain": "事实表",
    },
    "sales_orders.order_no": {
        "table": "sales_orders",
        "field": "order_no",
        "description": "订单编号，用于查询特定订单明细。",
        "domain": "事实表",
    },
    "sales_orders.customer_id": {
        "table": "sales_orders",
        "field": "customer_id",
        "description": "客户外键，关联 dim_customers.customer_id；按客户维度分析时需要使用。",
        "domain": "事实表",
    },
    "sales_orders.product_id": {
        "table": "sales_orders",
        "field": "product_id",
        "description": "产品外键，关联 dim_products.product_id；按产品维度分析时需要使用。",
        "domain": "事实表",
    },
    "sales_orders.region": {
        "table": "sales_orders",
        "field": "region",
        "description": "订单销售区域，可直接用于按大区过滤或汇总订单收入。",
        "domain": "事实表",
    },
    "sales_orders.order_date": {
        "table": "sales_orders",
        "field": "order_date",
        "description": "订单日期，用于本月、上月、季度、年度、最近 N 个月等时间范围筛选，也用于关联汇率日期。",
        "domain": "事实表",
    },
    "sales_orders.order_status": {
        "table": "sales_orders",
        "field": "order_status",
        "description": "订单状态，枚举值包括 completed、cancelled、pending；统计收入、订单量等指标时必须过滤 completed。",
        "domain": "事实表",
    },
    "sales_orders.quantity": {
        "table": "sales_orders",
        "field": "quantity",
        "description": "订单数量，用于统计销量和计算成本。",
        "domain": "事实表",
    },
    "sales_orders.unit_price": {
        "table": "sales_orders",
        "field": "unit_price",
        "description": "订单单价，不含税，用于分析定价和客单价。",
        "domain": "事实表",
    },
    "sales_orders.discount_amount": {
        "table": "sales_orders",
        "field": "discount_amount",
        "description": "折扣金额，用于分析折扣力度和实际售价。",
        "domain": "事实表",
    },
    "sales_orders.gross_amount": {
        "table": "sales_orders",
        "field": "gross_amount",
        "description": "含税总额；除非用户明确要求含税金额，否则收入和销售额不使用该字段。",
        "domain": "事实表",
    },
    "sales_orders.net_amount": {
        "table": "sales_orders",
        "field": "net_amount",
        "description": "不含税收入，财务口径的销售额；收入、销售额、营收默认使用该字段。",
        "domain": "事实表",
    },
    "sales_orders.currency": {
        "table": "sales_orders",
        "field": "currency",
        "description": "订单币种，关联 exchange_rates.currency，用于多币种金额折算。",
        "domain": "事实表",
    },
    "exchange_rates.rate_date": {
        "table": "exchange_rates",
        "field": "rate_date",
        "description": "汇率日期，通过 sales_orders.order_date = exchange_rates.rate_date 关联。",
        "domain": "参考表",
    },
    "exchange_rates.currency": {
        "table": "exchange_rates",
        "field": "currency",
        "description": "币种代码，通过 sales_orders.currency = exchange_rates.currency 关联。",
        "domain": "参考表",
    },
    "exchange_rates.rate_to_cny": {
        "table": "exchange_rates",
        "field": "rate_to_cny",
        "description": "兑人民币汇率；人民币金额 = 外币金额 * rate_to_cny。",
        "domain": "参考表",
    },
    "finance_expenses.expense_id": {
        "table": "finance_expenses",
        "field": "expense_id",
        "description": "费用记录唯一标识，主键。",
        "domain": "事实表",
    },
    "finance_expenses.expense_date": {
        "table": "finance_expenses",
        "field": "expense_date",
        "description": "费用日期，用于按时间范围筛选费用记录。",
        "domain": "事实表",
    },
    "finance_expenses.department": {
        "table": "finance_expenses",
        "field": "department",
        "description": "部门名称，例如研发部、销售部、管理部，用于按部门分析费用。",
        "domain": "事实表",
    },
    "finance_expenses.rd_expense": {
        "table": "finance_expenses",
        "field": "rd_expense",
        "description": "研发费用，用于研发投入分析。",
        "domain": "事实表",
    },
    "finance_expenses.selling_expense": {
        "table": "finance_expenses",
        "field": "selling_expense",
        "description": "销售费用总项，已包含市场费用、物流费用和质保费用，汇总时不要重复相加。",
        "domain": "事实表",
    },
    "finance_expenses.admin_expense": {
        "table": "finance_expenses",
        "field": "admin_expense",
        "description": "管理费用，用于行政管理相关费用分析。",
        "domain": "事实表",
    },
    "finance_expenses.finance_expense": {
        "table": "finance_expenses",
        "field": "finance_expense",
        "description": "财务费用，包括利息支出、汇兑损益等。",
        "domain": "事实表",
    },
    "finance_expenses.marketing_expense": {
        "table": "finance_expenses",
        "field": "marketing_expense",
        "description": "市场费用，属于 selling_expense 的子项，费用汇总时不能与 selling_expense 重复相加。",
        "domain": "事实表",
    },
    "finance_expenses.logistics_expense": {
        "table": "finance_expenses",
        "field": "logistics_expense",
        "description": "物流费用，属于 selling_expense 的子项，费用汇总时不能与 selling_expense 重复相加。",
        "domain": "事实表",
    },
    "finance_expenses.warranty_expense": {
        "table": "finance_expenses",
        "field": "warranty_expense",
        "description": "质保费用，属于 selling_expense 的子项，费用汇总时不能与 selling_expense 重复相加。",
        "domain": "事实表",
    },
}


BUSINESS_RULES = [
    {
        "type": "whitelist",
        "trigger_keywords": ["收入", "销售额", "营业收入", "营收", "毛利", "毛利率", "利润"],
        "force_include": ["sales_orders.net_amount"],
        "reason": "收入默认使用不含税口径",
    },
    {
        "type": "blacklist",
        "trigger_keywords": ["收入", "销售额", "营业收入", "营收", "毛利", "毛利率", "利润"],
        "force_exclude": ["sales_orders.gross_amount"],
        "reason": "未明确含税时排除含税总额",
    },
    {
        "type": "whitelist",
        "trigger_keywords": ["含税", "含税金额", "含税收入"],
        "force_include": ["sales_orders.gross_amount"],
        "reason": "明确含税时使用含税总额",
    },
    {
        "type": "blacklist",
        "trigger_keywords": ["含税", "含税金额", "含税收入"],
        "force_exclude": ["sales_orders.net_amount"],
        "reason": "明确含税时排除不含税收入",
    },
    {
        "type": "whitelist",
        "trigger_keywords": ["成本", "毛利", "利润"],
        "force_include": ["dim_products.material_cost", "dim_products.labor_cost"],
        "reason": "成本计算使用材料成本和人工成本",
    },
    {
        "type": "whitelist",
        "trigger_keywords": ["收入", "销售额", "订单量", "订单数", "客单价"],
        "force_include": ["sales_orders.order_status"],
        "reason": "销售指标需要订单状态过滤",
    },
    {
        "type": "conditional",
        "trigger_keywords": ["人民币", "汇率", "换算", "折算", "统一币种"],
        "force_include": [
            "exchange_rates.rate_to_cny",
            "exchange_rates.rate_date",
            "exchange_rates.currency",
        ],
        "reason": "金额折算需要汇率表字段",
    },
    {
        "type": "blacklist",
        "trigger_keywords": ["总费用", "期间费用合计", "费用汇总"],
        "force_exclude": [
            "finance_expenses.marketing_expense",
            "finance_expenses.logistics_expense",
            "finance_expenses.warranty_expense",
        ],
        "reason": "费用汇总排除销售费用子项，避免重复计算",
    },
]


CHROMA_PERSIST_DIR = Path(__file__).resolve().parent / "chroma_db" / "fields"


def _cosine_relevance_score(distance: float) -> float:
    """将 ChromaDB cosine distance 转换为相似度分数。"""
    return 1 - distance


def get_embeddings() -> OpenAIEmbeddings:
    """构建项目统一配置下的 Embeddings 客户端。"""
    return OpenAIEmbeddings(
        model=LLM_CONFIG["embedding_model"],
        base_url=LLM_CONFIG["base_url"],
        api_key=LLM_CONFIG["api_key"],
    )


def get_vectorstore() -> Chroma:
    """获取字段描述向量库。"""
    return Chroma(
        collection_name="field_descriptions",
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_PERSIST_DIR),
        collection_metadata={"hnsw:space": "cosine"},
        relevance_score_fn=_cosine_relevance_score,
    )


def _build_documents() -> list[Document]:
    """将字段元数据转换为 LangChain Document。"""
    documents = []
    for field_key, metadata in FIELD_METADATA.items():
        documents.append(
            Document(
                page_content=metadata["description"],
                metadata={
                    "table_name": metadata["table"],
                    "field_name": metadata["field"],
                    "field_key": field_key,
                    "domain": metadata["domain"],
                },
            )
        )
    return documents


def build_field_index(force_rebuild: bool = False) -> Chroma:
    """构建或加载字段级向量索引。"""
    vectorstore = get_vectorstore()
    existing_count = vectorstore._collection.count()

    if existing_count > 0 and not force_rebuild:
        return vectorstore

    if existing_count > 0:
        existing_ids = vectorstore._collection.get()["ids"]
        if existing_ids:
            vectorstore._collection.delete(ids=existing_ids)

    documents = _build_documents()
    vectorstore.add_documents(
        documents,
        ids=[doc.metadata["field_key"] for doc in documents],
    )
    return vectorstore


def evaluate_rules(query: str) -> dict[str, list[str]]:
    """根据用户问题评估字段强制包含和排除规则。"""
    force_include = set()
    force_exclude = set()
    normalized_query = query.lower()

    for rule in BUSINESS_RULES:
        if not any(keyword in normalized_query for keyword in rule["trigger_keywords"]):
            continue

        if rule["type"] in {"whitelist", "conditional"}:
            force_include.update(rule.get("force_include", []))
        elif rule["type"] == "blacklist":
            force_exclude.update(rule.get("force_exclude", []))

    force_exclude -= force_include
    return {
        "force_include": sorted(force_include),
        "force_exclude": sorted(force_exclude),
    }


def match_fields(
    query: str,
    candidate_tables: list[str] | None = None,
    top_k: int = 10,
    score_threshold: float = 0.15,
    rule_weight: float = 0.3,
) -> list[dict[str, Any]]:
    """
    在候选表范围内匹配相关字段。

    最终分数由向量相似度和业务规则共同决定。业务规则用于处理模型容易混淆
    的字段，例如 net_amount 与 gross_amount、费用总项与费用子项。
    """
    vectorstore = get_vectorstore()
    if vectorstore._collection.count() == 0:
        build_field_index(force_rebuild=False)

    search_kwargs: dict[str, Any] = {"k": min(top_k * 3, 30)}
    if candidate_tables and len(candidate_tables) == 1:
        search_kwargs["filter"] = {"table_name": candidate_tables[0]}
    elif candidate_tables and len(candidate_tables) > 1:
        search_kwargs["filter"] = {"table_name": {"$in": candidate_tables}}

    results_with_scores = vectorstore.similarity_search_with_relevance_scores(
        query,
        **search_kwargs,
    )

    rule_result = evaluate_rules(query)
    force_include = set(rule_result["force_include"])
    force_exclude = set(rule_result["force_exclude"])

    scored_fields = []
    seen_keys = set()

    for doc, embedding_score in results_with_scores:
        field_key = doc.metadata["field_key"]
        if field_key in seen_keys:
            continue
        seen_keys.add(field_key)

        if candidate_tables and doc.metadata["table_name"] not in candidate_tables:
            continue

        rule_score = 0.0
        rule_applied = None
        if field_key in force_include:
            rule_score = 1.0
            rule_applied = "强制包含"
        elif field_key in force_exclude:
            rule_score = -1.0
            rule_applied = "强制排除"

        final_score = (1 - rule_weight) * embedding_score + rule_weight * rule_score

        scored_fields.append(
            {
                "field_key": field_key,
                "table": doc.metadata["table_name"],
                "field": doc.metadata["field_name"],
                "score": round(final_score, 4),
                "embedding_score": round(embedding_score, 4),
                "rule_applied": rule_applied,
                "description": doc.page_content,
            }
        )

    for field_key in force_include:
        if field_key in seen_keys:
            continue
        metadata = FIELD_METADATA.get(field_key)
        if not metadata:
            continue
        if candidate_tables and metadata["table"] not in candidate_tables:
            continue

        scored_fields.append(
            {
                "field_key": field_key,
                "table": metadata["table"],
                "field": metadata["field"],
                "score": round(rule_weight, 4),
                "embedding_score": 0.0,
                "rule_applied": "强制包含（补充）",
                "description": metadata["description"],
            }
        )

    scored_fields.sort(key=lambda item: item["score"], reverse=True)
    return [item for item in scored_fields if item["score"] >= score_threshold][:top_k]


def retrieve_schema(
    query: str,
    table_top_k: int = 3,
    field_top_k: int = 10,
    table_threshold: float = 0.2,
    field_threshold: float = 0.15,
) -> dict[str, Any]:
    """先召回相关表，再在候选表范围内匹配字段。"""
    tables = retrieve_tables(query, top_k=table_top_k, score_threshold=table_threshold)
    candidate_table_names = [table["table_name"] for table in tables]
    fields = match_fields(
        query,
        candidate_tables=candidate_table_names,
        top_k=field_top_k,
        score_threshold=field_threshold,
    )

    return {
        "tables": tables,
        "fields": fields,
        "schema_snippet": build_schema_snippet(tables, fields),
    }


def build_schema_snippet(tables: list[dict[str, Any]], fields: list[dict[str, Any]]) -> str:
    """根据召回表和字段生成精简 Schema 片段。"""
    table_fields: dict[str, list[str]] = {
        table["table_name"]: []
        for table in tables
    }

    for field in fields:
        if field["table"] in table_fields:
            table_fields[field["table"]].append(field["field"])

    lines = []
    for table_name, field_list in table_fields.items():
        if field_list:
            lines.append(f"表：{table_name}（相关字段：{', '.join(field_list)}）")
        else:
            lines.append(f"表：{table_name}")

    return "\n".join(lines) if lines else "未召回相关表"


def main() -> None:
    """命令行入口：构建索引并执行一次字段匹配检查。"""
    build_field_index(force_rebuild=False)
    result = retrieve_schema("各产品线的毛利率")
    print(result["schema_snippet"])


if __name__ == "__main__":
    main()
