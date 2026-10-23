# 55条/155主张作者复核：当前使用analysis-v2

本目录是已接触项目历史与输出的当前助手新增作者复核，实际独立语义审核仍0。原独立审查包及空白模板在同级semantic-claims-v1，未被覆盖；不得将本目录交给声称未接触作者判断的独立评审。

input-manual.json及input-seal.json保存本轮先处理输入的判断。output-manual-part1/2/3及output-seal.json保存手写主张及封存；此前输出已暴露，当前轮输入先封存不使其成为盲审。

原analysis.json、rows.csv、claims.csv和claims.md是v1快照。judgment-addendum.json显式将Q055_C03的名称使用者归属从contradicted收紧为unsupported，保留原稿；没有改目标端点或重新拟合。

**当前结果为[analysis-v2/claims.md](analysis-v2/claims.md)及[analysis-v2/report.json](analysis-v2/report.json)。** 155个主张实例含重复，计数取决于拆分；82句文本覆盖不自动认证原子主张完全穷尽，不能报语义Accuracy或总体发生率。

只读复核：

```sh
python3 -B scripts/semantic_claim_author_review_analysis_v2.py --stage verify
python3 -B scripts/verify_semantic_claim_author_review.py
```

本轮研究决策是保持原上限收尾和380封存，先实际独立审查，再决定是否值得继续证据状态解释准确性问题。无新GPU就绪任务，不恢复一次拟合预算，不新增采集、probe读出或patching。
