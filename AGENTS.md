# 项目交接入口：先读本文件

本文件供新会话中的助手快速恢复背景。更新时间：2026-10-18（Asia/Shanghai）。
路径均相对项目根目录；具体运行状态以用户最新消息和实际产物为准。

## 开始工作的读取顺序

1. 读本文件，了解研究目标、已知结果、当前任务和文件位置。
2. 读 [记录索引](docs/records/README.md)，再读其中最新交接记录；按任务读取相应实验记录。
3. 要运行或分析实验，读 [当前实验计划](docs/evidence_behavior_plan.md) 和 [运行说明](docs/evidence_behavior_run.md)。
4. 需要追溯早期问题时，再按节查 [活动日志](docs/activity_log.md)；不要一开始加载所有大型 JSON、激活数组或原始输出。

## 研究背景与边界

仓库对应 Knowing Before Answering: Decoding Language Models for Reliable RAG。
当前本地工作使用冻结的 Qwen2.5-3B-Instruct，从提示最后一个 token 的隐藏状态读出
answer（证据充分）、refuse（证据不足）、conflict（证据冲突）。训练对象是线性探针/路由器，不是大模型。

当前研究主线：先建立可靠的三分类提示词基线，再验证“生成前能读出不足/冲突”与“模型实际回答/拒答/选边”之间的关系。
首要问题是：真实缺证样本中，探针在生成前判为缺证后，模型是否仍给出实质答案？同时报告全部缺证样本的回答率。
冲突与不足分别分析；能够解码类别不等于已经证明模型知道、故意忽略证据或具有因果机制。

原发布数据按底题划分：train 1,821 / val 95 / test 480 个底题；每题有三类证据配置，每条有五篇文档。
本轮固定抽样 train 600 / val 285 / test 300 条（200 / 95 / 100 底题），seed=42。
当前 300 条测试已经查看，仅用于诊断；剩余 380 个测试底题未纳入本轮预测，留待冻结设置后的确认。
提示词选择、选层、超参数调整只用验证集；不要依据当前测试错误调优后宣称独立测试成功。

## 当前进度与可靠结论

