# 2026-10-21：v5修后语义验收、风险清单与交付封存

状态：v5_exposed_author_acceptance_complete_with_residual_risks_sealed_no_GPU。
操作者：已接触AGENTS、历史、作者意图及v4判断的当前助手。用户要求直接完成修后语义验收、验收表/风险清单和封存交付三个步骤；本轮均已完成。这个完成状态表示作者侧检查和交付完成，材料仍有未决项，不表示独立语义审核或探针迁移可靠性通过。

## 实际阅读与判断来源

读取v5全部30底题、240个八变体输入。按1–5、6–10、11–15、16–20、21–25、26–30底题六批显示，阅读两个目标槽全文和每底题三个背景槽全文；同底题相同目标片段用精确相同文本指针复用。覆盖1200文档槽、435去重全文，其中90背景槽对应83篇去重全文。全部480条目标引用保存原文、槽位、字符偏移及全文SHA256。背景逐槽说明沿用v4笔记，经本轮对照相同原文复查；不是新的独立证据。

本轮同时阅读train/dev/eval，是作者侧修后QA；没有另造“先封存开发再读评估”的时间顺序，也没有新的盲评或隔离评估声明。历史暴露、全文阅读声明和判断政策保存在[显式判断](2026-10-21-semantic-transfer-v5-acceptance-ratings.json)，程序只核验和汇总这些判断，不从S/K/I/C条件自动赋标签。正式材料semantic_label仍全部null。

## 六十组S→I的验收

全60组均检查匹配S、I残余、三背景是否残留答案支持、额外事实、词义或外部知识补桥。结果为58组暂可接受的关系删除/弱化、2组保留unknown_support_scope；全部60条I暂判refuse。两组未定来自扑克A/B的S本身是否支持have to义务，而不是I仍保留了showdown答案别名。

与修订前相比，v5的I不再另加亚军、人数、翻唱、例句等无关事实。本轮未识别出新的无关事实引入，但这是作者判断，不是程序证明。保留Sharon/Pittsburgh、chess-like/abstract strategy、Pachisi、Colorado等已在匹配S中的属性，使关系删除与抹去全部答案线索保持区别；它们依然可能被模型通过常识补桥。相关词义边界项标为moderate，不能把猜中答案当作有据支持。

Ohio保留“Columbus是Ohio城市”和“政府在Statehouse开会”，同时删除capital关系与Statehouse→Columbus城市链接；这是删除多条通向同一所问关系的路径。全60组都未证明逐字仅删一个原子或形式单原子最小性。

逐组证据见[60组S/I验收CSV](2026-10-21-semantic-transfer-v5-acceptance-S-to-I60.csv)，含四段原文引用、删除关系、保留事实及具体理由。

## 十八个旧问题与全部A/B配对

上一轮18个明确问题逐项核对：15项的原具体差异在本轮作者检查中已修复且该配对未再识别具体差异；2项原差异修复，但同配对仍有其他附带事实差异；扑克C描述/规范层次已经对齐，但have to范围仍未定。见[旧18项验收CSV](2026-10-21-semantic-transfer-v5-acceptance-old18-repairs.csv)。这些是修后判断，不是18项独立通过。

检查扩及全部120组A/B：118组有同一确定语义判断，2组双方均unknown。另有13组附带命题或范围注意点如下。107组仅表示本轮未识别具体差异，不能称107组已证明形式等价，也不能用118组同类别声称全部命题等价。

| 底题 | 条件/组数 | 仍需保留的差异 |
| --- | --- | --- |
| stv02 战役名 | K，1组 | A明确总部位于village of Waterloo；B只写总部位置，村名/村落命题未全保留。 |
| stv05 Khet/Quarto | C，1组 | chess-like已补回，但B_C没有A_C的Quarto双人属性。 |
| stv10 Rifleman | I，1组 | A写appeared/featured；B明确as an actor，显式命题精度有差别。 |
| stv12 吞蝇童谣 | S/K/I，3组 | A明确last/final stanza；B写ending/sequence，诗节结构位置的精度不同。 |
| stv13 两大学 | K/C，2组 | research已修复；B这两条件仍缺A保留的Missouri与Colorado州级位置。 |
| stv21 Masters | K，1组 | A的not singles限定those victories；B的rather than singles可能被读为更广范围排除。 |
| stv25 CNN博物馆 | S/K/I，3组 | agency sending的动作主体明示程度，以及参访目的/主题与实际教学发生/效果之间有差别。 |
| stv27 Little Women | K，1组 | B称作者为novelist；A仅author，职业类型属性未完全对齐。 |

