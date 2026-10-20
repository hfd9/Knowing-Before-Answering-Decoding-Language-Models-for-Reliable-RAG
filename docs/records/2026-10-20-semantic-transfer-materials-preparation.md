# 2026-10-20：跨表达材料CPU准备完成，构造覆盖70%，语义审核门槛未满足

状态：materials_prepared_and_CPU_verified / semantic_review_pending / coverage_gate_not_met / no_gpu。

用户要求开始落实[30底题跨表达冻结设计](../semantic_transfer_validation.md)。本轮由当前有完整项目历史暴露的协调助手阅读来源、手写材料、复核支持链并完成CPU工具，不称独立语义评审。构造数量、底题分区、候选层和训练次数沿用原冻结设计；无新probe预测或生成回答，不通过结果筛选/替换底题。

## 实际完成的材料与覆盖

只打开发布instances.zip的instances_train.jsonl；从已固定的30底题提取answer包及其refuse包最短三篇完整背景，背景同长度按原槽位，保留相对次序与重复。150个原answer槽+90背景槽去重为154篇，全部已读。初次工具显示截去了T006–T013部分内容，随后单独完整读取这八篇，未把截断显示算作读完。原发布文本本身可能是网页片段，不声称读过未提供的完整网页。

完成21个底题的两表达×S/K/I/C共168条作者草稿；另外9底题保留72个未完成单元，不替换底题、不删除计划分母240。作者草稿不等于语义金标准，所有semantic_label均null；作者建议类别只保存在协调端。构造覆盖率70%，当前独立语义标签覆盖0%。

| 分区 | 计划底题 | 草稿底题 | 计划单元 | 已构造草稿 | 未完成单元 |
| --- | ---: | ---: | ---: | ---: | ---: |
| semantic_train | 12 | 9 | 96 | 72 | 24 |
| semantic_dev | 6 | 5 | 48 | 40 | 8 |
| semantic_eval | 12 | 7 | 96 | 56 | 40 |
| 合计 | 30 | 21 | 240 | 168 | 72 |

168条包含每种S/K/I/C各42条；这些是作者构造意图，不是评审确定标签。两表达同条件有84配对，同表达S→K/I/C有126配对，共210行，仍只有21个已构造底题，不能当成210独立样本。每底题问题/范围、背景三文档、目标槽位/顺序固定；C仅改目标B、目标A与S相同，显式否定直接针对相同事实时才作为互斥，不靠“换一个名字/类别”强行宣布冲突。

K负对照包含：Irrawaddy/Ayeyarwady别名；比赛冠军与亚军；季数与集数；有较早未成功发行和后来热门版本的同一歌手；主要原因与次要贡献；不同学校/时间的成立事件；类别与更窄子类。用于检验兼容支持误报，不在模型文档中写“这些是兼容事实”之类评审提示。A是近来源的人工摘要，B是人工改写，二者均非自然网页原文；不将“source-like”称为已验证的自然度。

三题有明确、统一应用到八条件的问题澄清：train_1430限定给定series overview的季数，避免把旧快照当当前总数；train_1302明确来源中的Old Order Amish及典型礼拜；train_1222明确来源2017–18队史记录的Stanley Cup最新夺冠。原题、改题及理由逐项保存，不隐藏范围变化。

## 九个未完成底题及原因

| 底题 | 作者初审未决原因 |
| --- | --- |
| train_744 | James II未限定国别；来源区分苏格兰与英格兰同名君主，保留背景也提及英格兰君主。不能静默选定指代。 |
| train_1136 | 来源说现代hula hoop在1958年发明，同时提及历史悠久的玩环；发明时间与题问debut的事件范围尚未明确等同。 |
| train_1154 | 来源提到吞马及“不要吞马”的寓意，未明确给出该版本中最后吞下的动物关系。 |
| train_405 | Washington University明确在美国，Colorado系统仅明确在Colorado；缺少所需的地名到国家前提，不由常识或gold补齐。 |
| train_1470 | Columbus被写为最大城市，未明确写为Ohio首府；最大城市不能替代首府关系。 |
| train_1805 | 来源写Wayne Cochran的Last Kiss，缺少与题中歌词式名称的身份连接。 |
| train_1605 | 来源有战争爆发及战前驻军/撤军，缺少美国参战起止区间，不能用开战时间替代。 |
| train_254 | 有Alcott/Little Women作者信息，缺少小说家庭姓氏，不能从gold_answer补出March。 |
| train_33 | 来源将sushi/sashimi混在同一描述中，未清楚建立题中具体准备方式与唯一菜名的对应。 |

这是当前作者在固定来源、不给S补外部关键事实的保守准备决定，不是独立证实发布标签错误，也不证明这些题绝对无法构造任何合成材料。某些歧义可能经新的来源或明确题意解释解决；若以后解决，应保留理由、另存版本并重新核验，不静默改变本轮覆盖/分区/门槛。

## 生成前修订与版本保护

v1已实际CPU准备。后续作者复核发现train_1179的I仍写Luoding归Yunfu管理，原题泛问“位于哪里”，这可能已经给出一个位置答案。v2去掉两表达I中的该位置关系，只保留county-level city行政类别，原问题保持不变。另外将train_315的作者预期答案缩为主因“人类改造土地表面”，避免把S输入未给出的次要waste heat也写成必需答案。