| 工作 | 状态 / 已知结果 |
| --- | --- |
| 环境与模型接口 | kba-rag、3B、RTX 3090 验证通过；7B 仅检查权重，未做 GPU 实验 |
| 小规模隐藏状态路由器 | 完成；最佳层 24（从 0 编号）；test 242/300，Accuracy 80.67%，Macro-F1 80.54% |
| 原纯文本 8-token 分类基线 | 完成；首行事后解析为 150/300，Accuracy 50%，Macro-F1 39.93%；原严格格式通过率 0% |
| 四条件分类对照 | 2026-10-11 正式生成与分析核验完成：八份预测共2340条（2040新+300旧复用）；plain8/64 test均150/300、Accuracy 50%、Macro-F1 39.93%；chat8/64均129/300、Accuracy 43%、Macro-F1 32.12%；两预算逐条分类相同。严格格式plain0%、chat99.67%；旧300条输出及冻结指纹核验通过 |
| 自由回答 | 2026-10-09 已核验 generation_complete：plain/chat 各 train 600、val 285、test 300，最后回答于北京时间 11:39:33 保存；2,370 个特征和 600 条探针预测复算通过 |
| 自由回答同模板探针 | plain L24：244/300，Accuracy 81.33%，Macro-F1 81.42%；chat L28：233/300，Accuracy 77.67%，Macro-F1 77.34%；这是证据分类，不是实际行为指标 |
| 行为标注与分析 | 2026-10-12：300输入第二评分、232行为第二评分+2协调者补评已校验汇总；117行148分歧字段逐项裁定，98行118字段改变，正式v4导入并analyze/600对齐/22项率核验完成；468条五字段确定、132条至少一项unknown。原v3及旧报告保留，补评与裁定不称独立评分；第二评审有项目背景暴露 |
| 新验证集分类提示词 | 2026-10-12用户启动，v3正式855条+smoke27条生成/分析/核验完成，末条09:55:45；definitions/decision_order/illustrations Accuracy37.89/36.14/36.49%，Macro-F1 25.81/23.45/23.20%，冲突召回0/3.16/3.16%；三候选均未达预设门槛，no_qualified_baseline；只用val，确认集未用 |
| 验证集证据诊断准备 | 2026-10-13代码、空白盲审包与285正式/9smoke CPU检查完成，46项CPU测试通过；512-token带原文引用草稿与四组旧val输出诊断，smoke结构门槛6/9，GPU尚未启动，由用户运行；不选择新候选或自动导入语义标签 |
| 验证集证据诊断启动尝试 | 2026-10-13用户入口在模型加载前被GPU活动计算进程保护阻止并退出；smoke0/9、正式0/285，均仍prepared_not_started。日志未给PID，实时占用未核验；待GPU空闲原样重跑 |
| 确认集与因果干预 | 尚无结果；剩余 380 个测试底题未使用，暂不直接 patching |
| 验证集证据诊断smoke失败 | 2026-10-16用户已完成9/9条GPU生成及草稿分析；结构/引用检查0/9，未达6/9门槛，入口退出；正式仍0/285。首错为空缺失事实2、字段类型1、引用不匹配3、JSON代码围栏3；无空输出或截断。保留v1，原样重跑复用缓存再次失败，新设计须新目录/协议 |
| 验证集证据诊断v2准备 | 2026-10-16明确字符串schema/合成示例/短逐字引用及终端报错，严格解析与6/9门槛不变；50项CPU测试、285/9输入检查完成，v2两目录0输出prepared_not_started。用户入口sh scripts/run_validation_evidence_audit_v2_review.sh；规划45–140分钟，未实测v2 GPU |
| 验证集证据诊断v2实际失败 | 2026-10-16用户完成9/9 smoke，但仅3/9结构合法且均显式unknown，低于6/9门槛，入口exit1；另6条首错为漏citations4、引用不匹配1、JSON语法1。正式仍0/285，无空/截断，14指纹/输出哈希/解析重放通过。不要原样重跑或自动再加提示重试，先全文语义复核 |
| 验证集证据诊断v3修复准备 | 2026-10-16用户要求修复并继续285条；已实现256token自由分析+128token受约束JSON/片段ID，程序按原偏移还原引用，新schema/新协议，6/9数量门槛不变。58项CPU测试与285/9预检查通过，v3尚无GPU输出；用户入口sh scripts/run_validation_evidence_audit_v3_review.sh，完整规划90–180分钟 |
| v3实际失败与v4预算修复 | 2026-10-16用户v3完成9/9，全部决策JSON完整/EOS，但8条前置分析触及256上限未EOS，门槛1/9失败，正式0/285。v4分析1024+决策128，新协议/目录，62项CPU测试与285/9检查通过，v4 GPU未启动；入口sh scripts/run_validation_evidence_audit_v4_review.sh，满预算容量规划约4–8小时，非实测预期 |
| v4诊断生成完成与根因核验 | 2026-10-16用户完成smoke9条/8通过及正式285条；17指纹/两阶段token/来源/独立计数重放通过，正式末条17:14:01，生成约48分钟。277结构合法、43合法unknown+8分析截断，234确定草稿（87充分/49不足/98冲突）；与发布标签一致100/285=35.09%，仅标签一致率非语义准确率。全文例子已见无关引文/跨实体假冲突，不能将草稿当金标准；先做val语义复核，不自动新GPU |
| 30条val语义诊断复核 | 2026-10-16用户要求前三步直接完成：seed42固定10底题/30条，完整150文档槽（68去重原文）已读；输入先封存为11充分/12不足/4冲突/3未知，再看模型输出，27确定中v4类别一致7、不一致18、技术invalid2；6条确定判断与发布标签不同，非已独立证实错标。30条手工归因/54原文引用/对照CSV及3项CPU流程测试完成；当前助手有历史及部分日志暴露，不是独立金标准，不改正式标签 |
| 语义诊断报告与空白新评审包 | 2026-10-16用户已执行CPU入口，正式导出完成；助手核验10文件哈希/入口指纹/原始来源、30模型副本/54引文与全部内容重放一致，30行新评分全空、7优先项匹配。v4相对旧助手判断全确定7/27、high子集5/23，仅诊断一致计数。下一步新评审填写副本，无需重跑GPU；新增独立评分0条 |
| 当前助手30条追加语义判断 | 2026-10-16用户要求直接判断，7优先+23其余完整原文均复核；12充分/13不足/4冲突/1unknown，high23/moderate6/ambiguous1，50引用与已填CSV副本/封存/来源核验通过。P004按2018年6月并区分账号/个人改answer，P025按available事件缺日期改refuse，其余28模式不变；均为同助手解释修订。相对本轮确定判断v4一致7/29（20不一致、2invalid），非独立准确率。P008双署名歧义仍保留，用户要求的本轮判断已完成；独立新评分仍0，不覆盖旧判断或空白模板 |
| 新语义规则分类候选 | 2026-10-16用户已启动；20:33:27快照：两组smoke各9/9通过，正式首组semantic_rules227/285、examples0/285，29秒从154推进到227，最新保存0.23秒前，均技术合法/无截断；13指纹一致。输出44answer/182refuse/1conflict仅分布，语义成绩待报告；宿主GPU实时占用沙箱不可见。最终79CPU测试通过，旧筛选门槛不变，30条开发诊断非独立评分；运行中不改依赖或重启 |
| 2026-10-18背景恢复与当前分类状态 | 实际产物已为正式570+smoke18、两目录analysis_complete；四份预测均保存技术合法/未触及上限，两目录各13代码指纹匹配。正式末条2026-10-16 20:35:54；保存报告rules/examples Accuracy41.40/37.19%、冲突召回2.11/1.05%，仍no_qualified_baseline。这是本轮轻量核对，完整缓存/指标/bootstrap重放待做；详见docs/records/2026-10-18-context-restored.md，无新GPU |

