# 2026-10-16：按交接入口恢复项目背景

记录日期与时区：2026-10-16，Asia/Shanghai。
状态：背景恢复与轻量产物核对完成；没有新实验或指标复算。
操作者：助手；用户要求按根目录AGENTS.md恢复背景。

## 目标与背景

接续[最近背景恢复](2026-10-13-context-restored-02.md)、验证集证据诊断准备与启动阻止记录，确认当前正式分析版本、研究边界和下一步入口。

## 实际操作

读取AGENTS、记录索引、最新背景恢复/证据诊断准备/启动阻止记录、v4裁定、验证集三候选完成记录、研究结论、实验计划、运行说明及证据诊断说明。只读查看Git状态、最近三次提交、活动日志末尾及相关产物文件清单，轻量核对正式标注、候选输出数量、保存的选择状态与诊断进度。

## 证据、检查与产物

- 文档修改前本地HEAD为`a168cec`；工作区已有暂存的`docs/activity_log.md`、`docs/records/README.md`与`docs/records/2026-10-13-context-restored-02.md`，本次保留原有改动，未提交或推送，也未查询远端哈希。
- 正式v4为600行、600个唯一item_id；132行至少一项unknown，468行五字段确定。SHA256为`32591defb20e343f1f5593540410d9a57dceebe1cfec1d2be200e0e715b5496a`，与持久v4副本逐字节一致；behavior.json、behavior.md和joined_records.json均存在。
- 验证集分类提示词v3保存状态为`analysis_complete`，definitions、decision_order、illustrations各285条，共855条。报告保存`eligible_candidates=[]`、`selected_candidate=null`、`diagnostic_best_candidate=definitions`及`status=no_qualified_baseline`。
- 验证集证据诊断smoke仍为`prepared_not_started`、0/9；正式仍为同状态、0/285。两目录均无drafts/predictions.json及last_failure.json，正式launch/full.log不存在。
- 已有smoke.log在9条CPU预检查通过后，记录模型加载前GPU活动计算进程保护异常；本次未检查实时GPU占用、进程或PID，不能据此判断GPU当前仍忙。
- 本次未重新执行全套CPU测试、完整指标核验、bootstrap或语义评分，未加载模型或激活数组；上述是保存状态与关键产物的轻量核对，不是新实验结果。

## 结果与解释边界

当前产物与10月13日最新交接一致。研究对象为冻结Qwen2.5-3B-Instruct，训练线性探针/路由器；已有生成前发布类别可解码及实际行为失配的诊断证据，不能证明模型自知、故意忽略或因果机制。行为采用正式v4的完整分母上下界，132未知为裁定后保留歧义，不能自动清零或套用旧v3置信区间。同模型第二评分、项目背景暴露、2条协调补评与协调裁定限制继续披露。

## 未完成项与下一步

可靠三分类提示词仍未建立，下一步沿用仅val的证据质量与旧分类行为诊断。GPU空闲时由用户原样执行`sh scripts/run_validation_evidence_audit_review.sh`，助手后续核验生成和报告；完整入口历史规划约35–75分钟，未经实测，不保证时限。预计超过10分钟或不能保证低于10分钟的GPU任务继续由用户启动，不修改运行中依赖或绕过空闲保护。

当前300条test仅作诊断，剩余380测试底题保留待冻结设置后的确认；不追改门槛认证旧候选，不直接开展patching，新代码/提示/抽样须新run_dir与protocol。

## 索引更新

新增本记录，更新记录索引与活动日志。研究状态和入口未变化，AGENTS.md、experiments.csv、代码、配置、协议、运行产物和历史快照不改；未提交、推送或发布。
