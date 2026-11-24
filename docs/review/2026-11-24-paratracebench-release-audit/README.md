# ParaTraceBench 公开发行包核验

## 证据与范围

检查公开 Git 版本 `f9cbea4eccaf492a2d27afbf7a1d02533ff566bd` 的实际案例、结构、许可说明及四条外部路线保存的输出。通过公开 Git 远端核对分支；GitHub 树 API 在沙箱内连接失败、沙箱外返回 403，随后通过 Git 只取到临时目录，沿固定提交读取对象。审计脚本仅读外部 Git 对象。代码、数据和输出均留在临时目录，项目只归档数据摘要和计数。论文说明外部原始文档及受限情境正文未公开。以下观察的范围是这个公开 Git 版本。[固定公开版本](https://github.com/thecontrey/parabench/tree/f9cbea4eccaf492a2d27afbf7a1d02533ff566bd) · [原文数据可用性说明](https://www.mdpi.com/2673-2688/7/8/321)

## 情境与逐世界参照

| 检查 | 外部集 | 受控集 |
| --- | ---: | ---: |
| 唯一案例 ID | 567 | 140 |
| 唯一问题字符串 | 5 | 5 |
| 问题与有序证据正文的逐字唯一组合 | 567 | 140 |
| 只遮盖匿名案号数字后的唯一组合 | 61 | 48 |
| 遮盖后含多个状态标签的组合 | 31 | 8 |

集合键为原问题及原顺序证据正文。窄遮盖只替换正文中 `ANON-` 或 `АНОН-` 紧接的数字，保留其他日期、金额和阈值。两集合共享 **60 个逐字相同的可见输入**，其中 **39 个归档状态不同**。遮盖案号后跨集合共享 48 个组合。全部数字遮盖是宽松敏感性检查，两侧各 10 组且 10 组相交。它会合并可能具有实质含义的数字，结论以逐字和窄遮盖为主。受控集含注入的结构缺陷，跨集合不同状态只记录可见字段相同及标签不同的现象。审计没有重建论文原始运行的完整提示，因此这一比较的范围是公开字段，不能据此判定原研究的数据泄漏或错误标注。[固定版本的案例数据与结构](https://github.com/thecontrey/parabench/tree/f9cbea4eccaf492a2d27afbf7a1d02533ff566bd/data)

两个文件 707 条的 `provenance.source` 均为 `synthetic_anonymized_repository_payload`。每个案例仅有一个不同的归档 `source_doc_id`。归档有单一结论状态和符号追踪，缺少本项目所需的两个分支各自允许成立的范围、授权方向、结论及逐分支证据的独立参照。许可目录中的 CC BY 4.0 文件是条款链接占位，MIT 文件是省略文本。当前文件不能确定公开案例和提示各自的改编、再分发范围。[固定版本的许可目录](https://github.com/thecontrey/parabench/tree/f9cbea4eccaf492a2d27afbf7a1d02533ff566bd/licenses) · [上游数据质量说明](https://github.com/thecontrey/parabench/blob/f9cbea4eccaf492a2d27afbf7a1d02533ff566bd/docs/data_quality_caveat.md)

## 保存结果可复核到哪一层

- 四条外部路线的 `raw` 与 `normalized` JSONL 分别逐字节相同。按案例 ID 对预测状态和参照状态，B1–B4 的命中数为 167、324、416、486，各分母为 567，与公开表一致。CLA、NER、PHA、BRA 的整数计数也可从保存标志和真值分组复算。这些计数没有重做四项语义判断。各路线的 `answer` 仅见四种字符串。
- B4 的 `extracted_facts`、`extracted_rules`、`conflicts` 和 `priorities` 各自逐条与 567 条案例参照一致。固定版本的复现脚本从已规范化的记录及保存字段聚合，不能用来独立验证这些字段如何从模型文本抽取。公开 B4 提示可供以后做同题适配参考，仍需在两种允许解释下同题生成并核对证据和合并口径。[外部输出目录](https://github.com/thecontrey/parabench/tree/f9cbea4eccaf492a2d27afbf7a1d02533ff566bd/outputs) · [复现脚本](https://github.com/thecontrey/parabench/blob/f9cbea4eccaf492a2d27afbf7a1d02533ff566bd/scripts/reproduce_metrics.py) · [B4 提示](https://github.com/thecontrey/parabench/blob/f9cbea4eccaf492a2d27afbf7a1d02533ff566bd/prompts/baselines/b4_trace_based.md)

**去留。** 这个公开包排除为授权方向项目的自然独立留出来源，保留为近邻和输出合同参考。固定版本、两种输入遮盖、四路线匹配计数见[聚合结果](aggregate.json)。主脚本异进程重跑字节一致，另用 SQLite 复算外部 B4 为 486/567、外部窄遮盖为 61 组且 31 组含多个状态，以及逐字跨集合 60 组且 39 组标签不同。

仓库根目录的只读复算命令如下。参数为存有上述固定提交的本地 Git 仓库路径。

```sh
python3 docs/review/2026-11-24-paratracebench-release-audit/check.py /path/to/parabench
```