原路由器三分类错误可答判定率为 10%，纯文本首行基线为 31.5%；这不是自由回答中的实际缺证回答率。
路由器比基线净多判对 92 条：Answer +16、Refuse −10、Conflict +86；冲突贡献净增量的 93.5%。
真实不足误判可答：路由器 11、基线 6；真实冲突误判可答：路由器 9、基线 57。
因此不能仅凭整体提升认定不足类更好。旧首行解析是 post-hoc；新条件解析在推理前固定，invalid 保留分母。
完整数据跨集合的 original_id 和问题文本无重叠；既有特征未见 NaN/Inf/全零向量。
最近全套为2026-10-16新语义规则分类准备的79项CPU测试通过（10.899秒），包含旧62项、pilot3项、诊断导出5项、新分类9项；含小型CPU Qwen真实约束生成，不能由此推断新本机3B GPU结果。新两候选已由用户完成GPU生成与报告保存，2026-10-18仅轻量核对，完整只读重放待做；旧v4本机GPU完成另有核验。此前v4为62项、v3为58项、v2为50项、2026-10-13为46项、2026-10-12为36项。
四条件GPU正式新增2040条已于北京时间2026-10-11 12:30:06生成完并核验，见 [分类完成记录](docs/records/2026-10-11-classification-grid-verified.md)。
chat相比plain准确率−7个百分点，但分类错误可答率31.5%降到14%；chat不足→可答0/100、冲突→可答28/100。
分类chat的冲突召回只有1%，val两组chat未预测conflict；格式通过率提高不等于可靠三分类能力。
router与chat的分类错误可答率点差4个百分点，bootstrap区间含0；不能由总体准确率优势认定不足类或安全性稳定胜出。

