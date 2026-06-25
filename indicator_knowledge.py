"""
指标知识模块。

加载指标定义，识别自然语言问题中的指标关键词，并生成可注入 Prompt 的指标知识文本。
"""

import json
from pathlib import Path


class IndicatorKnowledge:
    """指标知识管理器。"""

    def __init__(self, config_path: str = "indicators.json") -> None:
        with Path(config_path).open("r", encoding="utf-8") as file:
            data = json.load(file)

        self.indicators = {indicator["name"]: indicator for indicator in data["indicators"]}
        self.alias_map = self._build_alias_map(data["indicators"])

    def detect_indicators(self, question: str) -> list[str]:
        """从用户问题中识别涉及的指标名称。"""
        detected = []
        normalized_question = question.lower()

        for alias, standard_name in self.alias_map.items():
            if alias in normalized_question and standard_name not in detected:
                detected.append(standard_name)

        return detected

    def get_indicator_text(self, indicator_name: str) -> str:
        """将单个指标定义格式化为 Prompt 可用文本。"""
        indicator = self.indicators.get(indicator_name)
        if not indicator:
            return ""

        lines = [
            f"指标：{indicator['name']}",
            f"  定义：{indicator['definition']}",
            f"  计算公式：{indicator['formula']}",
            f"  数据来源：{indicator['data_source']}",
        ]
        if indicator.get("depends_on"):
            lines.append(f"  依赖指标：{', '.join(indicator['depends_on'])}")
        if indicator.get("filters"):
            lines.append(f"  强制过滤：{' AND '.join(indicator['filters'])}")

        return "\n".join(lines)

    def build_knowledge_block(self, question: str) -> str:
        """根据用户问题构建指标知识文本块。"""
        detected = self.detect_indicators(question)
        return self.build_knowledge_block_from_detected(detected)

    def build_knowledge_block_from_detected(self, detected: list[str]) -> str:
        """根据已识别指标构建知识块，并补充依赖指标。"""
        if not detected:
            return ""

        blocks = ["【指标知识】"]
        injected = set()

        for name in detected:
            if name not in injected:
                blocks.append(self.get_indicator_text(name))
                injected.add(name)

            indicator = self.indicators.get(name)
            for dependency in indicator.get("depends_on", []) if indicator else []:
                if dependency not in injected:
                    blocks.append(self.get_indicator_text(dependency))
                    injected.add(dependency)

        return "\n\n".join(block for block in blocks if block)

    def get_indicator_context(self, question: str) -> dict[str, list[str] | str]:
        """一次识别同时返回指标列表和 Prompt 知识块。"""
        detected = self.detect_indicators(question)
        return {
            "detected_indicators": detected,
            "indicator_block": self.build_knowledge_block_from_detected(detected),
        }

    @staticmethod
    def _build_alias_map(indicators: list[dict]) -> dict[str, str]:
        """构建别名到标准指标名称的映射。"""
        alias_map = {}
        for indicator in indicators:
            name = indicator["name"]
            alias_map[name.lower()] = name
            for alias in indicator.get("aliases", []):
                alias_map[alias.lower()] = name
        return alias_map


if __name__ == "__main__":
    knowledge = IndicatorKnowledge()
    questions = [
        "查询上个月的利润",
        "按产品线统计毛利率",
        "查询已完成订单的总数量",
    ]

    for item in questions:
        context = knowledge.get_indicator_context(item)
        print(f"\n问题：{item}")
        print(f"识别指标：{context['detected_indicators']}")
        print(context["indicator_block"] or "未识别到指标")
