# chat L28语义迁移执行器：CPU准备与审核门禁

**原设计一次拟合预算已耗尽（2026-10-21）：** 用户按已说明范围要求开始，另存[作者参照探索性修订及一次CPU重训](records/2026-10-21-semantic-transfer-exploratory-retrain.md)。训练A48、同底题B41/48，eval来源旧57/96→新62/96，差区间跨0且冲突召回18/24→11/24；原独立标签和门禁不变，不称测量可靠性通过。共享预算声明及新run的同设计fit_attempt已存在，未改旧v5守卫能识别并拒绝另一fit。剩余预算0，后续实际独立审核也不能自动重置同设计预算。v1拟合完成后分析漏token字段报错，模型封存后只修v2分析，没有重拟合；CPU核验使用`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_exploratory_retrain_analysis_v2.py --stage verify`。新读出是离线读取生成前缓存，不是原生成回调；无新GPU/回答/行为评分/380访问。

**现有输出同题配对分析已完成：** [2026-10-21配对结果](records/2026-10-21-semantic-transfer-paired-analysis.md)复用240保存概率及封存行为，完成180对照、30底题/174作者参照合格/6未知保留、10000次整底题bootstrap、A/B与来源切片及PNG/PDF图。S→I不足概率+18.08pp，53/60升且19条仍答；S→C冲突概率+20.84pp，54升且34确定+5未知仍无消解选边；S→K冲突概率−5.87pp。I的probe类别两组仅2混合底题能题内比较且两表达都未答，不能将1/16与22/44当稳定题内预测优势。11新CPU/主分析与异进程图表重放/另写计算/885旧路径通过，无新GPU/评分/拟合；当前仍有历史暴露、正式语义批准0。CPU入口为`MPLCONFIGDIR=/tmp/kba-paired-mpl /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_paired_analysis.py --stage verify`。

**探索性行为复核已完成：** [2026-10-21离线复核](records/2026-10-21-semantic-transfer-exploratory-behavior.md)逐条审完240回答/1200槽/435全文，评分封存后再接旧probe；1652字段确定、17已审行28字段unknown。作者侧输入分组仅探索：不足作答23/60，probe判不足后1/16；冲突无消解选边37–43/60；确定充分且probe冲突58条中53–56条有据答对。13新CPU/实际分析与只读重放/独立计数通过，869旧路径含原run495不变。新评分/联合表另存，原模板保留；当前助手有历史暴露，独立标签仍0、正式门禁不变，无新GPU或拟合。CPU复算命令为`/large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_exploratory_behavior_review.py --stage verify`。下文行为未评分为采集核验时历史状态，当前本轮离线任务已完成。

**探索性采集已完成并核验：** [2026-10-21完成记录](records/2026-10-21-semantic-transfer-exploratory-verified.md)确认240回答/状态/已提交attempt，4技术smoke通过且计入240，空/触顶0、EOS240；完整只读verify和独立旧probe概率重放通过，最大误差0，原run495文件未变。行为包240项仍未评分，独立标签0，不代表正式语义成绩。无需重跑GPU，下一步离线行为复核；以下待用户启动/GPU0为准备时历史状态。

**用户已另行授权探索性采集（2026-10-21）：** [新入口/协议与CPU核验](records/2026-10-21-semantic-transfer-exploratory-preparation.md)允许独立语义审核前只采集v5全240条旧probe读出/状态/自由回答，不训练或计算正式语义指标。用户运行`sh scripts/run_semantic_transfer_exploratory_collection.sh`，同批4技术smoke计入240，预留30–120分钟；当前实际GPU0。该采集collection_allowed=true，不改变以下正式执行器的审核门禁。原96eval在采集后不再是预审后才揭示的前瞻评估，后续使用须披露时间和暴露。

**最新v5执行绑定已另存CPU准备：** [2026-10-21记录](records/2026-10-21-semantic-transfer-study-v5-preparation.md)使用新入口`run_semantic_transfer_study_v5.sh`，复用不变旧执行核心；240提示/token与v5一致，实际prepare/独立进程verify及28相关CPU通过，350旧路径不变。新准备目录为runs/qwen2.5-3b-semantic-transfer-study-v5-preparation-v1，批准标签全部null/审核0/GPUfalse，实际run在加载前按门禁退出。作者验收仅绑定风险来源，不用于批准标签。以下v4-r2入口及历史准备目录仍保留。

```sh
sh scripts/run_semantic_transfer_study_v5.sh --stage verify
```

本命令仅CPU重放新准备；当前没有就绪GPU任务。未来实际独立审核和上下文审计通过后，以新批准文件另存就绪运行，不修改当前无批准协议。L28/最多一次拟合/开发触发/评估锁继续约束，新入口也检查其他study目录中同设计已存在的拟合尝试。

