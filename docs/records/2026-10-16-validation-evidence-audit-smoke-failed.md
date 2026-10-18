# 2026-10-16：证据诊断smoke生成完成但技术门槛失败

记录日期与时区：2026-10-16，Asia/Shanghai。
状态：smoke生成与草稿分析完成，技术门槛failed；正式prepared_not_started。
操作者：用户执行GPU顺序入口；助手只读核验。

## 目标与背景

用户执行`sh scripts/run_validation_evidence_audit_review.sh`后返回提示符。本次确认退出原因，接续[准备记录](2026-10-13-validation-evidence-audit-preparation.md)和[此前启动阻止](2026-10-13-validation-evidence-audit-launch-blocked.md)。

## 实际操作

读取追加日志、两目录progress、包装脚本、固定指令、smoke报告及全部9条原始输出。CPU重放冻结parse_draft，校验输出哈希、ID顺序、预测协议绑定及11个代码/提示文件指纹；未重新推理或改写报告。

## 证据、检查与产物

- 日志前段保留旧GPU活动进程异常；本次新段已加载模型并完成9/9，随后抛出`Technical smoke structure gate failed: 0/9`。本次退出原因是技术门槛失败。
- smoke为analysis_complete、9/9、draft_analysis_complete_separate_review_pending；此状态不代表技术通过或语义审核完成。正式仍prepared_not_started、0/285，无正式预测或full.log；包装脚本set -eu在门槛失败后退出。
- 固定门槛至少6/9，实际0/9。首个解析错误：refuse_requires_missing_fact 2条、text_field_type 1条、unverifiable_quote 3条、invalid_json 3条。解析遇首错停止，计数不是所有问题的穷尽统计。
- 三条invalid_json均有Markdown代码围栏；另有列表/对象替代字符串、refuse缺失事实为空、引用不在指定文档逐字匹配。全部按冻结规则保留unknown；未去围栏、补字段或修改引用追认有效。
- 空输出0、hit_output_limit 0；生成111–295 tokens，预算512。生成耗时合计73.65秒，不含完整入口开销；首末保存时间北京时间15:40:21、15:41:25。
- 11个指纹、预测协议绑定、9条ID顺序/输出哈希全部匹配；冻结解析重放与保存结果一致。预测文件SHA256为`62aca7443d8771552709398542d160c8b92aaa6df8bb08fdf4b937b3c98e1e90`。
- nvidia-smi查询返回无法与驱动通信，未据此判断宿主驱动或实时GPU占用；日志与产物已足以解释退出。未重新跑全套CPU测试、完整提示/tokenizer核验或语义金标准审核。

## 结果与解释边界

本次模型推理成功执行，审核输出未过技术门槛；没有285条正式结果。0/9有效草稿不能解释为模型认为全部证据语义未知，也不能推算正式验证集准确率。引用来源检查不证明语义正确；旧三候选未合格、自由回答v4/132未知和380保留底题状态不变。

## 未完成项与下一步

保留冻结v1和6/9门槛。原样重跑会复用9条缓存并再次失败，不会自动启动正式。若继续模型辅助诊断，先设计更明确的schema及字段示例，在新run_dir/protocol做CPU检查与新smoke；通过后仍单独语义复核。也可使用现有空白盲审包并披露评分来源。新设计本次尚未实现，未自动启动新GPU任务。

## 索引更新

更新AGENTS、记录索引、执行说明、活动日志；不登记正式实验指标。代码、配置、协议、原始预测、报告与历史快照不改，原有暂存改动保留；未提交或推送。
