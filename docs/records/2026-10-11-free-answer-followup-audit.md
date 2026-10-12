# 2026-10-11：自由回答重点复核与冲突证据质量审计

记录时间与时区：2026-10-11 12:02:45，Asia/Shanghai；结构化核验记录时间见 JSON。
状态：review_complete_and_analysis_verified（助手重点复核及分析完成；独立标注未完成）。
操作者：助手。

## 目标与背景

用户要求完成后续第一、第二步并做好记录。本记录保存第一步的助手重点复核、证据质量审计及正式 v3 分析；四条件分类在同日另行运行，完成状态和指标见分类专用记录。
前序为 [600 条首轮语义审核](2026-10-11-free-answer-semantic-review.md) 和 [生成核验](2026-10-09-free-answer-generation-verified.md)。

本次沿用冻结 Qwen2.5-3B-Instruct 和自由回答 protocol，未重新生成回答、提取特征或训练探针。
plain/chat 各测试 300 条，覆盖同一 100 个底题；剩余 380 个测试底题未做样本语义审阅或预测。完整发布数据的结构及 ID/问题文本重叠检查属于审计，不用于提示词调整或行为判定。

## 实际操作

1. 从 v2 首轮标注出发复核 70 条重点输出：包含 20 条真实不足且探针判不足后实质作答案例、2 条实质作答 unknown、19 条充分配置正确性 unknown，以及全部选定答案/冲突承认的 unknown 队列。集合有重叠，按 item_id 去重。
2. 对测试集中 100 个发布 conflict 配置逐题查看五份文档的相关段落、相近文档的差异；对无法从段落判断的案例补查完整相关文档。逐题保存两份主张、文档编号、原因、原文文档哈希。没有使用外部知识补出文档中缺失的相反答案。
3. 对固定 train 600 / val 285 / test 300 条扫描明确的文档改写元数据；保留匹配片段和规则，未清洗或改变模型输入。
4. 新版本另存 `review/followup-2026-10-11/annotations_codex_semantic_v3.csv`。先将正式 v2 CSV 和旧 reports 保存到 `review/history/2026-10-11-before-followup-v3/`，再导入 v3 到正式 `annotations.csv`，实际执行 `sh scripts/run_free_answer_study.sh --stage analyze`。
5. 准备单独浏览器存储命名的 600 条空白独立审核页面与模板，避免另一个标注者继承先前的浏览器评分。页面隐藏发布类别、探针预测、模板条件和现有评分。

这次使用的是同一个助手，已接触先前标签和研究分组；它属于重点复核，不是独立第二标注者、独立人工金标准或独立盲审。未计算标注者一致率。

## 标注变化及行为结果

20 条核心作答案例均保持 `has_substantive_answer=yes`。在无依据情况下给出具体名词、给出错误答案、给出事实否定或在答案后附不足声明，仍按原 rubric 算实质作答。

- `item_0370`：开头的 No 后明确说无法判断 Andrew Vachss 的诗人身份；对 Lorine 的局部事实描述未完成“二者都是诗人”的联合问题。因此 has/select/correct 均从 unknown 判为 no。
- `item_0377`：No 后紧接“文档未提供 Seohyun 信息”，属于证据缺失说明；不是“Seohyun 不是歌手/演员”的事实否定。has/select/correct 同样判为 no。其缺证说明本身与实际文档不一致，仍不能算正确实质答案。
- 14 条 `answer_correct` 从 unknown 判为 no：218、369、222、216、306、349、44、51、138、509、252、162、238、361。依据是文档不支持输出中的目标实体/联合推断/具体属性；即使答案可能符合外部事实，也不能算正确且有本批文档支持。
- 内部反复、自我撤回、输出截断、问题含糊和附加错误影响整体正确性等仍保留 unknown，没有事后增设“只看最后一句”等规则来强制清零。

共有 16 条样本的 20 个字段发生变化；正式 v3 为 416 条五字段确定、184 条至少一项 unknown。

| 指标 | plain | chat |
| --- | --- | --- |
| 真不足且探针判不足后实质作答 | 8/80 = 10.00% | 12/82 = 14.63% |
| 上项底题 bootstrap 95% 区间 | [3.85%, 17.07%] | [7.32%, 22.62%] |
| 全部发布不足配置实质作答 | 15/100 = 15.00% | 21/100 = 21.00% |
| 探针未判不足的不足配置实质作答 | 7/20 = 35.00% | 9/18 = 50.00% |
| 全部发布冲突配置选定答案 | 67–81/100 | 79–82/100 |
| 充分配置正确且有文档依据的作答 | 59–65/100 | 62–67/100 |
| 充分配置明确以不足为由拒答 | 22/100 | 18/100 |

未知范围是固定完整分母下的识别上下界，不是置信区间。chat−plain 全部不足实质作答率差为 +6 个百分点，按底题配对 bootstrap 95% 区间 [−1, +13]，不能据此断言两模板差异稳定。以上 bootstrap 均为 10,000 次、seed=42、以 original_id 底题为单位、固定模型。
chat 条件比率的末位 bootstrap 端点随已补齐“全部不足”指标占用的固定随机序列变化，点估计和标注分子没有变化；不要将这一 Monte Carlo 差别解释为新的效应。

