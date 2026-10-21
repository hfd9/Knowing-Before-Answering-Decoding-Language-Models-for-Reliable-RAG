# 虚构实体属性绑定：48条行为采集运行说明

**后续补充已完成（2026-10-21）：** [同批48输入冻结chat L28结果](records/2026-10-21-behavior-binding-probe-results.md)已核验：S为answer13/conflict11、I为answer24，没有refuse；主行为仍全部正确，引用归属48unknown保持。S→I不足概率全部上升但三分类未正确区分，增加了冻结判定迁移有效性不足的证据；不等于隐藏状态无信息。无需再生成或跑GPU；下方补充待启动为历史。

**后续补充准备（2026-10-21）：** 用户要求同批输入—probe—行为联合对照，已另建[原48输入的冻结chat L28前向补充](behavior_binding_probe.md)。原本任务不存状态，因此新增48次decoder prefill，复用原回答和五字段评分，不重生成或拟合；当前仅CPU准备、3B前向0。补充入口为`sh scripts/run_behavior_binding_probe.sh`，与下方已经完成的回答采集入口分开。原48行为结论、48引用归属unknown与研究边界不变。

**最新状态（2026-10-21）：采集、只读核验及48行行为评分均已完成，参见[完成记录](records/2026-10-21-behavior-binding-results.md)。** 实际48回答/48attempt，smoke通过、空/触顶0、EOS48；I干扰采用0/24、I实质作答0/24、I目标不足承认24/24，S有据目标回答24/24，12场景四格全部保留。评分192字段确定/48具体证据归属unknown，全部已审；作者历史暴露，非独立金标准。无新GPU/拟合，不因零事件追加48；无需再次运行GPU入口。原run技术报告/模板的unreviewed为当时快照，本次评分另存。下文准备状态和启动说明保留历史，当前仅需离线分析verify。

当前状态（2026-10-21）：prepared_not_started_cpu_verified。48条材料、作者侧全文检查、评分规则、CPU测试、真实tokenizer和独立重建核验已完成；实际GPU调用0、回答0、probe拟合0。新任务只观察回答，原一次probe拟合预算继续为0。

问题是：目标单位的访问代码没有提供时，回答是否采用另一单位的代码；将另一单位的代码替换后，回答是否跟随。它由[23条旧回答审计](records/2026-10-21-insufficient-answer-audit.md)启发，使用新的明确虚构记录，不使用380保留题，不声称参数记忆或隐藏状态机制。

## 固定材料与边界

12组单位场景，各含S-v1、S-v2、I-v1、I-v2四格，最多48回答。S明确给目标代码t，I只保留目标记录存在；另一单位的代码为v1或v2。每格五条记录，问题只问目标单位。t/v1/v2互异，角色的六种数值排序各出现两次，目标在干扰之前/之后各6场景；五槽位置近似平衡，各出现2或3次。

材料固定seed42，未按tokenizer或模型结果选择值。48条共240槽、73个不同全文，当前助手逐条读过，但已有作者/项目历史暴露。24条I各有两个不同目标赋值、均保留已有事实的补全世界，共48个见证；这些协调数据不进入提示。独立语义批准仍0，旧正式门禁不改。

全部场景使用同一个英文句型、虚构单位和不透明代码，是12组标识符/位置实例，不是12种自然语言任务。U-132/U-130等名称接近程度不同，保留而不按预期难度换题。S→I也改变内容和长度，不能归因为单独的长度效应。结果适用于这类简单虚构记录，不能直接升级为自然文档语义泛化。

## 启动与续跑

在项目根目录执行：

```sh
sh scripts/run_behavior_binding_study.sh
```

入口自动读取现有kba-rag环境、GPU0与本地离线模型配置。固定Qwen2.5-3B-Instruct、原chat自由回答指令、greedy、最多128新tokens；不加载probe、不采隐藏状态、不拟合。模型加载前检查GPU是否已有计算进程，不与其他实验争用。

