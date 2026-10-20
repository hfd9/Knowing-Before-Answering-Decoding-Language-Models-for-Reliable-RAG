# 跨表达语义材料：当前v5关系对照修订与CPU交付

当前使用[v5修订记录](records/2026-10-20-semantic-transfer-materials-v5.md)，spec为prompts/semantic_transfer_materials_v5.json，修订声明为prompts/semantic_transfer_control_revision_v1.json，新run为runs/qwen2.5-3b-semantic-transfer-materials-v5。83输入/131片段变化、157原样；54条I重构，问题/背景/槽位/底题/分区与原来源不变。8新CPU44.533秒及实际prepare/verify通过，341–3055tokens、总323081。

```sh
sh scripts/run_semantic_transfer_materials_v5.sh --stage verify
```

评分接收快照为runs/qwen2.5-3b-semantic-transfer-review-intake-v4，须显式--materials-dir指定v5，不改旧接收默认值。两套240新匿名ZIP位于新run的handoff目录，完整性哈希可重放。当前独立评分0/批准标签0/门禁false，不提供GPU阶段。I事实台账与A/B作者修订不是逻辑蕴涵/最小性/独立标签证明；旧study执行器仍绑定v4-r2，须以后另存运行版本。

## 旧v4-r2工具与修订前状态（保留历史）


当前v4全部240作者材料已完成CPU准备/核验，构造覆盖100%，独立语义标签0，未启动GPU。 后续[执行器CPU准备](semantic_transfer_study.md)也已完成，审核门禁仍关闭；材料工具保持CPU专用，执行器另存新run，不改本材料协议。详见[v4来源补充记录](records/2026-10-20-semantic-transfer-source-augmentation.md)。原[v3来源受限复核](records/2026-10-20-semantic-transfer-source-followup.md)和v1/v2保留原样；原来“八题不能补齐”仅适用于不补外部来源的政策。

最新[全量作者侧语义/构造审计](records/2026-10-20-semantic-transfer-author-input-review.md)已另存：120/60/58/2unknown，不是独立金标准。发现27题54条I不是严格单前提删除，18组A/B有注意点；19具体文字候选及整体修订清单尚未应用。v4-r2输入/批准标签/门禁原样，数量覆盖100%不等于构造质量通过。

30题预算240单元，当前30题全部两表达×S/K/I/C完成；训练/开发/评估96/48/96，未完成0。240标签全null，作者稿不是训练金标准。100%构造覆盖满足材料数量条件，但独立语义覆盖0，不满足90%审核要求；GPU仍false。

当前spec为prompts/semantic_transfer_materials_v4.json，最终新run为runs/qwen2.5-3b-semantic-transfer-materials-v4-r2。初版跨进程重叠列表顺序不稳，原样保留；r2仅稳定排序，不改240输入。11短补充来源和显式政策修订为prompts/semantic_transfer_supplemental_sources_v1.json及semantic_transfer_source_augmentation_v1.json，只修八题64缺项；旧176输入和token数不变，30底题与分区/数量/训练预算不变。三新题明确市场亮相/童谣版本/战时作战范围，原始发布问题与来源保留。此版是来源补充的作者对照，不是原始数据原样评测，原来源方案不被追认为通过。

CPU只读核验：

```sh
sh scripts/run_semantic_transfer_materials_v4_replay.sh --stage verify
```

准备已实际完成，通常无需重做；相同版本的prepare只校验/复用相同文件，拒绝覆盖不同内容：

```sh
sh scripts/run_semantic_transfer_materials_v4_replay.sh --stage prepare
```

CLI只有prepare/verify，无GPU阶段。真实tokenizer长度345–3056，240提示总323252tokens；模型权重和probe未加载，GPU/生成/训练均0。最终37相关CPU91.444秒通过（原35项加两个跨进程/稳定排序回归），未重跑全套旧120。

| 新run下文件 | 用途 |
| --- | --- |
| source_catalog.json、source_train_answer30.json | 全部来源片段、源槽位和背景映射；发布gold仅作来源元数据，不自动填补事实 |
| materials/inputs.json | 240草稿问题/五文档；semantic_label=null |
| materials/unavailable_cells.json | 空列表，计划240全部已构造，独立标签未批准 |
| coordinator/author_review.html | 作者全文对照和建议类别，仅供协调端；不要交给独立评审 |
| coordinator/base_audit.json、author_judgments.json | 30题支持依据、54原来源引用+11补充来源引用、480目标引用、未决理由与作者意图 |
| coordinator/edit_provenance.json、pairs.json | 180编辑记录、300预设草稿配对及token差 |
| review_a、review_b | 两套不同匿名排列的输入包、原文HTML、rubric及空模板 |
| handoff/input-review-a.zip、input-review-b.zip | 可分别交付的包，不含协调信息/历史/作者判断 |
| sources/supplemental_source_excerpts.json、coordinator/source_policy_amendment.json | 11外部短来源与明确政策修订，不放进匿名审包 |
| preflight.json、protocol.json | 全部提示哈希/长度、预算、代码/来源/tokenizer绑定 |
| reports/overlap_audit.json、target_source_overlap.json | 原训练背景/来源重叠披露，不当成语义或OOD证据 |
| review_gate.json、progress.json | 明确构造已齐全、语义审核待完成、GPU未就绪 |

独立评审只接收各自ZIP，不接收AGENTS、项目历史、作者稿、probe或其他评审结果。应另存ratings.json，不覆写模板。八题原缺口由显式补充来源修复；这些作者判断仍不称独立语义金标准或已证实错标。

CPU评分接收/对照工具为scripts/semantic_transfer_review_intake.py，当前无评分快照为runs/qwen2.5-3b-semantic-transfer-review-intake-v3。只读核验：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_review_intake.py \
  --materials-dir runs/qwen2.5-3b-semantic-transfer-materials-v4-r2 \
  --run-dir runs/qwen2.5-3b-semantic-transfer-review-intake-v3 --stage verify
```

未来获得两份真实评分时用--review-a、--review-b及新的--run-dir，拒绝错误批次/漏项/假引用/未评模板/声明暴露评分。匹配评分仅形成候选，不自动裁定分歧、不批准标签或解锁GPU；自报独立需实际上下文审计。当前validated_review_files=0、批准语义标签0。

目前没有GPU启动命令。独立标签为0，构造已齐全但语义审核未完成，不能预先宣布可靠性通过。旧40、52/80/50结果不重跑，旧probe保持chat L28，最多一次语义训练的预算不变；380底题继续封存。
