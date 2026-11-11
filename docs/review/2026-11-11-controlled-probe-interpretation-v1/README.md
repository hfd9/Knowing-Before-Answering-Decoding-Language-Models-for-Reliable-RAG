# 受控探索逐题解释、跨批比较与研究去留

2026-11-11，Asia/Shanghai。本轮以已有材料、作者参照及保存的probe输出做知情复查和重新汇总；复查者已见题目、类别和历史结果，既非新盲评，也不改动封存参照。6个原创虚构底题来自一个相似的单目标、单值模板族，不能视为自然RAG随机样本。

## 判断

**将这条研究线收束为指定冻结读出在已研究材料上的阶段性测量局限，不启动新的确认实验。** 本批新的证据加强了此前对三分类映射不可靠的担忧：12个作者参照为缺证的输入无一读为refuse，6个缺证A/B对无一两端均符合参照；另一方面，S→I的refuse分数和S→C的conflict分数均呈一致方向变化。它补充的是一个人工模板族中的具体观察，不能证明固定读出普遍失效、隐藏状态缺少信息或模型已检测不足却未行动。

下一步如要继续做论文级确认，须先解决未暴露材料及具体用途权利、独立可审计参照和表达关系、应用容差与底题级资源、相对近邻的实质价值；目前这些未落实，不制定执行协议或提供GPU入口。可直接交付本报告与既有综合作为阶段结果。

## 逐项比较和材料复查

[42对完整表](pairs.csv)保留每对的左右输入ID、变化槽位和原文、真实token数、作者参照、读出、三类概率及差值；[生成代码](build_pairs.py)从存档重组并比对原报告，[来源哈希](source-hashes.json)固定输入、状态、报告和作者参照。A/B不是两种问题：每个底题的问题固定，A/B改目标文档措辞；6个C对均改槽1和槽2，12个S/I对均改槽1。下表的Δ均为右端减左端、单位为百分点；每行仅一个底题，两列各含A/B两个相关表达。

| 底题及目标 | S→I：类别 A/B | S→I：Δrefuse A/B | S→C：类别 A/B | S→C：Δconflict A/B |
| --- | --- | --- | --- | --- |
| 01 检查房间 | answer→conflict / conflict→conflict | +1.39 / +0.51 | answer→conflict / conflict→conflict | +53.30 / +46.35 |
| 02 设备模式 | conflict→conflict / answer→conflict | +0.56 / +0.46 | conflict→conflict / answer→conflict | +39.26 / +51.59 |
| 03 渡船目的地 | answer→conflict / answer→answer | +3.01 / +1.25 | answer→conflict / answer→conflict | +53.68 / +63.41 |
| 04 器皿釉面 | answer→answer / answer→conflict | +1.19 / +0.65 | answer→conflict / answer→conflict | +51.45 / +58.53 |
| 05 排练时间 | answer→answer / answer→conflict | +12.62 / +11.42 | answer→conflict / answer→conflict | +48.01 / +53.39 |
| 06 档案存储类别 | conflict→conflict / answer→answer | +0.37 / +2.41 | conflict→conflict / answer→conflict | +35.08 / +56.22 |

12个S→I对中，5个answer→conflict、3个conflict→conflict、4个answer→answer，**0对两端同时符合S=answer、I=refuse的作者映射**。12个S→C对中9个answer→conflict、3个conflict→conflict；9对两端符合作者映射，另3对的S端已判conflict。S/I/C的A/B对两端分别为：均符合3/0/6，一端符合3/0/0，均不符合0/6/0；其中缺证2对稳定为conflict、4对answer与conflict互换。所有分母为每状态6底题或同题12表达对，不将输入看成独立底题。

这次再次查看了六题的问题及五槽和先前作者理由：S第1槽陈述目标值；I第1槽保留同一对象及负责人等信息而移除目标值，第2、4、5槽并未直接写出目标值；C保留S第1槽，在第2槽提供同一目标不同值；第3槽约束同一条件唯一值并说明来源无优先级。判断是基于所给文本的知情作者式阅读，不认证所有可能推断或两表达语义等价；原作者参照的36条判断与引用均保留，不事后修改。第06题的“dry/cold storage”有日常语义可能交叠的风险，但材料第3槽明确规定不同名称代表不同类别；此结论依赖该约定。

可见的混杂是具体而一致的：I普遍将目标值语句替换为对象与负责人同列的语句，不只是去掉一个答案token；C第2槽增加与第1槽高度相似、仅值不同的陈述，并把原无关记录格式句替换掉。S→C增加2–10 token，S→I变化−6至+1 token（其中2/12相等）；A/B无一等token，变化+1至+10。重复句式、目标值、语义、局部词序、长度和位置共同变化。即使两个S→I等token也不意味着token身份、词汇或语义对照已经隔离；既有等token附注实验亦非此处编辑的直接对照。它们都是可检验的混杂线索，不是证明probe使用捷径的因果证据。

