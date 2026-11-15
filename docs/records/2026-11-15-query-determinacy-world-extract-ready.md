# 2026-11-15：模型提取可能值组件GPU准备

记录时间与时区：2026-11-15，Asia/Shanghai。状态：prepared_not_started；操作者：助手完成CPU准备，GPU待用户执行。

依用户持续推进要求，在[已知世界对照](2026-11-15-query-determinacy-oracle-results.md)及[固定模板CPU重放](2026-11-15-query-determinacy-template-world-replay.md)后，准备[模型提取两个可能值的开发测试](../review/2026-11-15-query-determinacy-world-extract-dev-v1/README.md)。复用12个已暴露虚构底题的双来源/双候选背景、删除问题列去重，共24输入；文本明示两个值和穷尽规则，不代表自然源文档。模型按文本顺序输出两个JSON字符串；本轮仅检验提取组件，不自动声称完整问答或RAG方法。

先固定[JSON解析与评分](../../scripts/query_determinacy_world_extract_parser.py)和[聚合](../../scripts/query_determinacy_world_extract_evaluate.py)：exact_order、correct_reversed、incorrect、invalid、T分别计数，另外报告无序集合正确，格式不事后放宽。独立文本解析程序复核24来源/参考和12×2形式，但与构造器均为同一知情助手。3项CPU测试覆盖解析、逆序/错误/格式、24行模拟与失败传播及24次模拟生成截断留痕。7模型文件SHA和清单重建一致，token 120–147，inspect为0 attempts/records；[清单](../review/2026-11-15-query-determinacy-world-extract-dev-v1/manifest.json) SHA `cb0ab4c89841c752807d34bed5dd42be91092f41d32d4b8b0b4df13ad442e1a8`。前4技术smoke覆盖两题族与两来源形式，空/无EOS即停；之后失败留痕继续、不重答，结构异常停止。

用户从项目根执行 `sh world_extract.sh`，建议预留10–25分钟仅规划；结束或报错后先核验源/输入/token再用冻结规则分析。本轮未用GPU或产生回答；原v1/E1-r1 gate=false、正式独立批准0、标签null、原拟合预算0、380封存，不训练/阈值搜索/patching。既有四处暂存与未跟踪材料保留；新报告、源码、材料及记录单独提交推送。
