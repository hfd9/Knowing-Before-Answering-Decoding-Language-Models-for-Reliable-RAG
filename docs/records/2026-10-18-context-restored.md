# 2026-10-18：背景恢复与新分类完成状态轻量核对

记录日期与时区：2026-10-18，Asia/Shanghai；产物检查约13:52。
状态：背景恢复完成；新分类产物为analysis_complete，尚未在本轮完整重放核验。
操作者：助手；用户要求根据AGENTS.md恢复项目背景。

## 目标与背景

按根目录交接入口恢复研究目标、证据边界、最新实验状态和协作约定。接续[10月16日背景恢复](2026-10-16-context-restored.md)及[新分类运行快照](2026-10-16-classification-semantic-baseline-running.md)，以实际产物更新当前状态。

## 实际操作

读取AGENTS、记录索引、最新背景恢复/新分类准备与运行记录、新分类说明、实验计划与运行说明、研究结论、v4行为裁定及30条追加语义判断记录。只读检查Git状态与最近提交、新分类目录/状态/预测/报告/日志、协议代码指纹和正式行为标注。未读取大型激活数组，未运行新推理、训练、语义评分或全套测试，未检查宿主实时GPU。

## 证据、检查与产物

- HEAD为a168cec；工作区已有大量已暂存、未暂存和未跟踪的代码/文档，均保留。未提交、推送或操作暂存区。
- 正式行为CSV为600行、600唯一item_id，132行至少一项unknown；SHA256为32591defb20e343f1f5593540410d9a57dceebe1cfec1d2be200e0e715b5496a，与持久v4副本逐字节一致。
- 新分类正式目录runs/qwen2.5-3b-classification-semantic-v1/保存analysis_complete、570新输出；semantic_rules和semantic_examples分别285条且各285唯一ID。smoke目录runs/qwen2.5-3b-classification-semantic-smoke-v1/同为analysis_complete、18条，各9条，保存technical_smoke_passed。
- 四份预测逐条保存technical_valid=true、hit_output_limit=false。两目录各13份代码/提示指纹当前均匹配；未见last_failure.json。上述字段计数与指纹检查不替代完整token/EOS/提示来源重放。
- 正式末条完成时间：rules为2026-10-16 20:33:48.736382，examples为20:35:54.527714（北京时间）。full.log末尾记录285/285和Analysis complete；不能继续把10月16日20:33:27的227/285快照视为当前进度。
- 正式报告保存eligible_candidates=[]、selected_candidate=null、diagnostic_best_candidate=semantic_rules、status=no_qualified_baseline。

以下仅转录保存报告，尚未在本轮完整复算，暂不登记experiments.csv完成指标：

| 方法 | 发布标签Accuracy | Macro-F1 | 充分/不足/冲突召回 |
| --- | ---: | ---: | --- |
| legacy_chat8 | 40.00% | 28.03% | 20.00 / 100.00 / 0.00% |
| semantic_rules | 41.40% | 30.57% | 23.16 / 98.95 / 2.11% |
| semantic_examples | 37.19% | 24.13% | 10.53 / 100.00 / 1.05% |

## 结果与解释边界

研究仍为冻结Qwen2.5-3B-Instruct的生成前证据类别解码与实际行为关系。探针优势主要来自冲突；分类正确率不等于真实缺证行为可靠性，不能证明自知、故意忽略或因果机制。

当前行为结果采用正式v4完整分母上下界，132未知为裁定后保留歧义，不自动清零、不套用旧v3置信区间。同模型评分、背景暴露、协调补评和裁定限制继续披露。

新分类生成与分析已保存完成，报告仍无合格基线。受约束格式不认证语义；30条诊断参与开发，29确定/1unknown仅作同助手开发对照。当前300条test仅诊断，剩余380测试底题保留；不因最高分放宽门槛、不改正式标签、不自动开展确认或patching。

## 未完成项与下一步

首先对已完成的新分类做完整CPU只读核验，包括缓存/完整提示/token/EOS、来源、指标、筛选与bootstrap；无需重跑GPU：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_classification_semantic_baseline.py
```

该命令本轮未执行；smoke完整核验可为同脚本传入--run_dir runs/qwen2.5-3b-classification-semantic-smoke-v1。核验完成后再归档正式结果并登记指标。本轮用户要求为背景恢复，未扩展为新实验或完整分析。

预计超过10分钟或不能保证低于10分钟的GPU任务继续由助手准备代码/检查/估时/断点，再交用户启动；已有同GPU任务时不另起实验，运行中不改依赖。代码/协议/输入改变使用新run_dir。

## 索引更新

新增本记录，更新README索引、AGENTS最新状态与activity_log；保留旧运行快照及所有历史结果。未更新experiments.csv，未修改实验代码、配置、protocol、输出或正式标注。