前4条技术smoke固定为bind01_S_v1、bind01_I_v2、bind12_S_v2、bind12_I_v1，包含在48总量内；检查非空、EOS结束、未触顶，不以答案正确或拒答作为门槛。通过后继续剩余44。所有输出包括错误、拒答或后续截断均保存，不因语义结果重答。

普通中断发生在已保存回答之间时，重复同一命令。程序核验已提交前缀后跳过，不再次生成。如果有未提交attempt，说明某次推理可能已执行而未完整保存，程序会在重新加载模型前停止；失败smoke也停止。请保留marker与原输出，交由助手检查，不删除marker、修改指纹或换目录重答。

日志：

```text
runs/qwen2.5-3b-behavior-binding-v1/launch/collection.log
```

规划预留约5–20分钟，包含CPU重核验、模型加载与48次生成；这是沿用本机既有采集表现的容量规划，新任务GPU尚未实测，宿主机竞争或长回答可能更久，不能保证10分钟内，因此由用户启动。实际最长总输出预算6,144 tokens，不把该上限当预期输出量。

## 当前CPU核验结果

- 48条真实chat提示全部匹配原renderer，无协调ID、期望值或见证泄漏；S均249tokens、I均238tokens，总输入11,688，最大249+128远低于32,768上下文，无裁剪。
- 24组S/I仅目标槽变化；24组v1/v2仅干扰槽变化；独立实现从实际句子解析实体和值并检查48个兼容世界。
- 模型元数据/tokenizer与两个完整权重分片SHA256均匹配旧冻结模型，协议绑定12实现文件、5来源文件及generation_config；未加载模型权重到推理对象。
- 10项新CPU测试通过，unittest2.870秒，含完整48模拟收集/完成导出/重复续跑、smoke失败、未提交attempt、缓存损坏及真实来源文件准备回归。模拟回答位于临时目录，不是实际模型回答。旧测试套件未重跑。
- 实际prepare与异进程verify均exit0。首次准备的依赖文件名错误发生在任何冻结产物写入前，目录只有锁文件；已在成功准备前修复并增加回归覆盖。
- 926个既有路径（含原run495与12拟合封存文件）哈希匹配；新准备产物、输入审阅材料及来源清单见[准备记录](records/2026-10-21-behavior-binding-preparation.md)与[JSON](records/2026-10-21-behavior-binding-preparation.json)。

只读检查准备版本：

```sh
sh scripts/run_behavior_binding_study.sh --stage verify
```

## 产物与采集后工作

| 路径（相对新run） | 用途 |
| --- | --- |
| materials/inputs.json | 固定48输入，协调字段不进入renderer。 |
| coordinator/witnesses.json | I双世界补全，不交给生成器。 |
| protocol.json、preflight.json、collection_plan.json | 指纹、精确提示长度与固定48顺序。 |
| input_review/inputs.html、packet.json | 已导出的48匿名输入，无模型输出或协调值；非已完成独立审核。 |
| input_review/ratings_template.json | 48行空白输入审核模板，原样保留，不用它覆盖作者检查。 |
| generation_attempts/、predictions.json | 启动后逐条保存attempt、原始token、回答、长度/停止及提示哈希。当前均不存在。 |
| reports/collection.json、completion.json | 全48结束后技术汇总；行为率仍null，不自动按关键词评分。 |
| behavior_review/packet.json、ratings_template.json | 全48结束后导出的匿名行为材料和五字段空白模板。 |

完成后助手先执行：

```sh
sh scripts/run_behavior_binding_study.sh --stage verify-results
```

再依据[冻结评分规则](../prompts/behavior_binding_scoring_v1.json)逐条复核。主指标为全部24条I中将该格干扰值赋给目标的比例，S对照为全部24条的有据目标回答；unknown保留完整分母。仅提及、引用或否认另一个单位的代码不算采用。明确不足表述必须指向所问目标代码；“承认后仍答”另需引文确定输出顺序，不能仅由两个布尔字段相与推出。

所有四格按12场景列配对，不以S成功筛选；原始输出保留。当前尚无行为评分或主率，不预判会发生误绑定。