2026-10-21已完成[v5修后作者验收与封存](records/2026-10-21-semantic-transfer-v5-acceptance.md)，保留扑克S/K四unknown及13组A/B细节风险，独立标签仍0/GPUfalse。作者侧三个交付步骤已完成，旧执行器和准备目录均未修改；当前无就绪GPU任务。

最新材料已经另存[v5关系对照修订](records/2026-10-20-semantic-transfer-materials-v5.md)：83输入/131目标片段修订、54条I重构，CPU材料/审包/空接收已核验。**下文旧执行器仍冻结绑定v4-r2**，不应改旧实现/准备目录来接受v5；新v5绑定已另存CPU准备见上文，实际独立审核后仍须另存对应就绪协议。当前独立标签0，无就绪GPU任务。

当前版本使用来源补充材料v4-r2，240条作者输入，30底题按12/6/12分区。独立审核仍0、批准标签0；当前准备目录的gpu_launch_ready=false。实现包含后续运行路径，但**尚未在本机3B上执行新GPU验证或正式训练**。材料构造达到100%不等于语义覆盖通过。

当前材料另有[全量作者侧审计](records/2026-10-20-semantic-transfer-author-input-review.md)：27题54条I需重构严格删除对照，18组A/B有附带命题等注意点，扑克C两条保留unknown。现有执行器继续冻结绑定v4-r2；材料修订须新版本/协议和对应实现，不能改本准备目录或冻结依赖来消化新材料。本轮作者判断不导入批准标签，独立审核仍0。

执行器为scripts/semantic_transfer_study.py，指标为scripts/semantic_transfer_metrics.py，入口为scripts/run_semantic_transfer_study.sh。继承[冻结设计](semantic_transfer_validation.md)及其JSON，不改写旧材料、旧探针或既有运行依赖。实际操作记录见[执行器准备记录](records/2026-10-20-semantic-transfer-study-preparation.md)。

## 当前可执行的CPU核验

```sh
sh scripts/run_semantic_transfer_study.sh --stage prepare
sh scripts/run_semantic_transfer_study.sh --stage verify
```

默认材料为runs/qwen2.5-3b-semantic-transfer-materials-v4-r2，默认新目录为runs/qwen2.5-3b-semantic-transfer-study-preparation-v1。prepare写入四个冻结文件；verify逐项重建核对且不写入。完整读取权重文件计算SHA256，但不将权重反序列化为模型，不加载旧probe的pickle。真实tokenizer检查全部240输入，与材料preflight逐项匹配。

| 文件 | 内容 |
| --- | --- |
| protocol.json | 材料/设计/来源/实现/旧探针指纹，模型元文件与完整权重SHA256、运行库版本、固定设置与审核门禁 |
| approved_labels.json | 全240项的批准语义标签；当前全部null |
| preflight.json | 各输入token数与提示哈希、上下文预算、审核状态 |
| review_gate.json | 构造覆盖与批准语义覆盖分开，分区分母96/48/96，上下文审计状态 |

没有审核时，run、analyze和verify-results入口先检查已保存门禁，在任何模型/probe加载前退出。当前实际run命令已验证以exit1报告Review gate closed；这不是GPU启动失败，也不是自动批准审查拒绝。

## 输入审核与显式批准文件

两份实际独立评分仍需先通过semantic_transfer_review_intake.py的批次、匿名映射、240分母、全文引用和判断理由校验。该工具只产生候选；执行器还要求显式批准文件和两份完整上下文审计记录，不因同意率高就自动批准。用户目前暂无外部渠道，维持待确认，不反复索要，也不再用获得项目历史的新上下文冒充独立评分。

未来的批准文件通过--approval指定，须包含下列字段；路径指向保留的原始记录，SHA256与实际文件一致：

- status为explicitly_approved_after_context_audit；materials_protocol_sha256绑定材料协议；approved_by、approval_rationale指定批准者及理由。
- no_probe_or_generated_outputs_seen=true明确评分发生在推理前；independence_limit_acknowledged=true确认软件不能证明外部审计声明的完整性或真实性。
- reviews.a/b各含path和sha256，指向原始评分JSON。两份评分必须由不同身份提交，history_exposed必须为false，每套240项完整且有可核对引用。
- context_audits.a/b各含reviewer、auditor、context_id、audit_rationale、received_packet_sha256、full_context_path、full_context_sha256。complete_received_context_checked须为true；history_exposed、author_labels_exposed、probe_or_outputs_exposed须为false。两上下文ID与记录哈希必须不同。
- labels包含全240个id及semantic_label，取answer/refuse/conflict/null。非空标签必须与两份原始评分的一致候选匹配。分歧或unknown保留null；本版本没有自动裁定路径。

