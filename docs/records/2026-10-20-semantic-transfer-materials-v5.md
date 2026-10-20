# 2026-10-20：v5关系对照修订、全240材料CPU准备与核验完成

状态：v5_author_control_repairs_prepared_verified / independent_semantic_review_pending / no_GPU。

用户要求直接开始修订。本轮根据[上一轮240条作者侧审计](2026-10-20-semantic-transfer-author-input-review.md)，将27题54条I重构、扑克C模态对齐与A/B附带事实修复合并成一批v5。旧v4-r2、旧评分与候选不覆盖；不是继续增加措辞候选或按probe输出调输入。

本批仍为30个原train底题、12/6/12分区、每题A/B×S/K/I/C、240条作者受控材料。问题、背景原文/重复/次序、槽位、底题和分区逐项保持。沿用原54条发布来源引用与11短补充来源，没有新增外部来源或缩窄问题。它是来源可追溯的作者控制材料，不能称发布数据原样重测。

## 实际修改范围

| 项目 | 数量 |
| --- | ---: |
| 全批材料 | 240 |
| 输入发生变化 | 83 |
| 输入逐字节保留 | 157 |
| 旧→新目标文档片段 | 131 |
| I输入重构 | 54，来自27底题 |
| 原三题I输入保留 | 6 |
| 其他S/K/C输入调整 | 29 |

按条件，改动S11、K10、I54、C8；对应目标片段13/11/99/8。修订清单与新spec严格互相核对，不接受未列入的改题、改源引用或额外目标事实。每条变体仍留在原分区，全部semantic_label仍为null。

显式数据为prompts/semantic_transfer_materials_v5.json和prompts/semantic_transfer_control_revision_v1.json。修订声明保存父spec/材料协议、旧审计/候选与冻结设计哈希，列出每段before/after、文档槽、哈希、元说明变化、S/I保留事实及尚待复核的风险。新CPU包装复用隔离加载的不变原构建器，未修改任何已绑定旧run的实现。

## I如何重构

不再把新的百科事实、人数、日期、亚军、翻唱或例句领域填进I。以对应表达的S为依据，保留已有非答案属性，删除通向问题答案的关系；需要补成完整句子时，只使用S已蕴涵的身份、上下文或存在性弱化表述，并保留作者解释和S逐字见证。

| 底题/类型 | v5处理 |
| --- | --- |
| RuPaul第四季 | 保留2012、Sharon Needles与Pittsburgh；去掉她与冠军的关系。不因名字能猜对就把它当已有获胜依据。 |
| Sorry! | 保留Pachisi依据和Barbarossa完整类型，只去掉Sorry的board-game类别；不再新加人数/年龄。 |
| Khet | 保留chess-like、lasers、abstract strategy和Quarto完整类型，只去掉Khet的board-game类别；不再新加Egyptian/mirrored属性。 |
| 两所大学 | 保留WashU的Missouri/USA及Colorado大学的Colorado位置，只去掉后者明确的USA国家桥接；不新加四个公立校区。不能用外部地理知识自动补桥。 |
| 热岛 | 保留城乡温差、术语、夜间和弱风描述，只去掉地表改变机制；A/B的usually/most频率、程度词也对齐。 |
| Old Order Amish | 保留private homes及alternate weeks频率，只去掉Sunday；不新加sermons/prayer/hymns。泛指多数基督徒Sunday仍不是指定社群的日程。 |
| 原唱 | 保留歌词→Last Kiss及1961原版存在，只去掉原唱者；不在I新加Pearl Jam1998翻唱。 |
| Ohio | 保留Columbus是Ohio城市及政府在Statehouse开会；同时去掉capital关系和政府会址与Columbus的城市链接，防止间接支持仍残留。 |
| 计数/日期题 | 保留原S已有的节目、记录、播出区间或商业使用上下文，只删所问值；不填入原S没有的首播、主持人、总冠军数或其他日期。 |

原Luoding/Dingzhou、Korean War作战区间与CNN培训博物馆的六条I不变。全60条I都有独立保存的关系/保留事实台账，含固定问题、匹配S原文、I残余原文、来源解释与数字子集检查。

**这些是同一背景暴露作者的删除/投影构造，不是独立的逻辑蕴涵证明，也不是“逐字仅删除一个词”或“形式逻辑最小单原子编辑”已成立。** 例如Ohio须删除多处通向同一问题关系的支持路径；仅删capital词而保留政府会址城市，可能仍充分。所有台账的independent_entailment_verified和literal_or_formal_single_atom_minimality_proved均为false。不能用程序计数把它们改成通过。

## A/B与扑克修复

上一轮18组A/B注意点均有对应输入改动：补回chess-like、38th、research、fresh和术语等属性，去掉仅B新增的出生名、plasticine与rice-based sushi对比；以新I整体重构替代局部I补丁，消除亚军四盘、词义例句和novel等新增/指代差异。

