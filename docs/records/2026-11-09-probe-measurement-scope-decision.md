# 2026-11-09：probe测量总表与研究去留

时间与时区：2026-11-09，Asia/Shanghai。状态：verified_complete；操作者：有项目历史和结果暴露的助手。

## 背景与实际工作

按用户要求先做研究去留，不追加GPU或重做已有13次前向、桥接和缓存审计。使用已归档240迁移、另一批48绑定和六题等token对照，形成[逐状态/表达的测量总表和决定](../review/2026-11-09-probe-measurement-scope-decision-v1/README.md)、[22行计数表](../review/2026-11-09-probe-measurement-scope-decision-v1/measurement-summary.csv)、[162个逐底题配对](../review/2026-11-09-probe-measurement-scope-decision-v1/paired-items.csv)及[九组配对汇总](../review/2026-11-09-probe-measurement-scope-decision-v1/paired-summary.csv)。等token的36单元包括24旧端点和12新中性输入，不与其他材料合并成独立样本；三批参照均有暴露，正式标签null。

## 发现、研究决定与文献范围

迁移I两表达各8/30读refuse、A/B 7/30两端符合作者参照；绑定I两版本各12/12读answer、12对全部两端不符构造参照。迁移C两表达分别23/30与24/30读conflict，但S/K也常读conflict；等token的六题在三种条件/两表达均conflict。迁移S/K各2条作者unknown保留；绑定48条具体证据归属unknown属于另一行为字段。120组A/B只来自30底题。

决定暂停以旧chat L28三分类probe作为可靠语义测量或“已检测不足但未行动”的依据；保留条件性信号响应和构造任务上的发现，不推断隐藏状态不存在相关信息，不把本批开发结果外推为原论文或所有模型失败。将潜在研究问题收缩为可审计参照下的证据状态读出边界，创新性尚未成立，也没有新的GPU研究协议。

定向阅读[原论文v1](https://arxiv.org/html/2608.27661v1)的提示稳健性、自然域迁移、控制及patching章节结构和[Hewitt/Liang控制任务论文](https://arxiv.org/abs/1909.03368)，明确不能宣称一般捷径问题或从读出走向生成首次提出。一次后续网页请求报`connection failed`，原因未知；文献对照是有限检索，不是系统综述。该连接故障不影响本地重排和配对计算。

## 核验及状态

`python3 -B scripts/probe_measurement_scope_decision_20261109.py --stage verify` exit 0；另从324已存单元及162配对独立重算22分组及9个配对组全部一致。第一次独立检查误把分组数写作10而报AssertionError，核对分组定义后修正为9并通过；没有改原始数据或评分。所有本地链接存在，来源SHA记录于结果包。

本次没有模型/权重加载、GPU、特征重放、采集、拟合或新评分，未访问380底题；正式独立批准0、正式标签null、原拟合预算0及原v1/E1-r1门禁false保持，不自动扩样、阈值搜索或patching。必要GPU工作仍由用户执行。任务进行中发现此前中断恢复记录及交接索引已暂存，保留原字节，与本次记录同属项目交接；按长期约定提交推送，实际哈希以Git及回复为准。
