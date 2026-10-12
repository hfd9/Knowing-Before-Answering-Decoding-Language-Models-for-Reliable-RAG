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
- 2026-10-09 自由回答已完整核验：plain/chat 各 train 600、val 285、test 300，最后回答北京时间 11:39:33 保存；2,370 个特征和 600 条探针预测复算匹配。
- 自由回答同模板探针：plain L24，Accuracy 81.33%、Macro-F1 81.42%；chat L28，Accuracy 77.67%、Macro-F1 77.34%。2026-10-11 发现部分标注 CSV：40 条已有判断、560 条全 unknown，现有行为报告未载入该进度；尚无完整行为结论。
- plain/chat 触及 128-token 输出预算且未以 EOS 结束分别为 154/300、1/300；审核保留截断不确定性。详见第 18 节。
- 2026-10-11 默认四条件分类目录已有 protocol/preflight/audit，但未找到 predictions 或 reports；其他路径/命名结果仍待核验。
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

## 17. 2026-10-09：按 AGENTS.md 恢复项目背景

按用户要求读取 AGENTS.md、记录索引、背景交接、最近 SSH 核验记录、当前实验计划与运行说明，
并检查活动日志末尾和工作区状态；记录写入前工作区干净。
恢复研究主线、旧结果解释边界、诊断集/确认集划分及用户启动长期 GPU 实验的协作约定。
本次未检查实时运行进度，未重新核验旧指标，未运行实验或测试，未修改运行代码、协议和产物。
追加 [背景恢复记录](records/2026-10-09-context-restored.md) 并更新索引；无新实验指标，不更新 experiments.csv。

## 18. 2026-10-09：自由回答生成完成核验与初步分析

用户报告实验应该已结束，要求检查、分析和记录。只读核验两个模板各 600 train / 285 val / 300 test，
完整探针和审核产物均已保存；最后 chat 回答北京时间 11:39:33 完成，未发现 failure 文件。
2,370 个特征的哈希、形状、有限值与非零检查通过；协议、样本顺序、提示哈希、探针来源和选层一致。
600 条生成前探针预测与概率从保存特征复算一致，指标、配对 bootstrap 和 joined_records 匹配。
核验前后运行目录的文件列表和全部哈希相同；未加载大模型、未改运行产物、未重复运行 analyze。

plain L24：244/300，Accuracy 81.33%、Macro-F1 81.42%；chat L28：233/300，Accuracy 77.67%、Macro-F1 77.34%。
chat 比 plain 在充分类少判对 15 条，不足与冲突各多判对 2 条；准确率差 −3.67 个百分点，
按底题配对 bootstrap 95% 区间 [−8.00, +0.33]，充分召回差区间 [−25, −5] 个百分点。
三分类错误可答判定率分别为 13.50%、11.50%，不等于实际行为回答率。

plain/chat 平均生成 103.73/42.13 tokens，触及输出上限 154/1 条，空输出均 0。
没有正式 annotations.csv，600 条行为均待审核；真实不足且探针判不足分母 80/82，
实际作答数仍未知。未知分子显示 0 不代表没有作答，相关点估计仍为 null。
后续先完成盲审再 analyze，分类四条件结果仍待定位；不自动启动确认集或干预。

追加 [核验与分析记录](records/2026-10-09-free-answer-generation-verified.md) 及同名 JSON，
更新 AGENTS.md、索引与实验登记；登记范围仅为已核验的同模板探针诊断指标，行为结果不登记。

## 19. 2026-10-11：恢复项目背景并补充当前产物状态

按用户要求读取 AGENTS.md、记录索引、最新生成核验与背景交接、实验计划和运行说明。
只读列出轻量产物、读取行为报告，并用现有 load_annotations 在内存中检查部分标注文件。
默认分类目录已有 protocol/preflight/audit，尚无 predictions 或 reports，不能判为分类推理完成。
review/annotations_codex_semantic_v1.csv 共 600 行，40 条至少一项已有判断、30 条五字段完整，560 条全 unknown；
标注者为 Codex-LLM-semantic-v1，批次哈希与格式校验通过；本次未复核判断内容。
根目录 annotations.csv 仍不存在，行为报告仍显示待审核；plain/chat 预测清单各 300 条，本次未重做完整特征核验。
追加 [背景恢复记录](records/2026-10-11-context-restored.md)，同步入口和索引，保留已有未提交修改。
本次未启动 GPU、未运行 analyze、未修改运行产物或代码，无新实验指标，未提交或推送。

