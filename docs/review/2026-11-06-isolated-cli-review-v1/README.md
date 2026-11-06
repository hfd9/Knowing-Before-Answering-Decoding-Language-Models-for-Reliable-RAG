# CLI20261106R01：55条材料的隔离会话两阶段复评

日期：2026-11-06，Asia/Shanghai。状态：55输入/55回答/172主张完成并已接收；正式独立批准、标签和GPU门禁不自动改变。

本包是一个评审会话的结果，多阶段、备份和元数据修订均不算额外评审。研究解释见[复评结果与接续建议](../../isolated_cli_review_results.md)，操作与证据见[本轮记录](../../records/2026-11-06-isolated-cli-review.md)。

## 来源与顺序

材料来自[原55条包](../2026-10-23-semantic-claims-v1/README.md)，问题、五文档和回答未改写。评审在项目目录外 `/tmp/text-evidence-review-20261106-neutral` 使用独立CLI新会话，未继承本对话；先[上下文自审](context_audit.json)，再执行[输入任务](phase1_task.md)，输入封存后才执行[回答任务](phase2_task.md)。执行轨迹和交付记录保留在下列目录。

| 目录或文件 | 内容 |
| --- | --- |
| [phase1/input_review.json](phase1/input_review.json) | 55条输入判断。 |
| [phase1/input_seal.json](phase1/input_seal.json) | 原有工具生成的收据，封存时间早于回答交付。 |
| [phase1/input_reading_log.json](phase1/input_reading_log.json) | 阅读声明与275槽/140去重文本映射。 |
| [phase1/trace.json](phase1/trace.json) | 可见执行轨迹，含完整文本呈现；不是私有系统上下文。 |
| [phase2-initial/claim_review.json](phase2-initial/claim_review.json) | 首次完整172主张判断，时间元数据尚待澄清的原稿。 |
| [phase2/claim_review.json](phase2/claim_review.json) | 最终接收表；仅补齐收据时间元数据，55条评分行与原稿完全相同。 |
| [metadata_clarification.md](metadata_clarification.md) | 收据sealed_at到表单字段的映射澄清，无作者标签或语义反馈。 |
| [phase2/output_context.json](phase2/output_context.json) | 暴露声明、阶段完成时间与元数据澄清说明。 |
| [phase2-initial/trace.json](phase2-initial/trace.json)、[phase2/trace.json](phase2/trace.json) | 回答复评和纯元数据澄清的可见轨迹。 |
| [coordinator/intake-snapshot/intake_report.json](coordinator/intake-snapshot/intake_report.json) | 实际接收报告的逐字节Git备份。 |
| [coordinator/comparison_summary.json](coordinator/comparison_summary.json) | 与原作者判断的端点分歧，未自动裁定。 |
| [coordinator/focal_cases.json](coordinator/focal_cases.json) | 原三条发现案例的复评主张连接；选择注记不算新盲评分。 |

coordinator目录含作者比较资料，未提供给本评审，不可作为未来未暴露评审的输入。后续新盲审应另开会话，重新审计上下文和交付顺序。

## 阅读与复核

```sh
python3 -B scripts/verify_isolated_cli_review.py
```

从项目根目录运行该命令，只核对已保存文件、原文引用、时间连接、可见文本呈现和计数，不写文件或调用模型。评审生成的Python程序保存为判断形成过程的证据，不作为覆盖当前封存结果的运行入口。

实际接收run为 `runs/qwen2.5-3b-semantic-claim-review-intake-cli20261106r01-v1`，四JSON受runs忽略规则管理。本包coordinator/intake-snapshot保存这四个文件的相同字节，连同原始评分和审计数据纳入Git；原无提交run的0保持历史快照。

## 解释边界

本包提供一次未识别到项目历史暴露的LLM复评。上下文自述、目录检查、工具轨迹与输入封存支持可观察的流程隔离，不证明全部私有上下文来源、语义真值或模型错误彼此独立。目录分开也不是操作系统级禁止访问原项目；实际记录中未观察到原项目路径读取。

155与172主张是不同拆分下的实例数，不能直接比较支持率；55条也是按目的选择的材料，不估计总体错误率。接收工具保留context_audit_pending、独立批准0、formal_gate=false，不因收件完整自动认证。原作者结果、独立空表、一次拟合预算0及380题封存保持。
