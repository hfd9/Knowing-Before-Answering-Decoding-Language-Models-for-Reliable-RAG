# 55条逐主张审查：接收、封存与端点比较

本入口只处理已有材料的评分文件、原文引用和来源声明，使用Python标准库，无需模型、probe或GPU。程序验证结构与记录一致性，不判断主张的语义真假，也不自动批准独立性、正式标签或后续实验。

原两阶段包、空白表与作者复核不回写。本轮准备状态为`pending_no_review_files`，没有实际新评分。

## 当前可以运行的只读检查

```sh
python3 -B scripts/semantic_claim_review_intake.py --stage verify
```

它重放`runs/qwen2.5-3b-semantic-claim-review-intake-v1`的四文件：protocol、接收状态、规范化评分和端点比较。当前四文件只登记55条/82原句的固定范围及缺失评分，没有真实评分或分歧结论。语义Accuracy和总体错误率为null，正式gate与GPU就绪均false。

`--stage prepare`首次冻结输出；相同输入重复执行只检查并保留相同文件。评分文件或代码/口径改变后使用新的接收目录，不覆盖旧准备快照。

## 1. 在副本中填写输入判断

使用原[输入表](review/2026-10-23-semantic-claims-v1/public/input_review_template.json)，保留每个Q001–Q055行。未审行维持`status=unreviewed`且全部评分字段为null；部分完成时同样保留55行，不能删除未审项。

已审行填写：

| 字段 | 要求 |
| --- | --- |
| status | `reviewed`。 |
| target_interpretation | 具体说明所问实体、关系和范围。 |
| answerability | `answerable`、`insufficient`、`conflict`或`ambiguous`。允许独立评审不同于作者的分类。 |
| candidate_answer | 可答时为非空字符串；其他情况可为null。 |
| document_support | 至少一个逐字文档引用，格式见下文。缺失判断也应定位有关事实，并检查全部五文档。 |
| missing_link、ambiguity | 非空文字；无缺口或无已识别歧义时明确说明，不能把空白当已审。 |
| conflicting_propositions | 字符串列表；无冲突用空列表，判冲突时至少两条不同命题，并解释相同实体/关系/范围下为何互斥。程序不自动认证互斥性。 |

填写[上下文暴露表](review/2026-10-23-semantic-claims-v1/public/reviewer_context_template.json)，三份文件的`reviewer_id`必须一致。暴露字段使用true/false，未知不能自动填写false；`exposure_description`记具体来源，`actual_independence_determination`记当前自述，例如“未完成独立上下文审计”。

`prior_outputs_or_probe_results_exposure`指输入判断封存前或指定第二阶段以外已见的输出/probe结果；按流程读取第二阶段指定回答本身不等于此前暴露。`instructions_or_hidden_context_exposure`指系统消息、记忆或隐藏上下文带入的项目历史、作者判断等，不是正常的空白评分说明。程序仅保存这些声明；所有“未暴露”声明仍待实际审计。

## 2. 封存完整输入判断

以下命令示例中的`reviewer_work`是未来实际评审副本所在位置，本轮没有该评分目录，也未运行这些示例命令。

完成55条输入后，将`context.json`的`reviewed_at`填写为带时区时间，执行：

```sh
python3 -B scripts/semantic_claim_review_intake.py --stage seal-input \
  --input-review reviewer_work/input_review.json \
  --context reviewer_work/context.json \
  --input-seal reviewer_work/input_seal.json
```

收据和输入副本放在同一目录，新收据不覆盖已有文件。收据保存输入文件SHA256、实际封存时间和包指纹。将`input_review_sha256`和`sealed_at`分别复制到回答表的`sealed_input_review_sha256`与`sealed_input_review_completed_at`。

封存后保持输入副本不变；如需修订，另存输入版本和新收据，披露已经看过回答。哈希和时间不证明评审此前没看过输出，本入口也不将收据当作独立性认证。

## 3. 填写回答的逐主张判断

使用原[回答表](review/2026-10-23-semantic-claims-v1/public/claim_review_template.json)，保留55个item及每个原始句单元的`unit_id`和`source_span`。原句可能含多个命题；每个已审句的`atomic_claims`改为非空对象列表，一项一项独立判断。

句单元原有`document_support`、`counterevidence`、`missing_link`、`ambiguity`、`judgment`五个汇总字段保持null，评分放入各原子对象，避免一个句级评分掩盖其内部不同主张。

