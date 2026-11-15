# 2026-11-15：查询可判定性开发方案及用户GPU准备

记录时间与时区：2026-11-15，Asia/Shanghai。状态：prepared_not_started；操作者：助手完成CPU准备，GPU等待用户执行。

## 目标与材料

用户明确要求持续推进至需要用户GPU或额度耗尽，逐部分记录。沿选定主线固定[任务及评分合同](../review/2026-11-15-query-determinacy-development-v1/CONTRACT.md)：同世界集合下，区分答案一致和分歧，并用单世界对照定位基础错误；两种双世界措辞作为探索对照。新开发材料6虚构底题×3问题×4条件=72输入，当前助手构造且已暴露，不是确认集。三数值/三类别，来源顺序每族2:1，虚构简化分布不代表自然RAG。

## CPU检查与运行准备

[材料生成器](../../scripts/query_determinacy_dev_material.py)与[独立文本解析核验](../../scripts/query_determinacy_dev_audit.py)分别构造和复算；72参照、18个四条件组、两世界及问题配对一致，两实现均为知情助手开发而非独立语义审核。新[运行器](../../scripts/query_determinacy_dev_run.py)绑定清单/材料/实现/7模型文件，72真实token 78–115；随机种子19517，greedy/384、BF16、SDPA。清单从现场CPU重建完全一致；[清单](../review/2026-11-15-query-determinacy-development-v1/manifest.json)哈希 `7309be6174b484ccd9307a7f369d1cc67777b5a2643bebadba01b01b3cdf86a5`。合同哈希在入口报告列明，运行器不检查合同文件。

4新测试覆盖真实材料与篡改、72模拟含截断与无重答、未提交attempt和smoke失败阻断，另复用2项旧自动继续测试通过；实际inspect 0 attempts/records/72。前4 smoke计入72且失败停止，之后技术缺失留凭据继续，结构异常停止；无真实生成、GPU、模型权重加载或评分。入口、估时和失败处置见[说明](../review/2026-11-15-query-determinacy-development-v1/README.md)。建议用户预留20–45分钟，仅容量规划非实测。完成或失败后先核验再评分，不删除run或重答。

## 边界与记录

原v1/E1-r1 gate=false、正式独立批准0、正式标签null、原拟合预算0、380正文封存，不训练/阈值搜索/patching；用户批准探索不等于原协议放行。保留原四处暂存交接与未跟踪旧材料，本次新文件单独提交推送；现有共享索引不改。结果和实时Git以实际核验为准。
