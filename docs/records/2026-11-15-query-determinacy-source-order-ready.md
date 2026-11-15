# 2026-11-15：来源标签与顺序定向控制准备

后续更正：原代码分歧双候选逐值输出由4U修正为3U/1X，详见[来源对照结果](2026-11-15-query-determinacy-source-order-results.md)；下文保留运行前历史快照。

记录时间与时区：2026-11-15，Asia/Shanghai。状态：prepared_not_started；操作者：助手CPU准备，GPU待用户执行。

用户授权持续推进；依据[新底题192条结果](2026-11-15-query-determinacy-fresh-results.md)，4代码分歧题逐值双来源中3无依据选边/1未知，同题双候选均保留。为定位线索，[定向方案](../review/2026-11-15-query-determinacy-source-order-v1/README.md)复用4代码+4数值分歧底题原双来源逐值输入，固定两个版本：只互换资料甲/乙标签，以及保持资料值绑定而互换两句顺序（完整称谓与代词也相应变化）。共16新输入；原双来源/双候选各8输出复用，不重跑。只在已暴露底题上探索提示敏感性，未覆盖可判定问题，不声称因果或总体泛化。

[运行器](../../scripts/query_determinacy_source_order.py)从冻结原材料构造两个版本；3项CPU测试解析并检查原/新来源值映射、其余问题和参考不变、篡改拒绝及16次模拟中失败留痕不重答。代码由同一知情助手开发，不是独立语义评审。真实token 121–142，7模型文件SHA与快照匹配，清单重建一致；[清单](../review/2026-11-15-query-determinacy-source-order-v1/manifest.json) SHA `e611b44bce70dc56fec6f73b2acd32fdf6bd146cba5fdcc91f4aa0593d7ee38b`。实际inspect 0 attempts/records；4技术smoke覆盖两族两种改动，失败即停止，后续截断留凭据继续，结构异常停止。建议预留10–25分钟仅规划；用户在项目根运行 `sh source_order.sh`，结束或报错后助手先核验评分。

本轮无新GPU/前向；原v1/E1-r1 gate=false、正式独立批准0、正式标签null、原拟合预算0、380正文封存，不训练/阈值搜索/patching。保留四处原暂存和未跟踪旧材料；本轮各部分单独提交推送。
