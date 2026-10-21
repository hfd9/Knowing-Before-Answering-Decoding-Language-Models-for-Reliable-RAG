# 2026-10-21：用户同意v5探索性GPU采集，准备核验完成待用户启动

状态：exploratory_collection_prepared_verified / user_launch_pending / actual_GPU0。

用户在明确“不需要本人重新审240条”、本次先采集且不把作者复核作为独立标签后，回复“行直接开始运行吧”。沿用其上一条“要用gpu我来跑”及长期GPU分工，本轮助手完成实现、协议、CPU检查和时间规划，交由用户启动GPU。没有再次索要外部评审或批准。

## 明确另存的研究顺序调整

修订声明为[prompts/semantic_transfer_exploratory_collection_v1.json](../../prompts/semantic_transfer_exploratory_collection_v1.json)，绑定原冻结设计与v5材料协议SHA256。它允许在独立语义审核前进行这次探索性采集，保持原正式实验门禁、协议、标签及执行器原样。新目录的collection_allowed=true，independent_semantic_approval=false；原formal_gpu_launch_ready仍false，两者不可混称。

输入固定为同一30底题240条v5材料，A/B及S/K/I/C、问题/背景/分区均未改，最多240次生成。只读冻结chat L28旧probe并采集生成前状态、原始token/回答、概率和结束标记；原chat指令、BF16/SDPA、greedy、128-token上限保持。探针不反馈给生成器，无语义训练、开发触发、选层/校准、patching或380保留题访问。

原96条eval分区ID仅保留来源身份：这些输出采集后，不再是原先“独立预审完成后才揭示”的前瞻评估。以后若另有语义/行为评分，须单独保存时间、暴露及来源；不能把这些缓存改称原正式实验、独立确认，或自动再生成另一批240条。扑克四unknown与13组A/B细节风险继续保留。

## 启动、日志与续跑

在项目根目录执行：

```sh
sh scripts/run_semantic_transfer_exploratory_collection.sh
```

这是给用户的实际GPU入口。脚本先只读核对已准备协议，然后在同一240条中生成前4条技术smoke，通过后继续剩余236条，完成后重放全部缓存并导出技术汇总与未评分行为包。不会额外生成smoke或拟合probe。默认run为runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1。

运行日志：`runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/launch/collection.log`。查看进度可运行：

```sh
tail -f runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/launch/collection.log
```

普通中断或GPU空闲保护阻止后，原命令复用已提交的前缀。每条在生成前写attempt，保存状态/回答后提交预测；存在尚未提交的attempt时，入口在下一次模型加载前停止，需要核查原产物，不删除marker或自动重答。GPU有活动计算进程则在模型加载前退出并报告进程信息，不干扰已有任务。

预计预留30–120分钟，依据旧chat生成速度及满30720输出tokens预算作容量规划，非本轮实测。用户运行之前，本轮实际GPU前向/答案0。不要修改运行中依赖或输出。

## 同批技术smoke与完成条件

冻结前缀为stv01_B_S（最长输入）、stv16_A_I（最短输入）、stv17_A_C（修订扑克冲突）、stv01_A_I（第一题缺关系）。选择仅依据已冻结CPU长度和材料元信息，不看新probe输出；四条均在原240内，后续按原材料顺序补齐其余236条。

smoke要求4条非空、EOS结束且无128-token非EOS触顶。失败保留输出并停止，不放宽预算、不改变提示、不以空/截断当拒答，不自动重新生成相同样本。完成报告对其余样本如实计数空/触顶，保留原输出；不把结束标记等同语义正确性。

每条保存旧probe首token前回调判断、三概率、36×2048 float16状态及SHA256、原始token/文本/结束标记、提示哈希和耗时。续跑和完成核验重建提示/token、状态形状/非零/有限值、原输出、旧probe概率与attempt前缀，拒绝改动或缓存乱序。全部240完成才导出`reports/collection.json`、`completion.json`及七字段全unknown的行为审核包。汇总只含技术计数和整体probe预测分布，semantic_accuracy/MacroF1/实际行为率均null，不能解释成可靠性结果。

完成后只读核验：

```sh
sh scripts/run_semantic_transfer_exploratory_collection.sh --stage verify-results
```

## 本轮实际CPU操作与证据

新增scripts/semantic_transfer_exploratory_collection.py、shell入口及7项CPU测试；复用已冻结v5 CPU绑定及旧生成/缓存函数，无修改旧源码。实际执行下列两条均exit0，verify为独立进程/PYTHONHASHSEED=71：

```sh
sh scripts/run_semantic_transfer_exploratory_collection.sh --stage prepare
sh scripts/run_semantic_transfer_exploratory_collection.sh --stage verify
```

新目录只保存5个准备文件：protocol.json、collection_authorization.json、collection_plan.json、approved_labels.json、preflight.json。240正式标签仍全null；240条提示/长度与v5逐项相同，341–3055tokens，总323081，20实现/24来源指纹。完整权重哈希沿父准备核对，模型/旧probe未反序列化。

先跑新7项，含导入8.239秒通过；再跑新7+v5绑定6+核心16+验收6，共35项相关CPU测试通过，含导入11.916秒（unittest报告11.560秒）。覆盖显式修订/零训练约束、目录隔离、同240预算、完整模拟240生成/完成/续跑、概率篡改拒绝、四条smoke失败停止及重复运行不重答、未提交attempt停止模型重载、未完成不导出报告、七字段空行为包与正式门禁不变。测试中的240输出是临时合成状态/模拟模型，均不属于真实GPU采集。旧53/120全套未重跑。

另以独立代码核对240唯一ID/同批前缀、240提示/token一致、零训练/null标签、实际predictions/attempt目录尚不存在，以及[366旧路径保存清单](2026-10-21-semantic-transfer-exploratory-preparation-preserved.json)全部哈希。输入计划见[240行CSV](2026-10-21-semantic-transfer-exploratory-preparation-inputs.csv)；原CPU日志/CSV位于runs/qwen2.5-3b-semantic-transfer-exploratory-v5-preparation-audit-v1，机器检查、源码和产物哈希见[结构化记录](2026-10-21-semantic-transfer-exploratory-preparation.json)。

当前探索性GPU入口已就绪，尚待用户启动；不再把独立评审缺失作为这条已授权采集的启动门槛。正式独立标签/语义覆盖仍0，原90%要求和正式GPU门禁未变。当前不产出新迁移准确率、行为率、机制或因果结论。未提交推送。