这些修订发生于任何新probe/生成之前。v1 spec/CPU工具/运行产物原样保留；v2采用新spec、新入口和新run_dir，复用不变v1构建器的隔离模块，协议同时绑定两版本实现，未修改原指纹绕过冻结。独立比较两个run，模型输入仅stv04_A_I、stv04_B_I两条改变；另一项只改协调端答案注释。v1与v2均完成实际只读重放。

当前使用：

- prompts/semantic_transfer_materials_v2.json：30题显式作者spec、336目标文档槽（246不同全文）、53来源逐字引用/偏移及未完成理由。
- scripts/semantic_transfer_materials_v2.py、scripts/run_semantic_transfer_materials_v2.sh：当前CPU入口；v1构建器未改。
- runs/qwen2.5-3b-semantic-transfer-materials-v2：当前材料。v1目录仅保留初稿。

## CPU预检查、独立重建与重叠审计

实际执行当前入口prepare及verify，均exit0。只加载本地真实tokenizer和配置，不加载模型权重、不反序列化probe；仅核对probe文件哈希，没有计算新分数。168条自由回答完整提示长度345–3056tokens，总206362输入tokens，增加128回答预算后最大3184，低于32768，无输入裁剪。0次GPU前向、0答案、0拟合。

当前协议7实现/入口/提示指纹、4来源指纹及3个模型配置/tokenizer文件绑定；冻结设计SHA256仍为78476923d35aa72d9d0a65b0718be4eb38195ef9c5e12f9672045bb2add5f457。另不用构建器assemble，直接从作者spec、源目录和槽位规则独立重建168输入/72缺项/210配对与token差，逐项匹配。53个来源引用、336目标段引文和126条编辑记录的偏移/重建检查通过。完整verify前后27个v2文件哈希相同；v1准备文件保留；此前40试验64文件与支持表达89文件合计153个原产物哈希也保持不变。

实际使用58篇不同背景，22篇与旧probe的train600文档完全相同。T023是一个犬种背景，在semantic_train与semantic_eval均出现；它不含所问游戏目标事实，但这种重复仍披露。22篇用于作者事实依据的不同来源文档中，5篇也在旧train600出现。故只能称源底题ID/精确问题没有参与旧训练，不能称所有来源文本、目标事实或实体均未见，更不能据字面重叠断言预训练熟悉度/OOD。未为清除重叠而事后改分区、清洗背景或替换底题。

新增材料测试12项（v1基础9、v2修订3），连同此前复核/设计10项，共22项CPU测试通过，28.987秒；旧全套120没有重跑，不称142项全套通过。包含真实tokenizer下临时CPU准备/只读重放、禁止load_model、缓存文本/HTML篡改、版本隔离与原文件不变、无GPU阶段、分组/未知完整分母、两匿名排列、逐字引用、精确编辑还原和共享背景披露。

```sh
sh scripts/run_semantic_transfer_materials_v2.sh --stage prepare
sh scripts/run_semantic_transfer_materials_v2.sh --stage verify
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B -m unittest discover -s tests -p 'test_*semantic_transfer*.py' -v
```

以上为CPU材料工具，CLI不提供run/infer阶段。当前无需再次prepare，verify可只读重放。新材料或代码须另存新版本/run，不改当前冻结产物。

## 审核包、停止点与交付

已生成两套独立排列的168条匿名输入包，包含问题及五篇全文，无原ID/分区/条件/作者标签/生成/probe。两套均有原文HTML、rubric、批次哈希与空模板；未评分模板显式unreviewed，不能把默认unknown当已完成评分。交付ZIP为新run的handoff/input-review-a.zip与input-review-b.zip；各只有packet/rubric/template/HTML/README/checksums，无协调映射、AGENTS、历史或作者评分。当前用户暂无外部独立渠道，评审完成数仍0，不反复询问。

review_gate.json明确gpu_launch_ready=false。除了缺少两份可审计、无历史暴露的语义评审，构造覆盖70%已使当前草稿无法达到原90%语义覆盖通过要求；开发分区最多40/48=83.33%，同样不足。不能把分母缩到168或放宽门槛宣布通过，也不能把作者建议标签当干净标签训练。因此本轮完成材料与CPU交付后停在审核/覆盖门槛，未制作或提供GPU启动入口，未准备GPU耗时承诺。即使将来仅在这些草稿上获得高分，也不能宣布本轮可靠性通过。

下一步先解决九个底题的题意/来源未决项，以及可审计的独立语义标签来源；任何对来源范围或协议的修订需新版本、保留当前结果。不自动扩题、加表达、加层或训练；兼容支持负对照、旧probe与可选一次语义重训分开、行为指标不按probe筛选等冻结要求继续保留。380保留底题未用，旧80.67%发布类别结果、no_qualified_baseline与旧评分不变；本轮没有新的probe迁移表现、行为率或论文贡献结论。

持久记录：[准备/核验JSON](2026-10-20-semantic-transfer-materials-preparation.json)、[全部240计划单元CSV](2026-10-20-semantic-transfer-materials-preparation-cells.csv)、[210草稿配对CSV](2026-10-20-semantic-transfer-materials-preparation-pairs.csv)。完整原文与审包留runs，作者spec和轻量来源/汇总随Git记录。更新AGENTS/索引/活动日志/运行说明；不把准备登记为已完成GPU实验，不提交推送。