所有120组A/B及180组同表达S→K/I/C共300配对均有目标全文引用、逐项判断、token差和理由，见[300配对CSV](2026-10-21-semantic-transfer-v5-acceptance-pairs.csv)。本轮只列问题，没有边看边改稿，没有新增v6或继续扩措辞网格。

## 扑克与全240条判断

扑克C的两个目标如今在相同条件（最后一轮下注结束且至少两人留下）分别写“亮牌比较”与“不亮牌、全部保持隐藏”，在描述层面形成相关、未消解的正反矛盾。因此A_C/B_C由旧unknown修为本轮conflict，confidence为moderate，并明确没有证明完整义务规则。

S/K仍是通常程序描述，题目问have to。若按一般程序解释可支持回答，按严格规则义务解释则缺少义务/例外范围，故A_S/A_K/B_S/B_K四条保留unknown。没有借外部扑克规则强行消歧。

| 分区 | 充分 | 不足 | 冲突 | unknown | 总数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| semantic_train | 48 | 24 | 24 | 0 | 96 |
| semantic_dev | 20 | 12 | 12 | 4 | 48 |
| semantic_eval | 48 | 24 | 24 | 0 | 96 |
| 全部 | 116 | 60 | 60 | 4 | 240 |

相对旧作者判断的6处类别变化全部来自上述扑克解释修订；旧v4的120/60/58/2unknown及其评分不覆盖。这是作者判断更新，不能把差异解释为独立准确率、真实模型变化或修订效果的统计验证。全部逐项判断见[240条验收CSV](2026-10-21-semantic-transfer-v5-acceptance-cells.csv)和[显式判断JSON](2026-10-21-semantic-transfer-v5-acceptance-ratings.json)。

## 风险清单与封存交付

[风险清单](2026-10-21-semantic-transfer-v5-acceptance-risks.json)保留七类：独立审核缺失、扑克义务范围、13组A/B细节、I熟悉线索/语言知识边界、关系投影非单原子证明、来源政策/重叠/小样本、执行器版本及真实GPU路径尚未验证。

封存目录为runs/qwen2.5-3b-semantic-transfer-v5-acceptance-v1，共16个文件，含protocol、显式评分、240行验收表、300配对、60组S/I、旧18项对照、风险、全文清单、322旧路径保存清单、README、seal_manifest及SHA256SUMS。

- `public/input-review-a.zip`与`public/input-review-b.zip`逐字节复制原v5匿名包，各240条，空模板仍全部unreviewed。分别交给两个评审即可；本轮没有实际对外发送。
- `coordinator/v5-acceptance-coordinator.zip`含暴露作者判断、配对/风险、匿名映射、完整输入和来源政策快照，只供协调端保管。独立评审不应接收此协调包或本报告/AGENTS历史。
- ZIP成员排序、时间戳、字节内容及源文件均可重放；封存表示哈希/版本固定，不修改系统文件权限，也不批准未来实验。

实际seal及两次独立进程verify均exit0。只读核验入口：

```sh
sh scripts/run_semantic_transfer_v5_acceptance.sh --stage verify
```

## 实际验证与停止点

本轮实际v5材料verify与intake-v4 verify均exit0；新验收工具6项加旧作者审计5项共11项CPU测试通过，2.206秒。测试覆盖错批次/错引用/缺行、背景改变、正式标签非null、暴露升级、匿名包不变、确定性封存、损坏拒绝、只读缺文件拒绝和旧路径不变；它们不验证语义真值。此前首次新6项1.747秒通过，追加配对全文引用后运行上述最终11项。旧53/120全套未重跑。

另以独立代码重读CSV，240行/300配对/60组S/I/18旧问题、480条单元引用/1200条配对引用均与当前原文一致；两个匿名包各240项且模板全空，封存文件哈希一致。[322旧路径保存清单](2026-10-21-semantic-transfer-v5-acceptance-preserved.json)全部SHA256一致，包括旧材料、评分、来源、执行器、批准标签与门禁。机器记录及全部新产物哈希见[结构化记录](2026-10-21-semantic-transfer-v5-acceptance.json)。

当前停止点明确：作者验收/风险/交付封存已完成，独立标签0、语义覆盖0、90%要求不变、GPUfalse。用户暂缺外部评审渠道的答复持续有效，不反复索要，不使用有历史注入的新上下文替代。后续有实际审核时保留原评分与完整接收上下文，先审计再显式批准；接收工具一致只产生候选。旧study仍绑定v4-r2，以后接v5须另存对应实现/协议，继续L28、最多一次拟合、开发触发和评估锁。当前没有就绪GPU命令。

本轮未修改240输入/问题/背景/分区、未打开380保留题、未加载模型/probe、未前向/生成/训练/干预；原80.67%发布类别结果、no_qualified_baseline及旧行为报告保留原边界。代码与记录保留工作区，未提交推送。