## 20. 2026-10-11：600 条审核任务中断位置定位

用户指出上次处理 600 条的任务可能中断。只读核查部分标注 CSV，判断连续保存到 item_0040，
第一条尚未审核为 item_0041；前 40 条中 10 条仍有 unknown，余下 560 条全 unknown。
在 /tmp 找到上次的 kba_review_batch.py 和 kba_save_review.py，分别读取盲审内容与保存语义判断。
现有产物与审核中途停止相符，但无日志确定中断原因；600 条回答生成已完成，无需重跑。
追加 [中断位置检查记录](records/2026-10-11-review-interruption-check.md) 并更新索引；未新增标注或行为指标。

## 21. 2026-10-11：600 条首轮语义审核与行为分析完成

按用户“继续完成”要求接续中断任务。保留 v1，使用 Codex-LLM-semantic-v2 逐条审核剩余 560 条，
重审前 40 条并统一判断口径；600/600 有标注者和备注，401 条五字段确定，199 条至少一项 unknown。
正式 annotations.csv 通过批次/ID/字段校验，实际执行 `sh scripts/run_free_answer_study.sh --stage analyze`。
分析前报告另存历史快照；独立复算 20 项率/上下界、核对 600 条对齐与原始输出哈希，12 个受保护文件未改变。
本次未重新核验大型激活数组，未启动 GPU，未修改冻结实验代码/协议/原始预测。

本次 LLM 首轮标注下，真实不足且探针判不足仍作答 plain 8/80=10.00%、chat 12/82=14.63%；
全部不足作答率分别 15/100 和 21–22/100（chat 1 条未知）。真实冲突选边上下界分别 67–81% 和 79–83%；
真实充分的明确不足拒答率 22% 和 18%。当前诊断结果不能证明模型自知、故意忽略或因果机制。
保留单一 LLM 审核、截断、正确性歧义和 conflict 改写可能兼容等限制；未做独立人工复核或确认集实验。

追加 [审核与分析记录](records/2026-10-11-free-answer-semantic-review.md)、JSON、持久标注与歧义 CSV，
更新入口/索引/实验产物登记。正式报告保留 pending_or_ambiguous，表示已审核但仍有未知字段。
未提交或推送；后续从未知项复核队列接续，不要从 v1/空模板覆盖现有结果。

## 22. 2026-10-11：重点复核、证据质量与四条件补跑

用户明确要求完成后续第一、第二步并做好记录。助手同一会话重点复核70条：20条核心缺证作答保持原判，370/377按证据缺失说明判为未实质回答，14条正确性unknown因无文档支持判no。16行20字段变化另存v3，先快照v2及旧报告，再导入正式CSV并实际analyze。416条五字段确定、184条至少一项unknown；600输出哈希、22项率/上下界、12个受保护源哈希核验通过。主比率plain8/80、chat12/82不变；全部不足15/100、21/100。

100条发布conflict逐题审计：68明确冲突、13兼容或答案不变、19不足或含糊；明确冲突选边plain42–52/68、chat53–54/68。固定三集合显式改写元数据匹配train6/600、val2/285、test4/300，均在conflict，原输入未清洗。独立空白审包已备；本次同助手复核不能算独立标注。持久CSV/JSON、变化清单与限制见[重点复核记录](records/2026-10-11-free-answer-followup-audit.md)。

未找到其他路径完成的分类产物。22项CPU测试、preflight/audit、四条件3底题GPU smoke通过；在GPU0空闲且用户明确授权后由助手启动正式分类补跑，日志`runs/qwen2.5-3b-classification-grid/launch-2026-10-11/full.log`。当前运行中，不登记未完成指标；冻结代码/protocol未修改，剩余380测试底题未用。完成核验后另存分类记录。没有提交或推送。

## 23. 2026-10-11 12:30：四条件分类完成并核验

上述补跑实际完成，包装命令退出0；正式末条于北京时间12:30:06保存。四条件各val285/test300共2340条，2040条新生成、300条旧plain8/test复用；另有3底题smoke，不混入正式分母。实际执行只读核验脚本，2340解析、300旧原始输出、10组指标、128个配对差值点估计及6个冻结依赖哈希检查通过。保留380个确认底题未预测、未调参，预测ID无重叠。

