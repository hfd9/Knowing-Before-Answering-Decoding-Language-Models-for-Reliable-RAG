# 原48条输入的冻结chat L28补充读出

**后续CPU定位已完成（2026-10-21）：** [校准前后诊断](records/2026-10-21-probe-calibration-diagnostic.md)显示，本批原线性S为answer18/conflict6，旧sigmoid将5个S改成conflict，最终answer13/conflict11；I24条在两阶段均answer。既有240也已同法检查，I类别同样不变，不能以撤销校准修复缺证判定。只读同一旧probe和缓存，没有新GPU/拟合/行为评分；原48回答和引用unknown保持。

**最新完成（2026-10-21）：** 用户完成48前向，完整只读verify-results与独立手算概率核验均exit0，见[结果记录](records/2026-10-21-behavior-binding-probe-results.md)。S读answer13/conflict11、I全部24读answer，没有refuse；原S有据24/24、I不答24/24和48引用unknown保持。S→I不足概率24/24升、均值+10.66pp，不能把三分类失败解释成状态无信息。当前不再需要GPU，后续仅读缓存；下文准备/待启动为历史快照。预算0/正式gate=false/380封存保持。

本补充任务连接已完成的48条虚构绑定行为与旧chat L28探针，不重新生成回答，不拟合探针。原48回答的运行目录、评分、引用、模板与报告保持原样。当前CPU准备已完成，异进程verify exit0，等待用户启动GPU；尚无实际3B前向或本批probe结果。参见[准备记录](records/2026-10-21-behavior-binding-probe-preparation.md)及[机器核验](records/2026-10-21-behavior-binding-probe-preparation.json)，结果必须以实际运行及核验后的产物为准。

用户在讨论后要求直接开始后续工作。新增[补充协议](../prompts/behavior_binding_probe_v1.json)固定原12场景×S/I×v1/v2的48个输入、原顺序和前4条技术smoke（计入48）；只用原冻结chat L28校准探针，SHA256为`db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d`。不比较后来作者参照重训的probe，不扫描层、阈值或参数。

## 测量身份与控制

旧采集明确不保存状态，因此这里必须新增48次输入前向，不能称已有缓存的纯离线分析。原问题、五篇文档、自由回答指令、native chat模板、输入token IDs及其顺序均逐项核对旧实际回答记录；不会把答案、作者参照、目标值或评分拼入提示。

冻结Qwen2.5-3B-Instruct，BF16/SDPA、batch1、eval，执行decoder一次prefill，use_cache=true以对应原生成的首次输入处理。不调用LM head或generate，不生成新token。复用LastPromptCapture保存全部36层最后位置的36×2048 FP16，按既有定义仅读取零基L28；保存全部层供完整性重放，不进行选层。

这是在回答、行为评分已见之后重算的输入侧状态，不能写成原回答当时同步记录了probe决定。原绑定任务没有状态可作同输入数值桥接；不能认证重算与原生成执行轨迹逐位相同。已用小型CPU Qwen验证capture与HF hidden_states定义一致，这也不等于本机3B GPU路径已实测。

前4条技术smoke只检查输入身份、完整非零有限状态、概率及attempt提交，不以S/I预测正确与否决定继续。即使4条全部语义误判，也应保留并继续固定48；缓存损坏或技术失败则停止检查。

## 启动、续跑与日志

沿用2026-10-11的协作约定：不能保证少于10分钟的GPU任务由用户启动。冻结preflight按历史39次prefill的最大秒/token、原11688输入tokens和模型加载/写盘余量给出4–11分钟容量估算；本轮真实CPU准备又发现旧缓存校验逐token重复查询词表大小，需要数分钟。因此完整入口建议预留10–20分钟，包含启动前CPU审核；这不是新3B实测时间。当前冻结版本保留旧校验的所有条件及实现，未为性能修改已封存代码。

在项目根目录启动，正常中断后续跑也使用同一命令：

```sh
sh scripts/run_behavior_binding_probe.sh
```

日志位于`runs/qwen2.5-3b-behavior-binding-probe-v1/launch/prefill.log`。入口读取本地kba-rag与离线权重，调用既有GPU活动进程保护，不与同GPU其他实验争用。默认顺序执行48次前向、技术检查及预固定的描述性联合分析。

每次前向之前保存attempt，成功后保存特征和states记录。仅有完整已提交前缀时跳过已完成输入。未提交attempt、孤立特征、缓存/代码/来源变化会在下一次模型调用前拒绝；不能删除marker重跑。中断若发生于特征或attempt写入后、states提交前，先检查而非直接恢复计算。已完成48后同命令只核验缓存，不重新加载模型。

只读核对CPU准备（无模型前向）：

```sh
sh scripts/run_behavior_binding_probe.sh --stage verify
```

运行完成后另行只读重放全部缓存、概率和联合结果：

```sh
sh scripts/run_behavior_binding_probe.sh --stage verify-results
```

## 冻结的联合分析

| 产物 | 内容 |
| --- | --- |
| protocol.json、specification.json、preflight.json | 原48输入身份、完整模型/实现/来源/probe指纹、测量时序和范围 |
| source/behavior_rows.json、source/preserved.json | 已封存五字段/原回答的只读副本与既有文件哈希保护 |
| forward_attempts、features、states.json | 每格前向attempt、36层状态、L28三概率与类别、完成时间 |
| reports/joint.json | 完整分母的作者参照混淆计数、配对与行为条件计数 |
| reports/cells.json/.csv | 48行输入身份、原回答、原行为五字段、三概率及类别 |
| reports/S_to_I_pairs.json/.csv | 24个S→I配对、双端类别、三概率差与原行为 |
| reports/distractor_pairs.json/.csv | 24个v1→v2配对，分别报告S/I类别与概率变化 |
| reports/base_scenarios.json/.csv | 12场景的四格预测及全部四格是否与作者参照一致 |

S=answer、I=refuse仅为有历史暴露的构造参照，不导入正式标签，不计算独立语义Accuracy/F1。全部48保留；不得依据S是否成功或probe是否正确筛场景。S/I分别列出3类分布，I按probe类别给已有作答计数，空条件子集的比率为null。

具体引用归属沿用旧五字段原值，48项unknown不计引用错误或成功，也不重审改分。实际主行为已全部正确，本批增加读出不能创造“可靠读出且行为不当”的案例；即使两者全部一致，也只支持该简单任务的一致性，不证明自然文档迁移或因果使用。

只报告描述性计数、概率差与完整配对，不新增bootstrap或显著性检验。48格属于12场景、一个英文句型，不当作48个独立场景。原一次拟合预算0，独立语义0/正式gate=false/标签null、380封存保持。旧40独立语义复核及更广泛迁移有效性仍待确认；不因结果全好或全坏自动扩样、重新生成、调参或patching。
