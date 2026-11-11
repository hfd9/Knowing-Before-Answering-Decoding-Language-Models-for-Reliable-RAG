# 2026-11-11：FaithEval 四步依赖核查及去留

状态：部分完成并按既定停止条件收缩；操作者：助手。用户要求依次完成来源条款、真实数据独立复算、封存碰撞处置及研究去留。未将未知视为通过。

## 1. 条款：具体用途仍未闭合

本轮直接以 curl 读取固定版本 [I 数据卡](https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0/resolve/4a14e0e9860e270a8c9ff57c511821f4f50dce57/README.md) 与 [C 数据卡](https://huggingface.co/datasets/Salesforce/FaithEval-inconsistent-v1.0/resolve/e29508db3955db2c82a80a1f3c3aadc11f93fc3f/README.md)。两卡均说明面向论文研究用途，并要求遵守适用法律和使用政策；卡中未列独立明确数据许可，不能由此推定保存、改写、公开或再分发所有上游内容的权利。

[RACE原发布页](https://www.cs.cmu.edu/~glai1/data/race/)限定非商业研究并说明文章来自互联网；适用到本项目的具体使用性质及派生内容权利尚未认证。[NewsQA发布仓库](https://github.com/Maluuba/newsqa)称CNN文章不能直接分发、CNN保留权利；其[MIT许可证](https://github.com/Maluuba/newsqa/blob/master/LICENSE.txt)明确针对代码，不能视作文章许可。[DROP原发布页](https://github.com/allenai/allennlp-website/blob/master/drop.html)对原数据列CC BY-SA 4.0，不能单独证明FaithEval具体改写及所有再发布条件已符合。MRQA论文说明TriviaQA和SearchQA涉及网络来源、BioASQ涉及科学文章等，来源链各异，见[原论文](https://www.cs.princeton.edu/~danqic/papers/mrqa2019.pdf)。现有固定连接包含十个来源；并非逐来源、逐权利人完成了合法性论证。具体项目用途、各材料权利和改写/再发布权仍待明确；无法从未发现条款推定禁止或允许。

本轮仅沿用此前限定的研究核查用途：候选列在内存读取并输出聚合，不存候选正文、ID或逐题标记；没有授权新实验材料或公开派生文本。未就研究用途的法律性质作确定结论。

## 2. 真实数据复算：主要计数通过，独立范围有限

运行 `python3 scripts/verify_faith_eval_document_overlap_20261109.py`；沙箱内远程范围请求三次失败，退出1；按网络失败流程在沙箱外重试，退出0，输出 `passed_independent_shingle_aggregation`。实际785连接，I/C短于16词为6/0，I/C相等均0、包含均0，片段线索I/C各1且涉及同一qid；与[原汇总](../review/2026-11-09-faitheval-dependency-gate-v1/README.md)主要聚合一致。未保存候选ID、正文或逐题结果，未读取问题/答案；远程范围请求可能涉及相邻字节，未验证完整文件SHA。

复算器独立实现片段、倒排和聚合，但共用原始远程读取器、来源版本、规范化与旧白名单，故不能称整条数据读取及规范化独立复验。脚本不独立断言2,270文档数、315次旧短文档槽的分组计数或命中旧训练组；这些仍来自原始筛查。原先问题统计独立通过与本次文档复算是不同检查。规则只检精确、包含及预设片段重合，短文本及其他类型重叠未被排除；不证明其余题目无碰撞。

## 3. 380封存碰撞：处置为 unknown，不读取正文

已有audit中的380个本地 `test_数字` ID与FaithEval十六进制qid不同命名空间，字面无交集不能说明内容无碰撞；目前未找到可用跨命名空间映射或经允许的指纹。项目既定规则封存380题正文，输出聚合也不自动授权读取，也不能保证选择决策不受确认集信息影响。此次未读取封存问题、文档或测试归档，也未生成与之比较的指纹。结果保留unknown，FaithEval候选不能据此宣称对380无污染。将来须先确定可允许的流程及其对确认集的影响，或者放弃把380用于该研究确认。

## 4. 去留

依据上述条件，停止FaithEval确认实验分支的推进：真实复算使一项技术缺口闭合，但未解决来源实际用途、封存碰撞、最终五文档语义参照和预算。没有构造最终输入、审核S/I/C与表达等价、形成协议或实际近邻实验对照。旧probe的测量边界问题与既有有限负结果仍可保留，不能据此声称创新或泛化；已完成的文献比较与其范围见[研究决定](../review/2026-11-09-probe-research-decision-v1/README.md)。如未来来源权利及独立参照落实且封存风险获得有效处置，可重新评估，不自动恢复实验。

原v1/E1-r1门禁false、独立批准0、正式标签null、原拟合预算0、380正文封存；本轮无新样本选择、语义评分、模型前向、GPU、训练、阈值搜索或patching。按长期约定更新交接与索引、提交推送；实际Git状态见回复。
