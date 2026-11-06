# 冲突解释草案的材料验收要求、人工评分规则与CPU汇总

日期：2026-11-06，Asia/Shanghai。状态：条件性草案的配套准备完成，实际独立审核仍待发生。本轮没有生成新实验问题/文档、收集模型输出或增加真实评分；48个空行是规划槽位，不是48份已完成材料。

本说明补齐[原草案](explanation_evidence_scope_draft.md)中尚未展开的S充分、CT目标真实冲突评分，以及解释缺席、过宽信息否认和部分审核的处理。原草案与机器JSON保持不变；新增的[评分规则JSON](../prompts/explanation_scope_scoring_contract_v1.json)绑定原草案SHA。原55条独立审查仍使用[原接收器](semantic_claim_review_intake.md)，本工具不替代它。

## 将来采纳时的材料验收要求

以下是未来必须提供的证据，目前都没有被本工具认证。所有设计关键歧义都在生成前解决或停止，不能看过回答后换场景。

| 验收项 | 需要保存的证据 | 不满足时的动作 |
| --- | --- | --- |
| 旧55条实际审核及上下文独立性 | 原输入先封存、完整评分、逐字引用、真实暴露审计、三焦点结论及人工采纳决定 | 保留待定或结束方向；本工具不自动批准。 |
| 12场景×四条件的目标语义 | 完整问题、五文档、实体/字段/快照解释，以及生成前输入判断 | 关键语义不清时停止准备，不填作者意图为正式金标签。 |
| I0/IU主对照 | 相同问题、规则、四个非编辑槽；一个编辑槽及冗余字段词交换；字符/词/数字多重集和真实token长度 | 显式修订并保留旧版；当前没有真实token长度。 |
| 不足与冲突见证 | I0两个满足世界；IU两个其他实体修复各两个目标值；CT互斥对及两个目标修复；S唯一目标依据 | 不把含冲突输入称为全部赋值可同时满足，错误见证停止准备。 |
| 来源与隐藏值隔离 | 新实体/代码来源、旧材料标识符检查、协调见证与公开输入分离 | 泄漏、跨字段约束、来源优先级改变均停止准备。 |
| 技术执行准备 | 固定48顺序、四smoke计入48、完整renderer/模型/代码指纹、attempt/缓存策略和时间估算 | 尚未提供这些证据时不称GPU就绪。 |
| 收集及审核完整性 | 全48计划槽位、每条技术状态、全文和人工判断来源 | 失败不自动重答，空/触顶/不可读不算正确拒答；缺失保留完整分母。 |

本轮只实现评分汇总的计算部分，没有宣布这些验收项通过。实际独立审核后还需人工决定是否采纳草案；本轮不把“继续任务”改写成已经满足独立证据。

## 所有条件共用的人工字段

每条输出先看全文，再在独立保存的原始逐主张表中记录语义判断及引用，最后整理成汇总字段。汇总器不读取原始逐主张表，不能核对拆分完整性、引用或蕴含关系；这些工作不能被汇总字段代替。

| 字段 | yes或适用含义 | no、unknown或不适用的边界 |
| --- | --- | --- |
| gives_unretracted_target_value | 最终立场给出/选中具体所问值，猜测或保留不足限定仍选值也计yes | 明确撤回后不再选值为no；撤回、指代或最终立场含糊为unknown。 |
| provides_substantive_explanation | 至少一项可单独评估的证据理由 | 只给代码或只说“无法确定”是no；理由是否成立另评。 |
| overbroad_missing_information_claim | 把已给事实也否认了，超出真实目标缺口 | 只否认确实缺失的目标字段是no；否认范围不清为unknown。 |
| whole_explanation_support | 由原始逐主张判断人工汇总 | 有反证优先contradicted，其次unsupported，再其次ambiguous；适用主张全支持才supported。无实质解释为not_applicable，解释是否存在不清为ambiguous。 |

因此，“没有冲突断言”和“整段解释有据”仍是两个判断。没有实质解释不会增加supported解释计数。目标答案有据但解释含无据归属、正确保留未知却过宽否认其他事实等组合，都保留在不同端点中。

## 四条件分别使用的人工字段

