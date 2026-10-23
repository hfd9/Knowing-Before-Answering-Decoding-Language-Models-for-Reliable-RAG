# 2026-10-23：55条完整材料与155主张的有暴露作者复核

日期与时区：2026-10-23，Asia/Shanghai。
状态：作者侧逐主张复核与技术核验完成；实际独立语义审核0。
操作者：当前助手，已接触AGENTS、旧作者判断、完整输出和协调者资料。

## 授权与范围

用户要求接续后续工作直到长期GPU。现有最小审查包已准备，当前助手可以完成有历史暴露的全文复核与离线分析；本轮另存[作者复核口径](../../prompts/semantic_claim_author_review_v1.json)，明确允许55条现有材料的新增作者判断，不冒称实际独立审核，不改变原准备spec中独立审核0和空白表。

固定55条范围不变：旧23锚点、同13底题3相关I未作答、26条S全部输出以及新3冲突解释。原55/275槽/140去重全文、26配对和旧60不足分母不修改；无新采样、生成、外部检索、拟合或probe读出。恢复前未提交的诊断、材料准备与交接改动保留。

## 实际阅读、手写与封存

本轮全文读取55问题和275文档槽。140篇不同文本共65560字符，重复文本按原哈希及槽位连接；首次终端显示截断的文档段落另行完整补读，不将截断显示算作全文已读。源材料可能原本截断，按原呈现内容判断，不自行补充未给来源。

先另存55行[输入手写判断](../review/2026-10-23-semantic-claims-author-v1/input-manual.json)，北京时间15:04:57.076723按[input-seal](../review/2026-10-23-semantic-claims-author-v1/input-seal.json)封存，再打开当前轮回答文件并拆分。此前已看过输出，封存只证明本轮处理顺序，不消除历史暴露，不能称真正独立输入盲审。

当前轮完整读取55回答，手写155个主张实例：原文锚点、主张、支持判断、文档编号、缺失环节、歧义和角色逐条写在[part1](../review/2026-10-23-semantic-claims-author-v1/output-manual-part1.json)、[part2](../review/2026-10-23-semantic-claims-author-v1/output-manual-part2.json)、[part3](../review/2026-10-23-semantic-claims-author-v1/output-manual-part3.json)。北京时间15:10:55.672750按[output-seal](../review/2026-10-23-semantic-claims-author-v1/output-seal.json)封存后，再连接本轮来源映射与旧判断。

155是手写主张实例，含重复表达，不是155个独立事实或样本；部分同判属性仍在同一主张内表述。82原句候选单元都有至少一个手写主张引用，机器只验证文本跨度与逐句覆盖，不自动证明语义拆分完全穷尽。原引用244个实例，均绑定原文偏移与哈希。缺失与冲突主张另核对完整五文档，未按出现代码或关键词自动评分。

## 一次明确判断修订

首次作者分析将Q055_C03的Napoleon→Waterloo使用者归属记为contradicted。复核收紧为unsupported：文档给Napoleon使用Mont Saint-Jean和通常名Waterloo，没有给Napoleon使用Waterloo的关系，但也不逻辑排除他曾使用另一名称。提供文本不支持与外部事实为假必须区分。

15:15:00.252205另存[判断补记](../review/2026-10-23-semantic-claims-author-v1/judgment-addendum.json)，绑定原五份v1分析文件哈希，原手写、封存和v1分析不覆盖。新v2脚本只应用这一个显式修订到同一55条/155主张，无重新评分、采集或拟合；目标答案端点没有变化。后续以analysis-v2为当前结果，v1是可追溯原稿。

## 结果与解释

输入判断26 answerable、20 insufficient、9 ambiguous。9歧义包括Khet2、overview2、词义2、Sheila指代1、温差成因2。温差两输入均保留成因/条件范围，避免以输出是否选弱风来决定输入语义身份。原作者构造参照及旧8条输出边界均保留，不将新9与旧8混作同一端点变化，也不据此重算原60真缺证率。

155主张当前计数：supported101、unsupported34、ambiguous13、contradicted7。只是本包和本次拆分下的描述性数量，不能报语义Accuracy、模型总体解释准确率或显著性结果。

| 原选择角色 | 条数 | 本轮目标答案支持 | 全部主张均有据 |
| --- | ---: | --- | --- |
| 旧23作答锚点 | 23 | 15 unsupported、8 ambiguous | 17 no、6 unknown |
| 同底题I未作答 | 3 | 未给具体目标答案，目标支持不适用 | 1 yes、1 no、1 unknown |
| 同底题S充分构造对照 | 26 | 23 supported、1 unsupported、2未作答 | 21 yes、4 no、1 unknown |
| 新3冲突解释 | 3 | 均未给具体目标代码，目标支持不适用 | 3 no |

