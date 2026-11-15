# 2026-11-15：已知世界组合方法的开发性GPU准备

记录时间与时区：2026-11-15，Asia/Shanghai。状态：prepared_not_started；操作者：助手CPU准备，GPU待用户执行。

按用户持续推进授权，基于[事后离线规则组合](2026-11-15-query-determinacy-offline-world-aggregation.md)准备[新开发对照](../review/2026-11-15-query-determinacy-oracle-dev-v1/README.md)。12虚构底题（6数值/6原子代码）×3问题×4条件=144输入；其中每题的两个单世界结果用固定规则组合，另分别比较双来源/双候选直接回答。两个可能世界由题目构造者给定，方法需要两次模型调用，不测真实来源世界抽取，不是成本匹配或端到端RAG确认。题型、提示家族复用，由看过结果的助手设计，非独立确认材料；数值分歧world_a是/否3/3，代码world_a均为是、显示顺序3/3。

[解析器](../../scripts/query_determinacy_oracle_parser.py)与[评估器](../../scripts/query_determinacy_oracle_evaluate.py)在生成前固定并绑定[清单](../review/2026-11-15-query-determinacy-oracle-dev-v1/manifest.json)：仅精确接受是/否/无法确定（首尾空白和至多一个末尾句号或叹号可去），其他完整输出X、技术失败T；分支不确定不得冒充世界分歧。报告逐题结果与全部计划分母，可另做披露的人工诊断，不事后放宽主解析。独立文本解析代码重算144参照/36个四条件组；与构造器同助手开发，非独立语义审核。

4项CPU测试覆盖格式、25分支状态、36问题模拟与失败传播、144条模拟含截断；清单从现场重建一致，7模型文件SHA匹配既有快照，真实token 76–144；inspect 0 attempts/records。清单 SHA `b4202e3f5396a56b86bfc90f0451524a68b3296a51df3a8667547af59a423513`。前4技术smoke计入144，失败即停止；之后空/非EOS留痕继续、不重答，结构异常停止。GPU由用户从项目根执行 `sh oracle_dev.sh`，建议预留20–45分钟仅规划；完成或报错后先核验再按固定规则分析。

本轮无新模型前向、GPU、训练或380正文访问；原v1/E1-r1 gate=false、正式独立批准0、标签null、原拟合预算0、380封存，不自动扩样旧协议、阈值搜索或patching。既有四处暂存及未跟踪材料保留；各部分记录、源码及材料单独提交推送。