软件核验文件、身份、引用、声明和哈希，实际接收上下文是否完整及未被历史污染仍由具名审计者负责。仅有自报独立、两个名字或两份不同文件不足以证明独立性，记录中必须披露这一限制。不要把本会话或合成测试的审计声明用于真实批准。

批准后全体及每个分区语义覆盖均须至少90%，才可新建就绪运行目录。当前无标签准备目录保持原样；追加批准不能修改同一协议。训练A是否包含三类另外检查，缺类允许报告旧probe迁移，但禁止拟合新probe。

## 运行顺序、缓存和训练预算

审核通过后的新版本先生成训练/开发144条，读取冻结chat L28在首个token之前的预测。生成器不接收probe反馈，native chat/旧自由回答指令、BF16/SDPA/greedy/128 tokens保持不变。

开发48条单独决定是否重训：宏F1<0.75，或经语义审核为充分的S/K误报conflict比例>0.20，或同语义A/B预测一致率<0.80。覆盖不足不能宣布通过。若触发，仅训练分区A最多48条已批准标签进入StandardScaler与固定LogisticRegression；B不拟合。L28、C=1、balanced、lbfgs、2000、seed42；不校准、不选层、不扫描、不二次拟合。

fit_attempt.json在拟合前保存。成功保存pickle/哈希及收敛状态；缺类、失败和未触发分别记录。失败不自动重试，中断留下attempt但没有完整metadata时停止恢复流程。不得通过另起run目录规避本轮最多一次拟合预算。

生成评估96条之前，evaluation_lock.json封存批准标签、协议、旧probe、开发决策及可选新probe哈希。没有锁的评估缓存直接拒绝；已有锁须先核验，随后才能读取评估缓存。评估不参与触发或训练。

逐项保存原始token IDs/解码文本/结束标志、提示哈希、旧probe概率、float16的36×2048预填充状态及哈希。续跑逐项重放保存前缀，不重复已保存样本；不接受NaN/Inf/零层/不匹配状态或改动的概率。generation_attempts在生成前记录，遇到尚未提交结果的旧attempt时停止，不擅自重答。恢复这种中断需核查原始产物和预算，而非删除attempt直接重跑。

run只完成生成与锁；analyze在全部240缓存核验通过后离线生成指标；verify-results只读重放完整报告。三阶段仍受门禁约束。此轮未运行这些就绪路径；CPU集成测试使用合成状态、模拟模型加载/生成及临时探针，不是本机3B GPU结果。

## 指标和行为接口

旧probe与一次语义重训probe分别报告train/dev/eval及A/B：确定标签下Accuracy/MacroF1/三类混淆与召回，完整计划分母的语义覆盖，S/K假冲突，同语义A/B一致与双侧正确，S→I/C双侧正确（S→K补充），所有三概率与token差。非空独立标签决定语义归属，作者条件不会自动成为金标准。A/B标签不同的对照保留在配对表，单列其不满足同语义条件的事实。

每分区整体指标及旧新差值按底题10000次bootstrap，旧新使用相同底题抽样；A/B各自点指标另列。缺分母的重采样次数单列，不将未知变成0；最多12评估底题的小样本限制保留。稳定地错也可能有高A/B一致率，故必须并列双侧正确率。

旧probe的实际决策来自生成前回调。可选新probe在锁定后离线读取同一批保存的生成前状态，不增加模型前向；报告明确readout_timing=offline_on_saved_prefill_state_no_generation_feedback，probe_decision_pre_first_token=false，不能描述为已在每次真实生成回调中执行新probe。这是实现层面的时间标记澄清，不改变旧probe测量或新probe的特征定义。

完整报告同时导出新的行为包，只有匿名ID、问题、五文档和回答，隐藏probe、输入语义标签、构造条件、底题ID与分区；协调映射单列。七字段空模板不自动评分。主行为汇总计算器独立于probe：全部语义不足作答、全部真实冲突选边/无消解选边、S/K有据正确与错误不足拒答。错误拒答要求“明确不足且未作实质回答”，仅承认不足后仍作答不算拒答。未知行为保留完整 eligible 分母和识别上下界；未知输入语义归属另外披露。

**本版本尚未提供真实行为评分导入及完整上下文审计的自动流程**；生成后的行为包须另存实际评分、核对引用/来源和分歧，再以版本化分析消费。当前指标中的behavior_pending全部unknown，不能当行为结果。评分计算器虽有CPU测试，仍不代表已有行为审核。

满预算为323252输入tokens及30720输出tokens。旧chat测试300条耗时650.30秒、均值42.13输出tokens，按历史有效速度折算满输出约26.3分钟，仅作容量规划；计入新提示/IO/竞争可预留30–120分钟，非本轮GPU实测。门禁通过后GPU仍由用户启动，并先记录实际协议与预算，不在当前审核缺失状态尝试运行。