自由回答 plain/chat 触及 128-token 输出上限且未以 EOS 结束分别为 154/300 和 1/300，空输出均为 0。
当前正式v4按发布不足标签且探针判不足后实质作答为plain6–8/80（7.50–10.00%）、chat11–12/82（13.41–14.63%）；
全部发布不足实质作答plain13–15/100、chat20–22/100。相关字段含unknown，点估计null，不能套用历史v3 bootstrap区间。
发布冲突选边plain66–81/100、chat79–83/100；发布充分有据正确回答plain55–61/100、chat61–64/100，明确不足拒答22–25/100、20–21/100。
范围保留未知在完整分母中，是识别上下界，不是置信区间。v3旧点估计8/80、12/82及区间保留在历史记录。
第二输入判断300条为充分100、不足120、冲突70、未知10；发布answer中20条判不足，发布conflict中24条判充分。
按第二判断语义不足且探针判不足后作答plain8–10/86、chat13–14/92；语义冲突选边45–54/70、55–56/70，均为事后诊断。
核心20条输入均被第二判断判不足；其中明确作答plain6/chat11，plain2/chat1先答后回撤保留unknown。370/377也保留实质/选边unknown。
以上为同模型第二评分加协调补评/裁定，仍非独立人工金标准，不能证明模型自知或故意忽略。
chat−plain 探针准确率差 −3.67 个百分点，按底题配对 bootstrap 95% 区间 [−8.00, +0.33]；
充分召回率差 −15 个百分点，区间 [−25, −5]；不足/冲突各 +2 个百分点，区间均含 0。
详见 docs/records/2026-10-09-free-answer-generation-verified.md 与同名 JSON。
最新行为交接见 [第二评分、v4裁定与启动准备](docs/records/2026-10-12-semantic-review-adjudication.md) 及同名JSON；v3历史见 [重点复核](docs/records/2026-10-11-free-answer-followup-audit.md)，首轮历史见 [v2审核](docs/records/2026-10-11-free-answer-semantic-review.md)。
旧核验与背景恢复记录是当时快照；现有报告已加载正式标注，仍显示 pending_or_ambiguous 是因为歧义字段保留 unknown。
100 个 conflict 配置中明确冲突 68、兼容/答案未变 13、不足/含糊 19；明确冲突子集选边 plain 42–52/68、chat 53–54/68（事后诊断）。
固定 train/val/test 的显式改写元数据匹配分别 6/600、2/285、4/300，均在 conflict；检测非穷尽，冻结原输入未清洗。发布类别不能直接等同于明确语义矛盾。

## 文件导航

### 本地可用入口与公共实现

