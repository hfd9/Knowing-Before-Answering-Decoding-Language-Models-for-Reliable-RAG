# 2026-10-21：原48条输入的冻结chat L28联合对照准备

日期与时区：2026-10-21，Asia/Shanghai。
状态：prepared_not_started_cpu_verified；实际3B前向0、回答新增0、拟合0。
操作者：当前助手准备与CPU核验；GPU启动继续由用户执行。

## 用户要求与固定范围

用户认可将48条虚构实体绑定视为M3的一个行为边界工作包，并要求直接开始后续、做好记录。本轮准备同批输入—冻结probe读出—实际行为联合对照。原48采集明确没有保存隐藏状态或probe结果，因此需要新增48次输入侧前向，不重新生成回答、不新增场景、不拟合探针。

新增[补充协议](../../prompts/behavior_binding_probe_v1.json)、scripts/behavior_binding_probe.py、用户入口scripts/run_behavior_binding_probe.sh与[运行说明](../behavior_binding_probe.md)。只读取原冻结chat L28校准探针，哈希db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d；不比较后来一次作者参照重训的probe，不调层、阈值、校准或参数。

固定原12场景×S/I×v1/v2共48，原顺序及前4smoke不变，4条包含在48。技术smoke不设语义成绩门槛。原问题、五文档、自由回答指令、native chat模板、提示及token IDs均与原实际回答记录逐项比对，作者目标值/行为字段/答案不会拼入输入。BF16/SDPA、batch1、eval，只执行decoder prefill，use_cache=true对应原生成首次输入处理；不调用LM head或generate。复用LastPromptCapture保存36×2048 FP16，仅读取冻结L28，不扫描层。

## 测量与分析身份

原回答及评分已经查看。本轮是事后重算的生成前输入状态，不是原回答生成时同步记录的probe决定；原绑定状态不存在，无法做同输入数值桥接，不能声称逐位复现原生成轨迹。小型CPU Qwen检查只验证状态定义与HF一致，不当作本机3B GPU实测。

联合分析预先固定48行明细、24组S→I、24组干扰v1→v2、12场景四格；全部保留，不按预测/S成功筛底题。报告作者参照2×3混淆计数、完整分母一致计数、三概率差、类别变化、S/I双端及四格一致计数，以及I按probe类别分组的既有作答计数。空条件分母比率null，不计算独立语义Accuracy/F1、bootstrap或显著性检验。

沿用封存的五行为字段和完整回答，不自动重新评分。48个具体引用归属unknown仍为unknown，不计引用错误或成功；本批主行为已全部正确，补读出不能创造“可靠读出且不当行为”的案例。即使全一致，也仅限一个英文句型的12场景，不能外推自然文档迁移、校准可靠性或因果使用。

## 已完成CPU检查与准备产物

12项新CPU测试通过，unittest运行10.517秒；覆盖48完整完成/只读重放/重复入口不重载模型、正常提交前缀续跑、未提交attempt停止、smoke坏状态停止、缓存身份/概率/阶段/token/特征篡改、孤立特征、未完成不能分析、完整48/24/24/12连接、引用unknown和零分母、错误probe仍保留正确行为，以及真实tokenizer48输入和小型CPU Qwen状态定义。旧套件未重跑。其后增加的模型metadata/36×2048前置一致性检查由真实prepare路径核对。

新run为runs/qwen2.5-3b-behavior-binding-probe-v1，冻结6准备文件（另锁）：protocol、specification、preflight、materials/inputs、source/behavior_rows、source/preserved。实际48提示238–249tokens，总11688；20实现、12来源、旧probe及完整2分片权重/metadata按原冻结来源核验。准备阶段没有states、features、forward_attempts或新结果报告。

另写独立实现从原P0模板与tokenizer重建48提示/token身份、原mapping/评分/完整回答连接，全部一致；48引用unknown保留。1007个既有路径字节匹配，含原run66文件且集合不变，旧926路径和一次拟合声明未改。[独立实现核验](2026-10-21-behavior-binding-probe-preparation-verification.json)保存6产物哈希；这里独立指程序实现复算，不是独立语义评审。

真实prepare在旧输出缓存的逐token词表大小查询处耗时数分钟；另起只读诊断的20秒堆栈确认调用位于transformers tokenizer.__len__，随后中止该诊断（exit130，无写入）。最初prepare已完整写出6文件并输出prepared_cells48/committed0后，收到中断返回130；没有模型前向或未提交attempt。当前保留已冻结版本及旧执行器，不为性能改变指纹；后续以异进程只读verify及独立重建确认完整准备状态，实际退出码另见机器记录。

最终实际`PYTHONHASHSEED=211 sh scripts/run_behavior_binding_probe.sh --stage verify`正常exit0，输出prepared_cells48、committed_new_forwards0、new_answers0、new_fits0；6冻结文件逐字节重建一致，未写入新产物。独立实现核验在记录维护后再次重放exit0，1007路径及6准备产物哈希仍匹配。完整命令、退出状态与范围保存于[机器记录](2026-10-21-behavior-binding-probe-preparation.json)。两Python AST、补充JSON、shell语法与差异格式检查通过；只完成准备，不登记新的实验成绩。

## 启动、续跑与后续核验

历史39次prefill秒/token与输入容量推导4–11分钟，不含旧CPU缓存检查额外开销；完整入口建议预留10–20分钟，非新3B实测。沿用2026-10-11分工，不能保证低于10分钟的GPU任务由用户启动，当前助手不自动启动。

```sh
sh scripts/run_behavior_binding_probe.sh
```

日志：runs/qwen2.5-3b-behavior-binding-probe-v1/launch/prefill.log。正常提交前缀中断后同命令继续；未提交attempt、孤立特征或损坏需检查，不能删marker重跑。每格先存attempt，再前向、保存特征、提交states；已提交格不重复计算。默认完成48后自动生成预固定描述性联合JSON及4套CSV/JSON。

完成后只读核验：

```sh
sh scripts/run_behavior_binding_probe.sh --stage verify-results
```

原一次拟合预算仍0、独立语义批准0/正式gate=false/正式标签null、380封存保持。旧40独立语义复核和更广泛迁移可靠性仍未解决，不借补充诊断重开原240/一次拟合设计，不因结果全好或全坏追加网格、调参或patching。同步交接、索引、活动日志与运行说明；仅准备不新增experiments登记，未提交推送。