原子对象结构示例（纯合成格式演示，不是55条材料的评分）：

```json
{
  "claim_id": "reviewer_local_c1",
  "claim": "Unit T has code C-1",
  "judgment": "supported",
  "role": "target",
  "output_citation": {"start": 0, "end": 20, "quote": "Unit T has code C-1."},
  "document_support": [
    {"document_index": 1, "start": 0, "end": 20, "quote": "Unit T has code C-1."}
  ],
  "counterevidence": [],
  "missing_link": "No missing premise in this synthetic example.",
  "ambiguity": "Synthetic structure example only."
}
```

实际引文必须来自对应原回答或文档，字符偏移按Unicode字符计数，end不含末位置，不能把示例偏移复制给真实材料。输出引用须落在所属原句范围内；可以用同一原句中的相同片段为不同主张定位，但每项主张ID在该item内必须唯一。

`role`为`target`或`explanation`。判断值为supported、contradicted、unsupported、ambiguous、not_applicable；supported需文档支持引用，contradicted需反向证据引用。所有主张都填写缺失环节与歧义说明；unsupported要具体写明缺少的关系，不能只写占位词。引文匹配仅证明原文存在，不自动证明蕴含、反证或原子拆分完整。

填写item级端点：

- 给出具体目标答案时，`gives_specific_target_answer=true`，目标支持按已填target主张汇总，`withholding_matches_gap=not_applicable`。
- 没给具体目标答案时，目标支持为`not_applicable`，另判断保留未知的依据；原子主张按解释角色记录，不将“不提供代码”误作一个具体目标代码。
- target主张内部一致性汇总按contradicted、unsupported、ambiguous、supported顺序取首个已出现类别。该计算只是检查已填判断是否一致，不是程序新打语义分。
- `explanation_all_claims_supported`为yes、no、ambiguous或not_applicable：解释主张中有unsupported/contradicted则no，否则有ambiguous则ambiguous；没有适用解释主张则not_applicable；其余为yes。
- `full_answer_claim_coverage_confirmed=true`是评审的完整性声明。程序检查每句都有主张，但不能证明所有语义命题都被正确拆分。

完成回答后更新上下文表的`reviewed_at`为本次完成时间，晚于输入封存时间，并如实保留输入先审声明及暴露情况。题意歧义与未审null分开保留。

## 4. 校验与接收实际文件

仅校验、不写接收目录：

```sh
python3 -B scripts/semantic_claim_review_intake.py --stage validate \
  --input-review reviewer_work/input_review.json \
  --claim-review reviewer_work/claim_review.json \
  --context reviewer_work/context.json \
  --input-seal reviewer_work/input_seal.json
```

收据参数可省略，此时只核对回答表声明的输入哈希及时间，报告明确没有收据。输出已审前要求完整55条输入均已审；暂未完成的输出行仍保留原空白状态。

接收并冻结到新目录，后续用相同参数改成`--stage verify`重放：

```sh
python3 -B scripts/semantic_claim_review_intake.py --stage prepare \
  --run-dir runs/qwen2.5-3b-semantic-claim-review-intake-reviewer01-v1 \
  --input-review reviewer_work/input_review.json \
  --claim-review reviewer_work/claim_review.json \
  --context reviewer_work/context.json \
  --input-seal reviewer_work/input_seal.json
```

原评分副本留在接收目录之外。目录必须直接位于runs下并采用本任务前缀，不能写入旧采集目录。完整接收也只是`complete_submission_context_audit_pending`；有暴露的评分照实保存并标识，不冒称独立，也不丢弃其来源。

## 5. 分歧比较与实际裁定

`endpoint_comparison.json`为协调者文件，比较同item的输入判断、是否提供目标答案、目标支持、保留未知依据及解释支持。作者原unknown保持原值，仅在比较列桥接为ambiguous，原评分不改变。未审端点的分歧为null，不当成一致或错误。

不同评审的主张数和拆分方式可能不同，不能按第几条或主张ID自动对齐。每行保留`claim_alignment=manual_required_different_decompositions`和`adjudication=null`，供实际逐主张对照；文件不产生自动共识或金标签。

接收目录包含作者比较内容，不可交给声称未接触作者结果的评审。实际独立性仍需审计真实上下文与来源，实际语义分歧仍需保留原判断后另作裁定。本入口不会写正式标签、模型、拟合预算或实验登记，不自动放行GPU或patching，380题继续封存。
