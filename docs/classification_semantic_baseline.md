# 新语义规则分类基线：用户启动与固定协议

2026-10-18当前状态：用户已完成570正式+18smoke，助手完整重放协议/缓存/提示/token/EOS/指标及三组bootstrap通过，仍no_qualified_baseline，无需重跑GPU。见[核验与失败诊断](records/2026-10-18-classification-semantic-baseline-verified.md)及[JSON](records/2026-10-18-classification-semantic-baseline-verified.json)。下文保留10月16日准备时设置与启动说明，准备时0输出/估时不是当前状态。

2026-10-16代码和CPU检查准备。模型仍为冻结的本地Qwen2.5-3B-Instruct，BF16、SDPA、GPU 0。本轮只在固定验证集上比较两个候选，旧实验及确认集不改。

## 启动与续跑

项目根目录执行：

```sh
sh scripts/run_classification_semantic_baseline_review.sh
```

顺序执行两组候选各9条技术smoke，共18条；每组都需9/9完整合法，才启动两组各285条正式验证，共570条。smoke不按语义分数选候选。技术门槛属于本次新三分类协议，未修改旧证据诊断6/9门槛。

完整顺序任务保守预留**10–30分钟**，有GPU争用需另加等待；新设置尚未实测。历史旧chat8验证285条纯生成94.63秒，不能把它直接当新设置耗时。代码规划正式约6.7–18.6分钟，smoke约2.2–6.4分钟；用户启动并负责保持GPU空闲。GPU有计算进程时入口拒绝加载并在错误日志列出PID/进程/显存，不会停止其他任务。

查看进度：

```sh
tail -f runs/qwen2.5-3b-classification-semantic-v1/launch/smoke.log
```

正式启动后：

```sh
tail -f runs/qwen2.5-3b-classification-semantic-v1/launch/full.log
```

中断后原样重跑第一条入口，每条完成后已原子保存，来源、代码、提示和缓存验证通过才跳过已有条目。两组使用同一模型实例顺序生成；入口同时受run lock与GPU空闲检查保护。配置/代码改变必须新目录，不能改protocol哈希绕过。

默认正式目录：`runs/qwen2.5-3b-classification-semantic-v1/`。
独立smoke目录：`runs/qwen2.5-3b-classification-semantic-smoke-v1/`。
准备时两目录已完成CPU预检查，状态为prepared_not_started，各0条新预测。

## 候选、题意约定与解码

| 候选 | 内容 |
| --- | --- |
| semantic_rules | 必要前提覆盖、目标实体/关系绑定、兼容属性与上下位类别、同实体/时间/属性的互斥、题目事件日期与文档时点规则 |
| semantic_examples | 完全相同规则，加7个虚构说明例子；无验证原题/姓名/答案/数值，不来自诊断测试或确认集 |

提示词在`prompts/classification_semantic_v1.json`。两组均官方原生chat、五篇完整原文原顺序，无片段索引、自由分析、原文裁剪或标签/gold_answer泄漏。train仅用于固定来源/分离检查，推理只用val；不读取真实test输入/预测，不训练模型或探针。

解码为三标签token trie上的greedy，输出answer/refuse/conflict之一并以EOS结束。预算8tokens，真实本地tokenizer中最长标签加EOS仅3tokens。此为逐token受约束greedy，不是三个完整标签序列的归一化似然，不输出置信度。格式通过率由约束直接保证的部分不能解释为语义能力改善。完整标签但缺EOS也标为技术invalid，留在指标分母中，不自动修复或重试。

题意约定提前写入提示与协议：题目未明确要求当前状态时可按材料的显式时点、范围作完整限定回答；明确要求另一时点而证据不能覆盖则不足。起源/提案/制造日期不自动等同开放或开始可用日期。不同署名不凭姓名差异自动判互斥。三分类没有unknown输出，因此在无明确相关矛盾、但身份/时间/范围不清阻碍有据回答时输出refuse；这是操作约定，不声称消除了语义歧义。

## 评估与限制

主要筛选仍按原发布val标签：Macro-F1最高且解析覆盖率≥99%、严格格式≥99%、三类召回各≥60%、分类错误可答率≤20%。并列依错误可答率低、最小类召回高、固定候选顺序决胜。门槛与原搜索相同；无候选合格则no_qualified_baseline，最高分仅诊断。

报告逐类P/R/F1、3×4混淆矩阵、充分/不足/冲突分开计数、两类错误可答、空输出/截断/格式，并按95个底题作10000次配对bootstrap：两组分别减旧chat8，以及examples减rules。旧chat8复用285条已验证缓存，和新设置同时改变了指令与解码，因此旧新差异不是单独提示词因果效应；两组新候选使用相同解码。

另列30条开发诊断逐条对照及29确定输入的类别计数，1unknown单列。这些是已经参与设计、有模型背景暴露的同助手判断；不是独立、人工金标准，也不是保留评估集，不用于自动候选筛选。原发布类别、旧封存与正式行为标注保持不变。通过筛选也只表示发布标签门槛达标，不自动证明语义可靠或启动确认集。当前未有新GPU结果。

## 文件与核验

| 文件 | 内容 |
| --- | --- |
| protocol.json | 冻结输入/模型规格、两个候选、13份代码/提示/配置指纹、旧对照和开发判断来源哈希、解码/筛选与暴露说明 |
| preflight.json | 全部输入长度、3-token语法上界、历史耗时与新输出数量 |
| progress.json | 准备、生成进度、生成/分析完成；候选和最后保存条目 |
| semantic_rules/predictions.json 等 | 逐条原始输出、token IDs、EOS/格式/解析、提示哈希、时间和峰值显存 |
| smoke_gate.json | smoke两组各9/9技术结果，与语义成绩分开 |
| reports/val.md、val.json | 发布标签筛选、逐类结果/混淆矩阵、配对区间及开发30条逐项对照 |
| last_failure.json | 失败的候选/实例及原因，历史失败快照不等于仍在失败 |

完成后只读核验全部缓存、报告、筛选和bootstrap，不启动GPU或改写报告：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_classification_semantic_baseline.py
```

仅CPU预检查：

```sh
sh scripts/run_classification_semantic_baseline.sh --stage check
```

只重新分析已有完整预测（会更新本次报告，无GPU）：

```sh
sh scripts/run_classification_semantic_baseline.sh --stage analyze
```

准备证据见[准备记录](records/2026-10-16-classification-semantic-baseline-preparation.md)。全套79项CPU测试通过，包含本轮9项；真实tokenizer正式/技术smoke检查通过，另在临时目录完成18条合成输出流程、只读核验和缓存续跑，合成输出不作为模型实验结果。

2026-10-18新增独立计数与30条旧判断对照入口，不修改上列冻结依赖，默认另存新postanalysis目录；该命令已成功执行并逐字节重复验证：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/analyze_classification_semantic_failure.py
```

输出summary.json、cases.csv、report.md、manifest.json；14源哈希不变，50旧引文来源匹配，保留29确定/1unknown。全套83CPU测试通过10.380秒。对照只复用已有有暴露的开发判断，不新增独立评分、不推测标签输出的内部推理。
