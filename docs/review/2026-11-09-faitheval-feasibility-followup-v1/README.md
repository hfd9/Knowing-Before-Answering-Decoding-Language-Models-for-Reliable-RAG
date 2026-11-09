# FaithEval条款、问题排重及五文档语义参照核查

2026-11-09，Asia/Shanghai。按用户要求完成三项CPU/资料工作。实际做了固定版本FaithEval与旧材料的**问题文本聚合比对**，没有采样、生成新输入、独立语义评分或预测；未知项明确保留。结果只支持判断下一步是否可行，不是实验协议或新合格确认集。

## 1. 来源和使用条款

| 来源层次或子来源 | 查到的原始依据 | 本项目实际处理和未解决事项 |
| --- | --- | --- |
| FaithEval固定I/C | 数据卡声明支持论文的研究用途：[I](https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0)、[C](https://huggingface.co/datasets/Salesforce/FaithEval-inconsistent-v1.0)；[代码仓库](https://github.com/SalesforceAIResearch/FaithEval)Apache-2.0 | 两个数据卡未见明确数据许可标识；不能把代码许可、论文许可或公开下载当作数据及上游全文再发布授权。本轮只临时处理问题列并发布非逐题聚合；后续保存、改写或公开具体文本前需查清相应数据与来源条款。 |
| MRQA中间来源 | [MRQA作者说明](https://github.com/mrqa/MRQA-Shared-Task-2019)有统一抽取式格式和源数据列表；[仓库MIT](https://github.com/mrqa/MRQA-Shared-Task-2019/blob/master/LICENSE)是软件许可 | FaithEval使用其test来源，但当前没有确认与每个原始数据集的逐条映射；MRQA软件许可不能证明底层所有文本许可。 |
| DROP | [AI2原DROP页面源码](https://github.com/allenai/allennlp-website/blob/master/drop.html)标CC BY-SA 4.0 | 对原DROP数据是具体依据；仍须确认FaithEval改造记录与MRQA版本的来源链及适用范围，不将其推广至其他子来源。 |
| TextbookQA | [AWS开放数据登记](https://github.com/awslabs/open-data-registry/blob/main/datasets/allenai-tqa.yaml)列CC BY-SA 4.0，管理方为AI2 | 登记是原TQA的线索；AI2对应文档页面本轮返回403，未核清FaithEval/MRQA具体派生与再发布条件。 |
| RACE | [原数据发布页](https://www.cs.cmu.edu/~glai1/data/race/)称仅供非商业研究，并列出上下文及派生数据的商业用途限制 | 不能因FaithEval公开而将原来源当作通用自由再发布许可；后续用途须结合具体派生与条款核对。 |
| NewsQA | [Maluuba原仓库](https://github.com/Maluuba/newsqa)说明CNN文章权利及数据无法直接发布的原因；[MIT文件](https://github.com/Maluuba/newsqa/blob/master/LICENSE.txt)明确是NewsQA代码 | 不把代码MIT扩展为CNN文章或FaithEval文本许可；本轮不归档正文。 |
| SQuAD | [Stanford页面](https://rajpurkar.github.io/SQuAD-explorer/)列SQuAD 2.0下载采用CC BY-SA 4.0，2.0包含1.1问题 | 页面中的许可说明与本次FaithEval/MRQA使用的具体版本/派生内容的衔接未逐文件核实，不能直接称本批文本已获得完整再发布授权。 |
| BioASQ | [BioASQ作者数据入口](https://participants-area.bioasq.org/datasets/)声明BioASQ数据CC BY 2.5，并指出其资源来自美国国家医学图书馆且受相应条件约束 | 已找到原数据声明；具体MRQA及FaithEval派生、文章摘录与归属要求仍须核实。 |
| SearchQA | [SearchQA作者仓库](https://github.com/nyu-dl/dl4ir-searchQA)说明问题源于Jeopardy、上下文来自网页检索；[仓库许可证](https://github.com/nyu-dl/dl4ir-searchQA/blob/master/LICENSE)是BSD 3-Clause软件条款 | 软件许可证不能直接认证Jeopardy问题和网页片段的权利；相应MRQA/FaithEval派生内容的条款仍未核清。 |
| HotpotQA / NQ / TriviaQA | KBA与FaithEval论文均列为来源，固定交集分别86/76/66 | 本轮不以来源相同认定每题重叠；不把这三个来源自动选为确认集，亦未完成它们的逐源许可审计。 |

来源构造路径以[FaithEval §3](https://arxiv.org/html/2410.03727v3)为准；`qid`只是在同一FaithEval两个发布文件内的连接键，尚未认证与KBA本地`original_id`同源同编码。许可证核查结论：**可确认若干上游来源的具体声明，不能整体判定全部候选内容的改写/存储/再发布许可**。未向作者发送询问。

## 2. 已用材料的问题排重：实际结果与局限

两侧固定在[I commit `4a14e0e9860e270a8c9ff57c511821f4f50dce57`](https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0)和[C commit `e29508db3955db2c82a80a1f3c3aadc11f93fc3f`](https://huggingface.co/datasets/Salesforce/FaithEval-inconsistent-v1.0)。以此前两边各一行、同subset的785个qid为**统计分母，不形成候选清单**。这次允许在内存读取两个文件的`qid`、`subset`和`question`；没有解析候选`context`/`answers`、没有保存源文件、问题、qid、匹配条目或自动筛选数据。Parquet的HTTP范围可能含邻近字节；未全文件重算发布方SHA。

本地对照白名单为固定`runs/qwen2.5-3b-small/data/instances_{train,val,test}.jsonl`及`prompts/semantic_transfer_materials_v5.json`中的作者问题：200训练、95验证、100已用诊断、30已用作者问题。先核验manifest和三个文件SHA/数量；另核对各记录`id`/`original_id`与已用chat运行train、val、test记录完全相同。这里的test仅100已暴露诊断底题；**没有打开**`dataset/instances.zip`的原测试成员或封存380题。30题覆盖的是v5作者问题，不代表所有探索过的历史问题、背景文档或原始来源问题都已纳入。

规则在运行前固定：NFKC、大小写折叠、Unicode词元化后规范化完全相等；此外比较词元**集合**Jaccard≥0.8且两边均至少5个不同词，作为可能近重复的线索。短问题仍进行精确比对，28个候选qid含少于5个不同词的问题，不进行Jaccard近匹配。此阈值是可复现的开发筛查规则，未校准召回或准确率，不能自动裁定泄漏，也未使用输出选择题目。

| 核查结果 | qid数 | 解释 |
| --- | ---: | --- |
| I/C严格同qid同subset | 785 | 指标分母，非已选样本。 |
| 两侧问题规范化相同 | 785 | 非字节完全相同或语义/证据状态认证。 |
| 与四组旧问题任一规范化精确命中 | **1** | 命中旧train200，FaithEval标为TriviaQA-web；只说明问题字符串经规范化相同，不认证文档或底题身份。 |
| 与任一旧问题精确或达到上述Jaccard线索 | **1** | 除上述精确命中外无额外词集合线索；不等于其余784个无重叠。 |
| 两侧任一问题不同词数少于5 | 28 | 只做精确、未做Jaccard。 |

逐组精确/包含精确的近匹配为：train200 **1/1**、val95 **0/0**、diagnostic100 **0/0**、transfer30 **0/0**；各组重叠时不能相加。去除问题中的实体、同义改写、词序改变、源文档重复等可能漏检；Jaccard也会误报。未检查上下文/答案或文档同源，未覆盖其他旧探索或模型预训练，更未检查380，不能把低命中率写成经确认的不重叠率。[机器汇总](summary.json)不含ID或题目。

[主计数器](../../../scripts/faith_eval_question_overlap_20261109.py)的合成样例检查Unicode、精确匹配、近匹配、短问题及空值；[第二进程倒排索引复算](../../../scripts/verify_faith_eval_question_overlap_20261109.py)得到785相同、1精确/1含精确近匹配、28短问题。两者共享固定输入读取、白名单及规范化，不是独立来源或语义审核；固定版本且行数核验，不认证完整远程文件SHA。

## 3. 五文档输入的语义参照：结论和具体缺口

**原始I/C有外部参考，最终五文档三状态/两表达目前还没有可认证参照。** FaithEval原文报告三个标注者对原始I/C的多数判断及筛选；本轮未接收单人原票，也未对候选正文评分。上述785只检查问题字段，不能证明I缺证、C冲突，不能把原始人工审核转移到新拆分、干扰或改写上。

未来若来源和新协议允许，至少要对每个**最终完整输入**逐项记录并审查：

1. **充分S：**唯一目标实体、时间及范围；指出直接或多跳支持目标值的完整证据链，并检查其他四文档无未消解反例。原C两文档中单取一份只是S候选，不自动是充分。
2. **不足I：**记录缺少的必要前提及文档中相关但不足的内容；审查是否可构造至少两个与完整五文档相容但目标答案不同的解释。不能以原答案字面缺失即断言缺证；多跳或一般常识造成歧义则保留unknown。
3. **冲突C：**分别引用两处目标字段互斥的证据，核对同一实体、时间、范围及定义、无可用优先规则；源真伪或不同话题不能替代目标冲突。原C合并文本拆为文档、增加干扰后须重新审查。
4. **表达A/B：**分别审查每个最终版本保持同一问题及证据关系，保存位置、条件、缺失信息和潜在隐含事实差异；相同token数、句子重排或相同作者意图不足以证明等价。
5. **来源与分歧：**保留原始第三方标注来源、完整输入与逐槽证据，先封存各评审的S/I/C/unknown与逐字证据，再连接分组及任何probe读出；评审历史和条件暴露如实披露。不同会话或随机编号不能保证独立，分歧无法解决就保留unknown，不能将有暴露的助手复核写成原门禁的独立批准。用户不需要本人逐条审核。

原评价只能支撑“有外部审核线索”，不能给出最终五文档可靠度、覆盖率或可用题数。候选最终输入、两份经过审计的参考、允许的底题来源/再使用权、采样及停止规则均未落实；因此当前**不具备确认实验或GPU采集条件**。若这些条件未来可以满足，可以另定协议并准备由用户运行的GPU命令；若无法满足，则只保留当前探索结果和元数据，不靠降低原门槛通过。

本轮无候选样本导出、新标签、评审、前向、拟合、阈值搜索或patching。旧v1/E1-r1门禁false、正式独立批准0、标签null、原拟合预算0、380封存；本次未访问GPU，不改既有实验结果。