test：plain8/64均150/300，Accuracy 50%、Macro-F1 39.93%、分类错误可答率31.5%、严格格式0%；chat8/64均129/300，Accuracy 43%、Macro-F1 32.12%、错误可答率14%、严格格式99.67%。两预算在val和test的分类逐条完全一致。chat不足→可答0/100、冲突→可答28/100，充分召回28%、冲突召回1%；分类格式修正并未建立可靠三分类能力。router242/300整体较高，但不足召回84%低于chat100%，不能据整体指标宣称不足类更好；router和chat错误可答率点差4个百分点，95%配对区间含0。

追加[分类核验记录](records/2026-10-11-classification-grid-verified.md)及完整协议/指标/配对/分层/哈希JSON，登记四条件验证指标到experiments.csv，更新入口和索引。自由回答v3、重点复核与独立审包已保存；独立第二标注、184条未知最终裁定、确认集与因果干预仍未完成。无自动提交、推送或发布。

## 24. 2026-10-11 14:44：独立语义复核准备与版本保护

用户要求执行下一步第一项并记录。当前助手已接触旧标签，未将自身复核算独立审核；根据会话禁止未授权启用子助手的协作规则，已异步请求明确第二评审安排，记录时尚无回复，未启动子助手。
新增准备/校验脚本，重新编号300完整证据配置和600原始回答，公开输入不含发布类别、探针、模板条件和旧评分；协调映射单独保存。优先队列为184未知+20核心+370/377共204条，加30随机对照为234条，分24批。300输入也分30个审核批次。
完整五文档、原始输出哈希、公开字段白名单、优先覆盖和批次对齐核验通过；两种空白评分模板校验通过，独立评分0条。批次错误、缺少评审者、非法值、无答案但答案正确和重复编号均能拒绝；9个受保护源/报告哈希不变。重复准备逐字节一致，未导入评分、未执行analyze或GPU。
追加[独立复核准备记录](records/2026-10-11-independent-semantic-review-preparation.md)和JSON，更新入口与索引；正式v3及184未知不变，无新完成指标，不更新experiments.csv。第二评分和裁定待完成；未提交、推送或使用确认集。

## 25. 2026-10-12：背景恢复与第二评审实际进度核查

按AGENTS读取入口、索引、最新动作/结果记录及实验计划/运行说明，发现0评分交接已落后于本地产物。只读验证reviewers/a,b,c六份CSV和受保护源，300/300输入、232/234行为已保存且结构/批次/编号检查通过；缺b组B0594、B0596，未发现comparison-v1或readiness.json。评分说明披露项目级背景暴露，不能称完全背景盲审或独立人工金标准。正式v3仍600条、416五字段确定/184未知，哈希与历史记录一致。

新验证集三组提示词及代码已准备，v1/v2正式和smoke目录均prepared_not_started、已保存输出0且无预测文件。没有启动GPU、补写评分、执行汇总/analyze或修改运行产物；未核验实时GPU占用或重算旧实验指标。追加[恢复记录](records/2026-10-12-context-restored.md)，同步入口与索引，保留所有已有未提交文件；无新完成指标，不更新experiments.csv，未提交或推送。

## 26. 2026-10-12：第二评分、v4裁定与用户GPU启动准备

用户授权直接开始，长期GPU由用户运行。缺B0594/B0596另存协调者补评，不冒用b评审身份，不改原232条第二评分；300输入+232第二行为/2补评全部覆盖并校验汇总。第二输入充分100/不足120/冲突70/未知10；发布answer20条判不足、conflict24条判充分。背景暴露、同模型偏差及补评限制披露，不称独立人工金标准。

当前协调者读取117条分歧完整输出、评分理由，逐项手工裁定148字段；98行118字段改变，正式v4为468确定/132未知。先快照v3及旧报告，再导入并实际analyze；600对齐/原始输出哈希、22项率核验和显式旧快照重放通过，原输入/预测/protocol未改，未重复扫描大型激活。核心20输入均第二判不足，明确作答plain6/chat11，其余2/1有回撤歧义；370/377也保留unknown。