这些是有历史暴露的作者端点判断。旧23中的15条未支持并不等于15条独立确认错误或无歧义真缺证；其中还包括输入成因边界。原整体正确性字段与新“目标支持/全部解释支持”定义不同，联合表是端点对照，不是覆盖旧评分的自动裁定。

若只看具体行为，新3条均保留未知，本轮作者判断其保留依据supported；同时三条conflict实例均unsupported：

- rel03_OA_v1 / Q004：另一单位inspection赋值与目标access未知兼容，未给互斥对。
- rel05_TA_v2 / Q026：目标单位只有一个inspection赋值，独立access未知不构成冲突。
- rel03_OQ_v2 / Q052：另一单位access赋值与目标未知兼容，字段/单位规则不提供互斥对。

仍无实际独立核验，不能升级为新的正式冲突终点、总体发生率或内部机制结论。

其他关键端点分离例子：

- stv02_A_S / Q055：Waterloo目标答案supported，Napoleon使用者归属unsupported，全文no；原整体unknown保留。
- stv04_B_I / Q050：不完整回答两城位置有据，否认Dingzhou位置信息与D5直接相反；不答不意味着解释正确。
- stv19_B_I / Q008：首府未知有据，“没有州政府位置”若泛指建筑则被Statehouse限制，若指城市则仍缺，保留ambiguous。
- stv05_A_S和stv05_B_S / Q021、Q030：两个S本有board类别却否认信息，原失败对照保留；Q021额外conflict无据。
- stv04_B_S / Q053：Luoding地点有据，northern China改为northern Hebei的更细范围无支持，不能据此判断外部地点一定假。
- stv26_A_S / Q041：两游戏目标类别有据，末尾导演娱乐形式的过宽否认有范围歧义，整体unknown；旧目标相关评分不覆盖。

## 技术检查与产物

实际stdlib作者分析exit0；显式补记后的v2 analyze及PYTHONHASHSEED277异进程verify exit0。另写[独立实现核验](../../scripts/verify_semantic_claim_author_review.py)，不导入两分析器、不加载模型/probe，直接从原手写、补记和原55问答重建字段、引用及计数，actual exit0。[核验JSON](2026-10-23-semantic-claim-author-review-verification.json)记录55目标端点、155主张、82原句覆盖、244文档引用、四组计数及CSV逐字段一致。

59来源文件哈希通过，包括原审查包16载荷、27来源中的原12拟合封存、手写/封存/原v1分析及新补记等；原审查包、独立评审空白表与正式标签不改写。这里的独立是核验程序实现，不是第二语义判断。没有重放全部历史运行目录或重跑旧实验测试套件。

当前产物：[v2报告](../review/2026-10-23-semantic-claims-author-v1/analysis-v2/report.json)、[55行CSV](../review/2026-10-23-semantic-claims-author-v1/analysis-v2/rows.csv)、[155主张CSV](../review/2026-10-23-semantic-claims-author-v1/analysis-v2/claims.csv)、[可读主张全文](../review/2026-10-23-semantic-claims-author-v1/analysis-v2/claims.md)、[275槽阅读清单](../review/2026-10-23-semantic-claims-author-v1/reading-inventory.json)。新Python AST/JSON/CSV/本轮文档链接与差异格式检查通过，不登记新模型实验指标。

仅读当前结果：

```sh
python3 -B scripts/semantic_claim_author_review_analysis_v2.py --stage verify
python3 -B scripts/verify_semantic_claim_author_review.py
```

## 研究决策及当前停止位置

[决策说明](../semantic_claim_review_decision.md)保留“目标未知被正确保留时的证据状态解释准确性”为候选具体问题。真实独立语义审查完成后再决定是否需要另立设计。当前不因三个已见事后案例而创建新措辞网格、采集代码或GPU就绪协议；长期GPU分工不变，本轮未形成需要用户启动的GPU任务。

用户要求的可执行离线复核、结果连接、核验及决策已完成；实际独立审核仍不是当前助手能够自证完成的环节。独立批准0、正式gate=false、正式标签null、原拟合预算0、380题封存保持，无新前向/回答/拟合/补probe/patching。同步AGENTS、综合结论、索引和活动日志，不改experiments.csv；未提交推送。
