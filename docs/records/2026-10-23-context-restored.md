# 2026-10-23：项目背景恢复与最新冻结诊断衔接

记录日期与时区：2026-10-23，Asia/Shanghai。
状态：背景恢复完成；未运行实验或完整结果重放。
操作者：当前助手。

## 目标与实际操作

用户要求根据根目录AGENTS.md指导恢复项目背景。本轮阅读完整交接入口、记录索引的最新条目、2026-10-21第二次本地归档、原48输入的旧chat L28联合结果、288条原线性/旧sigmoid校准诊断、综合研究结论和此前恢复记录。按最新完成记录解释较早的准备、运行中、待评分与未提交快照。

只读执行git status、git log，核对主要运行目录存在，并读取共享一次拟合预算声明与唯一fit_attempt。恢复前工作区干净，本地main的HEAD为`615d9c2ba10c3e84a198eb5184491842b56f0b83`，父提交为`5152ca9dfcf63896fb5101ab7c64d17263d97441`，相对本地保存的origin/main引用领先2个提交。未联网核对远端，该引用不代表实时远端状态。

实际确认以下目录存在；目录存在性检查不代替完成核验：

- `runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1`
- `runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-v1`
- `runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-analysis-v2`
- `runs/qwen2.5-3b-behavior-binding-v1`
- `runs/qwen2.5-3b-behavior-binding-probe-v1`
- `runs/qwen2.5-3b-probe-calibration-diagnostic-v1`

v2分析是独立的同级目录，不能假定为拟合目录内的analysis-v2子目录。共享声明`runs/semantic-transfer-shared-one-fit-budget-v1.json`绑定原design_sha256与唯一owner_run，maximum_attempts为1；对应fit_attempt.json存在，原预算按既有完成记录已用完。

## 恢复后的研究状态

研究对象是冻结Qwen2.5-3B-Instruct的生成前隐藏状态与线性探针，当前重点为旧chat L28对真实证据语义的迁移有效性。需要分别检验发布构造类别、证据语义、连续分数、三分类判定、实际行为与因果使用。原论文已有生成级状态替换，不以“首次从分类走向生成/patching”作为新增贡献。

按既有完成记录：

- v5的30底题/240变体采集、行为复核、180配对、唯一作者参照拟合与v2离线分析，以及23条缺证作答审计均已完成。旧240中不足作答23/60、旧probe判不足后作答1/16；条件子集受底题组成影响，未确证稳定题内预测优势。
- 12虚构场景的48回答已采集、评分和核验：S有据回答24/24，I实质作答及干扰值采用均0/24。该简单任务未观察到误绑定，不能推广为自然文档总体零错误。
- 原48输入的旧L28补充读出已完成：S为answer13/conflict11，I全部24读answer，没有refuse。I中probe-refuse分母为0，条件率null。原主行为正确与冻结三分类失效共存；不足概率在24组S→I中均升、均值+10.66pp，不支持“隐藏状态没有不足信息”。这是回答已见后的输入状态重算，不冒称原生成同步读出。
- 288条校准诊断已完成：48作者参照一致原线性18/48→校准13/48，240保持117/236，4作者unknown保留；16次类别变化均转conflict。两批I类别完全不变，因此撤销校准不能修复本批缺证判定，也没有定位隐藏状态的唯一根因。

上述数值来自已保存的[综合结论](../semantic_transfer_conclusions.md)、[48联合结果](2026-10-21-behavior-binding-probe-results.md)、[288校准诊断](2026-10-21-probe-calibration-diagnostic.md)和[归档记录](2026-10-21-code-submission-02.md)。本轮没有重新认证这些指标、全部缓存、引用或文件哈希，也没有检查实时GPU进程。

## 当前边界与后续衔接

原设计一次拟合预算剩余0；分析修复、换目录、调层/参数均不恢复预算。独立语义批准0、正式gate=false、正式标签null；380保留底题继续封存。当前助手已读取项目历史，不是独立盲评者；用户暂无外部渠道，不反复索要。已经查看的eval不恢复前瞻确认身份。

当前探索工作包已完成，后续以封存报告和按需只读复核为基础，不把旧准备命令或未评分快照当待执行任务，不自动新增GPU、重生成、扩措辞网格、拟合、阈值搜索或patching。需要复核校准诊断时使用`scripts/probe_calibration_diagnostic.py --stage verify`或`scripts/verify_probe_calibration_diagnostic.py`；48联合使用`sh scripts/run_behavior_binding_probe.sh --stage verify-results`或独立核验脚本；重训结果只用`scripts/semantic_transfer_exploratory_retrain_analysis_v2.py --stage verify`，不再运行原拟合入口。这些命令本轮未执行。

本轮新增此记录，同步AGENTS、索引和活动日志；仅检查文档差异格式。未修改实验实现、协议、评分或runs产物，未新增实验登记、运行测试、GPU、前向、回答或拟合，未提交或推送。