当前按发布不足且探针判不足后作答plain6–8/80=7.50–10.00%、chat11–12/82=13.41–14.63%；全部不足13–15/100、20–22/100。按第二语义不足且探针判不足8–10/86、13–14/92；均为未知保留分母的识别上下界，非置信区间或确认结果，旧v3点估计/区间仅历史使用。

新提示词候选/门槛不变，门禁明确232第二评分+2补评及v4裁定来源；协议代码变化后新v3目录，855正式/27smoke CPU检查通过，最长验证5563+8<32768、审核就绪及代码哈希核验通过。36CPU测试9.065秒和shell语法检查通过。未启动GPU，正式和smoke均prepared_not_started；顺序入口由用户运行，估计8–20分钟非保证。记录、v4/第二评分/手工裁定持久副本见[裁定与准备记录](records/2026-10-12-semantic-review-adjudication.md)，同步入口/索引/运行说明并登记已核验v4行为产物；旧v3报告索引指向其历史快照。未提交、推送或使用380确认底题。

## 27. 2026-10-12：用户新提示词GPU完成、核验与无合格候选

用户报告运行顺序入口，助手检查时smoke27/27完成，正式仍在第二组；保存文件持续增长，第三组末条北京时间09:55:45保存。正式855/855与smoke27/27均analysis_complete，无last_failure文件。未另起GPU或修改运行依赖/输出；沙箱驱动与进程不可见，不据此判宿主异常，完成来自完整产物。

只读重建两份协议，来源/代码/提示/门禁哈希、完整渲染/输入长度、882新输出缓存/顺序/独立解析、旧验证对照核验通过。独立复算smoke及正式8组指标和预设选择，六组配对bootstrap复算一致，核验后预测哈希不变。新增只读核验脚本，保存轻量完整结果与证据。

val285：旧chat8 Accuracy40%、Macro-F1 28.03%、错误可答率10.53%；definitions37.89%/25.81%/11.58%，decision_order36.14%/23.45%/4.21%，illustrations36.49%/23.20%/3.68%。新充分召回15.79/6.32/6.32%，冲突召回0/3.16/3.16%；格式98.95/97.19/100%。所有新候选未达三类各≥60%召回门槛，前两组还未达99%格式门槛，no_qualified_baseline，definitions仅诊断最高分。降低错误可答伴随过度refuse，不当成可靠分类或更好自由回答。

追加[验证完成记录](records/2026-10-12-classification-prompt-validation-verified.md)及JSON，同步入口/索引/运行说明并登记3条val-only结果，test指标留空。未使用诊断test或380确认底题，v4行为不变，未提交或推送。下一步仅val语义质量与分类行为诊断，不能追改门槛或直接patching。

## 28. 2026-10-12：综合全部结果的研究结论

按用户要求复读当前入口、分类/生成/v4/新val核验记录，汇总证据层级。生成前发布类别可线性解码，外显分类薄弱；整体探针优势主要来自冲突而非不足全面更好。当前v4显示探针判不足后仍有明确作答，冲突选边更普遍；语义分层后两现象仍在，但不是自知/故意忽略或因果证据。chat明显减少截断，没有显示全方位可靠性提升。发布answer/conflict的语义质量问题、构造元数据、同模型第二评分及协调裁定、132未知和缺独立确认仍限制解释。
追加[研究结论综合](records/2026-10-12-research-conclusions.md)并更新索引；无新实验、标注或指标重算，不改experiments.csv，不启动GPU或提交推送。

## 29. 2026-10-12：代码、测试与实验记录版本归档

用户明确要求提交代码。检查ade9d1c之后全部57个原待归档文件，范围为代码、测试、提示词和文档；新增文件约1.4MB，runs仍忽略，凭据格式检查无命中。实际重跑36项CPU测试9.144秒全部通过，新增Python/JSON与sh语法检查、已跟踪工作区diff检查通过。完整暂存检查提示两份历史快照的5处行尾空格，原文摘录和Markdown换行原样保留；代码及其余文件的提交差异检查通过，例外已记录。补充[提交范围与检查记录](records/2026-10-12-code-submission.md)，与索引/本条一起纳入本次本地main提交，本地commit已成功；同一未推送提交补齐检查说明，最终哈希以包含本条的git log为准。未执行远端推送、新GPU或改变实验结果。
