# 2026-10-20：探针输入变化诊断，CPU端点复算与新对照准备完成

记录日期与时区：2026-10-20，Asia/Shanghai；具体检查时间见[准备JSON](2026-10-20-probe-input-shift-preparation.json)。
状态：cached_endpoint_cpu_replay_complete / new_gpu_prepared_not_started。
操作者：助手完成设计、实现、材料检查、测试与冻结；新GPU由用户启动。

## 背景与本轮已实际发现的情况

用户要求直接开展上轮建议的“探针为何将充分短目标材料判冲突”诊断。已完成的[行为复核](2026-10-20-controlled-evidence-pilot-behavior.md)中，S有据答对10/10但probe九条判冲突。

本轮使用**既有状态数组和原冻结chat L28探针**，CPU重新核验20个端点的完整提示、输入token、数组形状/FP16/非零/有限及哈希，再重新计算探针输出。没有重新提取状态或生成文本：

| 已有端点 | 条数 | probe answer | probe refuse | probe conflict |
| --- | ---: | ---: | ---: | ---: |
| OO：原问题＋原发布answer五篇全文 | 10 | 9 | 1 | 0 |
| AP：上轮澄清问题＋作者S五篇全文 | 10 | 1 | 0 | 9 |

同题conflict概率在10/10题都上升。原发布answer仅为来源构造类别，不自动证明真实语义充分；原probe选层/校准用过这些val底题。原文→上轮材料同时改变问题范围、目标事实/措辞、干扰来源、顺序及长度，含WWW反事实日期等变化，不能由上述端点差直接推断“短文本导致冲突”或任一具体根因。逐条端点及概率保存在[端点JSON](2026-10-20-probe-input-shift-endpoints.json)。

## 新固定设计

10个底题沿用既有顺序，不按新GPU结果筛题。固定O/A两个问题层级和O/P两个文档层级的2×2，共40单元；另在六个明确含重复否定片段的底题加入N文档层级，与两个问题层级交叉，增加12单元。合计**52输入，20已有端点复用、32新前向**。

- OO10：原问题、原五篇原序文档，复用旧val抽取缓存。
- AO10：澄清问题、原五篇原序文档，新前向。
- OP10：原问题、上轮S五篇原序文档，新前向。
- AP10：澄清问题、上轮S文档，复用上轮S生成前缓存。
- ON6/AN6：固定问题，使用S删除两目标中指定重复否定片段的文档，新前向。

六个N底题固定为val_14/3/31/28/17/13。逐一阅读12个修改后目标全文，核对删除与保留正面事实：dog删除not-cat、public删除not-private、sole composer删除重复no-other-composers、magazine删除not-newspaper、mountain删除not-plateau、novel删除not-play。每条只删除预指定片段，两个目标同步修改，其他三篇全文、槽位和顺序完全保留。12处Unicode偏移/作者解释及12个保留正面事实引文写入edits.json。小说中的not-stage-adaptations范围约束仍保留；本轮不是将所有否定都删掉。对52单元不新设语义标签，不声称全部原文已被本轮独立重新审成充分。

比较问题时文档固定；比较P/N时问题固定。O/P为整体文档包变化，不称纯简化实验；O/A有时改变题意范围，不称同义改写。N相对于作者明确分类轴/版本范围保留正面回答事实，但改变长度，不能排除长度等影响、也不能声明所有开放世界语义完全等价。已知端点先被查看，本轮为事后提出并对新单元冻结的开发诊断，不是独立确认。

## 实现与核验

新增prompts/probe_input_shift_v1.json、scripts/probe_input_shift.py、两sh入口、tests/test_probe_input_shift.py及[运行说明](../probe_input_shift.md)。旧18份受控试验依赖未改，新协议纳入**22份实现/提示指纹与9份源文件哈希**，再以逐特征哈希保护缓存。

