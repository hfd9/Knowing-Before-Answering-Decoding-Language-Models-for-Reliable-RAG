# 实际用途、封存碰撞与候选问题增量核查

2026-11-11，Asia/Shanghai。沿用[综合报告](../2026-11-11-frozen-probe-synthesis-v1/README.md)，不重复实验或既有真实聚合复算。本轮核对公开原始来源、既有封存记录和近邻论文，研究者已见项目历史。未获取候选数据文件、选题、读取封存正文、做新语义评分或模型前向。本报告是依据可见信息的研究用途判断，不认定所有相关权利或具体司法辖区结论。

## 1. 将用途落到具体操作

当前可证伪问题的**候选用途**是：固定旧 chat L28 三状态读出，在未暴露底题的完整五文档问答上，分别检验 S/I/C 的参照一致性及经审核的表达变化稳定性，报告 unknown 和底题级分母。它不是已放行的确认协议，也没有确定公开数据、文章全文或商业用途。完成此用途可能涉及：A 临时读取和机械排重；B 保存固定输入、来源及评审证据供复验；C 拆分、改写、组合为五文档及两表达；D 公开论文、代码、引用、摘要结果或可重放数据；E 将材料提供给可能的外部评审或托管服务。各用途和实际使用者需分开判断；**只发布汇总指标与公开原文、向外部处理者传输原文不等价**。当前未确定B–E的具体范围或项目商业性质，不能预设某权利链已覆盖。

## 2. 固定 FaithEval 与上游：按用途的判断

