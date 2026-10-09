# 2026-10-09：项目交接入口与实验/动作记录整理

记录时间：2026-10-09T10:58:10+08:00（Asia/Shanghai）。
本次文档动作状态：verified_complete。自由回答实验状态：running（用户报告，部分产物已观察）。
操作者：用户启动 GPU 实验；助手整理文档并做只读检查。

## 目标与实际操作

用户正在运行 `sh scripts/run_free_answer_study.sh`，要求项目中有一个助手开头读取即可恢复背景和文件位置的入口，
以及集中保存实验、动作记录的文件夹。

- 新建根目录 [AGENTS.md](../../AGENTS.md)：读取顺序、研究目标、已知结果、当前状态、文件地图、环境、协作方式及下一步。
- 沿用本目录 `docs/records/`，新建 [README.md](README.md) 索引和 [TEMPLATE.md](TEMPLATE.md) 记录模板，保留四份历史 JSON。
- README 增加入口；docs/activity_log.md 更新当前交接摘要并追加本次动作。
- 约定后续助手每次有实质工作后追加记录并更新索引；已完成且核验的指标才登记 experiments.csv。

本次未修改实验脚本、配置、协议或运行输出，也未启动其他 GPU 实验。

## 只读状态快照

以下是记录时的一次采样，会随正在运行的任务推进；不能当作最终完成情况。

- `runs/qwen2.5-3b-free-answer-study/plain/train/states.json`：当时已保存 600 条。
- `runs/qwen2.5-3b-free-answer-study/plain/val/states.json`：当时已保存 285 条。
- `runs/qwen2.5-3b-free-answer-study/chat/train/states.json`：当时已保存 160 条。

- 默认分类正式目录 `runs/qwen2.5-3b-classification-grid`：未发现；不能据此排除用户用了其他 run_dir。
- 本地 HEAD 本次读到 `35fd098`（300条测试集复线）。四条件/自由回答代码及本次文档尚有未提交修改。
- 旧路由器和旧提示词结果沿用既有核验记录，本次未生成新结果。

## 结论与下一步

新会话先读 AGENTS.md → 本目录 README.md → 最新交接记录，再按任务读取计划和运行说明。
不用每次先加载两份约 200 KB 的完整历史 JSON。

当前先让用户的自由回答任务继续。结束后检查两个格式的 train/val 状态、probe 和 test 原始回答是否齐全，
再处理盲审标注与 behavior 报告。未经审核不能把生成完成等同于最终行为结果。
随后核验四条件分类是否已经在其他目录完成；不足和冲突分开分析，再决定确认集或干预。

## 验证

本次仅改文档，检查 Markdown 本地链接、历史记录保留、文档空白和运行代码未被本次修改。
实验代码此前 22 项测试通过的证据见 [准备快照](2026-10-09-evidence-behavior-preparation.json)；本次不把它记作新实验结果。
