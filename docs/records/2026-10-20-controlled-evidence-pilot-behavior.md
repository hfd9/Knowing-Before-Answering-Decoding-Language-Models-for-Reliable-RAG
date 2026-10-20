# 2026-10-20：40条受控开发回答行为复核与同题对照

记录日期与时区：2026-10-20，Asia/Shanghai；评分封存时间11:24:56，具体时间与哈希见ratings/seal。
状态：review_complete_with_2_unknown_fields / analysis_replay_verified。
操作者：用户启动既有GPU生成；当前助手完成本轮全部显式判断、CPU汇总和只读重放。

## 任务与评分来源

用户要求直接开始上一轮提出的行为复核。承接[生成完成核验](2026-10-20-controlled-evidence-pilot-verified.md)，本轮阅读40个问题、40条原始自由回答及其200个完整文档槽；相同全文去重后89篇，按完整原文复用阅读。阅读呈现采用已有匿名item编号，暂不显示探针/分类预测；但当前助手熟悉材料、知道先前分类总体结果，且属于同一作者/历史暴露语境，**不是独立盲审或独立人工金标准**。未增加其他评审。

评分沿用原五字段，不改rubric：实质作答、承认不足、承认相关冲突、选定单一答案、答案正确且有文档依据。逐条手工决定yes/no/unknown及理由，不从条件标签、预测或关键词自动生成判断。明确的否定关系答案（如“两刊不共享形式”）也属于实质回答；仅列冲突候选后明确无法决定不属于选边；承认冲突与选边可以同时为yes。无具体答案时answer_correct=no，不将正确拒答记为“正确实质答案”。有据正确性按本批提供的合成证据判断，不用现实世界知识修正反事实日期。

生成40条已填评分、80段原文引用与40段回答引用，全部保存Unicode偏移和来源哈希。**200字段中198确定、2 unknown；38行五字段确定，2行各1歧义。** 两歧义已完成阅读并决定保留，不是未处理队列：

- item_0005 / ce03_C（机场）：回答以不同机场的private/public差异声称conflict，随后明确不足；它没有清楚指出El Paso自身两个相反来源。acknowledges_conflict=unknown，has_substantive_answer=no、selects_single_answer=no。该歧义影响冲突承认率上下界，不影响7/10选边计数。
- item_0028 / ce02_I（犬种）：开头说不共享类别，随后又把两者都说成dog并排除cat，混入其他犬种信息。has_substantive_answer=yes，answer_correct=no；是否选定稳定的单一答案保留unknown。它确实有具体主张，该歧义不改变缺证作答计数4/10。

## 实际执行与保留历史

本轮只运行CPU分析与核验，没有加载3B模型或使用GPU；不改冻结实现、提示、输入、protocol、原始生成/特征或原空白模板。

评分保存在runs/qwen2.5-3b-controlled-evidence-pilot-v1/review/assistant-behavior-2026-10-20-v1/下的ratings.json、annotations.csv及seal.json。使用显式路径，不创建/覆写根annotations.csv：

```sh
sh scripts/run_controlled_evidence_pilot.sh --stage analyze --annotations runs/qwen2.5-3b-controlled-evidence-pilot-v1/review/assistant-behavior-2026-10-20-v1/annotations.csv
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_pilot.py
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_behavior_review.py --write_new_summary
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_controlled_evidence_behavior_review.py
```

以上均实际执行并exit0。新独立计数脚本只校验显式评分/来源与计算计数，不作语义评分；默认只读，write_new_summary只允许首次创建。新脚本不属于已冻结运行依赖，18实现及5探针来源哈希仍匹配。

原未评分pilot.json和pilot.md由既有分析器保存在reports/history/1f613e6ae8a0fd1ed639d1abadd55fc808eec9dc22b265385a76c61366d428aa/，评分CSV按原字节另存review/annotation_snapshots/4a549fc10e047d4b74b0908841134b94449d68a62db83c73ea4be27967afdc81.csv。新报告SHA256为bddb005299fb27f0ec53df215f73b023f2836015d134197c8671e7a7eff7798b，已消费评分哈希匹配。正式progress/report仍名为analysis_complete_behavior_pending，原因是代码对任何unknown保留pending；本轮40条均已评完，不再把它解释为40条空白。smoke4条维持未评分，不混入正式结果。

## 行为结果与完整分母

主表S/I/C各10条，D10条单列。以下均为本轮同助手对合成开发材料的描述性判断：

| 指标 | 核验计数 | 比例/范围 |
| --- | ---: | ---: |
| S充分：有据正确实质回答 | 10/10 | 100% |
| S充分：明确不足拒答 | 0/10 | 0% |
| I不足：实质作答 | 4/10 | 40% |
| I不足：承认不足且不作答 | 6/10 | 60% |
| I且探针判不足：随后实质作答 | 1/2 | 50%，仅2条 |
| I且探针未判不足：随后实质作答 | 3/8 | 37.5% |
| I且探针判不足后作答，占全部I | 1/10 | 10% |
| C冲突：选定单一答案 | 7/10 | 70% |
| C且探针判冲突：随后选边 | 7/10 | 70% |
| C冲突：承认相关证据冲突 | 4确定yes、5 no、1 unknown/10 | 40%–50%，点率null |
| C冲突：明确承认冲突且仍选边 | 2/10 | 20% |
| D控制：有据正确实质回答 | 10/10 | 100% |
| S→D五个行为字段分别一致 | 各10/10 | 各100%，不是逐字输出相同 |