| 资料 | 可核实事实 | 对上述用途的实际判断 |
| --- | --- | --- |
| [固定不足卡 I](https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0/resolve/4a14e0e9860e270a8c9ff57c511821f4f50dce57/README.md)、[固定冲突卡 C](https://huggingface.co/datasets/Salesforce/FaithEval-inconsistent-v1.0/resolve/e29508db3955db2c82a80a1f3c3aadc11f93fc3f/README.md) | 两卡声明支持论文的研究用途，并要求遵守适用法律与政策；未见独立明确的标准数据许可。I `4a14e0e...`，C `e29508d...`；[代码仓库](https://github.com/SalesforceAIResearch/FaithEval)的代码许可不是内容权利证明 | 既往受限A聚合已执行并归档，不能倒推B–E均允许。B–E及内容来源链未核齐，当前不能用于最终材料。 |
| [DROP 原发布](https://github.com/allenai/allennlp-website/blob/master/drop.html)、[SQuAD 发布页](https://rajpurkar.github.io/SQuAD-explorer/) | 分别声明原数据CC BY-SA 4.0 | 存在可追溯原始条款；需核实所用原始版本、权利范围、归属、修改标记及适用的相同方式共享条件，不能自动推定FaithEval所有改写和混合材料获准。原始三状态与改造后五文档语义仍须独立验证。 |
| [RACE 原发布页](https://www.cs.cmu.edu/~glai1/data/race/)、[NewsQA 仓库](https://github.com/Maluuba/newsqa) | RACE限非商业研究，网页称内容来自互联网；NewsQA指出CNN保留文章权利，仓库MIT许可针对代码 | 项目具体用途性质及派生/外发条件不明；不把现有研究声明扩张为B–E许可。 |
| TextbookQA | [Ai2旧页面搜索缓存](https://prior.allenai.org/projects/tqa)显示CC BY-NC 3.0，但页面本轮直接打开重定向；[AWS开放数据登记](https://registry.opendata.aws/allenai-tqa/)列CC BY-SA，未给版本 | 两个公开描述不一致，无法仅凭搜索缓存裁定哪个适用于固定派生版本；当前须视为未核实，而非“确定CC BY-NC”或“确定CC BY-SA”。固定连接中TextbookQA有95个qid，数字不是可用样本数。 |
| BioASQ、HotpotQA、NaturalQuestionsShort、TriviaQA-web、SearchQA | [MRQA原论文](https://www.cs.princeton.edu/~danqic/papers/mrqa2019.pdf)说明其问题和上下文来源有生物医学文章、Wikipedia或网络片段等不同谱系；[BioASQ页面](https://participants-area.bioasq.org/datasets/)按数据和原来源列条件 | 仍需逐项追溯问题、上下文及修改权利；排除某个来源家族只改变分母，不证明剩余无重叠。无法从本次检查推断完整允许或禁止。 |

因此不形成任何已获批准的来源子集。原785严格连接按十来源为 BioASQ 76、DROP 71、HotpotQA 86、NaturalQuestionsShort 76、NewsQA 72、RACE 92、SQuAD 81、SearchQA 70、TextbookQA 95、TriviaQA-web 66；来自[固定元数据汇总](../2026-11-09-faitheval-metadata-v1/summary.json)，并非可用底题数。既有文档复算主要计数通过，读取/规范化/白名单仍共用；不重跑且不改变其结论。

## 3. 封存规则与可选处置

[原恢复记录](../../records/2026-10-09-context-restored.md)写明300条测试作为诊断、剩余380底题留待设置冻结后的确认；[研究结论](../../records/2026-10-12-research-conclusions.md)亦将380标为未消费。最新[后续计划评价](../../records/2026-11-09-next-plan-assessment.md)明确聚合输出不自动许可读取，也不自动保证确认集未受选材影响。现有记录支持封存与用途目的；本轮未发现已经批准的、涵盖380问题/文档的内容指纹或受控读取方案。此前已查到本地数字编号与FaithEval十六进制qid不在同一命名空间，仅凭字面交集无法判断内容碰撞。

| 路线 | 现在能否执行 | 对碰撞与确认的含义 |
| --- | --- | --- |
| 保持封存；保留unknown | 可以，已采用 | 无法声称候选对380无碰撞；不读取、不依据其聚合选择材料。 |
| 依照预先批准、独立隔离的程序仅输出聚合 | **尚不可执行**：未有明确访问范围、执行者、冻结规则、产出使用边界或准许 | 聚合仍能泄露信息或影响选材；即使以后获准，也须先固定阈值、结果接收者、冲突处置及是否仍适合原确认用途。程序或散列本身不是授权，也不保证无泄露。 |
| 不再将380用于此候选的确认，另找合规来源及参照 | 原则上可作为以后方案，尚未选择样本 | 能避免依赖380作为本研究的确认集；本身不证明候选与旧训练、验证、探索或模型预训练无重叠，也不改变原380封存规则。 |

本轮没有批准新封存访问，也不生成新指纹或查找题目正文；380碰撞保持 unknown。已经看过确认集信息后不能仅通过改名、重封存或更换目录恢复其前瞻身份。

## 4. 替代来源：SciFact 是线索，不是可直接使用的三状态集

以只读远程元数据查到 SciFact 仓库 `master` 在本轮指向 `68b98a56d93e0f9da0d2aab4e6c3294699a0f72e`。该提交的[许可文件](https://raw.githubusercontent.com/allenai/scifact/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e/LICENSE.md)将 claims 与 evidence annotations 标为CC BY 4.0，摘要 corpus 标为 ODC-By 1.0，代码为Apache 2.0。重要区别是[ODC-By原文](https://opendatacommons.org/licenses/by/1-0/)说明其处理数据库权利，**不单独覆盖数据库内每项内容的独立版权**；[S2ORC作者仓库](https://github.com/allenai/s2orc)也提示核实底层内容用途。仓库提交固定了声明和代码文件，但其[下载说明](https://raw.githubusercontent.com/allenai/scifact/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e/README.md)指向 `latest`，本轮没有固定、下载或验证数据包版本和SHA，亦未核实具体摘要权利与使用条件。

[SciFact原论文](https://aclanthology.org/2020.emnlp-main.609/)是科学主张验证，提供支持或反驳主张的摘要与证据；其[数据说明](https://raw.githubusercontent.com/allenai/scifact/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e/doc/data.md)的 SUPPORT/CONTRADICT 是**单篇摘要对主张的关系**。摘要反驳一个主张，不自动意味着两份证据互相冲突；未标注也不自动代表无证据。它不是同题问答的S/I/C、五文档或已审核A/B。仓库说明train/dev有标注、test无公开金标签；未核实可用规模、与旧项目材料或380的碰撞、模型预训练暴露及审核成本。**决定：仅保留为许可证结构较明确的来源线索，不选题、不改写、不作为直接替代或宣称已经通过。** 与以权属清晰的新原创虚构材料探索形成对比：后者可以设计可追溯权利和受控关系，但自然域代表性弱，独立参照、重复风险和资源仍须证明；本轮均未构造新样本。

## 5. 可证伪问题与近邻比较

限定性候选问题：**在事先确定的输入分布、冻结的旧模型／模板／L28 probe及可审计参照下，是否存在证据状态均被审核为保持、而同底题两种表达的三分类读出不一致或两端稳定但均不符合参照的情况；同时对S/I/C分别报告？** 以底题为单位，预先约定表达关系、可接受失配率和不确定区间；unknown及不合格完整底题保留在覆盖报告。若独立审核后，两端均符合且预定误差上界达到实际用途容差，则这项“在该范围内不可靠”的假设不获支持；如失配或覆盖达不到事先固定标准，则该配置不适用于该限定用途。无需假装现在已知容差或样本量；未证明材料和参照可行，不作运行协议。

- [KBA v1 §2.1、§5.2、附录G](https://arxiv.org/html/2608.27661v1)已有同题三状态构造和提示变化，RAGTruth自然迁移为二分类，论文明确指出自然三状态标注缺口。可能增量仅是**经审核的状态保持表达与同题状态改变，在同一冻结读出上同时评估正确性和稳定性**；不是首次三状态或提示稳健性。
- [ContextConflict v1 §4、附录D.1](https://arxiv.org/html/2609.03148v1)已有冲突／一致配对和逐层线性probe，覆盖多类冲突；其二状态目标和候选S/I/C不同，不能把配对探测当新增贡献。
- [Hidden Commitment v2 附录C](https://arxiv.org/html/2610.38296v2)在FaithEval已有顺序、单文档和改写一致对照；其主要读出关注选源及冲突披露，控制思路不是空白。其改写一致对照不意味着论文把冲突两文档都改写。
- [Hewitt–Liang控制任务](https://aclanthology.org/D19-1275/)已经说明高probe任务分数不必然等于理想表征解释；随机标签控制本身也不能认证新输入语义。

**判断：问题可以被证伪，但实质论文增量尚未成立。** 价值依赖真正可审计的未暴露参照及可复现的状态保持编辑，且需进一步查明是否已有等价组合；若只能得到旧构造材料或无法建立参照，只能保留本项目探索性诊断。并非系统性文献综述，也没有实际新对照结果。

## 决定与未完成

延续FaithEval确认分支暂停，不新建最终五文档、标签、协议或GPU任务。可继续只读调查源数据包固定版本、具体内容权利、未暴露材料及语义评审资源；若关键用途或审核条件仍不成立，则结束该候选并保留已有成果。原v1/E1-r1门禁false，正式独立批准0，标签null，原拟合预算0，380正文封存；无扩样、前向、拟合、阈值搜索或patching。
