# 冻结 probe 的证据状态测量：阶段性研究报告

日期：2026-11-11（Asia/Shanghai）

性质：既有探索结果的整合；不是独立确认、自然任务准确率评估或新的实验协议。

## 摘要

本项目检查一个冻结的生成前 probe 能否把给定文档的证据状态读为“充分、缺证、冲突”。在既有迁移、受控材料及选例复评中，一些证据编辑伴随相应类别的连续分数上升，但固定三分类读出仍经常与知情作者参照或CLI复评不一致。最近一批6个原创虚构底题中，12个作者标为缺证的输入没有一个读为 `refuse`，12个作者标为冲突的输入均读为 `conflict`；缺证与冲突变化也分别伴随相应分数上升。表达稳定并不保证两端符合参照。

这些结果**不足以支持将该固定读出作为可靠的三状态语义测量，也不足以支持“模型已可靠检测不足却没有行动”**。结果同样不能证明隐藏状态没有相关信息，也不能断定模型依赖语义或表面构造中的某一种。不同批次的作者判断、CLI判断、输入构造及行为评分有不同暴露、重叠和选择方式，不应合并成一个独立准确率。

当前研究决定是以指定配置和已研究材料上的测量局限作为阶段成果，暂停确认实验及论文级创新宣称。未来是否继续取决于可审计参照、合法且未暴露的材料范围、用途容差及资源，以及相对已有研究的增量能否成立。

## 1. 问题、配置与参照

研究对象固定为本项目的 **Qwen2.5-3B-Instruct、自由回答 P0 chat 提示、末提示 token、零基第28层、原标准化线性分类器及其原 sigmoid 校准后的三类 argmax**。模型生成时不接收该 probe 的反馈。`answer`、`refuse`、`conflict` 在本报告中分别与充分、缺证、冲突作描述性映射；尤其 `refuse` 是旧分类器类别名称，不表示本次实际生成了拒答。

原 chat L28 对发布构造类别的诊断为 **233/300（77.67%）**；曾出现的80.67%属于另一 L24 分类提示路由器，不能混用。发布构造类别诊断不等于独立语义金标准下的新分布准确率。具体配置、原始来源和定向文献比较见[研究去留报告](../2026-11-09-probe-research-decision-v1/README.md)。

材料中的 S 表示作者预期支持目标答案，I 表示目标缺证，C 表示同一目标的证据冲突；部分旧迁移材料另有 K。作者参照来自了解项目与部分历史结果的作者或助手；CLI是实际发生的一次复评，但完整私有上下文和错误独立性无法认证。各参照的技术可追溯性不能自动认证语义正确或独立性。

## 2. 探针结果：按批次分别报告

| 材料、分母及参照 | 结果 | 主要限制 |
| --- | --- | --- |
| [原发布构造类别诊断](../2026-11-09-probe-research-decision-v1/README.md)：300条、发布构造类别 | chat L28 为233/300（77.67%） | 非本报告新材料的语义准确率；不能与另一 L24 的80.67%混同。 |
| [跨表达迁移](../2026-11-09-probe-measurement-scope-decision-v1/README.md)：30个已暴露底题×两表达×S/K/I/C，240输入；知情作者参照 | I的A/B各8/30读 `refuse`；7/30底题两表达均为`refuse`。S→I的`refuse`概率53/60上升，S→C的`conflict`概率54/60上升 | 每题贡献多个相关输入；S/K作者参照各有2个unknown；表达关系与作者语义判断非独立认证。 |
| [绑定48](../2026-11-09-probe-measurement-scope-decision-v1/README.md)：12个虚构场景×S/I×两版本；作者构造参照 | I两个版本各0/12读`refuse`，均读`answer`；S→I的`refuse`概率24/24上升 | probe状态在回答已见后重算；不是E1同批，也不是独立语义准确率。 |
| [等 token 中性附注](../2026-11-09-probe-neutral-control-results-v1/README.md)：6个已暴露val底题×两表达×三条件，36单元；24旧端点、12新端点 | 全36读`conflict`；否定−中性`conflict`概率差均值D为+2.68、P为+6.56个百分点 | 长度相同不等于token身份、位置、措辞或语义相同；不能单独归因否定词。 |
| [CLI选例连接](../2026-11-09-cli-probe-comparison-v1/README.md)：13个迁移底题、26个同表达S/I对，52输入；一次CLI复评 | CLI判为S的26条，probe为13 answer/0 refuse/13 conflict；CLI判为I的26条为15/2/9；26对仅1对两端符合描述性映射 | 23个I按原有作答选择；作者55复评对其中9个I保留ambiguous，与CLI分歧不裁决。2个refuse来自同一底题；与迁移批次重叠。 |
| [新受控探索](../2026-11-11-new-controlled-exploration-results-v1/README.md)：6个原创虚构底题×S/I/C×两表达，36输入；知情作者参照 | S为9 answer/0 refuse/3 conflict；I为4/0/8；C为0/0/12。S→I的refuse概率12/12上升、均值+2.99个百分点；S→C的conflict概率12/12上升、均值+50.86个百分点 | 6底题均为相似的单目标单值构造；词汇、长度、重复及语义变化混杂，不能把12个表达对当独立底题。 |

