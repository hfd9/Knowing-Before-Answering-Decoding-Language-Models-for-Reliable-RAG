# 项目交接入口：先读本文件

本文件供新会话中的助手快速恢复背景。更新时间：2026-10-09（Asia/Shanghai）。
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
| 四条件分类对照 | 代码准备完成；本次交接检查未发现默认正式运行目录，是否已用其他目录运行需核验 |
| 自由回答 | 用户 2026-10-09 明确报告正在运行 `sh scripts/run_free_answer_study.sh`；已观察到 plain/train 状态保存，尚不能宣布全流程完成 |
| 行为标注、确认集、因果干预 | 尚无已核验的最终结果 |

原路由器三分类错误可答判定率为 10%，纯文本首行基线为 31.5%；这不是自由回答中的实际缺证回答率。
路由器比基线净多判对 92 条：Answer +16、Refuse −10、Conflict +86；冲突贡献净增量的 93.5%。
真实不足误判可答：路由器 11、基线 6；真实冲突误判可答：路由器 9、基线 57。
因此不能仅凭整体提升认定不足类更好。旧首行解析是 post-hoc；新条件解析在推理前固定，invalid 保留分母。
完整数据跨集合的 original_id 和问题文本无重叠；既有特征未见 NaN/Inf/全零向量。
最近代码验证为 22 个测试通过，属于运行准备证据，不是新 GPU 实验结果。

## 文件导航

### 本地可用入口与公共实现

| 文件 | 用途 |
| --- | --- |
| `scripts/run_small_repro.sh`、`scripts/small_repro.py` | 数据抽样、隐藏状态提取、逐层探针、校准路由器；旧实验入口 |
| `scripts/run_prompt_baseline.sh`、`scripts/prompt_baseline.py` | 原纯文本 8-token 分类基线与严格解析；保留历史设置 |
| `scripts/analyze_prompt_baseline.py` | 对旧原始输出进行首行事后补充分析 |
| `scripts/run_classification_grid.sh`、`scripts/classification_grid.py` | plain/chat × 8/64-token 分类对照、审计、分类型指标和混淆矩阵 |
| `scripts/run_free_answer_study.sh`、`scripts/free_answer_study.py` | 同模板提取/重训探针、128-token 自由回答、生成前判断与行为汇总 |
| `scripts/free_answer_review.py` | 离线盲审 HTML、带批次哈希的 CSV、未知行为与完整分母统计 |
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
| 自由回答目录下 `review/`、`annotations.csv`、`reports/` | 盲审页面与模板、最终标注、behavior 报告和 joined_records |

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
- 用户偏好助手准备代码、验证和分析，用户启动长期 GPU 实验。已有任务运行时不要另起同 GPU 实验。
- 不修改运行中实验所依赖的代码、配置、protocol 或输出；文档整理与只读检查可以继续。
- 协议包含代码指纹；代码/指令/抽样改变后使用新的 run_dir，不以修改指纹文件来绕过校验。
- 提取失败应中止并记录实例，不能补零；空/截断/未知行为不能自动算拒答。

## 当前任务之后怎么推进

1. 用户报告运行结束后，只读核验 plain/chat 的 train、val、probe、test 记录是否齐全，是否有失败。
2. 查 `reports/behavior.json` 和 `review/blind_review.html`。生成完成仍需行为审核；未知项保留分母及上下界。
3. 协助完成带批次哈希的行为标注，再执行 `sh scripts/run_free_answer_study.sh --stage analyze`。
4. 核验四条件分类是否已在其他目录运行；若未完成，按运行说明补齐。不要打断当前自由回答。
5. 分别分析不足和冲突，再决定确认集与干预；暂不直接开展 patching。

## 每次工作结束后的记录维护

- 在 `docs/records/` 追加有日期与主题的实验/动作记录，按 [模板](docs/records/TEMPLATE.md) 写清操作、证据、结论、未完成项和下一步。
- 更新 `docs/records/README.md` 的索引；背景、状态或文件位置变化时同步更新本文件。
- `docs/activity_log.md` 追加摘要；只有完成并核验指标后才更新 `docs/experiments.csv`，不要编造进行中结果。
- 不覆写历史结果快照。区分用户报告、助手实际检查、准备完成、运行中、生成完成、审核完成。
- 用户的新指令优先。未经当前任务授权，不自动提交、推送或发布；不在记录中保存凭据。
