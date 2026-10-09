# 项目活动与实验记录

记录日期：2026-10-08，2026-10-09 追加提示词基线准备与运行分析。时间按 Asia/Shanghai（UTC+8）表示。
本记录根据本次对话、当前代码、实验产物和文件修改时间整理。
它是可查阅的工作记录，不是终端逐条命令的自动录屏；没有留存的精确时间不作推断。

## 当前交接摘要

- 专用 Conda 环境 kba-rag 已配置，3090 上的模型接口检查通过。
- 本地 Qwen2.5-3B-Instruct 已用于本轮实验；7B 权重完整性已检查，尚未进行 7B GPU 实验。
- 小规模隐藏状态路由器全流程已完成：600 train / 285 val / 300 test。
- P0、seed=42、最佳层 L24、sigmoid 校准；测试 Accuracy 80.67%、Macro-F1 80.54%、FAR 10.00%。
- 2026-10-09 已完成同一批测试数据的纯文本提示词基线；首行解析补充分析为 Accuracy 50%、Macro-F1 39.93%、FAR 31.50%，原完整输出格式遵从率为 0%。详见第 11 节。
- 四条件 chat/plain × 8/64-token 分类对照与同模板自由回答代码已准备，22 个测试通过；详见第 12 节。
- 用户 2026-10-09 报告正在运行自由回答入口；已观察到部分训练状态保存，尚待完整核验及行为审核。
- 四条件分类默认正式目录本次检查未发现，不能断言已经完成；后续核验是否使用了其他目录。
- 四条件分类/自由回答代码与交接文档已通过 SSH 推送；用户已添加专用公钥，远端 main 与本地提交核验一致。正常使用 git push origin main；最新哈希请用 git log 核验。
- 最新项目背景与文件导航见 [../AGENTS.md](../AGENTS.md)，实验/动作记录入口见 [records/README.md](records/README.md)。

环境说明：[environment.md](environment.md)。运行说明：[small_reproduction.md](small_reproduction.md)。
实验登记表：[experiments.csv](experiments.csv)。
机器可读结果与校验值：[2026-10-08-kba-record.json](records/2026-10-08-kba-record.json)。

## 1. 项目浏览与数据审查

用户最初希望先浏览完整项目，再指导小规模复现。
助手阅读了原仓库 11 个 Python 脚本、4 个 SLURM 脚本、README、提示词 JSON，
并查看论文的方法、模型与实现设置。

主方法是：冻结大模型，从最后一个提示词 token 的各层隐藏状态提取特征，
训练线性 answer/refuse/conflict 三分类探针，在验证集选层并校准。
训练对象为轻量路由器，不是大模型参数。

原脚本分工：

| 原文件 | 作用 |
| --- | --- |
| code/0.py | 将问题级证据包展开为三类实例 |
| code/2.py | 提取隐藏状态、MLP 输出和 SAD 注意力派生特征 |
| code/3.py | 各层线性探针及两层组合扫描 |
| code/6.py | 选层、训练和校准路由器 |
| code/5a.py、code/base.py | 生成与提示词类基线 |
| code/11.py | SAD 特征分类器 |
| code/cas2.py、code/diagram.py | 隐藏状态替换及可视化 |
| code/base_rag3.py | 有上下文、无上下文和 CAD 对照 |

实际发布数据：

| 集合 | 原始问题 | 展开实例 | 每类实例 |
| --- | ---: | ---: | ---: |
| train | 1,821 | 5,463 | 1,821 |
| val | 95 | 285 | 95 |
| test | 480 | 1,440 | 480 |
| 合计 | 2,396 | 7,188 | 2,396 |

已逐条检查：标签映射 answer=0、refuse=1、conflict=2；每个问题的三类配置完整；
每条实例含五篇文档，检索分数长度匹配；集合间无重复问题文本或 original_id。
使用 code/0.py 的转换逻辑可重建与现有 JSONL 一致的实例。
code/ 与 dataset/ 下的同名压缩包内容相同。

数据来源 instances.zip 的 SHA256：
7dc9d0d23d8518d23c189decd548e5207130fb4ec1df54fc421889ddf0b55d41。
rcsr_processed.zip 的 SHA256：
2f5a3e58236ae410d432cb9acd7c27067ba2a77b5d9900128ab6df7f57ea9383。

