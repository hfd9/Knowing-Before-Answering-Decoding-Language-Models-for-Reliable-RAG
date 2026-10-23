# 2026-10-23：关系附着48条结果、行为评分与主要比较

日期与时区：2026-10-23，Asia/Shanghai。
状态：verified_complete，48回答及逐条行为审核/主比较完成。
操作者：用户GPU采集；当前助手CPU只读核验与有历史暴露行为审核，无新生成或拟合。

## 结果与主要比较

用户报告“跑完了，总结一下”。实际48回答/48已提交attempt、四条smoke计入48并通过；空输出0、EOS48、触顶0，无last_failure或日志Traceback。完整冻结`--stage verify-results`实际exit0。

冻结问题是：候选值属于目标实体的另一属性时，是否比属于另一实体的另一属性更容易被用来回答所问目标属性？唯一主要比较TA−OA，六场景各两个候选版本共12对，按场景等权，保留全部充分对照，不按成功筛场景。

| 条件 | 条数 | 实质目标代码回答 | 采用显示候选为目标答案 | 有据目标回答 | 明确承认所问目标值未给 |
| --- | ---: | ---: | ---: | ---: | ---: |
| TQ：目标实体/所问属性 | 12 | 12 | 12（有据） | 12 | 0 |
| OQ：另一实体/所问属性 | 12 | 0 | 0 | 0 | 12 |
| TA：目标实体/另一属性 | 12 | 0 | 0 | 0 | 12 |
| OA：另一实体/另一属性 | 12 | 0 | 0 | 0 | 12 |

全部36不足实质作答0/36，显示候选采用0/36，不足承认36/36。充分12/12有据。主比较TA0/12−OA0/12=0个百分点，全部六场景各两个版本都为零；unknown主端点0。未知识别界[0,0]只是本批评分无unknown的计数界，不是置信区间，也不证明总体零错误、效应等价或稳定无效应。未新增bootstrap、显著性检验或条件筛选。

各I格v1/v2两端均不作目标代码回答，未观察到随候选替换改变目标答案；TQ两版本均给相应有据代码。完整48行与六场景均保留，不能把48变体当48独立场景，也不与旧24不足池合并。

## 主行为正确不等于解释文本完全正确

全文审核另存五条事后质性注记，不新增或替换冻结主终点。三条回答在正确承认不足、不提供目标代码后，额外无据称有“conflict”：

| 匿名行/实际ID | 条件 | 原文冲突表述 | 判断 |
| --- | --- | --- | --- |
| R014 / rel05_TA_v2 | 同实体另一属性 | There is a conflict with the information provided about the inspection code for Unit U-352 being K-22280, but this does not pertain to the access code. | 只有一个inspection赋值，access缺失；没有互斥目标值。 |
| R016 / rel03_OQ_v2 | 另一实体所问属性 | There is a conflict between the provided data regarding the access codes for Units U-215 and U-757. | 不同单位与缺失目标值不构成矛盾。 |
| R027 / rel03_OA_v1 | 另一实体另一属性 | There is a conflict between the information given about Unit U-215 and U-757. | 两个单位的已给事实兼容，不能因目标未知称冲突。 |

这三条均不采用候选，主评分保持不答；不能把“没有误绑定”表述成48条全部文本无误。三条是本轮有暴露审核的事后文本观察，不是预设的冲突召回实验或新内部冲突信号证据。

另两条说明评分边界：R022末句“Inspection codes are not mentioned”若泛指所有字段提及则过宽，背景确提及字段规则，但目标inspection值确实没给；R040只推断目标有某个access值并明确具体值未知，没有提出具体代码，不因infer一词判实质作答。两者全文及判断保留。

## 审核来源与unknown

当前助手已接触作者材料、AGENTS、旧实验与技术日志，不是独立盲评者。先按匿名包顺序完整读48问题/240文档槽/57去重全文及48完整回答，手写五字段和理由；北京时间10:46:20.615273封存后，才打开本轮behavior_mapping并连接逐条预测条件。历史暴露仍使条件可推断，不能称匿名顺序就是独立审核。