这些批次不能求和为共同样本数：CLI选例来自迁移材料，旧材料还有底题复用、训练/验证暴露及不同时间提取的状态。连续概率是冻结读出的分数，不是已在目标分布上验证的语义置信度。

新受控探索中，S→I的12对为5个`answer→conflict`、3个`conflict→conflict`、4个`answer→answer`，没有一对两端均符合作者映射；S→C有9个`answer→conflict`及3个`conflict→conflict`。I的6个A/B对无一两端均符合参照，其中2对稳定为`conflict`。[逐题解释及42对明细](../2026-11-11-controlled-probe-interpretation-v1/README.md)保留原文、概率和编辑差异。

该新批次所有S→I编辑替换文档槽1，所有S→C编辑替换槽2：后者新增与槽1高度相似但目标值不同的句子，并增加2–10 token。因而语义状态、词汇、重复、长度和位置共同变化；这些是需要保留的混杂线索，而非已证实的因果机制。

## 3. E1 行为实验单列

[E1用户版](../2026-11-09-e1-results-assessment/README.md)为12个虚构场景×S/I0/IU/CT共48条回答；评分者已见历史和条件，v2对4条先答后表示不确定的最终立场保守改为unknown，原判保留。

对各12条I0和IU，狭义 E（无据断言**目标字段自身**存在互斥证据）均为0 yes/12 no/0 unknown；J（W且E）也均为no。W（有据保留目标未知）的I0为3 yes/5 no/4 unknown，IU为5 yes/4 no/3 unknown。这里“0 yes”是本批已审核端点的有限观察，不是等效证明或总体安全保证。

E1协议未采隐藏状态；对现场run及所检查的指纹和文件类型未发现可绑定的同批probe结果，该检索不排除其他位置或无指纹产物。旧绑定48属于另一批材料。因此不能把E1行为与另一批probe读出拼接，推断模型已检测缺证却不遵循。完整端点、12对及引用见[E1结果与证据](../2026-11-09-e1-results-assessment/README.md)。

## 4. 解释边界与研究价值

本项目已观察到，在特定模型、模板、probe及所见材料下，类别失配和方向性分数响应可以同时出现。不能由此推广到其他模型或自然RAG总体；也不能据固定读出失配断言所有层、其他读出或隐藏状态都没有信息。现有编辑尚不能隔离语义、文档内容、词序、长度及构造痕迹。

既有[定向近邻比较](../2026-11-09-probe-research-decision-v1/README.md)显示，KBA已有同题三状态及提示稳健性，ContextConflict已有配对冲突probe，Hidden Commitment已有改写和顺序控制；[ESB核查](../2026-11-11-reference-budget-increment-v1/README.md)还发现证据充分性梯度的行为研究。具体组合未被证实新颖；既有检索并非系统综述，本次整理没有新增文献搜索。