| 文件 | 用途 |
| --- | --- |
| `scripts/run_small_repro.sh`、`scripts/small_repro.py` | 数据抽样、隐藏状态提取、逐层探针、校准路由器；旧实验入口 |
| `scripts/run_prompt_baseline.sh`、`scripts/prompt_baseline.py` | 原纯文本 8-token 分类基线与严格解析；保留历史设置 |
| `scripts/analyze_prompt_baseline.py` | 对旧原始输出进行首行事后补充分析 |
| `scripts/run_classification_grid.sh`、`scripts/classification_grid.py` | plain/chat × 8/64-token 分类对照、审计、分类型指标和混淆矩阵 |
| `scripts/run_classification_grid_review.sh`、`scripts/verify_classification_grid.py` | 本轮顺序smoke/正式启动及完成后的独立计数核验；GPU空闲保护、冻结指纹、2340解析和10组指标检查 |
| `scripts/run_free_answer_study.sh`、`scripts/free_answer_study.py` | 同模板提取/重训探针、128-token 自由回答、生成前判断与行为汇总 |
| `scripts/free_answer_review.py` | 离线盲审 HTML、带批次哈希的 CSV、未知行为与完整分母统计 |
| `scripts/free_answer_followup_analysis.py` | 从冻结 v2 复算同助手 v3 变更、70 条重点判断、100 条质量分层及独立空白审包；不会自动导入正式标注 |
| `scripts/prepare_independent_semantic_review.py` | 重新编号独立输入/行为池、隔离协调映射、准备234条优先批次、校验新评分；拒绝覆写已有版本，不自动导入正式标注 |
| `scripts/summarize_independent_semantic_review.py`、`scripts/adjudicate_semantic_review.py` | 汇总第二评分与已披露协调补评；由明确手工决策另存v4/分歧/未知/质量分层，不自动导入正式标注；旧源重放须显式source-snapshot并核验原哈希 |
| `scripts/run_classification_prompt_search_review.sh`、`docs/classification_prompt_validation.md` | 用户顺序启动新提示词GPU smoke和正式验证，当前v3新目录；855条验证新输出，预设选择门槛，未读取test或使用确认集 |
| `scripts/verify_classification_prompt_search.py` | 仅CPU只读核验新提示词protocol、缓存/完整提示/解析、独立计数和预设选择，复算配对bootstrap；不启动GPU，不覆写报告 |
| `scripts/run_validation_evidence_audit_review.sh`、`scripts/validation_evidence_audit.py`、`docs/validation_evidence_audit.md` | v1历史入口与v2复用实现；512-token、严格JSON/原文引用、未知完整分母、旧输出诊断与空白评分入口；v1已完成9条smoke但0/9通过，正式未启动 |
| `scripts/run_validation_evidence_audit_v2_review.sh`、`scripts/validation_evidence_audit_v2.py`、`docs/validation_evidence_audit_v2.md` | v2格式/引用修订，冻结v1解析与门槛；50项CPU测试与285/9检查通过，但实际smoke仅3/9通过，正式未启动，不再原样重跑 |
| `scripts/run_validation_evidence_audit_v3_review.sh`、`scripts/validation_evidence_audit_v3.py`、`scripts/evidence_decision_grammar.py`、`docs/validation_evidence_audit_v3.md` | v3历史入口和v4复用实现：JSON约束已实际生效，但前置分析8/9截断导致门槛1/9失败，正式未启动 |
| `scripts/run_validation_evidence_audit_v4_review.sh`、`scripts/validation_evidence_audit_v4.py`、`docs/validation_evidence_audit_v4.md` | v4已完成285正式+9smoke并CPU核验；分析1024/决策128，277结构合法，语义复核未完成，不需重跑GPU |
| `scripts/verify_validation_evidence_audit_v4.py`、`docs/records/2026-10-16-validation-evidence-audit-v4-verified.md` | 当前已完成v4的CPU只读核验与根因分析；285+9逐条重放、17冻结指纹、独立计数，区分技术通过/发布标签一致/独立语义正确性；不重生成或改报告 |
| `scripts/validation_semantic_pilot.py`、`scripts/summarize_validation_semantic_pilot.py`、`docs/records/2026-10-16-validation-semantic-pilot.md` | 固定30条val输入复核、先封存后揭示、显式手工归因及校验；本轮已完成，3项流程测试通过；不自动作语义判断或导入旧标签 |
| `scripts/run_validation_semantic_diagnosis.sh`、`scripts/validation_semantic_diagnosis.py`、`docs/validation_semantic_diagnosis.md` | CPU导出已由用户完成并核验，默认runs/qwen2.5-3b-validation-semantic-diagnosis-v1；全文对照报告、全30条空白复核包和7优先项齐全，新独立评分0条；新评分另存副本，原模板勿覆写，不自动导入标签 |
| `scripts/verify_validation_semantic_followup.py`、`docs/records/2026-10-16-validation-semantic-followup.md` | 用户授权当前助手直接完成全30追加判断；新run保存已填JSON/CSV、50引用偏移、两处解释变更与7/29类别计数，验证脚本只读重放已通过。不是独立评审，不改原首轮、空白模板或正式标注 |
| `scripts/run_classification_semantic_baseline_review.sh`、`scripts/classification_semantic_baseline.py`、`scripts/verify_classification_semantic_baseline.py`、`docs/classification_semantic_baseline.md` | 用户已完成两候选各285val+9smoke，保存analysis_complete/no_qualified_baseline；2026-10-18轻量核对570+18条/两组13指纹一致，完整只读verify待做。79CPU测试为历史准备检查；旧筛选门槛不变、开发30条单列，无需重跑GPU |
| `scripts/evidence_experiment.py` | 固定协议、输入渲染、缓存校验、审计、配对 bootstrap、状态钩子和生成公共函数 |
| `scripts/check_environment.sh`、`scripts/check_environment.py` | 环境、权重与模型接口检查；加载模型的检查也会占 GPU |
| `tests/test_small_repro.py`、`tests/test_prompt_baseline.py` | 旧复现和旧基线验证 |
| `tests/test_analyze_prompt_baseline.py`、`tests/test_evidence_experiments.py` | 首行解析、四条件、生成前钩子、探针流程、缓存和行为审核验证 |

