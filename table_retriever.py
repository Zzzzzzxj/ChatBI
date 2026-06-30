"""
表级 Schema 召回模块。

使用 LangChain 的 Embeddings 抽象与 ChromaDB 持久化向量库，为自然语言问题
召回最相关的业务表。该模块用于在生成 SQL 前缩小 Schema 范围，降低无关表和
字段对模型判断的干扰。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from config import LLM_CONFIG


TABLE_METADATA: dict[str, dict[str, str]] = {
    "dim_customers": {
        "description": (
            "客户维度表，存储客户名称、客户类型、所属行业、国家和销售大区。"
            "用于按客户、客户类型、行业、国家或区域分析收入、利润和订单分布。"
        ),
        "domain": "维度表",
        "key_fields": "customer_id, customer_name, customer_type, industry, country, region",
    },
    "dim_products": {
        "description": (
            "产品维度表，存储产品名称、产品线、产品分类、技术路线、材料成本和人工成本。"
            "用于按产品、产品线、产品分类或技术路线分析收入、成本、毛利和毛利率。"
        ),
        "domain": "维度表",
        "key_fields": (
            "product_id, product_name, product_line, category, tech_route, "
            "standard_cost, material_cost, labor_cost"
        ),
    },
    "sales_orders": {
        "description": (
            "销售订单事实表，记录订单日期、订单状态、客户、产品、销售区域、数量、单价、"
            "折扣、含税总额、不含税收入和币种。用于收入、销售额、订单数量、销量、"
            "客单价、毛利和区域销售分析。"
        ),
        "domain": "事实表",
        "key_fields": (
            "order_id, order_no, customer_id, product_id, region, order_date, "
            "order_status, quantity, unit_price, discount_amount, gross_amount, "
            "net_amount, currency"
        ),
    },
    "exchange_rates": {
        "description": (
            "汇率参考表，按日期和币种记录兑人民币汇率。用于将多币种收入、销售额、"
            "毛利等金额统一换算为人民币口径。"
        ),
        "domain": "参考表",
        "key_fields": "rate_date, currency, rate_to_cny",
    },
    "finance_expenses": {
        "description": (
            "费用事实表，记录各部门期间费用，包括研发费用、销售费用、管理费用、财务费用、"
            "市场费用、物流费用和质保费用。用于费用分析、期间费用汇总和利润口径计算。"
        ),
        "domain": "事实表",
        "key_fields": (
            "expense_id, expense_date, department, rd_expense, selling_expense, "
            "admin_expense, finance_expense, marketing_expense, logistics_expense, "
            "warranty_expense"
        ),
    },
}


CHROMA_PERSIST_DIR = Path(__file__).resolve().parent / "chroma_db" / "tables"


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
    """获取表描述向量库。"""
    return Chroma(
        collection_name="table_descriptions",
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_PERSIST_DIR),
        collection_metadata={"hnsw:space": "cosine"},
        relevance_score_fn=_cosine_relevance_score,
    )


def _build_documents() -> list[Document]:
    """将表元数据转换为 LangChain Document。"""
    documents = []
    for table_name, metadata in TABLE_METADATA.items():
        documents.append(
            Document(
                page_content=metadata["description"],
                metadata={
                    "table_name": table_name,
                    "domain": metadata["domain"],
                    "key_fields": metadata["key_fields"],
                },
            )
        )
    return documents


def build_index(force_rebuild: bool = False) -> Chroma:
    """
    构建或加载表级向量索引。

    Args:
        force_rebuild: 是否清空已有索引并重新写入表描述。

    Returns:
        Chroma 向量库实例。
    """
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
        ids=[doc.metadata["table_name"] for doc in documents],
    )
    return vectorstore


def retrieve_tables(
    query: str,
    top_k: int = 3,
    score_threshold: float = 0.2,
    domain_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    根据自然语言问题召回相关表。

    Args:
        query: 用户自然语言问题。
        top_k: 返回的候选表数量。
        score_threshold: 相似度阈值，低于该值的结果会被过滤。
        domain_filter: 可选领域过滤，例如“事实表”或“维度表”。

    Returns:
        候选表列表，包含表名、相似度、领域、关键字段和描述。
    """
    vectorstore = get_vectorstore()
    if vectorstore._collection.count() == 0:
        build_index(force_rebuild=False)

    search_kwargs: dict[str, Any] = {"k": top_k}
    if domain_filter:
        search_kwargs["filter"] = {"domain": domain_filter}

    results_with_scores = vectorstore.similarity_search_with_relevance_scores(
        query,
        **search_kwargs,
    )

    results = []
    for doc, score in results_with_scores:
        if score < score_threshold:
            continue
        results.append(
            {
                "table_name": doc.metadata["table_name"],
                "score": round(score, 4),
                "description": doc.page_content,
                "domain": doc.metadata["domain"],
                "key_fields": doc.metadata["key_fields"],
            }
        )
    return results


def format_retrieval_context(tables: list[dict[str, Any]]) -> str:
    """将召回结果格式化为可读上下文。"""
    lines = []
    for item in tables:
        lines.append(
            "\n".join(
                [
                    f"表：{item['table_name']}（{item['domain']}，score={item['score']}）",
                    f"- 关键字段：{item['key_fields']}",
                    f"- 说明：{item['description']}",
                ]
            )
        )
    return "\n\n".join(lines)


def main() -> None:
    """命令行入口：构建索引并执行一次召回检查。"""
    build_index(force_rebuild=False)
    question = "按客户类型统计收入，需要换算成人民币"
    for item in retrieve_tables(question, top_k=5):
        print(f"{item['table_name']}\t{item['score']}\t{item['domain']}")


if __name__ == "__main__":
    main()
