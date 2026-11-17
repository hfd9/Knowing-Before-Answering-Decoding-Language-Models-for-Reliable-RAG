# 2026-11-17：下次恢复后继续改写开发运行

记录时间与时区：2026-11-17，Asia/Shanghai。状态：prepared_not_started，等待用户在GPU空闲后运行；操作者：助手记录，GPU由用户执行。

## 用户意图与停止点

用户要求做好记录，下次恢复项目背景后接着运行这项开发对照。请先读[完整运行说明](../review/2026-11-17-query-determinacy-paraphrase-dev-v1/README.md)和[设备占用记录](2026-11-17-query-determinacy-paraphrase-gpu-busy.md)。用户此前执行 `sh paraphrase_dev.sh` 时报告GPU有计算进程，设备检查在加载模型及写attempt之前停止。

本次CPU只读 `inspect` 为 `valid_prefix`、0 attempts、0 records、96计划、0技术失败；未查询实时GPU。此状态仅为2026-11-17快照，未来恢复时先重新检查实际run状态、用户最新消息和Git；不要假设仍为零或重复已经完成的生成。恢复前本地HEAD及实际远端main均为 `9bc5dbf10e74e790b382b8cc3c0a719024741022`；本记录提交和远端状态以Git为准。

## 恢复后的具体步骤

1. 只读运行 `/large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_paraphrase_run.py inspect`，核对已保存attempt和结果。如果已有输出或报错，先检查、保留run，不自动重答或删除；若已完成，直接核验分析，不重跑GPU。
2. 如果仍是0 attempts/0 records且GPU 0空闲，让用户从项目根运行 `sh paraphrase_dev.sh`。设备检查会再次执行；GPU是否空闲在运行时由用户核实，助手不终止其他进程。建议预留20–45分钟，仅为规划。
3. 用户完成或报告错误后，先核验输入、清单、attempt/record、EOS与失败留痕，归档来源，再按冻结规则分析。24抽取+72直接回答使用旧72单世界缓存做事后连接，不冒称联机端到端或自然RAG；抽取失败对同背景三个问题的影响不能当作三次独立失败。

## 约束与记录边界

原v1/E1-r1门禁false、正式独立批准0、标签null、原拟合预算0、380正文封存；不自动扩样、训练、阈值搜索或patching。此次不运行GPU、模型前向或新评分。工作区先前四处暂存交接改动和未跟踪先导包保留；AGENTS.md、索引及活动日志已有暂存改动，本记录单独提交推送，避免混入既有内容。