两个具体例子显示为什么不能只看一个汇总：底题05的S→I中A/B的refuse分别+12.62/+11.42个百分点，但最终仍为answer/conflict；A的conflict反而−11.47个百分点，B则+15.09。底题06的S→I两端refuse也都上升，但A为conflict→conflict、B为answer→answer；其S的A→B本身从conflict变answer，conflict概率降21.90个百分点，且增加5 token。底题03的S→C在B上conflict增63.41个百分点，为本批该差值最大；它同时新增7 token及相互矛盾的重复陈述。

## 与既有证据并列

| 材料和参照 | 关键观察 | 对本批的增量及限制 |
| --- | --- | --- |
| [迁移240](../2026-11-09-probe-measurement-scope-decision-v1/README.md)：30个已暴露底题，作者参照，I每表达30条 | I的A/B各8/30为refuse；S→I的refuse概率53/60上升，S→C的conflict概率54/60上升；S/K作者参照各2 unknown | 与本批同见方向变化和类别失配，但并非同一分布或独立金标准；未知项保留，不能合并算准确率。 |
| [绑定48](../2026-11-09-probe-measurement-scope-decision-v1/README.md)：12虚构场景，作者构造，I两版本各12条 | I各0/12 refuse，均为answer；S→I的refuse概率24/24上升 | 本批I同样0/12 refuse，但转为4 answer/8 conflict；结果是不同构造下的类分布，不是同一批重复实验。旧批隐藏状态在回答已见后重算。 |
| [等token中性附注](../2026-11-09-probe-neutral-control-results-v1/README.md)：6个已暴露val底题，36单元 | 全部conflict；否定−中性conflict概率差D均值+2.68pp、P +6.56pp | 已表明等长度下措辞/内容仍能伴随分数变化；词汇、语义、位置及格式混杂，不能据此归因本批的状态差异。 |
| [CLI选例连接](../2026-11-09-cli-probe-comparison-v1/README.md)：13迁移底题、26个S/I对，单CLI会话复评 | CLI标为I的26输入中probe 15 answer/2 refuse/9 conflict；作者其中9为ambiguous，CLI与作者分歧不裁决 | 显示另一参照下仍有类别失配，但23个I按既有作答选例，CLI私有上下文未认证；与迁移重叠，不能当总体发生率或独立金标准。 |
| [E1](../2026-11-09-e1-results-assessment/README.md)：12场景、48回答，知情行为评分 | I0/IU狭义E与J各0/12 yes；该批未绑定同批probe | 是不同任务的行为结果，不能与本批prefill拼接为内部检测与行为关系，也不证明等效或安全。 |

共同模式是：在若干有暴露或构造参照下，缺证类别映射不稳或不足，而连续读出可以随编辑改变；冲突类响应也可能出现在作者标为充分或不足的材料中。新批确认该现象还能在六个新构造场景中观察到，未解决其语义来源或总体范围。各批复用、选择和参照性质不同，不相加、不求共同准确率。

## 研究价值和决定

候选问题可表述为：在预先界定的材料分布与可审计参照下，指定旧L28 probe能否同时正确区分充分/缺证/冲突并在保持证据关系的改写下保持类别？以底题为单位分别报告每状态两表达均符合、单端符合、均不符合、unknown及失败；方向性分数为次级描述，不事后换层或阈值。本轮结果对该问题提供探索性反例，不为未来场景设定可靠性阈值。

现有定向近邻核查中，[KBA](../2026-11-09-probe-research-decision-v1/README.md)已有同题三状态及提示稳健性，ContextConflict已有配对冲突probe，Hidden Commitment已有改写及顺序控制；[ESB核查](../2026-11-11-reference-budget-increment-v1/README.md)表明证据充分性梯度和行为评估也有近邻。具体组合尚未被证实新颖，本轮没有新增文献搜索或系统综述。新数据提供有用的局限例子，但没有建立独立参照、确认可行性或相对既有工作的论文级增量；因此不以追加类似6题、扩样、重训或阈值搜索作为默认下一步。

## 核验、边界和状态

生成脚本比较了42个关系对的左右类别、三类概率及作者参照与原报告，逐对重建变化槽并核对问题相同；另用独立短脚本直接从存档输入和状态复核42个唯一对的槽位、token及概率差。`pairs.csv` SHA-256为 `7932a017dc8a27ae4d73c68ec5ab3c7353ed9feeb679c428af90ea2bd9228b1b`。两条计算路径共用既有输入与状态，不构成新的语义评分或对特征来源的独立采集。底题01–06的原始五槽和作者引用见[准备材料](../2026-11-11-new-controlled-exploration-v1/README.md)，技术核验见[运行结果](../2026-11-11-new-controlled-exploration-results-v1/README.md)。

本轮无新样本、模型前向、GPU、拟合、新独立评审或380正文访问。原v1/E1-r1门禁false、正式独立批准0、正式标签null、原拟合预算0；380正文封存，不自动扩样、重训、阈值搜索或patching。必要GPU未来由用户执行。
