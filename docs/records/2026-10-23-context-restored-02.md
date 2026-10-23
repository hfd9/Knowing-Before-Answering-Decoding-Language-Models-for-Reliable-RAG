# 2026-10-23：关系附着结果归档后的第二次项目背景恢复

记录日期与时区：2026-10-23，Asia/Shanghai。
状态：背景恢复完成；仅轻量只读核对与文档维护。
操作者：当前助手。

## 目标与实际操作

用户要求根据AGENTS.md恢复项目背景。本轮读取根目录交接入口、记录索引最新条目、此前恢复记录、最新提交归档、关系附着48结果、原48输入的旧L28联合结果、288条校准诊断、综合研究结论及GitHub贡献图诊断。按最新完成记录理解早期准备、待启动、待评分和未提交快照。

只读检查本地Git：main的HEAD为`9464e165235595982173e6efea5dd6421a5482dc`，本地保存的origin/main同哈希，左右提交差0/0。本轮未联网查询远端，不能把本地引用当实时远端认证。

恢复开始时工作区已有改动：AGENTS.md、docs/activity_log.md、docs/records/README.md已修改，贡献图诊断MD/JSON未跟踪。这些是本轮之前的诊断记录，不归因于本次恢复，不覆盖、提交或推送。

## 本轮实际轻量核对

确认以下七个运行目录存在，目录存在性不替代完整结果核验：

- `runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1`
- `runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-v1`
- `runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-analysis-v2`
- `runs/qwen2.5-3b-behavior-binding-v1`
- `runs/qwen2.5-3b-behavior-binding-probe-v1`
- `runs/qwen2.5-3b-probe-calibration-diagnostic-v1`
- `runs/qwen2.5-3b-relation-attachment-v1`

读取共享一次拟合声明及owner_run的fit_attempt.json：maximum_attempts为1，48个训练ID已登记，原拟合预算按既有完成记录剩余0。v2分析是同级独立目录，不重新运行原拟合入口。

关系附着原completion.json/progress.json均记completed=48，planned=48；predictions.json存在，generation_attempts下48个JSON存在。这只是原技术完成标记和文件数量检查，未重放每条缓存、提交状态、模型指纹或全部哈希。原标记`collection_complete_behavior_unreviewed`是采集时保留的快照，后续评分已另存在docs/records，不把它解释成评分尚未进行。

## 恢复后的研究状态

研究对象为冻结Qwen2.5-3B-Instruct的生成前隐藏状态、线性探针及自由回答行为；当前关注旧chat L28读出向证据语义任务迁移的有效性。发布构造类别、作者语义参照、连续概率响应、三分类判定、实际回答与因果使用分别解释。原论文已有生成级状态替换，不能将首次开展patching作为本项目贡献。

以下为既有完成报告中的结果，本轮未重新计算或认证指标：

- 30底题240变体已完成采集、行为评分、180同题配对、一次作者参照拟合与单独v2分析。缺证作答23/60；旧probe判不足后作答1/16，不能忽略底题组成而声称稳定题内预测优势。S→I不足概率均值+18.08pp，S→C冲突概率+20.84pp，方向响应不能认证可靠三分类。
- 唯一重训在评估来源作者参照下一致57/96→62/96，差+5.21pp的既有区间跨0；冲突召回18/24→11/24。行为未被干预，已见eval不恢复前瞻身份。
- 12虚构场景48回答：S有据24/24，I实质目标作答/干扰采用均0/24。补充旧L28读出中I全部24判answer，S为answer13/conflict11；S→I不足概率24/24升、平均+10.66pp。主行为正确与冻结三分类失效共存，不推出隐藏状态无不足信息。这是回答已见后的状态重算。
- 288校准诊断：48作者参照一致原线性18/48→校准13/48，240两阶段均117/236；两批16次类别变化均进conflict，两批I类别不变。因此取消校准不能修复本批缺证类别判定。
- 最新六场景关系附着48回答已完成：TQ有据12/12，OQ/TA/OA不足共36条均不作目标代码回答；主TA0/12−OA0/12=0pp。另有三条无据冲突解释，不能把没有误绑定写成全文正确。240评分字段194确定/46具体引用归属unknown，均已审；零事件不证明总体零错误或解释旧23/60与虚构任务差异的根因。

主要依据：[综合结论](../semantic_transfer_conclusions.md)、[48联合结果](2026-10-21-behavior-binding-probe-results.md)、[288诊断](2026-10-21-probe-calibration-diagnostic.md)、[最新48结果](2026-10-23-relation-attachment-results.md)。独立实现核验不等于独立语义评审。

## 当前边界与衔接

原设计拟合预算剩余0；换目录、分析修复、调层/参数不恢复预算。独立语义批准0、正式gate=false、正式标签null，380保留底题继续封存。当前助手已接触历史，不是独立盲评者；用户暂无外部渠道，不重复索要同批审核。最新工作包已完成，无待启动GPU任务，不自动扩样、重复生成、追加probe、阈值搜索、拟合或patching。

如需按需复核最新结果，使用以下现有离线入口；本轮未执行：

```sh
python3 -B scripts/relation_attachment_results.py --stage verify
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_relation_attachment_results.py
```

沿用长期GPU由用户启动的分工；本轮没有启动GPU或检查实时GPU进程。

[上一轮贡献图诊断](2026-10-23-github-contributions-diagnosis.md)记录当时公开API确认仓库fork=true、最近五个提交作者/提交者关联hfd9，定位为fork贡献统计条件；本轮只恢复该历史结论，没有重新联网诊断或修改仓库/账户/历史。

## 记录维护与检查

新增本记录，同步AGENTS、索引与活动日志；不更新实验指标登记。仅检查本轮新增记录和插入段落的差异格式及本地链接。保留原有诊断改动，没有修改实验实现、协议、评分或runs产物，没有新实验、评分、统计检验、拟合、测试套件运行、提交或推送。
