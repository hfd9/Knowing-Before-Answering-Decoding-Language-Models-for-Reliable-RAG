# YYYY-MM-DD：动作或实验主题

记录时间与时区：
状态：prepared / running / generation_complete / review_complete / verified_complete / failed
操作者：用户 / 助手

## 目标与背景

用户要求、本次要解决的问题、相关前序记录链接。

## 实际操作

修改了哪些文件、为什么修改；执行了哪些命令，哪些只是提供给用户尚未执行。
实验填写模型完整名称、输入模板、解码设置、train/val/test 规模、种子及 run_dir。
沿用已冻结协议时链接 protocol.json，不重复抄录全部配置。

## 证据、检查与产物

写明证据来源：用户报告 / 助手只读检查 / 实际执行。
列出结果文件路径、必要的哈希、检查或测试结果。
进行中快照标注采样时间；不要把快照进度写成完成状态。

## 结果与解释边界

仅填写已经完成并核验的指标。写清分母、invalid/unknown 处理、验证与测试角色。
准备记录可写“未启动推理、没有新指标”；生成完成但未审核则写“行为指标待审核”。

## 未完成项与下一步

剩余步骤、当前运行任务、下一次助手应先查看的文件和可直接执行的命令。

## 索引更新

更新 docs/records/README.md；同步 AGENTS.md 当前状态与 docs/activity_log.md 摘要。
实验完成并核验后才登记 docs/experiments.csv；保留历史快照。
