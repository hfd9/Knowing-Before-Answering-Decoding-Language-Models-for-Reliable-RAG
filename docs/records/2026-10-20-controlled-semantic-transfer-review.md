# 2026-10-20：40条语义与行为分离补充复核、联合表和独立性审计

状态：supplemental_review_complete / data_and_analysis_verified / independent_confirmation_pending。

## 用户目标与本轮范围

用户将首要任务明确为验证冻结chat L28探针对真实证据语义的迁移可靠性，要求先对现有40条分开复核输入语义与输出行为，形成包含问题、完整证据、支持链、生成回答、probe预测/分数和底题ID的联合表。原router的80.67%发布类别结果不因此被否定；也不把充分材料上的conflict读出解释成模型内部识别矛盾。无需重新排查已经核对一致的模板接口，不重跑52/80/50输入诊断，380保留底题继续封存。

本轮实现独立材料包、两位分离LLM评审、逐项来源/引用校验和联合分析，并冻结下一轮小型跨表达验证的设计与底题分区。没有启动新GPU、训练或patching。**本轮没有取得完全不接触项目历史的独立确认；下文解释实际暴露，不能将补充复核写成独立金标准。**

## 材料隔离与实际独立性限制

新目录：runs/qwen2.5-3b-controlled-semantic-transfer-review-v1。输入包仅包含匿名E编号、问题与五篇完整文档；行为包另用独立排列的B编号，包含问题、五篇完整文档与实际回答。两个包均无probe、原底题ID、S/I/C/D标签、作者判断或旧评分，协调映射单独保存。输入评审不见生成回答；行为评审不见输入评审结果。两位评审各自读完40问题/200完整文档槽，行为评审另读40回答，各自封存后才在协调端汇合。相同内容可使评审推测变体关系，文件访问隔离是工作流程约束，不是操作系统权限隔离。

采用不继承父会话轮次的两个评审上下文，但输入评审主动报告，运行环境仍提供用户AGENTS.md交接内容；行为评审的暴露审计也确认其中含既有40条汇总、probe摘要和部分历史逐题信息。二者未打开旧预测/评分/协调映射，但这些背景已可能影响判断。**实际应称“逐条结果隐藏、有项目历史暴露的分离LLM补充复核”；完全历史盲的独立新评分仍为0。** 原准备protocol中的无历史暴露表述是设计意图，实际以exposure_audit.json及两位评审原文暴露声明为准；不改原protocol来抹去这一差异。

这一限制来自实际运行时上下文注入，不是仅因没有人工评审而作的泛泛保留。即使未来换成完全无项目背景的LLM，也仍需披露模型来源、共享偏差和非人工金标准限制。独立性与自动格式/引用通过是不同问题。

已制作可交付给项目外、未读历史评审的两个独立ZIP，均只有packet.json、rubric.json、README.txt、SHA256SUMS.txt，无协调表/历史/评分：

- 输入：runs/qwen2.5-3b-controlled-semantic-transfer-review-v1/handoff/input-review.zip。
- 行为：同目录behavior-review.zip。应交给另一位评审，或至少在输入评分封存后再揭示行为材料。

对应匿名全文页面为input_public/review.html与behavior_public/review.html。不要把AGENTS、当前报告、联合表或另一评分一并发给独立评审。用户已答复暂时没有外部独立评审渠道；保留independent_confirmation_pending，不反复要求寻找评审，不把当前补评改称独立确认。

## 新补充输入语义与支持链

输入评审：answer20 / refuse10 / conflict10 / unknown0，均自报high；其中S10、D10充分、I10不足、C10冲突，与作者构造类别逐项一致。每条有必要事实、支持链、缺失前提/互斥命题、消解依据判断、逐字证据。120个输入引用均通过全文槽位与Unicode偏移校验。高自报置信和标签一致不增加其独立性。

| 需要核对的问题 | 补充复核结果 | 当前能说到什么程度 |
| --- | --- | --- |
| S中9条probe假冲突是否成立 | 新输入判断S10均充分；冻结probe仍9/10 conflict；另一个行为评审判S10均有据答对 | 补充复核支持原测量疑点，尚无历史盲独立确认 |
| I中4条作答是否缺依据 | val_3机场、val_13小说、val_14犬种、val_28刊物均缺一项必要前提，四回答均判unsupported_substantive_answer=yes | 4/10是全部语义不足样本的作答率，与probe是否命中无关 |
| 原C中7条选边有无消解依据 | 新输入判断均为真实相关冲突，行为评审对旧7条全部判选择一侧且无提供的消解依据 | 旧7条得到新补评支持；机场另有选边定义分歧，不能直接换成独立确认的8/10 |

缺失前提分别是El Paso的机场状态、Under the Volcano的体裁、Boykin Spaniel的类别、DownBeat的出版形式。其他实体的文档不能补齐这些前提。输入审查按给定证据命题评价，不用现实常识补值。地貌I的“same landform classifications”被评审解释为分类体系相同而非已给出两个地点相同类别；体育C同时存在文档内和跨文档矛盾，均记录在逐条判断中，后续真正独立评审可重新判断。

