# Text2SQL 评估基准

## 背景

人工观察单条 SQL 无法稳定衡量系统质量。项目需要一套可重复运行的评估基准，用执行结果判断生成 SQL 是否满足预期。

## 本次变更

- 新增 Text2SQL 评估器。
- 增加覆盖 simple、medium、complex 三类问题的测试用例集。
- 支持 Exact Match Accuracy 和 Execution Accuracy 两类指标。
- 评估器通过执行预期 SQL 与生成 SQL，对比结果等价性。

## 关键文件

- `evaluator.py`
- `test_cases.json`

## 验证结果

- 评估器可加载 JSON 用例并执行。
- 当前模型在原始测试集上可得到 `Execution Accuracy = 6/9 = 66.7%`。
- Exact Match 结果较低，说明模型 SQL 文本常与预期不同，但执行结果是更重要的衡量指标。

## 后续衔接

后续每次 Prompt、业务规则、指标知识或 Schema 能力改动，都可以用评估器观察执行准确率变化，避免只凭单条示例判断效果。
