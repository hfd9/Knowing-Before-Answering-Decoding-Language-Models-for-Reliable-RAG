# 2026-10-11：四条件分类补跑完成与核验

记录时间与时区：2026-10-11 12:30:48，Asia/Shanghai。
状态：verified_complete。
操作者：助手；用户明确要求完成后续第一、第二步，GPU 命令执行权限在本轮已批准。

## 目标与背景

完成此前只有准备产物的 plain/chat × 8/64-token 分类对照，并区分格式遵从、三分类性能与实际自由回答行为。
配套第一步见 [自由回答重点复核与证据审计](2026-10-11-free-answer-followup-audit.md)。
此前启动准备与运行中计数见 [12:08 历史启动快照](2026-10-11-classification-grid-launch.json)，该快照不能代表当前完成状态。

## 实际操作

未找到其他路径完成的四条件预测。先保留默认目录原 protocol/preflight/audit 到 `history/2026-10-11-before-followup-check/`。
实际执行 22 项 CPU 测试，全部通过（9.449 秒）；执行 `sh scripts/run_classification_grid.sh --stage check`，长度检查和参考产物审计通过。
确认 GPU 0 空闲后，实际执行 `sh scripts/run_classification_grid_review.sh`：先用3个底题的四条件 smoke，随后正式补跑，命令退出码0。smoke 每条件 val/test 各9条，八份预测和两份报告均完成。

正式运行沿用 2026-10-09 固定协议，Qwen2.5-3B-Instruct 本地权重、BF16、SDPA、单样本 greedy、单 beam；官方 chat template 使用 system 分类指令及 user 文档问题，plain 使用原纯文本 renderer。每题五份文档及顺序保持完整，未裁剪。
train600条仅作为旧探针/参考审计背景，本轮不训练或微调大模型。每个分类条件新生成 val285条；test每条件300条，其中plain8复用历史原始输出，另三组新生成。
正式共2,340条分类输出，新增2,040条、历史复用300条；四条件smoke另外63条新生成和9条历史复用，不混入正式分母。
新生成首条于北京时间11:54:39，最后一条于12:30:06保存；先完成全部验证条件，再执行测试条件。

协议与源指令、代码指纹、参考数据未修改。只新增顺序启动包装脚本及只读核验脚本，未修改运行依赖。
解析规则在新推理前固定：整个输出单个类别词评价严格格式，首个非空行单个类别词评价分类；invalid留在全部分母及对应类假负例。plain8/test保留历史事后解析标记。

## 结果

每条件 val95底题/285实例、test100底题/300实例。当前test已查看，属于诊断集。

| 方法 | val Accuracy | test Accuracy | test Macro-F1 | test 三分类错误可答率 | test 严格格式 | test 不足→可答 | test 冲突→可答 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 旧隐藏状态路由器 | 83.86%* | 80.67% | 80.54% | 10.00% | 不适用 | 11/100 | 9/100 |
| plain8 | 41.75% | 50.00% | 39.93% | 31.50% | 0.00% | 6/100 | 57/100 |
| plain64 | 41.75% | 50.00% | 39.93% | 31.50% | 0.00% | 6/100 | 57/100 |
| chat8 | 40.00% | 43.00% | 32.12% | 14.00% | 99.67% | 0/100 | 28/100 |
| chat64 | 40.00% | 43.00% | 32.12% | 14.00% | 99.67% | 0/100 | 28/100 |

*路由器val使用已在val标签上做sigmoid校准的模型，是校准内评估。该值与旧未校准选层分数不能混为同一个指标。
三分类错误可答率的分母为不足100+冲突100=200；它不是自由回答的缺证作答率。
四个条件test首行均解析299/300=99.67%；plain验证解析284/285=99.65%，chat验证285/285=100%。
四条件正式test空输出均0；触及输出预算且未EOS分别plain8 277/300、plain64 209/300、chat8/64各0。

同格式8-token与64-token的预测在val285/285、test300/300逐条相同；全部短输出文本也是对应长输出的前缀。两预算的配对分类差值均为0，bootstrap区间也为[0,0]。严格格式从plain的0%改善到chat的99.67%，没有转化为更高的三分类准确率。