因此，本报告适合用于项目内部交接、研究决策及带限制的阶段结果陈述，不应将其写成独立确认准确率、总体失败率、行为机制证明或已确立的论文创新。未来若另立研究，需先界定可审计的状态与表达参照、保留unknown、底题级隔离、合法材料范围与碰撞处置、预定用途容差及预算，再判断与近邻的实质差异。

## 5. 可追溯材料及复核入口

| 对象 | 可直接查阅的证据 | 既有核验范围 |
| --- | --- | --- |
| 迁移及绑定 | [分类汇总](../2026-11-09-probe-measurement-scope-decision-v1/measurement-summary.csv)、[配对明细](../2026-11-09-probe-measurement-scope-decision-v1/paired-items.csv) | 旧缓存及配对重排；参照有历史暴露，记录见[范围决定](../2026-11-09-probe-measurement-scope-decision-v1/README.md)。 |
| 等 token | [36单元](../2026-11-09-probe-neutral-control-results-v1/cells.csv)、[12对](../2026-11-09-probe-neutral-control-results-v1/pairs.csv)、[结果与复核](../2026-11-09-probe-neutral-control-results-v1/README.md) | 13条新记录/attempt、单条旧桥接、输入及读出复算；单条桥接和缺完整终端日志的限制保留。 |
| CLI | [52行连接](../2026-11-09-cli-probe-comparison-v1/linked.csv)、[26对](../2026-11-09-cli-probe-comparison-v1/pairs.csv)、[3条排除](../2026-11-09-cli-probe-comparison-v1/excluded.csv) | 输入、提示、token和特征身份连接及58份来源哈希；技术连接不认证评审独立性。 |
| 新受控探索 | [36输入及桥接](../2026-11-11-new-controlled-exploration-results-v1/source/materials/inputs.json)、[37记录](../2026-11-11-new-controlled-exploration-results-v1/source/states.json)、[42对](../2026-11-11-controlled-probe-interpretation-v1/pairs.csv)、[复核](../2026-11-11-new-controlled-exploration-results-v1/audit.json) | 37 attempt/特征、78份现场与归档来源、冻结读出和单旧输入桥接；参照非独立。 |
| E1 | [v2汇总](../2026-11-07-e1-user-results-v1/analysis-v2/summary.json)、[48行](../2026-11-07-e1-user-results-v1/tables/items-v2.csv)、[12对和引用](../2026-11-09-e1-results-assessment/pairs-evidence.md) | 56份现场/归档来源、48个attempt、输出解码、引用和配对重放；评分是知情判断。 |

各链接指向既有材料。本轮[报告核验脚本](verify_report.py)检查相对链接、来源哈希及各批部分关键计数，结果见[审计](audit.json)；这不是对全部历史指标或语义的复核，也没有重新运行模型或评审。对于具备原本地环境、现场run、旧probe和旧桥接来源的项目副本，新受控探索可执行如下CPU核验；它读取现场及归档并重算读出，不进行模型前向：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B docs/review/2026-11-11-new-controlled-exploration-results-v1/verify_results.py
```

上述脚本依赖现场run及旧probe，**仅Git归档并不能保证另一台机器可直接运行**；此前冻结运行器verify还依赖本机模型和冻结文件，详情见[运行核验](../2026-11-11-new-controlled-exploration-results-v1/README.md)。其他批次的已有检查入口与依赖分别记录在上表链接中。哈希和复算可检查所存证据的一致性，不能认证语义、评审独立性或设备全过程独占。

## 6. 当前状态

FaithEval确认分支暂停：来源具体用途、五文档语义参照和380封存题内容碰撞仍未闭合；此前主要文档聚合复算通过不等于完整独立验证或无碰撞，见[四步核查](../../records/2026-11-11-faitheval-four-step.md)。原v1/E1-r1门禁false、正式独立批准0、正式标签null、原拟合预算0，380题正文继续封存。不自动扩样、重训、阈值搜索或patching；未来必要GPU由用户执行。新受控探索已完成，不需重跑。