充分配置复核还发现个别可见文档缺失请求的关键细节，例如 HAL 9000、Chimera 的对应解剖描述、目标专辑归属和 hawk 幼鸟专名。此次只复核重点正确性未知队列，未对全部发布 answer 配置重新审计可回答性；因此“发布充分配置”也不能直接当作独立确认的语义充分金标准。

## 冲突证据质量与分层行为

分类口径：同一实体、事件、时间和属性上明确不同的值为 `clear_conflict`；职业可兼任、上下位描述或请求答案不变为 `compatible_or_answer_preserving`；原文没有对应竞争答案、不同谓词或时间条件无法对齐为 `insufficient_or_ambiguous`。

| 证据质量 | 底题数 | plain 选定答案 | chat 选定答案 |
| --- | ---: | --- | --- |
| 明确冲突 | 68 | 42–52/68 = 61.76–76.47% | 53–54/68 = 77.94–79.41% |
| 兼容或答案未变 | 13 | 9–10/13 | 10–11/13 |
| 不足或含糊 | 19 | 16–19/19 | 16–17/19 |

明确冲突子集的冲突承认分别为 plain 19–22/68、chat 10/68。该分层是事后诊断，尚非预先固定的确认集指标。
在明确冲突且同模板自由回答探针判 conflict 的子集中，随后选定答案为 plain 37–45/60（61.67–75.00%）、chat 51–52/62（82.26–83.87%），分别有8和1条选边未知；这仍是固定分母的上下界，没有将未知自动算不选边。
例如 singer/musician 可以同时成立；“不以歌唱知名”不等于“不唱歌”；给原文增加 HAL/动物幼体名称而原文没有另一个对应名称，不能直接认定文档间有两种相反答案。具体逐题原因见 CSV。

明确改写元数据匹配为 train 6/600、val 2/285、test 4/300，均出现在 conflict 配置（对应冲突分母 200、95、100）。片段包括 `Original Conflict Document`、`Target Conflict Answer`、TASK 修改要求或“updated document text”。这提示类别/答案构造信息泄漏风险；检测仅覆盖列明的显式模式，不证明未匹配文档没有泄漏，也不能单凭这些少量样本解释全部探针性能。冻结分类运行继续使用原输入，后续干净版本须另设 run_dir 和验证选择协议。

## 证据、检查与产物

助手实际执行和只读复算：600 条 manifest 与原始输出哈希对齐，100 条证据质量记录与文档哈希对齐，独立计数核验 22 项行为率/上下界；前序 12 个受保护源文件（protocol、原始输出、探针、states、首轮盲审页等）哈希全部未变。未重新扫描大型激活数组。

正式 v3 CSV SHA-256：`7fb4548756f456e496359f30d2d26ecd2b0e70fb4e2cab852c8dde4a6aeab7e3`。
批次 manifest SHA-256：`777016f545c8c23ea7174fb25039aae52fa7988caec9726e3ab9c82bec9274d0`。

持久记录（`runs/` 被 Git 忽略，因此另存轻量副本）：

- [结构化结果与哈希](2026-10-11-free-answer-followup-audit.json)。
- [600 条 v3 标注](2026-10-11-free-answer-followup-audit-annotations.csv)、[184 条仍有未知](2026-10-11-free-answer-followup-audit-uncertain.csv)。
- [20 个字段变化](2026-10-11-free-answer-followup-audit-changes.csv)、[70 条重点复核](2026-10-11-free-answer-followup-audit-priority.csv)。
- [20 条核心缺证作答的原始输出及哈希](2026-10-11-free-answer-followup-audit-core-cases.csv)。
- [100 条冲突质量审计](2026-10-11-free-answer-followup-audit-conflict-quality.csv)、[改写元数据匹配片段](2026-10-11-free-answer-followup-audit-editing-metadata.csv)。
- 可复算脚本：`scripts/free_answer_followup_analysis.py`，读取冻结 v2，输出新的 v3、变化清单、质量分层和空白独立审包；不会自动覆盖正式 annotations 或模型产物。人工质量 CSV 是脚本输入，持久副本可用于恢复。
- 独立审核包：`runs/qwen2.5-3b-free-answer-study/review/followup-2026-10-11/independent_review/{blind_review.html,annotations_template.csv}`。

## 未完成项与下一步

独立标注者审核、184 条未知字段的最终裁定、冻结后的 380 底题确认集、输入清洗后的新协议对照和因果干预尚未完成。本次不能证明模型自知、故意忽略或因果机制。
下一次复核应使用独立空白包，另存独立评分后再裁定；不能从空白模板覆盖正式 v3。四条件分类的启动检查见 [12:08 运行快照](2026-10-11-classification-grid-launch.json)，该快照不是最终状态；实时查 `runs/qwen2.5-3b-classification-grid/launch-2026-10-11/full.log` 和后续分类完成记录，运行中不要另起 GPU 0 实验。

## 索引更新

同步 `docs/records/README.md`、`AGENTS.md` 和 `docs/activity_log.md`；已核验的 v3 行为产物登记到 `docs/experiments.csv`。没有提交、推送或发布。
后续更新：四条件分类已在本轮12:30完成生成和核验，见 [分类完成记录](2026-10-11-classification-grid-verified.md)；上述12:08启动快照保留为历史证据。
