# E1逐主张接收与封存：输入合同

本文件补充[E1-r1协议](explanation_scope_e1_protocol_20261107.md)的**接收格式**，不更改研究设计或采集门禁。接收器仅验证文件来源绑定、字段及逐字引用；它不自动拆主张、判断蕴含、证明完整阅读或评审独立，也不自动作语义裁定。任何分歧或知情转换须保留来源及理由。

## 两个顺序阶段

1. 仅以公开packet和评审者自己的JSON作为输入，先验收评审声明及引用，原字节独占写入封存目录，再写含UTC时间、packet及评审字节SHA的收据。此阶段不读取coordinator、mapping或endpoint模板。需每个完整可评分条目显式标记reviewed或unreviewed，其他技术状态只能unreviewed。封存的不完整文件保留，不覆盖或自动修补。
2. 只有收据与封存原文、同一公开packet匹配后，才读取E1导出的coordinator及其封存收据，以及由转换者明确署名、记录暴露和理由的转换JSON。工具核对48槽原ID/伪ID、目标输入/输出SHA、状态、E1协议和已封存主张ID，再将**人工声明**写入未评分模板并调用原计算器。它不凭主张标签自动推断W/E。转换者可与评审者相同；如其见过映射、作者结果或项目历史必须如实声明，不能说成独立盲评。

程序可验证收据和本地调用次序，但不能证明评审或转换者在封存前未通过其他渠道看到映射，不能认证时钟或私有上下文；原材料48/48可通过全文匹配再识别条件。输入、收据、转换及输出仅作来源记录，不构成语义金标准或正式放行。`null`未审和`unknown`已审分开，空/截断/失败及未生成条目不能评判；48槽及完整12对不变。

## 评审JSON

根字段：`reviewer_id`、`history_exposure`（`unknown`、`declared_exposed`或`declared_unexposed`）、`exposure_description`、`items`。`items`恰好覆盖packet的48个`item_id`，每条为`item_id`、`review_status`（`reviewed`或`unreviewed`）、`full_answer_reviewed`（布尔）、`claims`。

未审的`full_answer_reviewed=false`且`claims=[]`；只有packet中`technical_status=complete`的条目可`reviewed`，须声明`full_answer_reviewed=true`并至少提供一项主张。完整阅读及主张覆盖仅为评审者声明，程序不能证实。每项主张字段：

```json
{
  "claim_id": "C1",
  "claim": "评审者的原子主张表述",
  "role": "target",
  "judgment": "supported",
  "reason": "理由与边界",
  "output_citation": {"start": 0, "end": 5, "quote": "原文片段"},
  "document_support": [{"document_index": 1, "start": 0, "end": 5, "quote": "文档片段"}],
  "counterevidence": []
}
```

示例只示意格式，不是有效评分。`role`为`target`、`explanation`或`other`；`judgment`为`supported`、`unsupported`、`contradicted`、`ambiguous`或`not_applicable`。同题主张ID唯一；输出及文档引用均为Unicode字符的左闭右开偏移，文档槽1–5，quote须与原文完全一致。`supported`需至少一处支持引用，`contradicted`需至少一处反证；`unsupported`可以没有引用但须给理由。程序核对偏移及逐字文本，不判该引用是否真正支持主张。

## 映射后转换JSON

根字段：`converter_id`、`history_exposure`、`exposure_description`、`sealed_review_sha256`、`items`。`items`可以为空或仅列出需转换的已审条目，每条含`item_id`、`claim_ids`（该题封存主张ID的非空子集）、`rationale`和`fields`。`fields`必须列齐原评分合同的全部字段；适用字段按原合同填写，其他条件的字段保持`null`。工具不会推断语义、修正分歧或将摘要判断当独立真值。未转换槽保持未审与null；写入的provenance明确使用转换者的声明，并保留原评审者声明与两者可能不同的身份。

输出包括完整48行endpoint表、原汇总器结果、来源收据及原始转换JSON的字节副本。新输出仅是声明的计算，`formal_gate=false`、`gpu_launch_ready=false`、独立批准0；没有已审主端点时主点和识别界均为null。不得覆盖已存在的结果目录或清除部分文件。

## CPU入口

[接收器](../scripts/explanation_scope_e1_intake.py)不加载tokenizer、模型或GPU。以下为未来文件路径示意，封存和转换输出目录须事先创建为空的私有目录，并放在原运行、E1公开包及协调端导出目录之外；不要将协调端文件交给评审者。E1导出器会拒绝其导出目录中出现这些额外子目录。

```sh
python3 -B scripts/explanation_scope_e1_intake.py seal --packet PUBLIC_PACKET --review REVIEW_JSON --output-dir SEALED_DIR
python3 -B scripts/explanation_scope_e1_intake.py connect --packet PUBLIC_PACKET --sealed-dir SEALED_DIR --coordinator COORDINATOR_JSON --export-seal EXPORT_SEAL_JSON --conversion CONVERSION_JSON --output-dir RESULT_DIR
python3 -B scripts/explanation_scope_e1_intake.py verify --packet PUBLIC_PACKET --sealed-dir SEALED_DIR --coordinator COORDINATOR_JSON --export-seal EXPORT_SEAL_JSON --result-dir RESULT_DIR
```

第一条保存评审JSON原字节及`receipt.json`；第二条先重验封存，再读取映射，保存转换JSON原字节、`endpoints.json`、`summary.json`与`receipt.json`；第三条在私有临时目录重放转换并比对保存结果，不修改原始输入及结果。收据分别绑定packet的实际字节和导出器使用的规范JSON哈希，以及接收器代码、E1协议和代码锁。它们不能认证真实模型输出来源；转包阶段的原始缓存核验与接收器的声明检查必须分开描述。命令中的占位路径不是已创建的评审或真实运行。