逐项核对又修正了此前未完全展开的差异：B海啸补回earthquake事件范围；B Mont Saint-Jean补回French用名；B Rifleman补回television-series类型；B Ohio S补回政府开会功能后才在匹配I保留该功能；B Amish补回private homes；Hula B使用与A相同的commercial-use关系，避免把商业使用自动改为本公司销售。这些在同一个v5修订声明中列明，发生在任何新probe输出之前。

扑克C的正反两边现在都是同一条件下的一般程序描述：正面亮牌比较，反面不亮牌、保持隐藏；不再混用实际行为描述与must not/prohibited规范。扑克I也去掉showdown，因为该词命名所问的亮牌事件，可能本身就是答案线索，不能当作无关属性保留。

问题仍是原来的have to，正面证据仍为通常程序描述，是否足以支持严格义务仍需新评审判断。Khet的chess-like、Sorry的Pachisi以及Colorado地名也作为显式保留线索交评审，不能靠作者意图保证I标签。本轮只报告已实施修订，不宣称18组已获独立语义通过，旧v4两条扑克unknown原记录不动。

## CPU实现、实际检查及交付

新增scripts/semantic_transfer_materials_v5.py及run_semantic_transfer_materials_v5.sh，只有prepare/verify阶段；不提供推理、拟合、校准或GPU阶段。默认输出runs/qwen2.5-3b-semantic-transfer-materials-v5。

```sh
sh scripts/run_semantic_transfer_materials_v5.sh --stage prepare
sh scripts/run_semantic_transfer_materials_v5.sh --stage verify
```

实际均exit0，两次为独立进程。真实tokenizer逐项检查240输入，341–3055tokens，总323081；比v4-r2总输入少171tokens。最大加128为3183/32768，无裁剪。预算仍最多240回答、30720输出tokens；本轮未加载模型或probe，前向/生成/训练均0。

新8项CPU测试在最终版本通过，44.533秒：父输入按修订表独立重建240行、未列入变更/改题/假引文拒绝、保留原名字/属性与去掉新事实的内容约束、扑克/weekday修复、台账不自动证明语义、真实tokenizer/ZIP/接收/禁止模型加载、同表达S/I见证一致性、两个新进程不同hash seed严格重放。测试证明流程与声明约束，不证明语义标签正确。旧53/120全套未重跑，不相加。

实际额外从冻结父输入直接应用131段改动，与新构建240行完全相同；全部300配对的token差与分区重算一致。131段旧→新字符偏移另存，480目标引用、原54来源引用及11补充来源的引用关联/哈希校验通过。背景仍83去重全文，30份与旧probe训练见过，T023跨train/eval、T092跨dev/eval；原引用来源34份中8份见过，11外部短来源单列，不能称文档全新或OOD。

两套新240匿名全文包、HTML、空模板与ZIP已生成，各自使用新排列种子；包内仅有packet/rubric/template/HTML/README/checksums，无协调标签、原ID、分区、probe、回答或项目历史。ZIP固定时间和成员顺序，可逐字节重放。30材料文件加4评分接收快照保持独立版本。

接收仍使用不变semantic_transfer_review_intake.py，显式参数如下：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_review_intake.py --stage verify \
  --materials-dir runs/qwen2.5-3b-semantic-transfer-materials-v5 \
  --run-dir runs/qwen2.5-3b-semantic-transfer-review-intake-v4
```

新接收目录实际prepare/verify均exit0，评分/候选/批准标签0。它只给匹配候选，不批准训练。两套匿名包不等于已经有两次独立评分；当前助手的事实台账也不满足历史独立门槛。

## 持久记录与当前停止点

- [结构化核验记录](2026-10-20-semantic-transfer-materials-v5.json)：实际计数/测试、协议、来源与产物哈希、保留状态。
- [240单元CSV](2026-10-20-semantic-transfer-materials-v5-cells.csv)：逐项是否改动及新旧token差。
- [300配对CSV](2026-10-20-semantic-transfer-materials-v5-pairs.csv)：新旧配对token差，probe字段为空。
- [60条I关系台账CSV](2026-10-20-semantic-transfer-materials-v5-I-ledgers.csv)：匹配S、I、保留事实与解释，明确不是独立标签。
- [131段编辑偏移](2026-10-20-semantic-transfer-materials-v5-edit-provenance.json)：逐项可重建旧→新文字修改。

构造覆盖240/240=100%，独立语义覆盖0，原90%要求不变，gate=false。旧v4-r2材料/评分、原80.67%发布类别结果、no_qualified_baseline和380保留题都不变。当前原study执行器继续绑定v4-r2，不能覆盖其实现/准备目录来消化v5；以后有实际审核标签时须另存对应运行实现和协议。

本轮材料修订和CPU交付已完成，未声称测量可靠性已验证。之后的实质条件是实际独立输入审核及接收上下文审计；用户暂无外部渠道的答复持续有效，不反复索要，不再以被AGENTS注入的新上下文替代，不自动训练/启动GPU。代码与记录在工作区，未提交推送。
