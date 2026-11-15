# 2026-11-15：新底题查询可判定性开发准备

记录时间与时区：2026-11-15，Asia/Shanghai。状态：prepared_not_started；操作者：助手完成CPU准备，GPU待用户执行。

按用户持续推进约定，在[同题提示对照结果](2026-11-15-query-determinacy-prompt-control-results.md)后准备[新底题开发试验](../review/2026-11-15-query-determinacy-fresh-dev-v1/README.md)。4新虚构数值底题+4新虚构原子代码底题，每底题3问×4条件×2提示共192输入；各题族显示顺序2/2，数值分歧在world_a的方向2/2，代码分歧world_a均为是、显示顺序2/2，方向不完全平衡。显式规定代码互异且无包含/同义以处理旧类别歧义。材料由看过旧结果的助手设计、题型和提示家族复用，非独立确认集；单世界、双世界答案一致/分歧分母、两表达及两提示均保留。

[生成器](../../scripts/query_determinacy_fresh_material.py)与[文本解析器](../../scripts/query_determinacy_fresh_audit.py)检查全部世界值、192答案与48个四条件组；另逐项检查96对提示的前三行、世界及参考相同。二者同助手编写，非独立语义审核。3项CPU测试覆盖实际材料重建、篡改参考/世界拒绝及192次模拟含留痕不重答；复用核心smoke与未提交attempt阻断测试已通过。真实token 68–150，7模型文件SHA匹配历史快照，清单从现场重建一致；[清单](../review/2026-11-15-query-determinacy-fresh-dev-v1/manifest.json) SHA `cd2a639dd5f6605f1727d933c4f7bcd1a2e1d5cb430d5e3ea577e0e388daf669`，inspect 0 attempts/records/192。前4技术smoke覆盖两题族、两提示、单双世界，失败停止；后续空/无EOS留痕继续，结构异常停止。原生chat、greedy、BF16、SDPA、384新token；未访问GPU或加载权重。

用户在项目根目录执行 `sh fresh_dev.sh`，完成或报错后助手核验并评分；建议预留20–45分钟仅规划。保持原v1/E1-r1门禁false、正式独立批准0、正式标签null、原拟合预算0、380正文封存；不训练/阈值搜索/patching。四处既有暂存和旧未跟踪材料保留；本轮代码、材料和各部分记录单独提交推送。
