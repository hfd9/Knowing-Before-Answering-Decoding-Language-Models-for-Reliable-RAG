# 2026-10-20：240条作者侧语义复核与八变体审计完成

状态：exposed_author_input_review_complete / material_revision_needed / independent_review_pending / no_GPU。

用户要求直接完成下一步工作。本轮先读开发6底题48条全文，保存development48_sealed.json，再完成训练/评估其余192条。总计30底题、240材料、1200文档槽、435去重全文均已读，90背景槽/83背景全文按槽位说明相关性。顺序仅指本轮工作；当前助手已经接触AGENTS和此前材料历史，**不是历史盲评审、外部独立评分或金标准**。不以不同会话名、自报独立或评分一致升级证据等级。

材料固定为runs/qwen2.5-3b-semantic-transfer-materials-v4-r2；旧材料、原作者建议、评分接收、执行器协议、批准标签与门禁均保留。新判断先另存并封存，再加载author_judgments作事后对照；全程未生成或读取这批材料的新probe/模型回答，未加载模型或probe。

## 逐条语义判断

| 分区 | 总数 | 充分answer | 不足refuse | 冲突conflict | unknown |
| --- | ---: | ---: | ---: | ---: | ---: |
| semantic_train | 96 | 48 | 24 | 24 | 0 |
| semantic_dev | 48 | 24 | 12 | 10 | 2 |
| semantic_eval | 96 | 48 | 24 | 24 | 0 |
| 合计 | 240 | 120 | 60 | 58 | 2 |

S/K120条均在本轮被判充分，I60条被判缺少必要关系，C60条中58冲突、2未知。238个确定判断与作者建议同类；这是有背景暴露的复核一致计数，**不是238/240独立语义准确率**。临时确定覆盖238/240=99.17%，独立审核覆盖仍0，正式批准标签仍0，不能套用90%独立门槛宣布通过。

每条记录包含底题ID、分区、问题关联、必要事实、支持结论/支持链、缺失前提或候选互斥主张、范围/消解理由、置信程度，以及两目标全文共480条逐字引用的偏移与文档哈希。240联合表保留probe预测、分数和回答为空；尚无新推理，不虚构这些字段。全部30题的问题、背景多重集、背景次序及目标槽位固定性通过程序核对。

开发48条的六题结论：

| 底题 | 审核重点与判断 |
| --- | --- |
| train_405 / 两所大学 | WashU与University of Washington不能混同；I只给WashU国家，四个公立校区不补Colorado国家。S/K充分，I不足，C同一Colorado大学的US/Canada且not US冲突。 |
| train_1525 / 2015法网男单 | 亚军Djokovic、四盘和其他赛事不能推出冠军。S/K支持Wawrinka，I不足，C同一赛事两名冠军冲突。 |
| train_1064 / ameliorate | 词性和例句领域不提供better/worse方向。S/K充分，I不足，C明确same sense的better与worse/not better冲突；不拿参数记忆补词典事实。 |
| train_315 / 城乡温差 | 夜间/弱风的显著程度不是主机制；水分和拟人化背景无地表机制桥接。K次要废热兼容主要地表改变；C否认地表改变有任何贡献，不能消解。 |
| train_989 / 扑克亮牌 | S/K按规则体裁理解可给条件，置信moderate；I没有亮牌时点。C正面一般程序描述与反面规范禁止存在模态层次歧义，两条unknown。 |
| train_1302 / Old Order Amish | I的场所和仪式内容无星期；背景“多数基督徒周日礼拜”不能推出指定社群的日程。C同一社群Sunday与Saturday/not Sunday冲突。 |

其他易误判点均在底题说明中记录：Ohio最大城市不等于州首府；童谣所给版本的horse与pie是最后动物/食物兼容；原唱与后来的翻唱、1960与1962录音、1567与1867两学校不应制造假冲突；月份March或歌曲中的姓名不能补目标姓氏/人物关系；其他季别、赛事和年代计数不能移植。

## 两条冲突判断暂不确定

stv17_A_C与stv17_B_C来自扑克题。正面说“remaining players expose/reveal and compare their hands”，反面使用“must not/prohibited”。

按通常的规则说明体裁，正面可理解为必须亮牌，与反面规则冲突；但若正面是实际/惯常行为描述，反面是义务禁止，违规行为与规范可同时存在。文本没有显式排除这一区别。本轮因此不把两条当毫无歧义的真实冲突标签，也不反向宣称它们已证实兼容。支持/兼容条件的回答仍可按通常程序解释，但注明从描述到have to的语境推断为moderate。

具体修订候选把C负面统一为一般程序描述“在同一条件下不亮牌/保持隐藏”，与正面的描述层次直接对齐；不是在此查证或重写现实扑克规则。候选尚未应用，之后须在新材料版本中复核。

## 表达一致与严格事实一致分别报告

120组A/B配对中，119组两侧都有确定且相同的证据状态，1组为上述扑克C的双侧未知。**相同证据类别不证明全部命题不变。** 本轮18组记录表达/指代/附带事实/术语或模态注意点，另外102组未识别出具体额外差异；这不是形式逻辑等价证明或独立通过率。

