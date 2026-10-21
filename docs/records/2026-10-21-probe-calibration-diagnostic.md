# 2026-10-21：冻结线性判定与sigmoid校准的288条离线诊断

日期与时区：2026-10-21，Asia/Shanghai。
状态：verified_complete；CPU离线分析，无新GPU、前向、回答、拟合或评分。
操作者：当前助手。

用户要求继续刚提出的读出链路诊断并做好记录。本轮对原48虚构绑定与既有240语义迁移分别比较同一旧chat L28探针的原标准化/线性argmax和原sigmoid校准/最终argmax。**缺证类别判定问题在校准前已经存在；校准额外将部分输出推成conflict，但去掉校准也不能修好这两批的缺证判定。** 这只是固定读出计算的定位，不是隐藏状态因果机制或参数记忆结论。

## 固定范围与方法

在查看新的校准前结果前另存[事后分析口径](../../prompts/probe_calibration_diagnostic_v1.json)，固定binding48先、transfer240后；仅使用旧probe db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d、零基L28，读取保存的36×2048 FP16状态。校准内部原线性分类器已存在，原训练代码采用cv=prefit；本轮没有重新训练或重新校准，没有读取后来作者参照重训模型进行预测，也没有修改默认probe。

每条保存原线性三分数、描述性raw softmax、校准仿射分数/未归一化sigmoid及最终三概率，以及两阶段类别、作者参照、原回答与五/七行为字段。raw softmax只用于描述原分数，不当作新的校准置信度。sigmoid各类映射后除以同一个正数不会改变其argmax，观察到的变化发生于各类别不同的映射，而非最后共同归一化。

全部288行保留，240中的4条作者语义unknown不计为正确或错误；原48的48项具体引用归属unknown仍保留。两批使用不同的状态采集时间身份：48为回答已见后的输入状态重算；240为原生成前捕获。所有作者参照/行为已有历史暴露，既有eval已见，不称前瞻确认或独立语义准确率。

## 主要结果

以下为与原作者参照一致的条数，不是独立语义Accuracy；两批不合并为一个成绩。

| 数据及切片 | 总行/确定参照 | 原线性判定一致 | 校准后判定一致 | 校准改对 | 校准改错 | 改变后仍错 |
| --- | --- | --- | --- | --- | --- | --- |
| 虚构绑定全部 | 48/48 | 18 | 13 | 0 | 5 | 0 |
| 绑定S | 24/24 | 18 | 13 | 0 | 5 | 0 |
| 绑定I | 24/24 | 0 | 0 | 0 | 0 | 0 |
| 迁移全部 | 240/236 | 117 | 117 | 5 | 5 | 1 |
| 迁移训练来源 | 96/96 | 43 | 42 | 1 | 2 | 1 |
| 迁移开发来源 | 48/44 | 18 | 18 | 1 | 1 | 0 |
| 迁移评估来源 | 96/96 | 56 | 57 | 3 | 2 | 0 |

train/dev/eval是既有30底题设计的来源分区，本轮全部不参与拟合；不能将评估来源净+1说成独立提升，也不按它选择新默认方案。

原48中，校准前S为answer18/conflict6，校准后answer13/conflict11。5次变化均由answer变成conflict，涉及bind02_S_v1/v2、bind06_S_v1、bind09_S_v1/v2；这些原实际回答均有据。24条I在两阶段均全部answer，没有refuse。因此校准是本批5条额外假冲突的直接计算环节，24条I的原始误判不能归咎于校准。

迁移240中，校准前分布answer107/refuse24/conflict109，校准后answer98/refuse22/conflict120。11次变化全部转向conflict，其中：

- C：5条改对，参照一致42/60→47/60。
- K：5条原本正确的answer变conflict，一致35/58→30/58；2条作者unknown仍单列。
- S：1条原本错误的refuse变为错误conflict，一致24/58不变；2条unknown仍单列。
- I：60条的类别完全不变，均为answer29/refuse16/conflict15，一致16/60不变。

两批共16次类别变化全转向conflict。这是这些固定输入的观察，不证明校准在所有分布上总会增报冲突；240的净0也不等于每条决定相同或校准完全无影响。

## 可核查的逐条例子

