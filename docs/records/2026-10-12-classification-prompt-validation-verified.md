# 2026-10-12：三组验证集分类提示词完成与核验

记录时间与时区：2026-10-12 09:56后，Asia/Shanghai；只读核验结束09:56:08。
状态：verified_complete；选择结果no_qualified_baseline。
操作者：用户启动长期GPU；助手检查进度、复算并记录。

## 目标与背景

用户报告已执行`sh scripts/run_classification_prompt_search_review.sh`，要求检查。
前序准备与审核来源见[第二评分、v4裁定与准备](2026-10-12-semantic-review-adjudication.md)，预设协议见[验证集提示词说明](../classification_prompt_validation.md)。
模型为冻结Qwen2.5-3B-Instruct，BF16/SDPA、官方chat template、完整五篇文档、greedy、8-token输出；不训练大模型或探针。

## 实际操作与完成证据

初次检查时，smoke已27/27并analysis_complete；正式definitions285/285，decision_order正在增长。检查期间第三组继续保存，随后855/855生成完成并analysis_complete，报告和选择结果已保存。
助手没有另起GPU、修改运行依赖、重跑生成或覆写报告。没有发现last_failure.json；这不证明无日志的历史失败。
沙箱NVIDIA-SMI无法连接驱动且进程命名空间隔离，因此不据此推断宿主GPU异常、空闲或已退出；完成依据是完整产物和校验。用户启动命令退出码未直接观察。

| 运行 | 每候选输出 | 新生成总数 | 复用旧chat8验证对照 | 状态 |
| --- | ---: | ---: | ---: | --- |
| smoke-v3 | 9 | 27 | 9 | analysis_complete，技术流程核验通过，不参与选择 |
| 正式v3 | 285 | 855 | 285 | analysis_complete，全部报告与选择核验通过 |

正式输出首条北京时间09:50:30.130374、末条09:55:45.451294，首末保存间隔315.32秒；855条记录的生成耗时合计297.86秒，不包含CPU准备、加载和报告时间。
smoke首末09:49:44.513368–09:49:53.523517。首条保存时间不是首次生成起点，所以保存间隔与生成耗时总和不能混为一个计时。

## 验证集结果

val95底题/285实例，发布answer/refuse/conflict各95；invalid保留完整分母。

| 条件 | 正确/285 | Accuracy | Macro-F1 | 分类错误可答率 | 严格格式 | 充分召回 | 不足召回 | 冲突召回 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 旧chat8对照 | 114 | 40.00% | 28.03% | 20/190=10.53% | 100.00% | 20.00% | 100.00% | 0.00% |
| definitions | 108 | 37.89% | 25.81% | 22/190=11.58% | 98.95% | 15.79% | 97.89% | 0.00% |
| decision_order | 103 | 36.14% | 23.45% | 8/190=4.21% | 97.19% | 6.32% | 98.95% | 3.16% |
| illustrations | 104 | 36.49% | 23.20% | 7/190=3.68% | 100.00% | 6.32% | 100.00% | 3.16% |

不足→可答次数分别0、2、0、0；冲突→可答分别20、20、8、7。分类错误可答率的分母190，不是自由回答缺证作答率。
definitions输出245个refuse、37个answer、0个conflict、3个invalid；decision_order为257/14/6/8；illustrations为267/13/5/0。三候选均无空输出，无触及8-token预算且未EOS的记录。
invalid确为直接回答实体/词语，例如seraphim-falls、tattersall、prague；decision_order另有space、citizen-smith、uk、kettle、pandora。未把它们事后改作answer类别，未改变解析规则。

预设选择要求首行覆盖≥99%、严格格式≥99%、每类召回≥60%、分类错误可答率≤20%，按Macro-F1及预设并列顺序选择。三候选均未通过类别召回门槛；definitions与decision_order还未通过格式门槛。核验得到：

```text
eligible_candidates = []
selected_candidate = None
diagnostic_best_candidate = definitions
status = no_qualified_baseline
```

definitions只是新候选中Macro-F1最高者，不是合格基线；旧对照Macro-F1仍更高。技术smoke的27条全部refuse，流程通过不代表三分类能力通过。

## 配对区间与解释边界

95底题配对bootstrap，保留每题三配置，10,000次、seed42、模型固定。

| 新候选−旧chat8 | Accuracy差（百分点）与95%区间 | Macro-F1差与95%区间 | 分类错误可答率差与95%区间 |
| --- | --- | --- | --- |
| definitions | −2.11 [−4.56,+0.35] | −2.21 [−5.24,+0.82] | +1.05 [−2.63,+4.74] |
| decision_order | −3.86 [−7.02,−1.05] | −4.57 [−8.77,−0.28] | −6.32 [−10.53,−2.11] |
| illustrations | −3.51 [−5.96,−1.05] | −4.83 [−8.48,−1.07] | −6.84 [−10.53,−3.68] |

decision_order/illustrations降低分类错误可答，同时充分召回降到6.32%，冲突召回仅3.16%；不能把更常判refuse解释成可靠三分类或更好的自由回答行为。
本轮只用val选择，发布验证标签未经完整独立语义审核，选择分数有乐观偏差；这些区间是诊断比较，没有重新训练不确定性或多重比较调整，不是确认实验。
未生成当前诊断test或380保留底题的预测，未调整已冻结候选，未开展patching。

## 核验与产物

助手实际只读核验：从本地tokenizer重建两份protocol并逐字段相等；数据/模型来源、7个代码提示词指纹、旧对照指纹、审核门禁全部评分/裁定/v4哈希一致。
27+855新输出的ID/发布标签/底题顺序、渲染提示哈希、原始回答哈希、分词输入长度、预算、独立正则首行/严格解析核验通过。旧285条对照来源通过完整缓存核验，smoke9条为其子集。
独立Python计数复算smoke/正式各4方法的混淆矩阵、Accuracy、Macro-F1、逐类P/R/F1、错误可答分母、格式和异常计数；独立实现预设选择规则，均与报告一致。另用冻结公共函数复算六个配对对照各八项差值/区间，与保存报告相等。核验后六份新预测文件哈希仍一致。

- [持久JSON：完整正式/smoke指标、bootstrap、协议哈希、输出哈希、计时和核验](2026-10-12-classification-prompt-validation-verified.json)。
- 正式目录：`runs/qwen2.5-3b-classification-prompt-validation-v3/`；报告`reports/val.json`、`val.md`，三候选各`predictions.json`。
- smoke目录：`runs/qwen2.5-3b-classification-prompt-validation-smoke-v3/`。
- 日志：正式目录`launch/{smoke,full}.log`。
- 新只读核验入口：`scripts/verify_classification_prompt_search.py`。原临时核验退出0；持久入口采用相同检查、项目相对根路径。

## 未完成项与下一步

可靠分类提示词仍未建立，没有候选进入确认实验。下一步仅在验证集审核所需前提/明确矛盾，诊断分类指令被解释成直接答题或过度refuse的情况，再决定新的预先固定设计。不能放宽门槛把当前最高分追认为合格，不能用诊断test调提示后宣称独立成功。
后续新代码/提示/数据必须新run_dir与protocol；预计长期GPU仍由用户启动。当前v4自由回答及132未知保持不变。

## 索引更新

更新AGENTS、记录索引、活动日志、验证与运行说明；experiments.csv追加3条已核验val-only结果，test指标留空。旧记录不覆写，未提交或推送。