### 数据、配置与原仓库文件

| 文件 / 目录 | 用途 |
| --- | --- |
| `configs/local.env` | 本机 GPU、离线模型路径和 CPU 线程配置 |
| `environment.yml`、`requirements.txt`、`requirements.lock.txt` | 环境定义、直接依赖和完整版本快照 |
| `dataset/instances.zip` | 发布的三分类实例；本地入口的数据来源 |
| `dataset/rcsr_processed.zip` | 发布的问题级证据包 |
| `prompts/baseline_prompts.json`、`prompts/prompt_robustness_P0_P5.json` | 发布提示词内容；`code/prompts.py` 按其重建 renderer |
| `code/0.py` | 问题级证据包展开为三类实例 |
| `code/2.py`、`code/3.py`、`code/6.py`、`code/11.py` | 原特征提取、逐层探针、路由器、SAD 分类器 |
| `code/5a.py`、`code/base.py`、`code/base_rag3.py`、`code/7_judge2.py` | 原生成/提示词/上下文与 CAD 基线、输出重评分 |
| `code/cas2.py`、`code/diagram.py` | 原隐藏状态替换实验与图表 |
| `code/0_run.slurm`、`code/6.slurm`、`code/faith_base.slurm`、`code/cas2.slurm` | 原集群任务；存在缺失引用与写死路径，不应默认当成本机可运行入口 |
| `code/readme.md`、`code/instances_test.jsonl` | 原运行简述与附带测试数据；本轮固定集合以 `runs/.../data/` 为准 |

原 SAD 缓存覆盖/目录约定、异常被吞导致零特征、部分 SLURM 缺失引用及 `5a.py` 不确定性统计问题尚未统一修复。
当前使用 `scripts/` 本地入口；本地 Qwen2.5 方法流程复现不等于论文全部数值复现。

### 文档与实验产物

