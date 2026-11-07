# 48条输入复评、三个旧案例与CLI流程证据审查

日期：2026-11-07，Asia/Shanghai。评审者：同一个项目外Codex CLI会话 `SCOPECLI20261107R01`。**实际完成48条输入判断、三个已选旧案例的判断和一份旧CLI流程证据审查；这不是48条新模型回答，也不自动授予正式独立批准。** 当前正式独立批准0、formal_gate=false、gpu_launch_ready=false，拟合预算0、正式标签null、380题封存保持。

## 顺序与隔离证据

先在项目外空临时目录开展候选[上下文自审](input/audit2-response.txt)，未交付材料；评审自述此前未见五类指定项目历史、作者判断、模型结果、协调映射及实际材料，并明确无法认证全部私有上下文。首次尝试因外层沙箱只读文件系统无法初始化而失败，保留[错误](input/audit1-stderr.txt)；之后按权限流程在外层授权执行，未修改全局配置或使用跳过沙箱/审批的选项。工作目录分离和自述不是操作系统级禁止读取项目，也不证明模型错误独立。

2026-11-07 07:31:29 UTC，向通过初步自审的同一会话交付[48条匿名输入](input/input_packet.json)、[空模板](input/review_template.json)及[输入复核任务](input/phase1_task.txt)，没有交付作者结论、条件映射、旧回答或焦点标识。匿名包只去除了原包顶层`draft_unapproved_author_exposed`状态，48条ID、问题和文档完全一致；每题文本本身可能使评审推断结构，不能说条件绝对不可推断。[交付记录](coordinator/phase1_delivery.json)及[准备记录](coordinator/preparation.json)保存SHA及范围。

评审最初因会话内工作区只读，只查看P001–P004，未生成所要求文件；[原始不完整回复](input/phase1-response.txt)与[轨迹](input/phase1-events.jsonl)原样保留。没有改变其权限；同一会话之后按8条一批返回六份JSON，由协调端保存，[第一批](input/batch01-response.txt)至[第六批](input/batch06-response.txt)及各自任务、轨迹和验证均保留。评审自述后续批次可见自己以前的批次判断；它们是**一位模型评审**，不是六位。模型未自行写原拟阅读日志或引用偏移文件，也未自行计算输入包SHA，该SHA由任务提供；[完成声明](input/completion-response.txt)按原文保留。

协调端对六份回复重验后，于07:57:01 UTC封存[48项原始判断](input/input_review_sealed.json)及[收据](input/input_seal.json)，随后才交付旧案例。六批每条问题及五文档均可从工具输出复原，252次引用实例在指定文档逐字匹配；这些验证文本呈现与引用，不证明实际理解、蕴含或独立性。协调端在封存后另生成[Unicode引用偏移](coordinator/input_citation_offsets.json)，252次引用各只有一个匹配位置；这是协调端程序补充，不声称评审自行给出偏移。

## 新48输入的复评结果

评审对目标记录状态给出24条无目标记录、12条有记录支持、12条目标记录冲突；未引入模型回答。在封存后，协调端才连接隐藏映射和作者侧结构表：[目标记录状态及冲突归属比较](coordinator/post_seal_comparison.json)均48/48相符，[目标记录值比较](coordinator/post_seal_target_values.json)48/48相符。12条单目标记录均被评审描述为“记录支持”，不认证世界真值。这里的48/48是**与材料构造预期的端点一致数**，不是自然语义准确率、独立样本泛化结果或正式独立批准。原始评审叙述和含条件的协调比较分开保存，勿向声称未接触条件映射的评审者交付coordinator目录。

## 三个旧发现案例：封存后的新增判断

07:57:20 UTC，在48项输入判断封存之后，向同一评审交付[F001–F003旧原文](focal/phase2_focal_packet.json)，包括三个问题、五文档和**旧回答**，未交付先前作者/CLI判断或编号映射。[新增原始复评](focal/phase2_focal_response.txt)于08:00:43 UTC由协调端[封存](focal/phase2_focal_seal.json)；三个完整输入和回答均可从轨迹重建，16次回答/文档引用实例逐字匹配。

