# 2026-10-21：原48输入的冻结chat L28读出核验与行为联合结果

日期与时区：2026-10-21，Asia/Shanghai。
状态：verified_complete；用户已完成48次补充前向，冻结入口与独立实现核验均通过。
操作者：用户GPU前向；当前助手只读CPU核验与记录，无新评分/拟合/回答。

用户报告跑完。本轮读取固定48输入的状态、旧冻结chat L28三概率和原行为评分，核对完整性并独立重算。核心结果为：**原目标行为保持正确，旧probe却把24条I全部判answer，24条S中11条判conflict；本批显示冻结三分类读出与行为分离，不能将该probe直接视为可靠语义测量。** 不把这一结果解释成隐藏状态完全没有不足信息，也不进入因果干预。

## 技术完成状态与保护

实际48条状态、48份36×2048 FP16特征、48个已提交attempt，前4smoke包含在48且技术通过。没有last_failure、日志Traceback、缺失/孤立特征、非有限值或全零层向量；日志的1–48、ID、预测与保存记录逐项一致。无新回答、拟合或行为评分。

20实现/12来源、固定原旧probe及完整2分片权重绑定沿用原协议。全部48真实提示/token与原生成输入一致，238–249tokens，总11688。6份准备产物哈希匹配，1007既有路径、原回答run66文件不变。本次前向run除锁116文件，检查前保存[完整哈希清单](2026-10-21-behavior-binding-probe-results-source-run-hashes.json)，核验中集合与字节保持不变。

逐条前向耗时合计5.300551秒；按记录首前向至末条记录完成5.775601秒，末条北京时间20:02:46.225352。该时段不包括CPU来源核验、模型加载及最后states/汇总写盘认证；不能把5.3秒称完整入口耗时。准备时10–20分钟为容量规划，也不冒充实测全流程时长。

独立CPU脚本scripts/verify_behavior_binding_probe_results.py不导入采集/分析核心，不调用生成或拟合。从FP16的L28向量手算float32标准化、三条线性分数、旧三路sigmoid校准与归一化，48条概率相对保存值最大绝对误差**0.0**，所有argmax一致；另从原P0和tokenizer重建提示，从原mapping/评分/完整回答重建联合字段，重算24/24/12配对、JSON/CSV和主要计数。[机器核验](2026-10-21-behavior-binding-probe-results-verification.json)保存实现哈希与计数。独立指复算程序实现，不代表独立语义评审。

实际`PYTHONHASHSEED=223 sh scripts/run_behavior_binding_probe.sh --stage verify-results`正常exit0，完整重放原来源、模型权重、特征、概率、联合JSON/CSV和完成标记；另写独立核验也exit0。两路核验及额外逐字段行为率复算、事后概率范围描述保存在[检查记录](2026-10-21-behavior-binding-probe-results-checks.json)，没有改冻结协议、原采集代码或原run。旧12测试不重跑。

## 同批probe与行为

| 条件 | 作者构造参照 | probe answer | probe refuse | probe conflict | 原实际主行为 |
| --- | --- | --- | --- | --- | --- |
| S，24条 | answer | 13 | 0 | 11 | 有据目标回答24/24 |
| I，24条 | refuse | 24 | 0 | 0 | 不提供实质目标代码24/24，承认不足24/24 |

作者参照一致13/48，其中S为13/24，I为0/24；仅为有历史暴露的构造参照描述，不称独立语义Accuracy。总分布answer37/refuse0/conflict11。原两条件均没有采用干扰代码，48项具体引用归属仍为unknown，不计引用错误或成功，不重新评分。

I中probe判answer的24条，实际作答0/24。probe判refuse的I子集为空，条件率为null，不能写成0/0=0%或“判不足后成功拒答”。S中probe判conflict的11条仍有据回答；这是读出与作者语义/行为不一致，不能据其输出正确证明模型在执行过程中完全没有冲突表征。

v1/v2切片：S-v1为answer6/conflict6，S-v2为answer7/conflict5；I-v1/I-v2各12条均answer。12场景四格全部与参照一致为0/12；24组S/I双端正确为0/24。没有按S成功、probe成绩或行为结果筛场景。

## 连续概率响应与类别判定必须分别解释

24组S→I中，**不足概率24/24上升，平均+10.66个百分点**，但没有一条I最终判refuse。与此同时answer概率平均+23.79个百分点，conflict平均−34.44个百分点。11组类别由conflict转answer，另13组answer不变；不能把“类别发生变化”统称为语义上正确的转换。

| 描述性不足概率 | S | I |
| --- | --- | --- |
| 平均值 | 0.003409 | 0.109961 |
| 最小值 | 0.001884 | 0.041814 |
| 最大值 | 0.006739 | 0.327631 |

上述范围是事后描述性补充，不新增阈值或筛选规则。本批连续不足概率有响应、且所见范围不重叠，说明不能把argmax失败解释成读出完全没有信息；它也不认证跨场景校准、冻结三分类有效性或隐藏状态因果使用。本轮不依据看到的概率范围重设二分类阈值或恢复拟合预算。

24组干扰代码v1→v2中，S有1/12类别变化、I为0/12。唯一变化为bind06_S：v1 conflict→v2 answer，answer概率+1.6268个百分点，conflict−1.6453个百分点；原S两端均有据答对且未采用干扰值。该变化限于测量输出，不能叫作干扰诱发目标误绑定。I两端主行为始终不答。全部12场景及48条保留。

## 对当前研究问题的影响

本结果落在预先讨论的“probe仍大量误判，而行为正确”分支，增加了旧冻结chat L28三分类判定在这类输入上迁移有效性不足的具体证据。它不支持“模型一般会把另一实体代码套给目标”，也没有提供“可靠判不足却仍不当作答”的新案例。

旧240中的23/60缺证作答、旧40的诊断仍按原材料/评审来源保留。两批材料多因素不同，不能据此归因于参数记忆、实体真实性、长度、复杂度、某一模板词或特定内部机制。旧probe的原发布构造类别成绩也不被改写；当前评估的是向新语义任务迁移的测量效度。

本轮为原48回答已见后的输入侧状态重算，不能声称probe在原生成时同步给出这些判断；没有原绑定特征可认证逐位桥接。所有语义/行为参照有项目历史暴露，独立批准仍0，正式标签null/原门禁false，原一次拟合预算剩余0，380保留底题未访问。总体继续处于测量核验与受控诊断阶段，不因负面结果追加场景、重生成、调层/阈值、拟合或patching。旧40实际独立复核及更广泛迁移可靠性仍待解决，不反复索要暂缺的外部渠道。

## 产物与后续入口

原run及技术报告不覆盖。[原报告JSON持久副本](2026-10-21-behavior-binding-probe-results.json)、[48联合CSV](2026-10-21-behavior-binding-probe-results-cells.csv)、[24组S/I](2026-10-21-behavior-binding-probe-results-S_to_I_pairs.csv)、[24组干扰替换](2026-10-21-behavior-binding-probe-results-distractor_pairs.csv)、[12场景](2026-10-21-behavior-binding-probe-results-base_scenarios.csv)保存完整分母。

后续无需再跑GPU。完整冻结入口的CPU只读核验：

```sh
sh scripts/run_behavior_binding_probe.sh --stage verify-results
```

独立实现重算，仅读已有特征/原回答：

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_behavior_binding_probe_results.py
```

原12测试同版本未重跑，无新评分测试或额外统计检验。新核验脚本通过真实48条整批重算验证；同步AGENTS、索引、活动日志、运行说明、综合结论和已完成实验登记。本轮未提交推送。
