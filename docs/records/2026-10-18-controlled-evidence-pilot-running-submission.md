# 2026-10-18：受控开发试验运行快照与本轮代码归档

记录时间与时区：2026-10-18 14:45:34，Asia/Shanghai。
状态：running_snapshot / commit_prepared；采样时正式自由回答24/40、分类0/40，非完成核验。
操作者：用户启动GPU并明确授权提交推送；助手只读检查共享产物，归档现有修改。

## 记录是否齐全

此前已保存[材料与CPU准备](2026-10-18-controlled-evidence-pilot-preparation.md)、[准备清单](2026-10-18-controlled-evidence-pilot-preparation.json)、40条显式输入判断、来源/修改偏移和[运行说明](../controlled_evidence_pilot.md)。本轮另存[运行JSON快照](2026-10-18-controlled-evidence-pilot-running-submission.json)，保留旧0输出准备快照，不覆写历史。

本次归档包含前一提交65a3f26之后的分类完整核验/独立分析、研究定位、同题证据试验建议/材料/实现/测试/准备记录，以及当前运行快照。提交标识以本记录所在Git提交为准；推送后用git ls-remote origin refs/heads/main核对远端，实际结果在本轮回复报告，不提前写为成功。

## 实际只读检查

- 用户报告正在运行。14:44:34第一次检查：smoke已完成自由4/4和分类4/4、technical_smoke_passed；正式日志显示正在加载模型，尚无首条输出。
- 14:45:34快照：正式progress为running/free_answer，保存24/40，最后ce05_S于14:45:33保存；分类0/40符合顺序执行。24条已保存自由回答无空/触及上限，未见last_failure.json。这些是技术进度，不是语义或行为成绩。
- smoke为analysis_complete_behavior_pending，4+4技术完成，不表示行为已评分，也不表示正式语义门槛通过。
- 两run各18份实现/提示指纹、各5份旧探针来源哈希均匹配；正式与smoke协议哈希分别98650b290d29779242cb4727e43a1625d5fe187bae275c9ed2fb8bdf445baf6f、ca8c52a01df554d88d0fd9164d0ea966309a7dedb19262156c1fd54a7e9c8e52。
- 提交前远端main与本地HEAD均65a3f26ee385e41fef77124494a1d33556cda28c。新增文件检查均位于docs/prompts/scripts/tests，单文件小于1MiB；Python AST、JSON解析、shell语法及git diff --check通过。
- 沿用最终冻结实现已通过的93CPU测试（52.405秒）；当前18实现哈希仍匹配。运行中不重复模型测试或改依赖，本轮仅文件/语法/状态检查。

## 边界、提交与下一步

未修改运行中代码、提示、配置、协议、原始输入、预测或特征；只增加记录并更新交接文档和Git索引。未重启/终止进程、另起模型或查询宿主实时GPU。Git提交不改变当前工作文件内容，runs/按既有忽略规则保留本地产物，不将大数组/权重/整批输出上传。

本轮按用户授权提交并正常推送origin/main，不force push、不改变远端或认证配置。快照是采样时状态，后续先看实际progress/日志，不用24/40推断当前仍未完成。生成完成后再执行正式/smoke完整只读verify及显式行为复核；不将unknown清零、自动打标签或提前写最终实验指标。

## 维护

新增本记录和JSON、更新AGENTS/索引/活动日志；旧准备记录保留。experiments.csv本轮新增内容仅为此前已完整核验的两条语义分类val登记，不登记进行中的受控试验结果。
