# 验证集证据诊断v2：用户执行

用户已要求修复并继续285条，当前请用[v3约束解码入口](validation_evidence_audit_v3.md)。下文是v2历史状态与准备说明。

最新状态（2026-10-16）：用户已生成9/9 smoke，但仅3/9结构合法且均显式unknown，未达6/9门槛；入口退出，正式仍0/285。见[失败核验](records/2026-10-16-validation-evidence-audit-v2-smoke-failed.md)。不要原样重跑完整缓存；以下准备与命令保留供追溯，下一步先做全文语义复核再决定后续方案。

2026-10-16：代码、50项CPU测试和正式285条/smoke9条输入检查完成。两个v2目录均prepared_not_started、0输出，尚未执行新GPU推理。

v1已生成9条但0/9通过技术门槛，见[失败核验](records/2026-10-16-validation-evidence-audit-smoke-failed.md)。v2明确三个字符串字段、refuse缺失事实、短原文引用和无Markdown要求，新增四个合成格式示例及user消息末尾提醒。示例不取自项目数据，不作为语义能力证明。仍用v1严格解析器、512-token预算、6/9门槛和同一固定验证集；新smoke复用原三个val底题，属于据失败诊断修订后的技术检查，不是独立语义验证。

## 启动与续跑

在GPU空闲时执行：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
sh scripts/run_validation_evidence_audit_v2_review.sh
```

入口先生成9条smoke并分析，再验证至少6条结构/引用来源检查通过；通过后自动生成285条正式草稿并保存报告。合法unknown可计结构通过，不能将技术通过当语义正确。失败会在终端打印阶段和日志末尾，不再只显示日志路径。GPU活动进程保护继续生效；不停止其他进程或绕过保护。

中断后原样执行相同命令，校验并复用已保存输出。若完整smoke仍未达门槛，重复命令不会改善结果，应保留本轮并分析失败，不改旧协议或宽松重解析。

另一个终端查看进度：

```sh
tail -F runs/qwen2.5-3b-validation-evidence-audit-v2/launch/smoke.log runs/qwen2.5-3b-validation-evidence-audit-v2/launch/full.log
```

建议完整入口预留约45–140分钟，非保证。v1实际1582生成tokens/73.65秒，约21.48 tokens/秒；若v2平均长度相近，正式生成约39分钟；每条满512预算则约113分钟，另加加载、更长提示和宿主竞争余量。v2吞吐及语义质量尚未实测。公共preflight打印的planning_minutes继承40–100tokens/秒假设，偏乐观，不用于本次排期。按项目长期GPU约定由用户启动。

## 路径与核验

- 正式：`runs/qwen2.5-3b-validation-evidence-audit-v2/`。
- smoke：`runs/qwen2.5-3b-validation-evidence-audit-smoke-v2/`。
- 各自`protocol.json`、`preflight.json`、`progress.json`和空白盲审包已保存；后续输出位于`drafts/predictions.json`，报告位于`reports/diagnosis.{json,md}`。
- CPU最长输入正式6041、smoke5588 tokens，加512预算均小于32768。50项测试通过，包含4项v2测试；v1的11个冻结指纹与9条预测文件哈希保持一致。
- 仅val；完整五篇文档和问题保留，不向模型提供发布标签、gold答案或旧分类输出。不使用test/确认集，不选择新分类候选，不自动导入语义草稿。引用检查仅验证来源；同模型草稿仍需另行语义复核。

仅CPU检查：

```sh
sh scripts/run_validation_evidence_audit_v2.sh --stage check
```

生成完成后仅重做草稿报告：

```sh
sh scripts/run_validation_evidence_audit_v2.sh --stage analyze
```

复核评分规范沿用[v1说明](validation_evidence_audit.md)；评分文件须显式传入v2入口，例如`--stage analyze --ratings runs/qwen2.5-3b-validation-evidence-audit-v2/review/ratings.csv`，披露评审来源和背景暴露，不将草稿称独立金标准。评分前复制本轮空白模板，不跨批次复用。
