# 跨表达语义材料：当前v2 CPU工具与审核入口

当前状态为材料草稿已准备、CPU核验通过、独立审核和覆盖门槛未满足，无新GPU。详见[2026-10-20准备记录](records/2026-10-20-semantic-transfer-materials-preparation.md)。冻结设计仍为[semantic_transfer_validation.md](semantic_transfer_validation.md)，不重抽源底题或放宽通过门槛。

30题预算240单元，当前21题168作者草稿、9题72未完成。训练/开发/评估分别72/40/56草稿，未完成24/8/40；所有计划单元保留在统计中。每题两表达×S一致充分/K兼容充分/I缺必要前提/C真实互斥，语义标签全null、独立评审0。70%构造覆盖不是语义覆盖，不能达到原90%覆盖通过要求。作者稿不是可用于训练的干净标签。

当前作者spec为prompts/semantic_transfer_materials_v2.json；新run为runs/qwen2.5-3b-semantic-transfer-materials-v2。v1在生成前作者复核后被v2取代，保留原样；v2修正Luoding缺证稿残留Yunfu位置，以及UHI的最小预期答案注释。

CPU只读核验：

```sh
sh scripts/run_semantic_transfer_materials_v2.sh --stage verify
```

准备已实际完成，通常无需重做；相同版本的prepare只校验/复用相同文件，拒绝覆盖不同内容：

```sh
sh scripts/run_semantic_transfer_materials_v2.sh --stage prepare
```

CLI只有prepare/verify，无GPU阶段。真实tokenizer长度345–3056，168提示总206362tokens；模型权重和probe未加载，GPU/生成/训练均0。新增12材料测试加旧复核设计10项共22通过，28.987秒，未重跑全套旧120。

| 新run下文件 | 用途 |
| --- | --- |
| source_catalog.json、source_train_answer30.json | 全部来源片段、源槽位和背景映射；发布gold仅作来源元数据，不自动填补事实 |
| materials/inputs.json | 168草稿问题/五文档；semantic_label=null |
| materials/unavailable_cells.json | 72未完成计划单元及理由，不删除分母 |
| coordinator/author_review.html | 作者全文对照和建议类别，仅供协调端；不要交给独立评审 |
| coordinator/base_audit.json、author_judgments.json | 30题支持依据、53来源引用、336目标引用、未决理由与作者意图 |
| coordinator/edit_provenance.json、pairs.json | 126编辑记录、210预设草稿配对及token差 |
| review_a、review_b | 两套不同匿名排列的输入包、原文HTML、rubric及空模板 |
| handoff/input-review-a.zip、input-review-b.zip | 可分别交付的包，不含协调信息/历史/作者判断 |
| preflight.json、protocol.json | 全部提示哈希/长度、预算、代码/来源/tokenizer绑定 |
| reports/overlap_audit.json、target_source_overlap.json | 原训练背景/来源重叠披露，不当成语义或OOD证据 |
| review_gate.json、progress.json | 明确审核待完成、覆盖不足、GPU未就绪 |

独立评审只接收各自ZIP，不接收AGENTS、项目历史、作者稿、probe或其他评审结果。应另存ratings.json，不覆写模板。原9题未决项仍需单独处理；对这些原题的保守准备判断不称独立语义金标准或已证实错标。

目前没有GPU启动命令。独立标签为0，构造覆盖不足，任何高分也不能被追认为通过冻结覆盖门槛。旧40、52/80/50结果不重跑，旧probe保持chat L28，最多一次语义训练的预算不变；380底题继续封存。