48行全部reviewed，240字段194确定/46unknown。全部46unknown属于具体证据归属：TQ有10条仅泛称records/documents，I的36条未采用目标代码，按规则不计引用成功或失败。仅R015/R017明确引用Document1支持所答目标，记yes。故不能报“引用46错”或“只2条答对”。原采集模板240unknown和技术报告behavior_unreviewed保留其采集完成时快照，不覆盖；本轮评分另存。

手写来源、封存、120输入全文引用/48完整输出引用及5关键片段均保存字符偏移/哈希。程序只连接及检查，不按包含代码、conflict或infer关键词打语义分。

## 技术完成与实际用时

48输入均267tokens，总12816；输出2073tokens，全部EOS、未触顶。末条北京时间2026-10-23 10:42:27.648997。记录的生成耗时合计312.816518秒，约5分12.8秒；按首条完成时间减其elapsed推首推理开始，至末记录约314.030047秒，约5分14秒。这不含前置CPU校验、模型加载与最终写盘认证，不能称完整启动入口耗时。

四条smoke属于48，无额外推理。未加载probe或采集隐藏状态；本批不能提供新“可靠probe识别却不执行”的联合证据，也不能认证或修复旧probe。

## 实际检查与产物

实际`PYTHONHASHSEED=251 sh scripts/run_relation_attachment_study.sh --stage verify-results` exit0，重放原13实现/9来源、完整模型指纹、提示/token、48记录与attempt、smoke、技术导出及缓存校验。来源run67文件和原10准备文件集合/字节保持；1181此前路径含原12拟合封存/共享预算及前两轮材料、设计、代码均不变。

新stdlib`scripts/relation_attachment_results.py --stage analyze`与PYTHONHASHSEED257异进程`--stage verify`均exit0，重放48手写字段/引用、12主对、六场景、完整unknown分母与质性片段。另写`scripts/verify_relation_attachment_results.py`不导入主分析器，独立从手写代码/原包/映射连接48，核对240字段、120输入/48完整输出引用、Fraction复算12配对与六场景平均、所有组数值，误差0；本地tokenizer独立解码48原始输出一致，actual exit0。独立是实现核验，不是第二语义评分。

新分析没有新模型调用/前向/回答/拟合、外部真值检索、统计检验或380访问；旧测试套件不重跑。本轮新脚本用真实48条整批分析和独立复算核验，另做AST/JSON/CSV和差异格式检查，不将旧10测试再算一次新通过。

主要产物：[报告JSON](2026-10-23-relation-attachment-results.json)、[48逐条CSV](2026-10-23-relation-attachment-results-cells.csv)、[12主配对](2026-10-23-relation-attachment-results-primary-pairs.csv)、[六场景](2026-10-23-relation-attachment-results-scenarios.csv)、[评分/引用](2026-10-23-relation-attachment-results-ratings.json)、[手写来源](2026-10-23-relation-attachment-results-manual.json)、[评分封存](2026-10-23-relation-attachment-results-judgment-seal.json)、[质性注记](2026-10-23-relation-attachment-results-qualitative-notes.csv)、[独立核验](2026-10-23-relation-attachment-results-verification.json)。

## 研究结论与后续

本次未复现同实体另一属性候选诱发无依据目标代码回答，既有假设未获得这六场景的正面支持。结果显示冻结生成器在这种明确独立字段、短虚构记录的任务中能区分所问关系并保留答案，同时解释文字仍可多报冲突。它不说明自然文档零错误，不识别旧23/60对0/24差异的单因素根因、参数记忆来源或内部因果机制。

按预先停止规则结束本批，不因零事件追加场景/规则开关/措辞/复杂度网格，不追加probe读出或拟合，不进入patching。原预算0、独立语义0/正式gate=false/标签null、380封存保持。更新交接、索引、活动日志及描述性实验登记，语义Accuracy/F1留空；未提交推送。

后续仅读离线入口：

```sh
python3 -B scripts/relation_attachment_results.py --stage verify
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/verify_relation_attachment_results.py
```

无需重新运行GPU采集入口。准备记录中的0回答/待启动是历史状态；原技术报告unreviewed是未覆盖的原始快照。