冻结Qwen2.5-3B-Instruct、BF16/SDPA、chat自由回答指令和L28 scaler/router；新阶段只调用decoder前向、use_cache=False，保存原状态定义的36×2048 FP16数组，不调用生成头，不生成长答案/分类标签，也不重训、校准、选层或阈值。报告七组预设配对方向、类别分布/概率差/token差，不计算新分类准确率或行为率。

smoke固定val_31重算六单元，其中OO/AP与已有状态做数值桥接：每层相对L2最大≤0.02、概率最大绝对差≤0.01。其余检查结构、有限与非零，不以语义分数决定过关。正式需重放smoke gate且同代码/材料/源哈希才运行。缓存身份/顺序、完整提示、token数、状态、来源和读出均校验，逐条原子保存、锁保护，GPU忙则加载前退出，失败记录实例。小幅概率差还需结合实际桥接数值误差，不能只看正负方向。

实际执行：

1. 新9项CPU测试通过（39.059秒）；最终全套**102项通过，82.850秒**。覆盖真实小型CPU Qwen的prefill与HF状态对齐/不调用LM头、真实tokenizer/旧probe、52材料配对/精确删除、缓存损坏、端点桥接、无模型缓存续跑、smoke失败禁止full、GPU忙保护。临时合成特征只写测试临时目录，不冒充3B结果。
2. `sh scripts/run_probe_input_shift.sh --stage prepare`实际完成正式52条；带`--smoke --run_dir ...-smoke-v1`完成6条smoke准备。真实tokenizer最大输入**4137**，上下文32768；不裁剪全文。正式260文档槽、85个不同全文用于程序输入去重统计，**不是宣称85篇在本轮新做独立语义金标准**。
3. 两目录`--stage verify --prepared_only`均exit0、prepared_verified_not_started；重建源材料、骨干/依赖/探针、逐提示/源状态、预检查及20/2已有端点报告一致。verify为只读，不写锁/报告。
4. 两目录progress均prepared_not_started/saved0，没有states.json，没有本轮新GPU输出。22实现/9源文件及记录JSON再次匹配；shell语法与diff检查通过。

正式协议SHA256：e514970336594349b6e0bbd9280facc8a3b17210cd149f7d519909a778d34d71。
smoke协议SHA256：20c9e926e1d22ba61a37b56585294bc87a4d96ba4aaa7d0e19bee246e20ea0a7。

## 耗时、用户入口与续跑

完整入口：

```sh
sh scripts/run_probe_input_shift_review.sh
```

先6次smoke，技术通过后正式32次新前向＋20次源复制，共38次新GPU前向，**0条新生成答案**。正式run_dir为runs/qwen2.5-3b-probe-input-shift-v1，smoke为runs/qwen2.5-3b-probe-input-shift-smoke-v1；日志正式launch/smoke.log、launch/full.log。中断后原样重跑，技术门槛失败先检查而非放宽门槛。

预检查测得新输入总量含smoke为62542token；十条旧原文prefill的最大elapsed/input-token比为0.0002441438秒/token。2倍/10倍容量余量加3/8分钟加载IO后规划**4–11分钟，建议预留10–20分钟**。attention成本并非线性且新GPU未实测，这不是完成保证；不能保证低于10分钟，按用户约定由用户启动，助手本轮未执行GPU入口，也未查询/停止宿主GPU进程。

用户完成后助手先只读核验smoke与正式，再分析三类对照，始终区分作用于具体编辑的敏感性与真实语义/因果机制；不依据新结果调层、选阈值或追认旧基线。

## 记录与未完成项

新GPU结果尚无；旧no_qualified_baseline不变，原40条行为评分与2unknown保留，未用380确认题、未patching。本轮完成CPU端点复算、设计、材料/代码/测试/冻结/时间估算和命令交付。只新增本轮文件及交接文档，不覆写旧结果。更新AGENTS、索引、活动日志；本轮准备不登记新完成GPU指标到experiments.csv。未提交或推送。