| 问题范围 | 具体差别 |
| --- | --- |
| Waterloo S | A沿Mont Saint-Jean ridge，B仅near the ridge，空间精度不同。 |
| Khet S/K/C | B省略A的chess-like属性。 |
| James II S/C | B未保留A的38th序数；K在第二目标中仍保留，单列处理。 |
| Connors K | B加born姓名关系；A只说professionally known as，不能自动等同出生名。 |
| 大学 K | B省略research属性。 |
| 法网 I | B第二目标省略2015/French Open，依靠问题与前文恢复指代。 |
| 热岛 S/I | S的B省略术语命名；I的A增加significantly程度，B没有。 |
| Amish S/K | B_S及A_K把Sunday称weekday；答案仍明确Sunday，但术语不当。 |
| Sorry/Barbarossa K | 仅B增加plasticine机制。 |
| Little Women I | 仅B明示该书为novel，A仅说作者。 |
| sashimi S/K | S的B未保留fresh；K的B额外引入rice-based sushi比较和类别词线索。 |
| 扑克 C | 双侧均有描述/规范层次歧义。 |

这些差别大多不改变本轮三分类判断，却可能改变probe概率。后续不能将所有A/B差异都解释为纯措辞迁移，更不能根据一致类别忽略其他事实变化。

## S→I存在系统性附带事实变化

60组同表达S→I，当前手工语义判断均为充分→不足，但严格构造审计结果不同：

| 构造审核 | 配对数 | 底题数 |
| --- | ---: | ---: |
| 必要关系层面可视为删除型，无新增附带事实 | 6 | 3 |
| 还新增/替换其他事实 | 52 | 26 |
| 扑克程序/模态重写 | 2 | 1 |

三题为Luoding/Dingzhou、Korean War作战年份、2014CNN培训博物馆。这里的删除型指必要关系层面的删去，**不是逐字只删一个词或已证明最小文本编辑**。

其余I常加入原S没有的人数、日期、节目属性、人物身份、职业经历、例句领域、翻唱版本、无饭属性等。例如法网I增加亚军与四盘，主赛第四季I增加十三选手和播出时段，Last Kiss I增加Pearl Jam1998翻唱，刺身I增加without rice。它们仍可以缺少必要依据，但不能称“其他事实都不变、只删除一个必要前提”。因此27题54条I列入整体修订清单。

S→C60组中58组被本轮判为充分→冲突、2组未知；S→K60组均判充分→充分。这些是材料语义/构造判断，不是模型类别翻转、probe表现或因果效果。

## 产物与实际核验

- [240条显式评分JSON](2026-10-20-semantic-transfer-author-input-review-ratings.json)：含30题必要事实、背景相关性与构造理由；不自动消费为正式标签。
- [开发48封存](2026-10-20-semantic-transfer-author-input-review-development48-sealed.json)：逐字节保存本轮先行判断，后续240评分中原48不变。
- [240行联合CSV](2026-10-20-semantic-transfer-author-input-review-cells.csv)与[300行配对CSV](2026-10-20-semantic-transfer-author-input-review-pairs.csv)：含底题/分区/引用、构造审计及真实token差，模型字段为空。
- [修订建议JSON](2026-10-20-semantic-transfer-author-input-review-revision-proposals.json)：19处具体文档文字候选及27题54条I整体重写清单。I局部表达修复与整体重写有重叠，不能自动顺序套用；候选不是就绪材料批次，没有应用到v4-r2。
- [结构化记录](2026-10-20-semantic-transfer-author-input-review.json)：实际计数、测试、源/新产物哈希及正式门禁快照。

新增CPU工具scripts/semantic_transfer_author_review.py仅汇总并校验明确写下的判断，不通过条件名、关键词或模型生成语义标签，无训练/GPU/批准路径。实际命令：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_author_review.py --stage analyze
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_author_review.py --stage verify
```

两进程均exit0。480目标引用、1200槽/435全文哈希清单、90背景槽、30题分组/固定问题/固定背景槽位、开发封存、240/300行导出、旧源保持及禁止升级独立性检查通过。新增5项CPU测试通过，0.474秒；测试是判断记录的完整性与分母校验，不证明语义判断正确。开发时发现CSV默认CRLF与只读文本归一化不一致，正式导出前改为固定LF并重测通过，原冻结实验无改动。旧53/120全套未重跑。

全文阅读是当前助手的显式声明；哈希及槽位清单能证明批次、映射与文本完整性，不能证明阅读理解或独立性。原材料及正式执行器的批准标签仍全部null，gate仍false，独立评分0。原40、旧probe成绩、发布类别80.67%、no_qualified_baseline和380保留题均不变，无新前向、回答、训练、校准或干预。

## 后续工作边界

当前先修这批固定材料的对照质量：同批次新版本中消除扑克模态歧义、恢复A/B附带事实一致，并重构54条I的删除对照。保持30底题/分区/数量/层/单次训练预算，不增加措辞网格或按未来输出换题；无法做到严格构造的题明确保留未满足状态。修订后须重新检查，再交实际独立上下文审核，不能以本轮238个确定判断替代独立标签。

本轮完成的是作者侧全量复核与修订清单；修订候选未应用，未声称新材料已经通过。用户暂无外部渠道的答复持续有效，不反复询问，不伪造独立评分，不自动放行GPU。代码与记录已写工作区，未提交推送。
