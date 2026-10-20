# 2026-10-20：九题来源复核、v3材料与语义评审接收校验

状态：source_followup_complete / materials_v3_CPU_verified / semantic_review_pending / coverage_gate_not_met / no_gpu。

用户要求直接开始后续工作。本轮逐题复核原九个未完成底题的全部五篇来源及三篇保留背景，去重49篇完整发布片段；初次合并显示被截断，随后按题组完整读取缺失内容，不把截断显示计作读完。继续只使用已固定的发布train来源，没有外部事实查询、gold答案补前提、替换底题或改变分区。操作者有项目历史暴露，以下都是作者判断，不是独立语义确认。

## 九题处理结果

| 底题 | 本轮处理 | 不能省略的区别 |
| --- | --- | --- |
| train_744 | 明确James II of Scots (1430–1460)，新增八条作者稿 | 来源索引同时列出苏格兰与英格兰同名君主。新增国别/生卒范围，保留所问绰号及原选项；这是公开的问题澄清，不声称原题原样已充分。 |
| train_1136 | 仍未完成 | 现代呼啦圈的发明年份不能直接代替未明确的首次亮相事件。 |
| train_1154 | 仍未完成 | 书评提到马及寓意，没有建立“最后吞下”的顺序关系。 |
| train_405 | 仍未完成 | WashU在美国与Colorado大学在Colorado，不足以在无外部地理前提时补齐两校共享国家。 |
| train_1470 | 仍未完成 | 最大城市与州首府是不同属性，其他州首府/国家首都不能补齐。 |
| train_1805 | 仍未完成 | Last Kiss与Wayne Cochran的元数据没有将题中歌词映射到该曲名。 |
| train_1605 | 仍未完成 | 战争爆发、美国战前驻军/撤军和美国战时介入区间是不同事件。 |
| train_254 | 仍未完成 | 作者身份、无关家谱及日历里的March不能建立小说家庭姓氏。 |
| train_33 | 仍未完成 | 源文混写sushi/sashimi，未唯一对应题中准备方式。 |

逐题原问题、拟议问题、所需关系、拒绝的补全方式、49全文ID及逐字引用见[prompts/semantic_transfer_source_resolution_v1.json](../../prompts/semantic_transfer_source_resolution_v1.json)。这是固定来源政策下的作者复核，不是证明发布标签错标或题目绝对不可构造。解决八题将需要新的来源前提或不同题意处理，须明确版本及适用范围，不能静默补入。

## v3材料与原版本保护

新spec为prompts/semantic_transfer_materials_v3.json，CPU入口为scripts/run_semantic_transfer_materials_v3.sh，新run为runs/qwen2.5-3b-semantic-transfer-materials-v3。复用不变v1构建器的隔离模块，同时绑定v3实现和来源复核JSON哈希，不修改v1/v2的实现、spec、协议或产物。

当前22底题176草稿、八底题64未完成，计划240分母及12/6/12底题分区保持原样；构造覆盖73.33%，独立标签0。训练/开发/评估分别80/40/56草稿，缺16/8/40。新增的仅stv07_A/B×S/K/I/C八条，旧168输入逐字段及token数完全不变。新增S建立同一苏格兰君主的绰号关系，K用兼容的王朝/序位/生卒信息，I移除绰号关系，C仅改目标B并显式否认同一绰号，不能靠多个可共存绰号制造冲突。

实际CPU prepare/verify及独立重建176输入/64缺项/220配对与全部token差匹配；全30题54来源引用（已构造22题39引用）、352目标槽引用和132编辑记录均校验。真实tokenizer345–3056，总229126输入tokens，加128回答预算后最大3184/32768。未加载模型权重或反序列化probe，未计算新分数。

两个新匿名审包各176条，独立排列，无作者标签/底题ID/分区/probe/回答；ZIP包含packet/rubric/template/全文HTML/README/checksums，已核对全部成员内容和哈希。留在新run的handoff/input-review-a.zip及input-review-b.zip，不改旧168审包。新材料背景61篇中22篇旧train见过，仍有1个背景跨train/eval；24篇引用来源中5篇旧train见过，包含君主指代消歧背景，不声称全文或实体全新。

## CPU评审接收校验工具

新scripts/semantic_transfer_review_intake.py只提供prepare/verify。检查冻结设计、240计划分母、同题分区、原始null标签、匿名映射与packet内容/哈希；两份评分必须成对提供、身份不同、覆盖全部本批输入、明确声明实际历史暴露情况，并提供支持链/缺失事实/互斥主张及可匹配的原文引用。错误批次、漏项/重复项、伪造引用/偏移、unreviewed模板或history_exposed非false均拒绝。

两份评分一致时只输出consensus_candidate；分歧或unknown不自动裁定。原材料semantic_label保持null，approved_for_training和gpu_launch_ready始终false。自报未暴露和两个不同姓名并不能证明上下文独立，实际接收上下文仍需可审计复核，工具不会自动把评分升级为独立金标准或导入训练。

实际无评分运行输出在runs/qwen2.5-3b-semantic-transfer-review-intake-v1：validated_review_files=0、agreement_candidates=0、approved_semantic_labels=0。此处的0表示没有输入新评分，不能将待评模板的unknown当作完成判断。用户暂无外部评审渠道，本轮未重新询问或另起背景暴露评审冒充独立确认。

```sh
sh scripts/run_semantic_transfer_materials_v3.sh --stage verify
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_review_intake.py --stage verify
```

日后获得两份真实评分时须使用新的intake run目录，显式指定--review-a和--review-b；当前空评分快照保持冻结。该工具没有GPU或拟合阶段，也不是正式标签批准流程。

## 验证与当前停止点

31项相关CPU测试全部通过，42.414秒，包含此前22项及本轮来源/v3材料3项、评分接收6项。覆盖真实tokenizer临时准备/只读重放、旧版本不变、来源引用、分区/分母、映射篡改、暴露声明、批次/漏项/假引用、分歧与候选标签不自动批准。旧全120本轮未重跑，不将其与31相加声称151项全套。最终两项只读verify exit0；149个既有产物/冻结来源路径及31个当前材料/接收产物前后哈希保持一致。

当前构造覆盖73.33%仍低于冻结90%要求，开发40/48、评估56/96的可构造上限也不足；语义标签覆盖仍0。不能缩分母、改门槛或用作者意图训练。八个剩余题的缺口已具体定位，现有固定来源政策下不能靠继续改写补齐。下一步若扩充来源或改变题意，必须明确新版本与任务变化，再重新做材料/语义审核；旧v1/v2/v3与本轮结论保留，不能将来源扩充后的成绩追认成原来源方案通过。

本轮没有新GPU、回答、训练、校准或patching，不重复52/80/50诊断；旧80.67%发布类别结果、旧行为评分及no_qualified_baseline不变，380原测试保留底题未打开。无新的迁移表现、行为率或因果结论。轻量审计/汇总/240计划CSV/220配对CSV随项目保存，原始全文与审包留runs；同步AGENTS/索引/活动日志，不提交推送。
