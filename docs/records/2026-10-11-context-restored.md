# 2026-10-11：恢复项目背景与当前产物状态补充

检查采样时间与时区：2026-10-11 11:17:08，Asia/Shanghai（UTC+8）；文档随后写入。
状态：背景恢复 verified_complete；行为审核未完成；分类结果待核验。
操作者：助手。

## 目标与背景

用户要求按根目录 [AGENTS.md](../../AGENTS.md) 恢复项目背景。
读取入口、记录索引、[最新生成核验](2026-10-09-free-answer-generation-verified.md)、
[背景交接](2026-10-09-project-context-and-records.md)、
[实验计划](../evidence_behavior_plan.md) 和 [运行说明](../evidence_behavior_run.md)。
恢复研究主线、诊断集/确认集边界及用户启动长期 GPU 实验的协作约定。

## 实际操作

- 执行 git status --short，发现已有文档修改及 10 月 9 日未跟踪记录，保留其内容。
- 使用 rg --files 列出 runs/ 轻量文件，读取现有 behavior.md；未加载激活数组或整批原始回答。
- 用 kba-rag Python 只读统计 plain/chat test 清单、部分标注 CSV 和默认分类目录。
- 调用现有 scripts/free_answer_review.py 的 load_annotations 在内存中校验 CSV，未写入报告。
- 追加本记录，更新 AGENTS.md、记录索引与活动日志；不更新 experiments.csv。

## 证据、检查与产物

- plain/chat 的 test/predictions.json 各有 300 条 records；本次仅确认保存条数。
  2,370 个特征及探针的完整核验沿用 10 月 9 日记录，本次未重复执行。
- runs/qwen2.5-3b-classification-grid 已有 protocol.json、preflight.json、audit.json；
  未找到该目录下的 predictions.json 或 reports 产物。文件时间分别显示准备产物保存于 10 月 9 日约 14:50。
  其他路径与命名未全面搜索，不能断言所有分类实验均未运行。
- 自由回答根目录 annotations.csv 不存在；review/annotations_codex_semantic_v1.csv 存在，
  文件时间为 10 月 9 日 14:55:07（仅作为文件时间，不推断操作历史）。
- 该 CSV 共 600 行，40 行至少一项为 yes/no，其中 30 行五项均已判断；其余 560 行全 unknown。
  40 行 reviewer 为 Codex-LLM-semantic-v1。批次、ID、值域、reviewer 与字段一致性检查通过。
- 审核 manifest SHA256：777016f545c8c23ea7174fb25039aae52fa7988caec9726e3ab9c82bec9274d0，
  与 600 行 CSV 的 review_manifest_sha256 一致。
- 现有 behavior.md 的全部行为比例仍显示待审核和未知边界，尚未反映这份部分标注。

## 结果与解释边界

背景恢复完成；发现旧交接之后新增的分类准备文件和部分标注进度，已同步当前入口。
格式和批次校验不证明标注语义正确，本次没有审核问题、证据与回答，也未验证盲审过程。
不能把这份文件视为完整行为审核，不能从报告中的零已确认分子推断模型未作答。
本次无新 GPU 实验、无新行为指标；未执行 analyze，未改代码、协议、标注或运行产物。

## 未完成项与下一步

1. 接续并复核部分语义标注，通过 blind_review.html 审核余下回答，保持 item_id 和批次哈希。
2. 标注汇总至根目录 annotations.csv 或使用 --annotations 指定路径，再运行分析；未知项保留分母及边界。
3. 核验是否存在其他分类运行目录；长期 GPU 实验继续由用户启动。
4. 保留 380 个确认集底题；不足和冲突分别分析，尚不启动因果干预。

## 索引更新

更新 docs/records/README.md、AGENTS.md 和 docs/activity_log.md。
保留历史快照及已有未提交修改；本次未提交、推送或发布。