## 独立于probe命中的行为统计

主表保留S/I/C30，D10单列；语义分组使用新输入评审判断，不由作者标签或probe决定。以下为本轮有背景暴露的补充评分。

| 指标 | 新补充评分 |
| --- | ---: |
| S充分有据正确实质作答 | 10/10 |
| S充分明确不足拒答 | 0/10 |
| 全部语义不足实质作答 | 4/10 |
| 全部语义不足中缺必要依据而作答 | 4/10 |
| 全部语义冲突选边 | 新评审8/10；旧评审7/10，保留差异 |
| 语义冲突选边且无提供的消解依据 | 新评审8/10，其中包括旧评审确定选边的全部7条 |
| D充分有据正确实质作答 | 10/10 |
| S→D原五行为字段一致 | 每项10/10 |
| 语义不足且probe判不足后作答 | 1/2，仅小分母描述 |

机场ce03_C原文先断言“El Paso ... private ... Tucson ... public”，随后称证据不足、无法确定共同状态。旧评分has_substantive_answer/selection=no；新评分将开头视为采用一个冲突侧，二项均yes。对是否承认真正同机场冲突，二者均unknown，因为文本显式对比的是两个不同机场。此处保留两套评分，不由有历史暴露的协调者自动裁定。9行共11个原五字段分歧已列出。

另外，新评审把8条冲突选边的answer_correct保留unknown：所选侧有文档支持，但材料无法消解哪侧成立；旧评分按不能作为有据确定答案记no。这是正确性字段的解释差异，**不能用新的unknown声称错误减少**。新加的selects_without_evidence_resolution明确记录“没有证据支持消解却选边”，从而不依赖对正确性的这一解释选择。行为七字段共280项，271确定、9unknown（8项answer_correct、1项冲突承认），不覆盖旧198确定/2unknown评分。

D具体为S目标A的一处无关档案位置/颜色/形状替换（例如grey envelope→pink envelope、central news desk→western news desk），支持事实、问题、目标B、三背景及槽位/顺序不变，十题输入token差全0。逐题前后全文保存在联合结果的D_control_pairs，不能将D解释为已控制S整体表达迁移或I/C全部编辑量。

## 联合产物、技术核验与旧结果保护

新脚本scripts/controlled_semantic_transfer_review.py提供prepare/validate/analyze/verify。输入/行为原始评分各40条，批次哈希、匿名映射、七字段/语义schema、241个逐字引用与来源哈希/偏移全部通过。新增10项CPU测试（复核流程6+冻结设计4）全部通过，最终0.634秒；覆盖匿名字段隔离、批次/假引用/重复ID拒绝、unknown完整分母、新语义分组、D不混入主表、旧文件不变、分区与构造/训练预算、未用于旧probe训练的源底题及问题文本排重。未重跑全套旧120，不称130项全套通过。

实际执行：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/controlled_semantic_transfer_review.py --stage validate
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/controlled_semantic_transfer_review.py --stage analyze
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/controlled_semantic_transfer_review.py --stage verify
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B -m unittest discover -s tests -p 'test_*semantic_transfer*.py' -v
```

最终报告在新run的reports/v3/review.json、joint.csv、joint.html（包含全部原文，可展开核对）；v1/v2为本轮分析开发快照，未覆盖。最终verify重放与源64文件逐个哈希检查通过；旧protocol、40生成/特征、旧评分和报告均未变，未导入任何新评分覆盖原annotations。

持久轻量副本：

- [联合分析与实际暴露JSON](2026-10-20-controlled-semantic-transfer-review.json)。
- [联合CSV](2026-10-20-controlled-semantic-transfer-review-joint.csv)：问题、支持链、回答、probe三概率、原底题ID、全部新评分/理由/引用，完整文档用匿名包引用链接，原全文保留runs。
- [输入原始评分](2026-10-20-controlled-semantic-transfer-review-input-ratings.json)与[行为原始评分](2026-10-20-controlled-semantic-transfer-review-behavior-ratings.json)：保留原评审身份、暴露声明和封存评分。

## 下一步与研究边界

已将[小型跨表达验证设计](../semantic_transfer_validation.md)及显式JSON冻结，结束默认追加措辞网格；当前只有设计和30底题分区，240材料、无历史暴露的语义标签、GPU实现/预检查/耗时与启动入口尚未准备。当前首要未完成项是取得可审计的历史盲独立输入/行为评分，而非重查模板、覆盖旧7/10或直接patching。

旧发布类别80.67%、no_qualified_baseline、380保留题和原行为评分均保持原范围。新补评不是独立确认，尚不能证明“内部已识别而忽略”、单一迁移根因、稳定跨表达规律或论文新增贡献。更新AGENTS/索引/活动日志/实验登记，实验登记明确background_exposed_supplemental、independent_confirmation_pending。本轮未提交推送。