| 原案例 | 新评审：有据保留未知 | 新评审：狭义目标冲突断言 | 先前知情助手的狭义判断 |
| --- | --- | --- | --- |
| Q004 | yes | unknown | unknown |
| Q026 | yes | no | no |
| Q052 | yes | yes | unknown |

三例的新评审均认为较宽冲突表述未受记录支持。Q052的区别在于：新评审认为“两个单位的access codes相关数据冲突”明确涉及目标字段；先前知情助手认为这并不必然明确声称**目标单位该字段本身**存在互斥证据。两种判断与理由并存，不能静默把争议改成一致，也不能仅凭新yes自动通过旧门禁。[封存后比较](coordinator/post_seal_focal_comparison.json)保留双方来源。这三条为事后选定案例，Q004与Q052同底题，不能估计总体发生率或计为新实验样本。

在三例原判和旧流程审计均已保存之后，协调端向同一评审透露了先前助手对Q052的unknown及理由，请它区分两个口径：[知情补充回复](scope-followup/phase4_scope_reconsideration_response.txt)对“冲突涉及目标单位及字段的信息，包括跨单位冲突”判yes；对“明确声称目标单位自身字段/答案有互斥证据”判unknown，说明原来的yes依赖前一口径。原始yes未改写，[补充记录](scope-followup/phase4_scope_reconsideration_seal.json)另存。由于此前已向该评审透露先前unknown及理由，补充回复不是新的盲评、不是另一位评审，也不证明裁定真值；它使分歧的语义边界更明确。回复中“user disclosed”指向CLI会话提交该信息的协调端，不表示项目用户本人给该评审写过指令。

## 旧CLI的流程证据审查

旧案例判断封存之后，08:01:45 UTC向同一候选会话交付旧CLI上下文、两阶段记录和三份归档轨迹；文件来源和SHA见[交付清单](coordinator/phase3_audit_delivery.json)。评审随后在已看过本批48输入和三个旧案例的上下文中形成[七项流程证据判断](process-audit/phase3_audit_response.txt)，包括先前自述的边界、封存早于第二阶段交付的记录、`recorded_at`未定义为实际交付时刻、memory检查发生在事后及归档轨迹不构成完整OS/私有上下文审计。它不能独立核实未交付原始字节的哈希，也不授予正式独立批准。

评审初稿明确只抽看了部分较长命令的文本。协调端先[封存初稿](process-audit/phase3_audit_initial_seal.json)，再请求[补充扫描](process-audit/phase3_audit_supplement_response.txt)：候选报告程序化扫描31个保留命令字符串、29成功/2失败，并明确**未逐字符人工/模型阅读全部命令**，也未审查所有输出或被省略事件。协调端独立复算命令SHA，31/31与此前清单匹配；这仍不能排除间接访问、恢复不可见历史或证明语义真值。两份审计由同一个本次候选会话完成，不能计成两位评审。

## 核验与仍待处理

```sh
python3 -B scripts/verify_explanation_scope_input_review_20261107.py
python3 -B -m unittest discover -s tests -p 'test_verify_explanation_scope_input_review*.py' -v
```

第一条只读核对原始匿名包、六批可见原文与252处引用、协调端偏移、三阶段封存/交付时间、三个旧案例16处引用、封存后比较、旧CLI审计源哈希及31条命令清单；不将一致性当语义真值或独立性认证。第二条测试检查伪造引文、错误文档、缺失完整呈现、重复ID、错包哈希、篡改原回复、交付顺序和修改封存后比较时拒绝。状态、保护来源和实际测试结果见[本轮记录](../../records/2026-11-07-scope-blind-input-review.md)。

候选会话确实进行了新的LLM输入语义复核和旧答案审查，不应说“没有新评分”；这与Qwen实验模型采集是不同活动。旧55作者复核55/155及原CLI复评55/55/172均保留；本次是另一个候选会话的48输入加3旧案例，不是48条新实验回答或新增正式金标签。正式独立性、Q052争议及原门禁的最终采纳决策仍待有来源处理；本轮不自动打开GPU或真实run。
