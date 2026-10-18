# 验证集证据质量与分类行为诊断：用户执行入口

当前v4已由用户完成285正式+9smoke且CPU核验，见[完成与根因审计](records/2026-10-16-validation-evidence-audit-v4-verified.md)。技术通过不证明语义正确，下一步val语义复核，不自动新GPU或导入模型标签。旧设置/命令保留追溯，不重跑完整缓存。

2026-10-13准备完成；2026-10-16用户完成v1的9条GPU smoke，但结构/引用检查0/9未达6/9门槛，入口退出，正式仍0/285。见[smoke核验记录](records/2026-10-16-validation-evidence-audit-smoke-failed.md)。原样重跑会复用缓存再次失败；下文保留冻结入口供追溯，后续新设计须新目录/协议，不降低门槛或事后改解析。
前序三候选均未合格，见[验证完成记录](records/2026-10-12-classification-prompt-validation-verified.md)。
本轮先定位验证集语义质量、可能过度refuse和直接答题的情况，再决定新候选。

## 固定设置与产物边界

- 冻结Qwen2.5-3B-Instruct、GPU0、BF16/SDPA、官方chat template、greedy、单样本、512-token输出预算。
- 完整val：95底题/285证据配置，每条保留五篇完整文档及其顺序。独立技术smoke：3底题/9条。
- 模型输入仅含问题、文档与固定审核指令；不提供发布标签、gold_answer、旧分类输出或旧审核评分。
- 每条输出一个简短JSON草稿：所需事实、缺失事实、判断理由、语义类别和原文引用。
- 严格JSON解析、引用文档编号和逐字子串检查在运行前固定。解析失败、引用不存在、非EOS截断保留unknown；不补默认refuse，不做宽松事后解析。
- smoke至少6/9条通过结构与引用来源检查才启动正式。合法unknown也可通过结构检查；这不证明语义正确或三分类合格。失败时入口停止，查看smoke报告后再决定新设计。
- 复用并核验旧chat8和三候选的val输出，只生成一组285条证据判断草稿。smoke9条不混入正式分母。
- 草稿为同模型辅助诊断，原文引用存在不代表推理、支持关系或矛盾判断正确。草稿不自动成为正式语义标签，不选择新提示词，不修改旧门槛。
- 本入口不读取test实例/预测或自由回答逐题标注，不生成保留确认集预测。原发布标签、模型、自由回答v4和旧实验指纹保持原状。

## 启动和续跑

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
sh scripts/run_validation_evidence_audit_review.sh
```

入口依次生成9条smoke、检查技术门槛，通过后再生成正式285条并保存诊断报告。每次加载模型前检查GPU计算进程，有活动进程时拒绝继续。2026-10-16用户实际GPU推理已完成，但smoke未通过，正式阶段未进入。

中断后原样执行同一命令。逐条原子保存，续跑核验协议、代码/提示/数据/模型、既有对照、提示/输出哈希、输入长度和草稿解析，跳过已保存样本。已全部保存的smoke不会重新加载GPU。失败不删除已完成输出；last_failure.json为历史失败快照，当前状态看progress和实际保存数量。

在另一个终端查看日志（`-F`会等待正式日志创建）：

```sh
tail -F runs/qwen2.5-3b-validation-evidence-audit-v1/launch/smoke.log runs/qwen2.5-3b-validation-evidence-audit-v1/launch/full.log
```

若停止在smoke，查看其`reports/diagnosis.md`、`drafts/predictions.json`及上述smoke.log；不要绕过结构门槛或改旧protocol。新指令或代码需新run_dir。

正式CPU检查最长5370输入tokens，预留512后小于32768；smoke最长4917。预留规划：正式27.3–65.8分钟，smoke3.8–6.9分钟，完整入口可预留约35–75分钟。估算假设每条使用全部512输出tokens、输出速度40–100tokens/秒，并留加载等余量；该速度没有实测，不是运行保证。CPU重复对照校验、宿主竞争和实际输出长度会改变耗时。按照既有超过10分钟任务约定，由用户启动。

## 文件与报告

正式目录：`runs/qwen2.5-3b-validation-evidence-audit-v1/`。
smoke目录：`runs/qwen2.5-3b-validation-evidence-audit-smoke-v1/`。

| 文件 | 用途 |
| --- | --- |
| protocol.json、preflight.json、progress.json | 冻结设置、CPU检查和保存进度 |
| drafts/predictions.json | 原始草稿、解析状态、引用错误、截断与耗时，逐条续跑 |
| smoke_gate.json | smoke结构门槛通过记录，仅smoke目录生成 |
| reports/diagnosis.json、diagnosis.md | 全285分母的草稿语义分布、发布标签对照和四组旧输出诊断计数 |
| reports/diagnostic_queue.csv | 全量队列，含原分类输出、invalid和草稿状态，供复核直接答题等现象 |
| reports/assisted_review.html | 辅助复核：完整文档、草稿、原分类输出；暴露模型判断，不能称盲审 |
| review/public/evidence_blind.html | 仅重新编号的问题和五文档，不含发布标签、旧输出或模型草稿 |
| review/public/ratings_template.csv | 全unknown空表，保持不覆写；复制后填写复核评分 |
| review/coordinator/packet.json | 协调映射与输入哈希，不给独立评审 |

报告的“refuse且草稿判充分”是待复核计数，不能直接称已证实误拒；invalid保留旧解析并显示原始输出，不自动改成answer。未知保留完整分母。程序不会将同模型草稿称为独立金标准，也不会改变三候选的no_qualified_baseline状态。

## 单独记录复核评分

可以先使用盲审页面独立判断，也可以在辅助页面审查草稿，但需按实际方式披露来源。将ratings_template.csv复制为`review/ratings.csv`，填写`semantic_mode`（answer/refuse/conflict/unknown）、reason、reviewer、引用doc_id和逐字quote。每个编号都保留，包括unknown。确定评分必须有理由和评审者；answer至少一条引用，conflict须两篇不同文档引用。程序只检查引用来源和格式，不认证评审是否人类、独立或判断正确；不能把逐字引用检查当语义金标准。

完成或保存部分评分后，单独分析并明确传入评分路径：

```sh
sh scripts/run_validation_evidence_audit.sh --stage analyze \
  --ratings runs/qwen2.5-3b-validation-evidence-audit-v1/review/ratings.csv
```

模型草稿统计与显式复核统计在报告中分开保存，记录评分文件哈希；不会覆盖评分文件或导入到旧自由回答标注。再次分析可覆写本轮派生报告，评分变更前需另存快照，并在记录中披露来源、背景暴露及保留歧义。

仅CPU准备检查或生成完成后重做草稿报告：

```sh
sh scripts/run_validation_evidence_audit.sh --stage check
sh scripts/run_validation_evidence_audit.sh --stage analyze
```

后一个命令未传入--ratings时只报告模型草稿；不会自动加载review/ratings.csv。后续由助手核验生成与报告、复核诊断，再决定预先固定的新候选。
