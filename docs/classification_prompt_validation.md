# 三组新分类提示词：仅验证集选择与用户启动

2026-10-11设计，2026-10-12审核汇总、v4行为分析和CPU检查完成。冻结模型为本地 Qwen2.5-3B-Instruct，BF16、SDPA、GPU 0。
助手准备代码、CPU检查、协议和断点；预计超过10分钟的GPU程序由用户启动。
正式任务的保守估计约6–15分钟；下述顺序smoke+正式入口预留约8–20分钟。
这是历史chat8验证285条的94.63秒纯生成时间、三组新候选和加载/检查余量的规划值，
不是运行实测或时限保证。2026-10-12用户已运行：855正式+27smoke完成并核验，正式末条09:55:45保存。
三候选均未达预设门槛，结果为no_qualified_baseline；[完整结果与检查](records/2026-10-12-classification-prompt-validation-verified.md)。

## 固定设计

候选定义见 `prompts/classification_validation_v1.json`，不改变已有四条件代码或产物：

| 候选 | 指令变化 | 例子来源 |
| --- | --- | --- |
| definitions | 明确证据充分、必要前提缺失、同实体/时间/属性的不兼容主张 | 无示例 |
| decision_order | 按所需前提、相关矛盾、完整支持、缺证依次判断 | 无示例 |
| illustrations | 定义及五个短任务说明例子 | 全部虚构，不是训练数据或诊断测试题 |

所有新候选均为官方原生chat、greedy、8-token、完整五篇文档与原顺序；不清洗或截断
固定输入，不以旧测试错误制作示例。旧chat8的285条验证输出只作经指纹核验的对照，
不重新生成。正式新增3×285=855条；GPU smoke另有3×9=27条，不混入正式选择。
读取固定train/val以核验来源和集合分离；此入口不加载test数据或预测，不支持test参数，
不使用保留380个底题，不训练模型或探针。

主解析仍是推理前固定的首个非空行单类别词；严格格式单独检查。invalid保留完整分母。
选择规则预先固定：Macro-F1最高，并须首行覆盖率≥99%、严格格式≥99%、三类召回各≥60%、
分类错误可答率≤20%。分数并列按错误可答率低、最小类别召回高、固定候选顺序决胜。
无候选达到门槛时明确记为no_qualified_baseline，最高分仅为诊断候选。
这些是进入后续确认的筛选门槛，不足以证明可靠性；发布验证标签尚非独立语义金标准。
验证分数用于选择而有乐观偏差，不能当独立确认结果。

## 用户启动与续跑

审核包现为300条第二输入评分、232条第二行为评分及2条协调者补评，全部编号覆盖与校验完成。
补评不算独立评分，原b组文件未改；117行148分歧字段已由协调者裁定，正式v4导入与分析核验完成。
`review/independent-semantic-2026-10-11/coordinator/readiness.json`已经写入；推理会验证该文件、
来源披露及评分/裁定/v4哈希。评审存在项目背景暴露限制，不是完全背景盲审或独立人工金标准。
详细来源与限制见[裁定记录](records/2026-10-12-semantic-review-adjudication.md)。

项目根目录执行以下命令，会顺序进行smoke和正式验证。GPU有活动计算进程时拒绝加载模型。

```sh
sh scripts/run_classification_prompt_search_review.sh
```

日志在 `runs/qwen2.5-3b-classification-prompt-validation-v3/launch/{smoke,full}.log`，
可以在另一个终端查看：

```sh
tail -f runs/qwen2.5-3b-classification-prompt-validation-v3/launch/full.log
```

中断后原样重跑启动命令。每完成一条原子保存`predictions.json`，续跑核验代码/指令/数据/模型
指纹、样本顺序、渲染提示哈希、回答哈希、解析及预算，跳过已保存样本。失败不填默认标签。
改变代码、指令或数据须使用新run_dir，不能修改protocol指纹来通过校验。

## 断点记录与结果

正式目录：`runs/qwen2.5-3b-classification-prompt-validation-v3/`。
独立smoke目录：`runs/qwen2.5-3b-classification-prompt-validation-smoke-v3/`。
v1/v2只有旧CPU准备产物；2026-10-12门禁来源说明与代码协议变化后换用v3，未改旧指纹。
两份v3 CPU检查已通过，最长完整验证输入5563 tokens，加8低于32768；36项CPU测试通过。
两目录当前analysis_complete；855正式和27smoke输出、报告、解析、指标、bootstrap和选择规则均已核验。
definitions/decision_order/illustrations验证Accuracy37.89/36.14/36.49%，Macro-F1 25.81/23.45/23.20%；
冲突召回0/3.16/3.16%，没有合格候选。definitions只为新候选中的诊断最高分，不推进确认集。

| 文件 | 含义 |
| --- | --- |
| protocol.json | 候选、选择规则、数据/模型/代码指纹；与推理设置不符时拒绝续跑 |
| preflight.json | 完整输入长度、对照核验和历史耗时估计 |
| progress.json | 准备/运行/生成完成/分析完成、最近保存位置 |
| definitions/predictions.json 等 | 每候选逐条原子保存的原始输出和恢复清单 |
| last_failure.json | 最近失败位置和磁盘实际已保存数量；是历史失败快照，不表示当前仍失败 |
| review_gate_snapshot.json | 启动时第二评审就绪文件快照 |
| reports/val.json、val.md | 各候选指标、逐类指标、选择结果和按底题配对bootstrap |

只作CPU检查：

```sh
sh scripts/run_classification_prompt_search.sh --stage check
```

GPU生成结束后只重新分析：

```sh
sh scripts/run_classification_prompt_search.sh --stage analyze
```

结果由助手核验和追加持久记录；准备阶段不登记实验数值，不自动提交或推送。

已完成结果的只读核验（无需GPU，不覆写原报告）：

```sh
/large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/verify_classification_prompt_search.py --output /tmp/kba_prompt_validation_verification.json
```