bind02_S_v1的原线性分数answer5.529134大于conflict4.605586，原判answer。经过旧的类别映射，answer仿射分数0.838586低于conflict0.961825，最终概率answer0.489459/conflict0.507209，类别变conflict。该例直接展示了映射改变排序，但不解释为何旧验证分布学得这些参数，也不是模型生成使用该信号的证据。

同样的answer→conflict变化在stv14_A_K上是改错，在stv14_B_C上是改对；不能只保留其中一种。bind01_I_v2的原线性answer5.550651已高于refuse−3.946144，校准前后都answer；不能说它是校准把一个正确不足判定改坏。

## 同题配对与原行为

保存全部348配对：48中的24组S/I与24组干扰替换；240中的180组S→I/C/K与120组A/B。另保存33切片及42底题汇总，未知端点的双端正确字段为null，不删行凑分母。

绑定24组S/I两端同时与参照一致，两阶段都0/24。绑定S的12组v1/v2双端一致9→6；I始终两端错误。迁移S/I双端一致两阶段都4/58，S/C为12/58→15/58，S/K为23/58不变；完整各60对仍保留2个S端unknown。A/B中C双端一致20/30→22/30、K为17/29→13/29，S为10/29、I为7/30均不变。此处只报告计数，不新增bootstrap、显著性检验或A/B全命题等价认定。

原行为完全不变。绑定I的probe-refuse子集两阶段都为空，率为null；probe-answer子集作答0/24。迁移I的类别和条件子集未变，原判refuse后作答仍1/16、全部不足仍23/60。比较读出方法没有干预生成器，不能把条件率或类别变化当行为改善。

原线性refuse分数在S→I中，绑定24/24上升、迁移53/60上升，与已有连续信号方向观察相容；类别失败不证明状态没有可辨信息。本轮不利用看到的分数范围扫描阈值或把二分类新目标冒充原三分类通过。

## 检查与产物

8项新CPU测试通过，unittest1.380秒，覆盖7种类别变化归因、unknown/空分母、改对改错计数守恒、固定类别映射改变排序的数值例、非法状态/概率拒绝、完整348配对/缺项/重复/跨分区拒绝，以及两批真实向量与旧probe重放。旧12/120等套件未重跑。

实际analyze与PYTHONHASHSEED=229异进程verify均exit0。全部288最终概率相对原保存值最大误差0。另写scripts/verify_probe_calibration_diagnostic.py，不导入主分析模块，手算标准化、线性、softmax、仿射/sigmoid和共同归一化；六组数值最大误差均0，288连接/原行为、348配对、33切片、42底题及4套CSV逐项通过。独立指实现复算，不是独立语义评审。

[1132个此前路径](2026-10-21-probe-calibration-diagnostic-preserved.json)包括原回答/特征/probe/旧评分与12拟合封存文件，共享一次拟合声明也保持不变。[新CPU run的10文件](2026-10-21-probe-calibration-diagnostic-run-hashes.json)在核验中集合和字节不变。原run/probe/行为文件未改写，没有新增GPU或加载大模型。

主要持久产物为[JSON报告](2026-10-21-probe-calibration-diagnostic.json)、[288逐条CSV](2026-10-21-probe-calibration-diagnostic-rows.csv)、[33切片CSV](2026-10-21-probe-calibration-diagnostic-slices.csv)、[348配对CSV](2026-10-21-probe-calibration-diagnostic-pairs.csv)、[42底题CSV](2026-10-21-probe-calibration-diagnostic-base_summaries.csv)、[独立手算核验](2026-10-21-probe-calibration-diagnostic-verification.json)。完整逐条JSON和冻结协议在runs/qwen2.5-3b-probe-calibration-diagnostic-v1。

## 当前决策与复核入口

此次定位支持“原线性判定已不可靠，同时校准在本批增加冲突判定”的限定解释。撤销校准并不能让绑定I或迁移I得到更好的类别；不自动替换默认probe，不宣称找到唯一根因。保留连续分数信息和分类器有效性之间的区分，独立语义确认和跨题稳定性仍待建立，当前不进入patching。

后续仅读已有缓存：

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/probe_calibration_diagnostic.py --stage verify
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_probe_calibration_diagnostic.py
```

原一次拟合预算0，独立语义批准0/正式gate=false/标签null，380题继续封存。无新拟合/评分/前向/回答、层或阈值搜索、统计检验，不恢复前瞻性。当前工作包完成，更新AGENTS、索引、活动日志、综合结论及完成实验登记；未提交推送。