论文描述为 2,391 个问题、7,173 条实例及 70%/10%/20% 划分，与发布数据不同。
本轮使用发布压缩包，未修改原始集合划分。
参考：[论文数据构建与实现设置](https://arxiv.org/html/2608.27661v1)。

## 2. 发现的原仓库运行问题

| 问题 | 本轮处理状态 |
| --- | --- |
| 缺少 prompts.py，多个脚本无法导入 render_prompt | 已按发布 JSON 补齐 code/prompts.py |
| code/2.py 捕获所有异常，不报告原因，可能保存全零失败特征 | 原文件未改；新入口提取失败会中止并报告实例 ID/token 数 |
| SAD 默认 JSON 在 train/val/test 间覆盖，code/11.py 的读取目录和合并要求不匹配 | 待修复；本轮为隐藏状态实验 |
| SLURM 引用缺失的 rag_base4.py 和缺少生成步骤的 ablation 文件 | 待修复；本轮使用本地 sh 入口 |
| 集群环境和模型路径写死 | 新增本地配置与专用 Conda 入口 |
| code/6.py 默认 isotonic，与论文描述的 sigmoid 不同 | 新入口使用 sigmoid，并在验证集校准 |
| 生成长度默认值不统一 | prompts.py 提供 64 token 解码配置；本轮尚未跑生成基线 |
| code/5a.py 提前删除 top2，平均最大概率和 margin 被记为零 | 已识别，尚未修复 |

本轮重建的 renderer 为纯文本 P0--P5，保留完整文档与顺序，不增加 chat wrapper。
原作者 renderer 未发布，因此不能确认所有渲染细节与内部实验版本一致。

## 3. 本地环境建立与验证

用户提供：一张空闲 RTX 3090（24 GiB），本地可能已有 Qwen2.5 3B 和 7B。
助手查到 GPU 0、驱动 535.183.01；初始沙箱内 CUDA/NVIDIA 驱动不可见，
宿主机权限下可正常读取 GPU，因此不是机器没有 GPU。

本地权重路径：

- 3B：/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct。
- 7B：/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-7B-Instruct。

3B 两个权重分片、7B 四个权重分片及 tokenizer 文件均存在。
3B 为 36 层、2048 隐藏维；7B 为 28 层、3584 隐藏维。

安装过程中发生并处理：

1. 首次联网创建 Python 3.10 / pip 24.3.1 环境时，Conda 元数据请求反复超时，停止该尝试。
2. 使用缓存离线建立 kba-rag，最初为 Python 3.10.20 / pip 26.0.1。
3. 尝试下载 Python 3.10 的 PyTorch CUDA wheel，下载较慢，助手停止下载。
4. 在本机 pip HTTP 缓存发现 PyTorch 2.5.1+cu121 的 Python 3.11 wheel。
5. 将新环境改为 Python 3.11.15，将兼容缓存 wheel 整理到 /tmp/kba-rag-wheels 并离线安装。
6. 从 PyPI 安装 requirements.txt 的固定版本依赖，导出 57 包的 requirements.lock.txt。

实际成功安装步骤的核心命令：

```sh
/large_disk/wf/miniconda3/bin/conda create -n kba-rag python=3.10.20 pip=26.0.1 --offline -y
/large_disk/wf/miniconda3/bin/conda install -n kba-rag python=3.11.15 --offline -y
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -m pip install \
  torch==2.5.1+cu121 nvidia-nvjitlink-cu12==12.4.127 \
  --no-index --find-links /tmp/kba-rag-wheels --progress-bar off
/large_disk/wf/miniconda3/envs/kba-rag/bin/python -m pip install \
  -r requirements.txt --index-url https://pypi.org/simple --timeout 30 --retries 2 --progress-bar off
```

上述 /tmp 路径是安装时的临时缓存，不是日后重建环境的必要条件。
日后重建使用 environment.yml 或 requirements.lock.txt，详见环境说明。

最终环境：

| 组件 | 版本 |
| --- | --- |
| Python | 3.11.15 |
| pip | 26.0.1 |
| torch | 2.5.1+cu121 |
| transformers | 4.56.2 |
| accelerate | 1.10.1 |
| numpy | 1.26.4 |
| scipy | 1.13.1 |
| scikit-learn | 1.5.2 |
| matplotlib | 3.9.4 |
| pandas | 2.2.3 |

环境目录：/large_disk/wf/miniconda3/envs/kba-rag。
scikit-learn 1.5.2 保留原代码的 multi_class 和 cv="prefit" 接口。

检查通过：pip check、线性探针与 sigmoid 校准接口、CUDA BF16 矩阵运算、
完整加载 3B、36 层隐藏状态、36 层 MLP hook、eager attention 和短文本生成。
独立短输入检查的峰值已分配显存为 5.77 GiB；不是长文档实验的显存值。

## 4. 用户终端问题与修复

用户终端为 /bin/sh，出现过无法 cd 到 s、python: not found，
且在 scripts 目录下使用了重复的 scripts/check_environment.py 相对路径。
此前给出的 source 写法不适用于 /bin/sh，已改为 POSIX 的点命令。

已验证的激活命令：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
. /large_disk/wf/miniconda3/etc/profile.d/conda.sh
conda activate kba-rag
. ./configs/local.env
```

另新增 scripts/check_environment.sh，任何目录均可运行：

```sh
sh '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG/scripts/check_environment.sh' --load-model
```

sh 入口直接使用专用 Python，并读取本地模型、GPU、离线加载和 CPU 线程设置。
用户随后确认环境已激活。

## 5. 最小复现流程与验证

新增 scripts/small_repro.py 与 scripts/run_small_repro.sh：

- prepare：从原压缩包按 original_id 抽样，保留三类实例，检查跨集合问题重复。
- extract：冻结 3B，BF16、SDPA、完整文档，仅提取最后一个提示词 token 的隐藏状态。
- probe：StandardScaler + LogisticRegression，C=1、lbfgs、max_iter=2000，逐层训练。
- router：验证集准确率选层，验证集 sigmoid 校准，测试集最终评估。

H 的索引约定为 H[i,l] = hidden_states[l+1][0,-1,:]；FP16 存储。
直接调用 decoder 避免每个输入位置的全词表 logits 分配。
输入超过模型上下文长度会报错停止，不自动裁剪证据。
缓存会检查模型与提示词指纹、数据哈希、ID/标签顺序、形状和特征有效性。
抽样设置变更时要求使用新的 run_dir，避免混用实验。

tests/test_small_repro.py 的 3 个测试全部通过，覆盖：
完整晚出现证据与字面花括号保留、三类问题组抽样、拒绝标签错序与模型改变的缓存。

助手先执行 27 条真实实例的全流程验证，每个集合为 3 问题/9 实例：

```sh
sh scripts/run_small_repro.sh --run_dir runs/qwen2.5-3b-smoke \
  --train_questions 3 --val_questions 3 --test_questions 3
```

该验证成功，最高输入 30,769 tokens，峰值已分配显存 12.72 GiB。
微型验证指标仅用于记录，不用作论文效果判断。
实验文件时间约为 16:35:43 至 16:36:18。

## 6. 用户执行的正式小规模实验

用户要求“给我命令，我来跑”。助手提供运行命令，正式 1,185 条实验由用户启动。
本次后续长实验优先提供命令让用户执行；助手负责准备、检查和分析，除非用户另有指示。

运行命令：

```sh
cd '/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG'
sh scripts/run_small_repro.sh
```

曾提供可选的后台日志命令：

```sh
mkdir -p runs/qwen2.5-3b-small
nohup sh scripts/run_small_repro.sh > runs/qwen2.5-3b-small/run.log 2>&1 &
tail -f runs/qwen2.5-3b-small/run.log
```

观察时没有 run.log，因此运行检查依据宿主机进程、GPU 状态和已保存的元数据。
不将上述可选命令记为用户实际执行过的命令。

正式设置：

| 项目 | 值 |
| --- | --- |
| run_dir | runs/qwen2.5-3b-small |
| 模型 | Qwen2.5-3B-Instruct，本地离线 |
| 模板 / renderer | P0 / plain_json_templates_full_docs_v1 |
| 随机种子 | 42 |
| train | 200 问题 / 600 实例 |
| val | 95 问题 / 285 实例 |
| test | 100 问题 / 300 实例 |
| 三类数量 | 各集合分别为 200 / 95 / 100 条每类 |
| 最佳层 | L24，从零编号，即第 25 个解码层 |
| 校准 | sigmoid，在 val 上拟合 |

运行时检查到 GPU 利用率 86%--100%，无失败特征或显存中断。
后来 GPU 利用率降到 0%，进程转入 CPU 线性探针训练，属于正常阶段切换。

| 特征提取集合 | 用时 | 峰值已分配显存 | 最大输入 tokens | 元数据文件时间 |
| --- | ---: | ---: | ---: | --- |
| train | 144.08 秒 | 12.72 GiB | 30,769 | 16:44:31 |
| val | 74.73 秒 | 7.49 GiB | 5,124 | 16:45:45 |
| test | 94.36 秒 | 15.91 GiB | 29,459 | 16:47:20 |

特征提取合计 313.17 秒，约 5 分 13 秒。
逐层探针结果文件时间为 16:48:21，最终路由指标为 16:48:22。
依据进程与文件时间估计整轮约 6.5 分钟；没有单独记录精确端到端 wall time。

## 7. 最终结果与核对

重新计算并核对：300 条预测与测试 ID、真实标签对应；准确率、Macro-F1、FAR 和混淆矩阵一致。

| 指标 | 值 |
| --- | ---: |
| 测试正确 / 错误 | 242 / 58 |
| Accuracy | 80.6667% |
| Macro-F1 | 80.5416% |
| FAR | 10.0000% |
| 最佳层的未校准验证准确率 | 84.5614% |
| 同一问题三类全部判断正确 | 59 / 100 问题 |

混淆矩阵：行是真实类别，列是预测类别。

| 真实 / 预测 | answer | refuse | conflict |
| --- | ---: | ---: | ---: |
| answer | 71 | 11 | 18 |
| refuse | 11 | 84 | 5 |
| conflict | 9 | 4 | 87 |

| 类别 | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| answer | 78.02% | 71.00% | 74.35% |
| refuse | 84.85% | 84.00% | 84.42% |
| conflict | 79.09% | 87.00% | 82.86% |

FAR = (11 + 9) / 200 = 10%。
预测为 answer 的 91 条里有 20 条不应回答，比例约 21.98%；与 FAR 的分母不同。
这些指标评价证据状态分类，不评价实际生成答案是否正确。

按原始问题分组、保留三类配置进行 10,000 次 bootstrap，seed=42：

| 指标 | 95% 区间 |
| --- | --- |
| Accuracy | 75.67%--85.67% |
| Macro-F1 | 75.43%--85.44% |
| FAR | 6.00%--14.50% |

区间反映固定模型下的测试问题抽样不确定性，不包括换训练种子后的不确定性。
验证曲线在中后层 L23--L28 较高，L24 最优，末层分数回落。

分析产物的文件时间为 16:52:45：

- 原始指标：../runs/qwen2.5-3b-small/results/router_metrics.json。
- 全部预测：../runs/qwen2.5-3b-small/results/router_test_predictions.json。
- 58 条错误及问题：../runs/qwen2.5-3b-small/results/router_errors.json。
- 分析与置信区间：../runs/qwen2.5-3b-small/results/analysis_summary.json。
- 曲线与混淆矩阵：../runs/qwen2.5-3b-small/results/router_analysis.png。
- 保存的路由器：../runs/qwen2.5-3b-small/results/router_hidden_dev.pkl。

## 8. 本次新增与修改的文件

| 文件 | 用途 |
| --- | --- |
| environment.yml、requirements.txt、requirements.lock.txt | 环境重建与版本固定 |
| configs/local.env | GPU、本地模型、离线加载、CPU 线程配置 |
| scripts/check_environment.py / .sh | 依赖、GPU、模型接口检查和 POSIX 入口 |
| code/prompts.py | 发布模板的纯文本 renderer 与解码配置 |
| scripts/small_repro.py、scripts/run_small_repro.sh | 小规模主流程 |
| tests/test_small_repro.py | 证据、抽样与缓存完整性检查 |
| .gitignore | 忽略 Python 缓存和本地 runs 产物 |
| docs/environment.md、docs/small_reproduction.md | 使用说明 |
| README.md | 增加本地说明与活动记录入口 |
| docs/activity_log.md、docs/experiments.csv、docs/records/ | 统一工作记录、实验登记及轻量结果快照 |

runs/ 被 Git 忽略；完整激活数组仍保留在本地。
本次另把结果、数据清单、特征元数据和重要文件校验值备份到 docs/records/，
避免只依赖被忽略目录中的指标记录。结果快照不包含大体积模型权重和激活数组。

## 9. 待办与实验边界

1. 在相同 300 条测试实例上运行提示词三分类基线，比较 Accuracy、Macro-F1、FAR。
2. 检查 58 条错误，尤其真实 answer 被判为 conflict 的 18 条，核对证据与标签。
3. 保持验证/测试集固定，增加训练样本或更换训练抽样种子，检验稳定性。
4. 后续扩展到 7B、MLP/SAD 特征、因果替换；原 SLURM 与 SAD 问题仍需修复。
5. 若严格对齐论文数字，确认论文模型、数据版本和缺失 renderer 的设置。

注意：当前 --seed 同时控制各集合抽样；直接换 seed 会改变测试子集。
多种子对照需固定评估集合，不能把测试集变动误当作训练稳定性。
目前完成的是 Qwen2.5 的小规模方法流程复现，尚未完成提示词基线或严格论文数值复现。

## 10. 2026-10-09：提示词基线准备

用户同意先在相同 300 条测试实例上补充提示词三分类对照，并要求助手完成准备工作。
新增 scripts/prompt_baseline.py、scripts/run_prompt_baseline.sh、tests/test_prompt_baseline.py
和 docs/prompt_baseline.md；README 增加入口。

- 默认读取 runs/qwen2.5-3b-small 的原测试数据和本地 3B 模型，不重新抽样。
- 保留 P0 文档格式、完整五篇证据与顺序，使用明确三分类指令和 Label: 后缀。
  无 chat wrapper，贪心生成，最多 8 个新 token；指令预先固定，没有按测试结果调优。
- 无法解析输出独立统计并计入分类错误；FAR 同时配合解析覆盖率解读。
- 逐实例原子保存，可中断续跑；设置和缓存指纹检查、并发目录锁均已实现。
- 完成后自动输出 Accuracy、Macro-F1、FAR、3×4 混淆矩阵、配对错误案例及对照表，
  准确率差按原始问题进行配对 bootstrap。
- 全部 300 条实例的 CPU 预检查通过；最大输入 29,566 tokens，
  加上 8-token 输出预算仍小于 32,768-token 上下文窗口。
- 全部 10 个测试通过，包含原有 3 个测试和新增 7 个测试；
  使用微型随机 Qwen2 CPU 模型验证实际生成接口，并模拟中断验证保存和续跑。
- sh 语法检查与 git diff --check 通过。

本次仅完成准备与 CPU 验证，没有启动真实 3B GPU 基线，也没有产生基线准确率结果。
下一步由用户运行 sh scripts/run_prompt_baseline.sh，助手随后核对并分析结果。
可选的 9 条 GPU 冒烟命令及后台日志命令见 [prompt_baseline.md](prompt_baseline.md)。

## 11. 2026-10-09：用户完成提示词基线与解析诊断

用户报告运行完成。检查确认：9 条冒烟和 300 条正式测试推理均已保存，
正式记录与既有测试数据、模型及标签顺序匹配，无丢失实例。
逐实例分词与生成耗时之和为 178.01 秒，峰值已分配显存 9.06 GiB。
正式首条与末条保存时间约为 09:16:51 和 09:19:49；不包含此前模型加载时间。

原评估有 300 条 invalid，Accuracy/Macro-F1/FAR 均为 0。
诊断原始输出发现模型先输出类别，再追加解释或重复标签，
原解析器要求整个输出仅有一个类别词，混淆了格式遵从与分类能力。
277 条达到 8-token 预算且没有以 EOS 结束；当前短输出与纯文本设置均需在后续验证集对照中检查。

新增 scripts/analyze_prompt_baseline.py 和 tests/test_analyze_prompt_baseline.py。
解析规则固定为首个非空行的单一类别词；解释、真实标签均不用于决定类别，
同一行含多个类别仍算 invalid。这是 post-hoc 补充分析，不覆写原预测或原严格评估。
正式输出只有 test_391_answer 的首行 answer conflict 仍无法解析。

| 指标 | 隐藏状态路由器 | 提示词首行解析 |
| --- | ---: | ---: |
| 正确 / 总数 | 242 / 300 | 150 / 300 |
| Accuracy | 80.67% | 50.00% |
| Macro-F1 | 80.54% | 39.93% |
| FAR | 10.00% | 31.50% |
| 不应回答却预测 answer | 20 / 200 | 63 / 200 |
| 三类全部正确的问题 | 59 / 100 | 0 / 100 |

提示词首行解析混淆矩阵：行是真实类别，列为 answer/refuse/conflict/invalid。

| 真实 / 预测 | answer | refuse | conflict | invalid |
| --- | ---: | ---: | ---: | ---: |
| answer | 55 | 43 | 1 | 1 |
| refuse | 6 | 94 | 0 | 0 |
| conflict | 57 | 42 | 1 | 0 |

配对结果：两者都正确 122、仅路由器正确 120、仅提示词正确 28、两者都错误 30。
路由器准确率高 30.67 个百分点；按原始问题配对 bootstrap 的 95% 区间为 25.00--36.33 个百分点。
固定模型区间不包含训练随机性。路由器的 18 条 answer→conflict 错误中，提示词首行判断正确 13 条，
可优先审查这些分歧；不能据此直接设计并在同一测试集调优融合规则。

分析产物：runs/qwen2.5-3b-prompt-baseline/first_line_analysis/ 下的 comparison.md、
comparison.json、errors.json、parsed_predictions.json。
独立使用 sklearn 核对全部指标，原 predictions.json 哈希保持不变；全部 12 个测试通过。
完整轻量结果备份见 docs/records/2026-10-09-prompt-baseline-result.json。

当前只能得出本次纯文本提示词设置下路由器表现更好的结论。
更强提示词基线仍需在验证集检查指令模型 chat-template 和输出约束；
训练规模对照、7B、MLP/SAD 和因果实验仍未完成。

## 12. 2026-10-09：四条件分类与自由回答代码准备

用户要求完成计划、修改代码并提供运行命令，真实 3B GPU 实验仍由用户启动。
计划与运行步骤见 [evidence_behavior_plan.md](evidence_behavior_plan.md)、[evidence_behavior_run.md](evidence_behavior_run.md)。

- 确认本地模型为 Qwen2.5-3B-Instruct。分类新增 plain/chat × 8/64 tokens 四条件，
  问题、五篇完整证据、分类指令与 greedy 设置固定；chat 使用原生模板和生成起始标记。
  默认先 val 285 再 test 300，test/plain8 校验并复用旧输出，新增 2,040 次生成。
- 新入口固定严格格式与首行解析两套口径，invalid 保留在分母；生成汇总表、逐类 P/R/F1、
  3×4 混淆矩阵、两类错误可答判定计数及按底题配对 bootstrap。
  当前 FAR 改称三分类错误可答判定率；原路由器 val 属于校准内评估，已明确标注。
- 完整原数据跨 train/val/test 的 original_id 与题目文本重叠均为 0；原特征形状与标签顺序匹配，
  NaN/Inf、全零实例及全零层向量均为 0。最佳层 24 对应验证准确率首个最大值。
  审计保存现有特征、标签和元数据哈希，以及剩余 380 底题的确认集 ID，不生成其预测。
- 实际数据的两种输入格式长度预检查全部通过：分类最长 chat 输入 29,579 tokens，
  加 64-token 输出预算不超过 32,768；自由回答最长 chat 输入 30,865，加 128 同样不超限。
  检查产物暂存在 /tmp，正式 runs 目录由用户运行时建立，避免预先冻结中间代码指纹。
- 新入口从历史 300 条输出复算出提示词正确 150、路由器正确 242；旧原始文件与旧实验脚本未改动。
- 自由回答支持 plain/chat 两个格式，各提取 train 600/val 285 并重新训练、选层和校准。
  test 各生成 300 个短答，预算 128；首次 prefill 的 logits 前做出探针预测，不反馈给生成器。
  状态钩子与 HF hidden_states[1:] 定义对齐，只保留提示最后 token。
- 增加离线盲审 HTML 和带批次哈希的 CSV。生成前探针和实际行为分开记录，
  不足、冲突单独分析；未知行为保留完整分母并给上下界，审核后才生成最终点估计与区间。
- 全部 22 个测试通过：包含实际微型 Qwen2 CPU 生成和钩子时序、真实探针拟合及合成状态全流程、
  缓存损坏、模板分词、四条件报告、盲审批次与未知分母；Python 编译和 sh 语法检查通过。
  盲审页面的实际 JavaScript 通过 Node 语法检查，导出的含中文、引号、换行 CSV 已成功回读。

准备快照见 docs/records/2026-10-09-evidence-behavior-preparation.json。
本次没有启动新的真实 3B GPU 推理，没有产生 plain64/chat8/chat64 或自由回答的实验结果。
下一步运行 sh scripts/run_classification_grid.sh，检查分类型结果后再启动自由回答。

## 13. 2026-10-09：项目交接入口与记录体系

用户报告已经启动 sh scripts/run_free_answer_study.sh，并要求建立可供新会话快速读取的背景/文件导航入口，
以及保存实验和动作记录的文件夹。

新增根目录 AGENTS.md，集中研究目标、可靠结论、当前状态、完整文件导航、环境和协作约定。
沿用 docs/records/，新增 README.md 索引、TEMPLATE.md 模板和本次交接动作记录；原四份 JSON 保持原样。
README 增加入口，本日志顶部同步当前状态，后续助手在每次实质工作后追加记录并维护索引。

只读检查观察到自由回答 plain/train 已在保存状态；这是进行中产物，未填写完成结果。
本次未发现默认四条件分类正式目录，记录为待核验，不能推断其他 run_dir 是否存在结果。
具体采样时间和保存条数见 [本次交接记录](records/2026-10-09-project-context-and-records.md)。

本次仅整理文档，没有修改运行中的代码、配置、协议或输出，没有启动其他 GPU 任务。

## 14. 2026-10-09：用户授权提交与推送

上次提交之后的工作摘要：补齐四条件分类对照、同模板自由回答探针与行为盲审流程，并建立项目交接入口和实验记录索引。
用户明确要求归档并推送 origin/main；提交前代码指纹与已通过 22 项测试的准备版本一致，格式检查通过。
归档范围和操作依据见 [提交记录](records/2026-10-09-code-submission.md)。
普通 HTTPS 推送实际遇到缺少凭据的认证错误，未推送成功；已有一小时缓存未提供凭据，需用户在交互终端重新认证。
本地最终哈希以本次会话反馈和 git log 为准；认证后再核验远端 main。正在运行的实验输出继续留在 runs/。

## 15. 2026-10-09：长期 SSH 推送配置

用户要求解决推送问题并选择长期使用。HTTPS 代理路径可读远端，直连不稳定，认证缓存没有可用凭据。
生成项目专用 Ed25519 密钥，安装独立 SSH 443 配置与官方主机公钥，以仓库本地 core.sshCommand 选择该配置，
origin 切换为 SSH；不修改全局 SSH 配置，不修改正在运行的实验。
SSH 443 直连和代理均通过握手及官方主机校验，未上传公钥前认证被拒绝。
待用户添加账号公钥后继续验证并推送。详见 [操作记录](records/2026-10-09-ssh-push-setup.md) 和 [推送说明](git_push.md)。

## 16. 2026-10-09：SSH 授权与远端推送验证成功

用户确认公钥已添加。SSH 读取仓库成功，git push origin main 将远端从 35fd098 更新到 e8b80ce，
包含 bd3cfc4 的实验代码/交接文档和 e8b80ce 的长期 SSH 配置说明。
随后独立读取远端 main，确认完整哈希与本地 HEAD 一致。
更新当前交接状态和 Git 推送说明，保留历史阻塞快照，追加 [成功验证记录](records/2026-10-09-ssh-push-verified.md)。
此验证记录及文档状态更新同样归档并普通推送；最终本地与远端哈希在本次会话再次核验。
