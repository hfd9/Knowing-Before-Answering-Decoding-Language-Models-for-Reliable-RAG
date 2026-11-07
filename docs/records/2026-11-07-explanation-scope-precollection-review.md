# 2026-11-07：解释行为采集前核对与近邻文献对照

记录时间与时区：2026-11-07，Asia/Shanghai。状态：知情助手核对、定向文献比较及条件性草案完成；未放行采集。

## 目标与交付

用户要求直接开始后续计划：检查尚未解决的材料语义、旧复评独立性、评分与门禁，比较Hidden Commitment、ContextConflict等近邻，并准备可审查的执行条件。完成[采集前核对与条件性执行草案](../explanation_scope_precollection_review.md)：逐项区分现有证据、待决条件和不允许自动推导的结论；原材料、计划、评分规则及门禁代码不修改。助手已知条件及项目历史，所有新判断都属知情核对，不是新盲评或正式批准。

## 本轮实际检查

- 不导入生成器的临时Python正则脚本解析48条英文材料的目标单位、字段和三个赋值：12个S/I0/IU/CT四格符合预期；每个I0/IU恰有一个不同文档槽，槽位依次为3/2/1/5/4/3/2/1/5/4/3/2。核对48顺序唯一及前四条恰为exs01四smoke。此检查只验证所匹配固定模板结构，并非独立语义审核。
- 实际执行 `python3 -B scripts/prepare_explanation_scope_materials.py --stage verify --version v2`、`python3 -B scripts/audit_explanation_scope_models.py`、`python3 -B scripts/explanation_scope_metrics.py --stage verify`、`python3 -B scripts/verify_isolated_cli_review.py` 和 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_explanation_scope_materials.py --version v2`，均exit0。独立文本/见证脚本复核48条均287输入tokens、12对长度及多重集相同；有限域结果仍依赖记录及局部修复假设。隔离CLI复评重核55/55/172、72来源、12拟合封存及4接收快照，结果不证明语义或私有上下文独立性。
- 只读核对执行预案绑定9文件的SHA均匹配；对W/E的9种合成真值组合核对J三值规则。空评分模板显示真实已审0、主点和识别界null，不是行为结果。默认真实run路径不存在。未重跑生产合成测试、检查实时GPU、重散列真实权重或加载模型。
- 查阅旧CLI暴露自述、协调者上下文证据、第一阶段与第二阶段交付记录和封存文件：保存有输入先封存、第二阶段后交付、五类暴露自述及当时29条已完成命令的协调者观察；memory功能检查发生在复评后。第一阶段交付`recorded_at`比评审自述完成时间晚41秒，前者并未声明是实际交付时间，不能据此推断实际交付顺序或确切时刻。未逐条重审29条命令或认证完整私有上下文；具体证据和限制写入核对文档。
- 检索并阅读[Hidden Commitment v2](https://arxiv.org/html/2610.38296v2)、[ContextConflict v1](https://arxiv.org/pdf/2609.03148v1)、[CONFLICTS v2](https://arxiv.org/html/2506.08500v2)、[Ragability](https://aclanthology.org/2026.lrec-1.182/)原文的方法、任务及指标；这是定向文献比较，不是系统综述或外部数据逐条核验。

## 结论与接续

材料符合结构设计；S只表示记录支持，IU冲突不能把所有报告同时当真，指代不清继续unknown。12场景是同一模板符号变体，配对控制不消除所有位置/措辞差异。真实主要指标仍为12对J(IU)−J(I0)，无模型回答或结果。现有文献已研究目标冲突披露、证据归属/faithfulness和缺证与冲突处理；本项目的候选细分是固定目标缺证时对其他实体冲突的作用范围做成对比较，并联合评分未知与无据目标冲突。是否首创未确立，也不能据输出证明内部机制。

现有CLI复评是实际证据，仍为context_audit_pending、正式独立批准0；旧关键案例狭义E为unknown/no/unknown，与旧草案的条件、后续知情采纳方向之间需要明确的正式协议处理。新48只有作者暴露判断与知情结构核对，记录相对支持及冲突作用范围仍须按最终协议进行语义审核。生产门禁在目录和模型加载之前拒绝，必须先有新的正式协议、明确采集决定及相应代码审查重验；不能以本轮文档或模拟测试代替。用户无需亲自逐条审核，但助手不能冒称独立盲评。

无新模型调用、生成、评分、拟合、GPU或380题访问；formal_gate/gpu_launch_ready=false、拟合预算0、正式标签null、380封存保持，不更新experiments.csv。按长期约定记录后提交推送，实际哈希和远端核验以Git及回复为准。
