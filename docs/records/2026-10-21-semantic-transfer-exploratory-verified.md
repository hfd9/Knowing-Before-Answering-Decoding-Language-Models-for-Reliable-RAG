# 2026-10-21：v5探索性采集240条完成并通过只读核验

状态：exploratory_collection_verified_complete / not_semantically_validated。

用户报告“应该跑完了”并要求检查。本轮确认实际240回答/240状态/240已提交attempt全部保存，完成标记与报告齐全；运行已完成，无需重跑GPU。原准备记录中的GPU0/待启动是历史快照。本轮仅CPU只读核验并另存记录，没有再次生成、训练或给240回答评分。

## 实际完成情况

| 项目 | 独立复核结果 |
| --- | --- |
| 输入/回答 | 240/240，240个唯一ID，顺序与冻结计划完全相同 |
| 技术smoke | 4/4通过，均在上述240内，无额外生成 |
| 生成attempt / 状态文件 | 240 / 240，均与已提交回答逐项对应，无未提交attempt |
| 空输出 | 0 |
| EOS结束 | 240/240 |
| 128-token非EOS触顶 | 0 |
| 总输入 / 输出tokens | 323081 / 9038 |
| 失败记录 | 无last_failure.json，日志无Traceback/Error/failed |
| 新probe拟合 | 0 |
| 独立批准语义标签 | 0 |

首条回答保存于北京时间2026-10-21 09:45:31.432036，末条为09:52:49.525674。逐条生成耗时合计436.186秒，约7分16秒；由首条结束时刻减去其生成耗时估计，首个推理开始至最后保存约441.381秒，约7分21秒。这些数值不含最初CPU预检查和模型加载，不能当完整shell命令墙钟时间。原30–120分钟为满输出容量规划，本次实际输出9038、低于30720满预算。

旧chat L28预测分布为answer98、refuse22、conflict120。这只是预测类别分布；没有独立语义标签，不能据此判断正确率、冲突识别可靠性或实际回答行为。没有用作者116/60/60/4unknown作为金标准计算Acc或MacroF1。

## 实际只读核验

执行以下已有入口，PYTHONHASHSEED=83，exit0：

```sh
sh scripts/run_semantic_transfer_exploratory_collection.sh --stage verify-results
```

该入口重新核对完整两分片权重/模型元信息、真实tokenizer、全部240提示/token、旧probe来源、240缓存/状态/概率、attempt前缀、smoke与完成报告及行为导出。未加载大模型，未调用generate或fit；只在CPU加载旧probe做概率重放。20实现/24来源指纹全部一致。

另以独立CPU代码逐项复核：

- 全部状态均为36×2048 float16，有限值、无全零层，240个文件哈希匹配。
- 从保存的L28状态直接经冻结scaler/router重算三概率，240条最大绝对误差为0.0；类别、层号和首token前决策标记匹配。
- 原始token长度/EOS位置、文本哈希、输入长度/提示哈希、五文档身份和attempt协议哈希全部一致。已有入口另重放真实解码文本。
- 日志恰有1至240连续保存记录，无重复或缺项；completion保存的协议/预测/汇总/计划哈希全匹配。
- [准备时366旧路径清单](2026-10-21-semantic-transfer-exploratory-preparation-preserved.json)全部SHA256一致，5个准备产物也未改。核验前后原运行目录495个文件的集合和字节哈希完全相同。

逐项结果保存在[240行核验CSV](2026-10-21-semantic-transfer-exploratory-verified-cells.csv)，原运行文件清单为[495文件哈希](2026-10-21-semantic-transfer-exploratory-verified-run-hashes.json)。CSV只列技术状态、读出/概率、时间和原文哈希，不新增语义或行为评分。机器汇总、完成标记、全部复核值及证据哈希见[结构化记录](2026-10-21-semantic-transfer-exploratory-verified.json)。

核验日志、独立计数及CSV副本另存runs/qwen2.5-3b-semantic-transfer-exploratory-verified-2026-10-21-v1，原run不写入。代码未修改，本轮未重跑单元测试；此前同版本35项CPU证据保留，不能当本轮新增测试或GPU结果。

## 行为包与研究边界

240项行为包已生成，协调映射是完整双射，逐项问题/五文档/回答与原产物相同。公开packet只含匿名ID、问题、文档和回答，隐藏probe/输入标签/条件/分区。240评分行仍全unreviewed，七字段共1680项unknown；这些是尚未评分，区别于旧40条已审仍保留歧义的unknown。当前没有实际行为率。

本批是在用户明确顺序修订下、独立语义审核前完成的探索性采集。独立标签仍0，原正式门禁未改；原96eval的结果现已采集，不能再称原计划预审后才揭示的前瞻确认。未做新probe训练/开发触发、因果干预或380保留题访问。

下一步为离线复核现有240回答的实际行为，评分须明确记录来源、时间和历史暴露；无需新GPU生成，不自动重生第二批240或训练新probe。已更新交接/索引/活动日志与实验登记；本轮未提交推送。
