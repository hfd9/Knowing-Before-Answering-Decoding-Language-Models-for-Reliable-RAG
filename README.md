# Knowing Before Answering: Decoding Language Models for Reliable RAG

This is the official codebase for our paper **"Knowing Before Answering: Decoding Language Models for Reliable RAG"**, accepted at COLM 2026.

Paper: https://arxiv.org/abs/2608.27661

新会话先读 [项目交接入口 AGENTS.md](AGENTS.md)，快速了解研究背景、当前进度、文件位置与下一步。
实验和动作的持久记录集中在 [docs/records/](docs/records/README.md)，新增记录参考 [记录模板](docs/records/TEMPLATE.md)。

本机长期 SSH 推送、首次公钥授权和诊断见 [Git 推送说明](docs/git_push.md)。

本地小规模复现的 Conda 环境、模型路径和验证命令见 [环境配置说明](docs/environment.md)。

隐藏状态三分类路由器的运行命令、抽样设置和结果位置见 [小规模复现说明](docs/small_reproduction.md)。

同一批测试实例上的提示词三分类对照、断点续跑和分析命令见 [提示词基线说明](docs/prompt_baseline.md)。

后续四条件 chat/plain 对照、同模板自由回答探针和行为盲审见 [实验计划](docs/evidence_behavior_plan.md) 与 [运行说明](docs/evidence_behavior_run.md)。

此前的操作、问题处理、实验结果和后续待办见 [项目活动记录](docs/activity_log.md)，实验指标登记在 [experiments.csv](docs/experiments.csv)。
