# 2026-10-16：两组新语义规则分类候选准备，交用户运行

记录时间与时区：2026-10-16，Asia/Shanghai。
状态：prepared_not_started；新GPU预测0条，没有新候选指标。
操作者：助手完成代码/CPU检查，用户启动GPU。

## 目标与背景

用户要求“你完成代码吧，给我命令”。接续[30条同助手追加判断](2026-10-16-validation-semantic-followup.md)，将必要前提、实体/关系、属性兼容与相关互斥、题目事件和时点区分固定到新提示词。原三候选no_qualified_baseline及旧证据诊断结果不改，当前只准备新val比较，不使用保留380底题或直接做干预。

## 实际修改与固定设计

新增prompts/classification_semantic_v1.json、scripts/classification_semantic_baseline.py、两个sh入口、只读verify脚本、9项CPU测试及[运行说明](../classification_semantic_baseline.md)。复用冻结旧模块的来源校验、渲染、旧val缓存、指标/筛选/配对bootstrap函数，不修改旧实验依赖。

两组semantic_rules与semantic_examples共用同一规则，后者增加7个虚构说明例子，未照搬原题实体/答案/数值。已知val错误用于开发，明确披露；真实诊断test和确认集未用于构建或调用。原生chat/完整五篇原文原顺序、BF16/SDPA、greedy、single beam、8-token上限、三标签token trie+EOS。无长分析、引用索引或裁剪输入，不训练模型/探针。

无法建立明确矛盾且歧义阻碍有据回答时，三分类操作约定输出refuse；文档时点允许限定答案，但不冒充当前事实。此约定写在推理前，不据输出事后改变或抹除原助手unknown。语法构造的格式通过率与语义正确性分开；新旧chat8对照同时改变指令和解码，不能认定为提示词单因素效应。

门槛与旧搜索保持：覆盖/严格格式各≥99%、三类召回各≥60%、分类错误可答率≤20%，符合者按Macro-F1及原并列规则筛选；无合格则no_qualified_baseline。旧chat8复用285条；新两组正式各285=570，独立技术smoke各9=18。新smoke各9/9要求只检查标签/EOS/格式完整性，不以语义得分决定能否生成正式；旧证据诊断6/9规则未动。

报告主要为发布标签指标、逐类结果与3×4混淆矩阵、三组10000次按底题配对bootstrap；附开发30条逐项对照与29确定/1unknown口径，非独立金标准，不用于筛选。不自动导入标签、选择确认设置或启动确认推理。

## 实际检查与准备产物

实际执行全套CPU测试：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B -m unittest discover -s tests
```

最终版本79项全部通过，10.899秒；其中本轮9项验证完整渲染/标签隔离、多token标签与EOS、小型CPU Qwen实际HF约束生成、原门槛不变/低冲突召回不合格、缓存token/提示/身份/设置/文本/状态篡改、两组9/9 gate与无语义门槛、GPU活动进程拒绝、smoke失败阻止full、新旧标签口径分别计数。首次完整测试后补充逐条开发对照与只读核验，再完整跑79项通过；不用早期版本的通过替代最终检查。

真实本地tokenizer先在临时目录完成正式与smoke CPU预检查；另以合成固定answer输出在临时目录跑通18条smoke、报告、只读verify及已有缓存续跑（断言不会加载模型），源文件逐字节不变。临时合成结果已清理，不称本机3B生成或语义表现。

最终正式及smoke目录只运行CPU check：

```sh
sh scripts/run_classification_semantic_baseline.sh --stage check
sh scripts/run_classification_semantic_baseline.sh --stage check --limit_questions 3 --run_dir runs/qwen2.5-3b-classification-semantic-smoke-v1
```

| 检查 | semantic_rules | semantic_examples |
| --- | ---: | ---: |
| 正式输入条数 | 285 | 285 |
| 正式最大输入tokens | 5532 | 5926 |
| 正式平均输入tokens | 2437.66 | 2831.66 |
| smoke输入条数 | 9 | 9 |
| smoke最大输入tokens | 5079 | 5473 |

上下文32768，均额外保留8输出；语法最长3tokens含EOS，三词真实分词answer=[9217]、refuse=[1097,810]、conflict=[6135,21242]。13份代码/提示/配置指纹写入两个新protocol，旧对照/开发判断来源单独绑定。两目录prepared_not_started、新预测0；CPU检查和旧val读出不加载3B或启动GPU。

旧chat8验证纯生成94.632秒；按新输入/约束未实测，正式规划6.7–18.6分钟，smoke2.2–6.4分钟，完整保守预留10–30分钟，主机争用另加。不是完成时限保证。按用户约定交其启动，助手没有运行新3B GPU。

## 用户命令、日志和断点

```sh
sh scripts/run_classification_semantic_baseline_review.sh
```

入口smoke通过自动正式；两个阶段失败均打印最后30行日志。GPU活动进程会列PID/进程/显存后拒绝加载，不终止其他任务。每条原子保存；中断原样重跑、核验后复用缓存；设置/代码改变须新目录。

正式：runs/qwen2.5-3b-classification-semantic-v1/；smoke：runs/qwen2.5-3b-classification-semantic-smoke-v1/。日志正式目录launch/smoke.log与full.log，结果reports/val.md与val.json。完成后助手可用只读scripts/verify_classification_semantic_baseline.py验证缓存/协议/输入长度/指标/筛选/区间，无需改报告或启动GPU。

## 状态与维护

设置与检查、目录状态和必要哈希见[结构化准备清单](2026-10-16-classification-semantic-baseline-preparation.json)。新增实验指标尚无，不更新experiments.csv的结果行；更新AGENTS、记录索引和activity_log。保留首轮/追加助手评分、全部旧协议/预测/正式行为标注及已有暂存改动，未提交、推送或发布。