test逐类召回：

| 方法 | Answer | Refuse | Conflict |
| --- | ---: | ---: | ---: |
| 路由器 | 71% | 84% | 87% |
| plain8/64 | 55% | 94% | 1% |
| chat8/64 | 28% | 100% | 1% |

chat在不足类很保守，但大量充分和冲突配置也被判不足；本轮固定提示词仍不足以称为可靠的三分类基线。
路由器比plain净多判对92条：Answer+16、Refuse−10、Conflict+86；比chat净多判对113条：Answer+43、Refuse−16、Conflict+86。因此不能用整体优势宣称路由器不足类更好。

## 配对区间与证据质量

预设8个配对对照，按original_id保留同底题三种配置，10,000次bootstrap、seed42、模型固定。
test的chat−plain（两预算相同）准确率差−7.00个百分点，95%区间[−10.33,−3.67]；错误可答率差−17.50个百分点，区间[−23.00,−12.50]。
chat−router准确率差−37.67个百分点，区间[−43.33,−31.99]；错误可答率差+4.00个百分点，区间[−1.50,+9.50]，不能据点估计宣称其错误可答率差异稳定。
plain−router准确率差−30.67个百分点，区间[−36.33,−25.00]。完整Macro-F1、逐类召回及两种误判率差值见JSON。

使用第一步的同助手事后证据质量审计，明确冲突68条中路由器判conflict61、answer5、refuse2；plain判conflict1、answer38、refuse29；chat判conflict1、answer16、refuse51。
这说明生成式分类在明确冲突子集也常输出refuse或answer，但质量判定仍未经独立标注，不能当独立金标准。
显式改写元数据匹配4条conflict中路由器判conflict3/answer1，plain判answer4，chat判refuse2/answer2；该分层样本很小，不作稳定效果结论。未匹配不证明无泄漏。

## 证据、检查与产物

助手实际执行 `python scripts/verify_classification_grid.py`（kba-rag环境）：八份预测计数、ID/发布标签顺序、首行及严格解析2,340条全部核验；旧300条raw_output与原始文件逐条相同，legacy_source哈希匹配。
独立复算val/test×五方法共10组3×4混淆矩阵、Accuracy、Macro-F1、逐类Precision/Recall/F1、完整分母和错误可答率；128个配对差值点估计与单组指标相符。六个冻结依赖指纹全部未变。
完整审计的特征形状、NaN/Inf/全零、ID标签顺序及跨集合重叠检查通过；最长chat测试输入29,579 tokens，加64仍小于32,768上下文。
剩余380个测试底题（1,140实例）没有生成预测，正式预测ID与其无重叠，也未用于调参；完整发布数据只做结构/重叠审计。

- [持久JSON：协议、所有指标、bootstrap、分层、核验与哈希](2026-10-11-classification-grid-verified.json)。
- 正式运行：`runs/qwen2.5-3b-classification-grid/`；八份`{plain8,plain64,chat8,chat64}/{val,test}/predictions.json`。
- 报告：上述目录`reports/{val,test}.md/.json`、`{val,test}_per_class.csv`及`{val,test}_errors.json`。
- 日志：`launch-2026-10-11/{smoke,full}.log`；smoke产物在`runs/qwen2.5-3b-classification-grid-smoke/`。
- 可复算核验：`scripts/verify_classification_grid.py`；启动包装：`scripts/run_classification_grid_review.sh`。

## 未完成项与下一步

本次完成的是固定四条件对照；可靠三分类提示词尚未建立。下一步先独立复核语义标签和证据质量，再只在验证集上设计新的提示词/示例及选择规则，变更须新run_dir和新protocol；冻结后才使用保留确认集。
自由回答的184条未知及独立第二标注尚未完成。发布配置、构造元数据、提示词变化、输出截断和同助手判定均限制解释；不要据此认定模型知道、故意忽略或直接做patching。

## 索引更新

同步AGENTS、记录索引、活动日志；仅将完成并核验的四条件指标登记experiments.csv。历史快照保留，没有提交、推送或发布。