| 路径 | 查什么 |
| --- | --- |
| `docs/environment.md`、`docs/small_reproduction.md`、`docs/prompt_baseline.md` | 环境、旧复现、旧基线细节 |
| `docs/git_push.md` | 本机专用 SSH 443 推送配置、首次添加公钥、诊断和恢复 HTTPS |
| `docs/evidence_behavior_plan.md`、`docs/evidence_behavior_run.md` | 当前固定协议、执行步骤、审核规则 |
| `docs/records/` | 实验与动作的持久记录；入口是其中的 `README.md` |
| `docs/activity_log.md`、`docs/experiments.csv` | 连续历史日志、已完成实验指标登记 |
| `runs/qwen2.5-3b-small/data/` | 固定抽样 JSONL、manifest、底题 ID 与数据哈希 |
| `runs/qwen2.5-3b-small/activations/`、`results/` | 旧特征；逐层验证、探针、路由器指标与逐样本预测 |
| `runs/qwen2.5-3b-prompt-baseline/predictions.json`、`first_line_analysis/` | 旧原始分类输出、事后解析及对照 |
| `runs/qwen2.5-3b-classification-grid/` | 四条件 protocol、audit、各条件 predictions；`reports/{val,test}.md/.json` 和逐类 CSV |
| `runs/qwen2.5-3b-free-answer-study/` | 当前自由回答；`{plain,chat}/{train,val}/states.json` 与 features、各自 probe、test/predictions.json |
| 自由回答目录下 `review/`、`annotations.csv`、`reports/` | 盲审页面、600 条语义首轮标注、behavior 报告和 joined_records；v1 与分析前报告历史快照保留 |
| `review/followup-2026-10-11/`、`docs/records/2026-10-11-free-answer-followup-audit*` | 历史v3、184未知队列、70重点判断、100冲突质量及元数据；勿覆盖当前正式v4 |
| `review/independent-semantic-2026-10-11/` | public为原匿名材料，coordinator勿给第二评审；reviewers/a,b,c保存300输入/232行为，另coordinator-supplement-2026-10-12保存2行为；comparison-2026-10-12-v1与adjudication-2026-10-12保存完整比较/裁定/v4/132未知；旧0评分、缺2条记录为历史快照 |
| `docs/records/2026-10-12-semantic-review-adjudication*` | 当前v4、300输入评分、234混合行为评分、148字段裁定、117手工决策、132未知与结构化核验的持久副本 |
| `review/uncertain_items_semantic_v2.csv`、`docs/records/2026-10-11-free-answer-semantic-review*` | v2历史199歧义及校验快照，勿覆盖当前v4 |

`runs/` 被 Git 忽略，是本地运行产物，目录存在不代表运行完成。
持久记录保存设置、轻量指标、必要校验值和产物路径；大权重、激活数组、整批生成留在原产物目录。

## 环境和执行约定

- 根目录：`/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG`。
- Python：`/large_disk/wf/miniconda3/envs/kba-rag/bin/python`；sh 入口会自动选择环境和本地配置。
- 3B：`/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct`，36 层、2048 维、上下文 32768。
- 默认 GPU 0（RTX 3090，24 GiB）；默认离线加载，BF16 模型、FP16 特征、SDPA。
- Git origin 已切换为 SSH，仓库本地 core.sshCommand 选择专用 443 配置；用户已添加公钥，2026-10-09 推送及远端哈希核验成功，正常使用 git push origin main，见 docs/git_push.md。
- 标准化只拟合 train；C=1/lbfgs/max_iter=2000；验证集选层并 sigmoid 校准。层号从 0 编号。
- 状态定义为 `hidden_states[l+1][0,-1,:]`，末层含 final norm；自由回答两种模板分别重训探针。
- 用户明确约定（2026-10-11）：预计运行超过10分钟的GPU程序，由助手先完成代码、检查、时间估算和断点记录，提供启动/续跑命令，再请用户运行；助手负责进度核验与分析。估算不能保证低于10分钟时按长期任务处理。已有任务运行时不要另起同GPU实验。
- 不修改运行中实验所依赖的代码、配置、protocol 或输出；文档整理与只读检查可以继续。
- 协议包含代码指纹；代码/指令/抽样改变后使用新的 run_dir，不以修改指纹文件来绕过校验。
- 提取失败应中止并记录实例，不能补零；空/截断/未知行为不能自动算拒答。

## 当前任务之后怎么推进

