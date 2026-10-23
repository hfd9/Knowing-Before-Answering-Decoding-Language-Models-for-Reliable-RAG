# 候选值关系附着：48条行为采集运行说明

日期：2026-10-23，Asia/Shanghai。当前状态：prepared_not_started_cpu_verified；48条输入、作者检查、真实tokenizer和独立重建核验均完成，实际模型推理/回答/attempt为0。

本任务检验：缺少所问属性时，模型是否更容易把目标实体的另一属性值用作答案。它承接[新对照草案](behavior_relation_attachment_design.md)，在单独的新run准备完整48条，不修改已经完成的旧48绑定任务或旧16条草案样例。原草案的16条已逐字保留并计入本次48，不是额外预试或smoke。

## 已固定的范围

六个虚构单位场景×四格×两个候选值=48回答，每格五条记录，固定greedy、最多128新tokens，使用同一个冻结本地Qwen2.5-3B-Instruct和原chat自由回答指令。无probe、隐藏状态采集或拟合，380题不访问。

| 格 | 显示候选归属 | 是否明确给所问目标关系 | 条数 |
| --- | --- | --- | ---: |
| TQ | 目标实体、所问属性 | 是，充分对照 | 12 |
| OQ | 另一实体、所问属性 | 否 | 12 |
| TA | 目标实体、另一属性 | 否 | 12 |
| OA | 另一实体、另一属性 | 否 | 12 |

唯一主要比较为TA−OA，共12对，先在每场景内平均两个候选版本，再等权平均六场景。目标、问题、候选和其他四槽固定；候选句与冗余ledger句交换实体，保持名称提及及词/数字多重集。本次实际12组主比较的完整chat输入token多重集也相同，但序列不同；这不认证相同注意力或内部机制。

输入的独立字段规则明确允许同值。全部36条不足输入各有两个兼容完整世界，共72世界；目标所问值在一个世界恰好等于候选、另一个不同。未展示值不是隐藏真答案，协调见证不会交给renderer。充分12条直接有据；这些是有历史暴露的作者关系判断，不是独立语义批准。

三场景问access、三场景问inspection；目标/另一实体数字顺序3/3，六种代码数值角色排列各一次。候选所在槽为[1,4,2,5,3,1]，每个场景八格槽位相同。先固定剩余单位/代码、顺序、smoke，再查看tokenizer，没有根据长度或结果选值。一个句型、两个代码字段仍是狭窄人工控制；明确独立规则可能使任务容易，不能解释旧23/60对0/24差异或证明自然文档泛化。

## 用户启动与正常续跑

在项目根目录执行：

```sh
sh scripts/run_relation_attachment_study.sh
```

入口自动读取kba-rag环境、本地离线模型和GPU0配置。先只读复核所有准备文件、来源/实现与权重指纹，再检查GPU是否已有计算进程；空闲后加载模型。首次四条是rel01_TQ_v1、rel02_OQ_v2、rel05_TA_v1、rel06_OA_v2，覆盖四格和两个提问方向，全部计入48预算。门槛仅非空、EOS、未触顶，不以答案或拒答正确为门槛。通过后生成剩余44，不额外采样。

正常停止发生在已完整提交的两条输入之间时，可用同一命令续跑，已保存前缀不会重复生成。若有未提交attempt、孤立临时文件、缓存损坏或失败smoke，入口会在新的模型加载/生成前停止；保留全部标记、输出和日志，交由助手检查，不删marker、不重答。错误或拒答不触发重试。

日志位置：

```text
runs/qwen2.5-3b-relation-attachment-v1/launch/collection.log
```

建议预留5–20分钟，包含CPU完整权重重核验、模型加载和48次生成。这是基于同机既有任务的容量规划，本任务GPU耗时尚未实测；最多输出6144tokens，不把上限当预期输出量。无法保证10分钟内，按AGENTS约定由用户启动，助手本轮未运行GPU。

## 已实际完成的CPU检查

- 全48条实际原chat提示均267tokens，总输入12816；预留输出128后远低于32768上下文，未裁剪。所有条件同长度是固定材料检查后的观察，不是按token长度筛选结果。
- 72结构配对均只变一个文档槽，含12组TA−OA主对；48问题、240文档槽及57去重全文已由当前有历史暴露助手全文检查。
- 36不足/72兼容世界与所给事实一致，代码、另一版本与见证无泄漏；保留原16例的精确问题/文档。
- 13实现文件、9来源文件和完整两个模型权重分片/元数据已在真实prepare与异进程verify核对；没有实例化推理模型或probe。
- 10项新CPU测试8.115秒通过，覆盖完整48模拟采集/重启无重复/全未评导出、正常提交前缀中断、未提交attempt/临时文件、缓存内容与停止/时间损坏、smoke失败停止、世界与材料破坏和真实来源文件准备/只读重放。模拟输出仅在临时目录，不是实际3B回答。旧套件未重跑。
- 真实`--stage prepare`与`PYTHONHASHSEED=241 ... --stage verify`均exit0；另一个不导入采集器的独立脚本从P0和指令源重建48提示/token，复核48/36/72、72配对和匿名包，exit0。独立指程序实现，不是独立语义审核。
- 1162个此前路径哈希不变，含上一轮差异审计/设计样例和原12拟合封存/共享预算；新run10份冻结文件在核验中集合及字节不变。准备目录另有锁文件，无predictions或generation_attempts。

启动前可只读检查：

```sh
sh scripts/run_relation_attachment_study.sh --stage verify
```

准备阶段独立复核（仅用于尚未生成时）：

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_relation_attachment_preparation.py
```

## 完成采集后

先执行完整只读核验：

```sh
sh scripts/run_relation_attachment_study.sh --stage verify-results
```

完成报告仅技术计数，行为240字段全unknown/unreviewed，TA−OA、全部不足作答率和充分正确率均null。不能按出现候选代码自动评分。匿名完整输入/输出在behavior_review/packet.json，协调映射另存；评分时先保存逐字引文判断及实际暴露声明，再连接四格，不称独立盲评。

按照[固定评分规则](../prompts/behavior_relation_attachment_scoring_v1.json)，同时报告全部36不足实质作答与全部12充分有据回答；候选采用为零也不能遮蔽其他未展示代码的猜测。泛称文档、未能识别具体证据归属时保留unknown；空或不可读输出不能默认拒答。主比较保留全部12对，不按充分对照成功筛场景；unknown保留完整分母和识别界。无新显著性检验/bootstrap、阈值或probe拟合。

全部48完成后无论事件多少都停止，不加样本、不换措辞追错误。原正式gate=false/标签null、独立语义批准0、一次拟合预算0、380封存保持。没有测量可靠性或因果使用的新确认，不进入patching。

## 文件位置

run为`runs/qwen2.5-3b-relation-attachment-v1`：materials保存48输入；coordinator保存36组世界、72配对与输入映射；protocol/preflight/collection_plan保存来源和顺序；input_review含匿名48输入HTML/JSON与空白模板。运行后才会出现generation_attempts、predictions、技术报告及behavior_review。所有原始产物保留本地run，轻量副本及检查见[本轮准备记录](records/2026-10-23-relation-attachment-preparation.md)。