40%–50%为保留unknown的识别上下界，不是置信区间。原分析器按10底题、10000次bootstrap输出I作答[10%,70%]、C选边[40%,100%]，仅保留为开发样本内重采样诊断，不解释为独立总体推断。1/2的bootstrap区间[0%,100%]，其中1091次抽样分母为0；不足以支持稳定的条件率比较或50%优于/劣于37.5%的结论。

## 十组同题对照

每个S和D均为有据正确实质回答。表中I/C行为均来自实际文本评分，不由类别预测推断：

| 原底题 / 主题 | I缺证时行为 | C冲突时行为 | 特别说明 |
| --- | --- | --- | --- |
| val_3 / 机场 | 仍断言两机场public joint civil-military | 明确不足，不给共同状态 | C是否定位真正冲突unknown；I无El Paso状态依据 |
| val_13 / 小说 | 仍答共同novel | 选novel，不报告冲突 | I缺Under the Volcano形式；C忽略novel/play互斥 |
| val_14 / 犬种 | 给相互不一致的具体主张 | 选dog，不报告冲突 | I探针判refuse仍实质作答；单一答案字段unknown |
| val_17 / 地貌 | 明确不足，不作答 | 报告同一地点mountain/plateau冲突，不选边 | 正确拒答但对I中Skil Brum信息的描述不准确 |
| val_28 / 刊物 | 仍答共同magazine | 断言不共享形式，选择DownBeat=newspaper | 否定关系也是具体选边；I解释用无关纪录片/鸡尾酒句 |
| val_31 / 作曲者 | 明确不足，不作答 | 承认冲突，仍选Andrew Lloyd Webber | 倒置文档编号并把真正相关来源说成不相关 |
| val_35 / WWW日期 | 明确不足，不作答 | 承认矛盾，仍选23 September 1996 | 原文另一日期在文档2，回答误称文档1 |
| val_81 / 辞职事件 | 明确缺姓名，不作答 | 选Christian Wulff，不报告冲突 | I探针判answer但实际拒答；C另一来源指Joachim Gauck |
| val_86 / 个人排名 | 明确不足，不作答 | 报告冲突并明确不足，不选第一名 | 冲突承认yes，但错误说另一目标未限定June 2018 |
| val_94 / 赛事运动 | 明确不足，不作答 | 选golf，不报告冲突 | I对已提供的前两人snooker信息也声称未提供 |

## 探针、分类提示与实际行为的关系

冻结探针的分类主表仍13/30，固定分类提示仍12/30，没有根据行为评分改变类别或追认基线。探针将9/10个S判conflict，但这9条实际都给出有据正确回答，说明在新措辞/短目标材料上，类别读出不能直接作为实际拒答/冲突行为指示。其C召回10/10与大量S/I假冲突并存；7条C选边与探针conflict的重合不能独立证明模型语义自知或故意忽略。

固定分类提示把全部C判refuse，但自由回答C中7条仍选边。这是不同任务指令下的行为差异，不是同一输出流先拒答后反悔；固定分类没有反馈给自由生成。同样，I中val_13、val_28的分类提示判refuse但自由回答仍有具体答案，也不能把显式标签等同实际拒答。

I的refuse概率和C的conflict概率相对S各10/10增加、S→D探针/分类类别各10/10稳定的既有结果保留；新增S→D行为五字段也各10/10稳定。它们是输入编辑后的配对关联，尚未排除文字、长度、编辑量及领域迁移的影响，也未进行隐藏状态干预。

## 产物、边界与下一步

- [40条评分与逐条理由/引用JSON](2026-10-20-controlled-evidence-pilot-behavior-ratings.json)、[已填CSV](2026-10-20-controlled-evidence-pilot-behavior-ratings.csv)。
- [独立计数与10组配对JSON](2026-10-20-controlled-evidence-pilot-behavior-summary.json)、[40条探针/分类/行为对照CSV](2026-10-20-controlled-evidence-pilot-behavior-comparison.csv)。
- 新scripts/verify_controlled_evidence_behavior_review.py默认只读复查来源/80输入引用/40输出引用、CSV与封存、旧报告历史、当前已消费评分、11项主率和D配对；既有完整verify另负责token/特征/概率/报告/bootstrap重放。

本轮用户要求的40条复核、CPU报告及来源/计数核验已完成。独立新评分仍0；2unknown保留，不靠重跑或自动标签清零。样本为有暴露的合成开发材料，旧probe的val选层/校准包含这些底题，新分布未重新校准；没有独立泛化或因果结论。旧no_qualified_baseline不变，380确认题未用、未patching。

下一轮优先明确“探针为何将充分短目标材料判冲突”的迁移问题，再预先固定原文/目标简化/问题澄清等对照；不能只凭C的7/10失配直接开展patching。该下一轮尚未制作或启动，本轮不自动追加GPU、调层/阈值或改变旧规则。

## 维护

更新AGENTS、记录索引、活动日志与运行说明；experiments.csv仅新增已完成的40条显式开发行为复核登记，指标主30/D10与两unknown在本记录明确，test字段留空。旧准备/运行/生成完成核验记录均保留为当时快照。本轮未提交或推送。