1. 先读 [2026-10-12裁定与启动准备](docs/records/2026-10-12-semantic-review-adjudication.md)，再按需读classification-grid-verified及生成核验记录；当前600条正式v4已分析核验，避免重跑旧GPU或从空模板覆盖。
2. 第二评分/补评汇总与148字段裁定已完成。132未知属于已裁定保留歧义，不是尚未处理的分歧队列；后续需额外证据或预先固定新协议，不能自动清零。背景暴露、2协调补评和非独立人工金标准限制继续披露。
3. `annotations.csv` 为正式v4；旧v3及报告在review/history/2026-10-12-before-adjudication-v4/，旧评分脚本重放用显式source-snapshot，不改原指纹。后续再更新仍先快照再analyze。
4. 新验证集三候选已由用户运行并核验完成，先读[完成记录](docs/records/2026-10-12-classification-prompt-validation-verified.md)。没有合格候选，不推进确认集或放宽门槛追认最高分。下一步仅在val审核可答性/明确矛盾并诊断直接答题/过度refuse，再设计预先固定新候选；新设置必须新run_dir/protocol，长期GPU仍交给用户。
   2026-10-13用户要求完成代码后交其执行；[证据诊断准备记录](docs/records/2026-10-13-validation-evidence-audit-preparation.md)与[执行说明](docs/validation_evidence_audit.md)已保存。2026-10-16用户完成v1 smoke9/9，但结构/引用0/9未达6/9门槛，正式`runs/qwen2.5-3b-validation-evidence-audit-v1/`仍prepared_not_started、0/285，见[失败核验](docs/records/2026-10-16-validation-evidence-audit-smoke-failed.md)。旧入口原样重跑只复用缓存再次失败；不放宽门槛或改冻结解析，新设计须新目录/协议并先CPU检查和smoke。同模型草稿仅辅助诊断；引用来源检查不证明语义正确，复核评分须显式传入并披露来源。
   v4已完成285且核验，技术通过不等于语义正确。用户随后要求直接完成固定样本/输入复核/模型归因，现[30条诊断复核](docs/records/2026-10-16-validation-semantic-pilot.md)已完成：seed42固定10底题，完整原文输入判断先封存为11充分/12不足/4冲突/3未知，27确定中v4类别一致7、不一致18、技术invalid2；7一致中4条仍有实体或引文问题。当前助手有历史及部分预测日志暴露，非独立金标准；6条与发布类别不同仅为本轮判断。后续先独立复查3未知/4moderate及明确判断，若改规则或扩展则新版本；不自动新GPU、改旧预测或导入语义标签。
   30条固定val首轮复核及CPU导出均完成，旧判断/空白包不回写。用户随后明确要求当前助手直接判断，已完成[全30条追加复核](docs/records/2026-10-16-validation-semantic-followup.md)：12充分/13不足/4冲突/1unknown，P004与P025采用明确题意解释后由unknown改为answer/refuse，50引文与来源/CSV/封存核验通过。用户本轮要求已完成，无需再要求其填写同一批表；仍为有模型/历史暴露的同助手判断，独立新评分0条，P008双署名不强制消歧。若以后有新评审再单独保留来源和独立性；不把本轮7/29类别一致率当独立准确率或新合格基线，不自动新GPU。
   用户已完成新分类生成与报告保存，见[2026-10-18恢复核对](docs/records/2026-10-18-context-restored.md)：正式两组各285、smoke各9，两目录analysis_complete，保存报告仍no_qualified_baseline；本轮只核对数量/保存字段/13指纹/报告，下一步执行scripts/verify_classification_semantic_baseline.py完整只读重放缓存、指标、筛选与bootstrap，无需重跑GPU。[20:33:27运行快照](docs/records/2026-10-16-classification-semantic-baseline-running.md)保留历史。约束格式不认证语义、旧对照同时改变指令/解码、30条参与设计只作开发诊断，保留1unknown，不自动修改发布标签或用确认集。
5. 分别分析不足和冲突，再决定确认集与干预；暂不直接开展 patching。

## 每次工作结束后的记录维护

- 在 `docs/records/` 追加有日期与主题的实验/动作记录，按 [模板](docs/records/TEMPLATE.md) 写清操作、证据、结论、未完成项和下一步。
- 更新 `docs/records/README.md` 的索引；背景、状态或文件位置变化时同步更新本文件。
- `docs/activity_log.md` 追加摘要；只有完成并核验指标后才更新 `docs/experiments.csv`，不要编造进行中结果。
- 不覆写历史结果快照。区分用户报告、助手实际检查、准备完成、运行中、生成完成、审核完成。
- 用户的新指令优先。未经当前任务授权，不自动提交、推送或发布；不在记录中保存凭据。
