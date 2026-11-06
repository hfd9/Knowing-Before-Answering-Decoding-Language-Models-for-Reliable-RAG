# 2026-11-06：逐主张审查工作包归档后的项目背景恢复

记录日期与时区：2026-11-06，Asia/Shanghai。
状态：背景恢复完成；仅轻量只读检查与记录维护。
操作者：当前助手。

## 目标与背景

用户要求根据项目根目录AGENTS.md恢复项目背景。本轮读取交接入口、记录索引最新条目、上一恢复记录、最新本地归档、阶段研究报告、逐主张复核后的研究决策和接收工具说明。按最新完成记录理解早期准备、待启动、待评分和未提交的历史快照。

研究对象为冻结Qwen2.5-3B-Instruct生成前隐藏状态的线性读出及其与自由回答行为的关系。当前证据需区分发布构造类别、作者语义参照、连续概率响应、三分类有效性、目标回答与解释主张支持，以及因果使用。可靠语义测量与原机制假设尚未确立；原论文已有状态替换研究，不将首次patching当作新增贡献。

## 实际操作与证据

恢复前工作区干净。实际本地分支main的HEAD为`4ce17d61291532fc56845328a02c2ec5c4ffd6b9`，保存的origin/main同哈希，`git rev-list --left-right --count HEAD...origin/main`为0/0。本轮未联网查询远端；本地引用一致不代表本轮认证实时远端状态，也不改写10月23日“仅本地提交”的历史记录。

确认以下八个run目录存在；目录存在不替代完整缓存或结果核验：

- `runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1`
- `runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-v1`
- `runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-analysis-v2`
- `runs/qwen2.5-3b-behavior-binding-v1`
- `runs/qwen2.5-3b-behavior-binding-probe-v1`
- `runs/qwen2.5-3b-probe-calibration-diagnostic-v1`
- `runs/qwen2.5-3b-relation-attachment-v1`
- `runs/qwen2.5-3b-semantic-claim-review-intake-v1`

读取共享一次拟合声明及owner_run的fit_attempt.json：maximum_attempts为1，训练ID共48个。唯一拟合已按原完成记录消耗预算，剩余0；另存v2分析不恢复预算。

关系附着completion/progress均记completed=48，progress的planned=48，generation_attempts下有48个JSON。原`collection_complete_behavior_unreviewed`是采集时技术快照，后续行为评分已另存；本轮未重放每条attempt的提交状态、模型指纹或全部哈希。

实际接收目录仅四份JSON：protocol、intake_report、normalized_reviews、endpoint_comparison。intake_report当前为`pending_no_review_files`，计划55条/82句，实际已审输入、输出及原子主张均0；独立语义批准0、formal_gate=false、gpu_launch_ready=false、剩余拟合0、semantic_accuracy及population_error_rate均null，held_out_380_accessed=false。原输入及回答阶段ZIP均存在。该检查仅报告当前接收目录状态，不声称搜遍所有位置或已经收到实际评审。

## 恢复后的研究结论

以下数字来自既有完成报告，本轮没有重新计算指标：

- 30底题240变体的采集、行为复核、180同题配对、一次作者参照拟合及v2分析均完成。旧不足实质作答23/60；旧probe判不足后作答1/16，受底题组成影响，不能据此认定稳定题内预测优势。S→I不足概率均值+18.08pp、S→C冲突概率+20.84pp，连续响应不认证可靠三分类。
- 唯一重训在评估来源的作者参照下一致57/96→62/96，差+5.21pp的既有区间跨0，冲突召回18/24→11/24。未干预回答，已见评估来源不恢复前瞻身份。
- 跨实体绑定48回答中充分有据24/24、不足作答及干扰采用0/24；同48输入补读却将全部24条不足判为Answer。S→I不足概率均上升、均值+10.66pp，不能由三分类失效推断隐藏状态无不足信息。288条诊断中取消sigmoid校准未改变两批不足类别，不能据此修复缺证判定。
- 关系附着48回答中充分有据12/12、不足目标作答0/36，主TA−OA为0pp；另有三条无据冲突解释的事后作者判断，待独立核验。零事件不证明总体零错误，也不解释旧自然题材料与简单虚构任务差异的根因。
- 55条/155主张作者复核已完成，当前采用analysis-v2：101支持、34未支持、13歧义、7反证；重复与拆分粒度使主张数不能当独立样本或总体解释准确率。旧23目标15未支持/8歧义不覆盖原23/60及8/9/6表面分类。当前助手已接触项目历史，不能作为独立盲评者。

主要依据：[阶段报告](../stage_research_report.md)、[最新归档](2026-10-23-code-submission-02.md)、[研究决策](../semantic_claim_review_decision.md)。技术重放和独立实现核验不等于独立语义评审。

## 未完成项与下一步

既定迁移探索、两项行为对照、补充读出、校准定位、作者复核及报告整理均已完成，无待启动的新GPU任务。实际独立语义审核仍为下一证据节点；有真实文件时按[接收说明](../semantic_claim_review_intake.md)另开接收run，保留输入先封存、上下文暴露、逐主张分歧及unknown，不自动认定独立性或生成正式标签。用户暂无外部渠道，不重复索要同批审核。

若实际独立审核支持相关案例，再决定是否单独设计“目标值正确保留未知时，解释为何仍可能无据”的较窄行为问题。当前预算0、独立语义批准0、正式gate=false、正式标签null、380底题封存继续保持；不自动新采集、拟合、补probe、阈值搜索、扩样或patching。长期GPU沿用用户启动的分工。

## 记录维护与检查

新增本记录，同步AGENTS.md、记录索引及活动日志。仅检查本轮四文件的差异格式和新增链接；没有运行旧测试套件、完整结果verify或实验重放，没有检查实时GPU、调用模型、增加评分/统计检验、修改runs产物、更新experiments.csv、提交或推送。
