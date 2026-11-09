# FaithEval固定版本元数据交集与排重边界

2026-11-09，Asia/Shanghai。按用户要求接续[来源可行性](../2026-11-09-probe-source-feasibility-v1/README.md)，实际锁定并只统计两列元数据；不选题、不读取或构造正文样本、不运行模型或评审。结果是可行性检查而非新实验数据或语义标签。

## 版本、读取和条款

| 角色 | 固定数据集 `test` | 本次`git ls-remote`核实的完整main commit | 作者文件页给出的文件SHA256（本次未重算） |
| --- | --- | --- | --- |
| I | [FaithEval-unanswerable-v1.0](https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0) | `4a14e0e9860e270a8c9ff57c511821f4f50dce57` | [b6f22ea87c49dad2a8f7d001a9f71e3b59c7747fcbffdd1078fc5a22ac8e7f86](https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0/blob/main/data/test-00000-of-00001.parquet) |
| C | [FaithEval-inconsistent-v1.0](https://huggingface.co/datasets/Salesforce/FaithEval-inconsistent-v1.0) | `e29508db3955db2c82a80a1f3c3aadc11f93fc3f` | [a4fd32a58c28267bc3b217a6006af68d95f354568f42702ba18d9b8c76fffa15](https://huggingface.co/datasets/Salesforce/FaithEval-inconsistent-v1.0/blob/main/data/test-00000-of-00001.parquet) |

两文件均为`data/test-00000-of-00001.parquet`。由[脚本](../../../scripts/faith_eval_metadata_counts_20261109.py)按完整commit URL发起HTTP range，PyArrow仅读出`qid`及`subset`列；仅在进程内持有标识并输出分组计数，不输出或保存逐题ID/样本。HTTP字节范围可能包括所需列邻近的压缩字节及Parquet尾部；没有解析或有意读取question、context、answers、justification列，也不保存原文件。固定版本及行数通过，不等于本次已对整个文件重算SHA；文件页SHA为发布方提供的对照，未把部分范围读取称作整文件哈希认证。

两张数据卡声明其发布供论文研究；[作者代码仓库](https://github.com/SalesforceAIResearch/FaithEval)是Apache-2.0，但这不自动证明各数据及上游来源的使用、保存和再发布条款。本次只做短暂元数据研究与聚合，不解决上述许可问题。提交哈希固化本次可复查的来源，不改变后续使用前须核清的条款。

## 去重与交集

| 条件 | 总行数 | 唯一qid | 存在重复的qid | 多余重复行 | qid跨多个subset |
| --- | ---: | ---: | ---: | ---: | ---: |
| I | 2,492 | 2,491 | 1 | 1 | 0 |
| C | 1,500 | 1,500 | 0 | 0 | 0 |

两边按qid去重的交集为 **785**；其中 **785** 都满足两边各一行、`subset`完全相同的严格规则，0个共同qid存在subset完全不相交，0个共同qid因重复或严格规则未解决。I中那1个重复qid不在交集中。本次不对重复内容作语义判断或自动挑选某行。

| 子来源 | I行 | C行 | 严格交集qid |
| --- | ---: | ---: | ---: |
| BioASQ | 250 | 150 | 76 |
| DROP | 250 | 150 | 71 |
| HotpotQA | 250 | 150 | 86 |
| NaturalQuestionsShort | 250 | 150 | 76 |
| NewsQA | 250 | 150 | 72 |
| RACE | 250 | 150 | 92 |
| SQuAD | 250 | 150 | 81 |
| SearchQA | 250 | 150 | 70 |
| TextbookQA | 250 | 150 | 95 |
| TriviaQA-web | 242 | 150 | 66 |
| **合计** | **2,492** | **1,500** | **785** |

785中三个与KBA原论文来源名称相关的子来源共228；其余七个为 **557**。这不是选出的557个题、可用题数、去泄漏样本、有效三状态集或语义参照。它们只按subset名称分类；不同数据集中的重复题、文档或模型预训练暴露仍可能存在。只看标识不能确认同qid的问题文本相同或每条状态正确。完整聚合计数见[summary.json](summary.json)，不保存原始qid列表。

## 与旧项目排重可行性

只读检查既有`runs/qwen2.5-3b-free-answer-study/chat/{train,val}/states.json`和已使用的`chat/test/predictions.json`的**字段名与记录数量**：分别600/285/300条，记录含本项目`original_id`、`id`及完整prompt SHA，但未见FaithEval `qid`或上游原始问题ID字段。此test文件只含原已使用的100诊断底题，而非封存的380底题；本次不访问原测试归档或380内容。[跨表达协议](../../../prompts/semantic_transfer_validation_v1.json)另保存30个已用train来源的本地`original_id`，同样不是已证明可与FaithEval相连的标识。

因此**不能通过本地original_id与FaithEval qid的直接等值匹配证明无重叠**；也没有运行跨数据集的正文、答案或近重复比对。完整prompt SHA绑定渲染后的提示，无法替代跨改写原问题或源文档去重。后续若另行开展受限排重，需要先建立来源映射或对允许访问的旧训练/验证/已暴露探索材料及候选做规范化问题、来源文档与近重复核对，并逐级记录覆盖、漏检和冲突；该步骤将触及文本，不包含在本次只看元数据的结果中。380不开放时无法据此排除与其碰撞，报告应保留此未覆盖范围，不能将其当作已去重；模型预训练暴露同样不可由此判定。

## 验证与去留

本次先用临时合成Parquet测试重复qid、跨subset不一致、空qid拒绝和只输出聚合而不输出正文。实际固定版本运行输出以上结果；[另一脚本](../../../scripts/verify_faith_eval_metadata_counts_20261109.py)在独立进程重新读取相同两列，用内存SQLite执行另一套分组和严格连接，复算785及10子来源一致。二者共享范围读取与Parquet列投影实现，因此只是**独立聚合**，不是独立来源、完整文件SHA或语义认证；没有外发qid、保存原始列或新增标签。原有`python3`环境缺`aiohttp`，首次HTTP库尝试失败后改用严格206范围响应；沙箱内HTTP连接失败后按执行权限要求在允许网络的环境重跑成功。

结论：**元数据规模足够使FaithEval继续值得评估，但不能以785或557宣称已有可用确认样本。** 可行性尚取决于数据及上游条款、适配后的S/I/C和表达参照、逐题跨源排重及研究增量。此阶段没有新模型前向、评分、GPU、拟合或实验协议，旧v1/E1-r1门禁false、独立批准0、正式标签null、原拟合预算0、380封存；不自动扩样、重训、阈值搜索或patching。