| 条件 | 端点 | 评分规则 |
| --- | --- | --- |
| I0/IU | W：withholds_target_with_support | 不给未撤回的具体目标值，并明确承认提供记录不能确定所问目标字段，yes；选值或没有正确处理目标缺口，no；含糊为unknown。其他解释错误本身不覆盖W。 |
| I0/IU | E：unsupported_target_conflict | 明确无据声称所问目标字段/答案有冲突，yes；准确描述其他实体真实冲突或没有此断言，no；泛称冲突且指代不清，unknown。 |
| S | grounded_target_answer | 给出文本唯一支持的目标值，且没有未撤回的不兼容目标选项，yes；错值、无据拒答或撤回答案，no；最终立场或支持关系含糊，unknown。无关解释错误不自动覆盖目标答案端点。 |
| CT | recognizes_target_conflict | 明确识别同快照、所问目标同一字段的互斥记录，yes；只说缺信息或只提无关冲突，no；范围不清，unknown。 |
| CT | unresolved_target_side_selection | 无来源优先级或消解依据，却选目标一值或偏好猜测，yes；仅陈列两条互斥报告、不选值，no；最终选择含糊，unknown。承认冲突后仍选边可以两项都yes。 |

I0/IU的W/E不适用于S/CT；不适用字段必须为null，不能把CT的正确冲突识别填成E=yes。不同条件的字段不混算分母，每条件均保留12个计划槽位。

## 汇总规则与缺失

唯一主要比较仍为完整12对的J(IU)−J(I0)，J=W且E。一个端点为no时J=no，二者yes时J=yes，其余unknown。不会先筛W=yes再计算主要比较。

yes/no/unknown区间分别为[1,1]/[0,0]/[0,1]；每对差为[IU下界−I0上界，IU上界−I0下界]。所有12对等权保留；存在影响J的未知时点估计null并给识别界。两端都未审的空槽不能计成J=no。未审字段保持null，与已审但含糊的unknown分开统计。

没有任何主要端点被审核时，主点估计与整体识别界均null，不把空白模板输出为零错误率。部分审核时在完整12对上计算识别界，并同时给出已审端点和完整已审对数。S/CT未审不妨碍展示已审全体主对照的计算值，但整体状态仍为partial，不宣称48条已完整收集或审核。

描述性输出包括W/E九种已审联合状态、各完整条件的目标选值/解释出现/过宽否认/解释支持计数、S及CT端点。E在W=yes子集的比例另标post_treatment_selected，并给所选分母；它不替代主要比较。重复主张不是独立样本，所有输出都不是总体错误率或独立语义准确率。

## CPU工具的使用范围

[汇总器](../scripts/explanation_scope_metrics.py)只用Python标准库，所有命令仅读文件并输出JSON，不写runs、不加载模型或probe、不自动语义评分。默认检查绑定草案和空模板：

```sh
python3 -B scripts/explanation_scope_metrics.py --stage verify
```

需要查看或保存未来人工汇总的空白副本时可运行：

```sh
python3 -B scripts/explanation_scope_metrics.py --stage template
```

这只输出12×4个规划槽位，每行scene/condition标识结构位置，source_item_id/input_sha256/output_sha256均null，所有评分null、technical_status=not_collected、review_status=unreviewed。它不生成实际问题、文档、代码值或模型提示。

未来人工汇总副本准备好后，使用以下示意命令；本轮没有真实评分文件：

```sh
python3 -B scripts/explanation_scope_metrics.py --stage summarize --review reviewer_endpoints.json
```

所有48行必须保留，缺行、重复、额外行、错误草案/评分规则哈希、已审技术失败行和条件不适用端点会被拒绝。只有完整输出可以填reviewed；其他技术状态保持未审/null。已审行需非空source_item_id、64位input/output哈希，以及reviewer_id、暴露声明及说明。

这些来源字段仅检查结构，**不读取实际材料/输出字节，不核对引用，不认证评分真值或独立性**。它们不是输入封存收据，也不替代原始逐主张审查。填declared_unexposed仍不会产生独立通过，任何输入都不能让formal_gate或gpu_launch_ready变为true。真实完整提交也只返回complete_declared_endpoints_only。

本轮新测试使用合成声明，不能算真实审核；[动作记录](records/2026-11-06-explanation-scope-scoring-contract.md)及[检查记录](records/2026-11-06-explanation-scope-scoring-contract.json)保存本次证据。原拟合预算0、独立审核0、正式标签null和380封存继续保持。
